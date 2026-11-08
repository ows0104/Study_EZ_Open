"""뿌리 학습 읽기 경로가 과제마다 DB를 왕복하거나 큰 JSON을 다시 싣지 않는다. 응답은 그대로다."""
import copy
from tests.root_support import setup, publish, start, view, document, ADMIN
client, user, SessionLocal = setup()
from sqlalchemy import event
from app import bank_personal
from app.database import engine
from app.models import QuizBank, BankPersonalEdit, PrequizJob
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent
from app.root_learning import content
from app.routes import root_learning

statements = []
event.listen(engine, 'before_cursor_execute',
    lambda conn, cursor, statement, parameters, context, executemany: statements.append(statement))


def selects(table):
    return [s for s in statements if s.lstrip().upper().startswith('SELECT') and f'FROM {table}' in s]


doc = document(); doc.update(bank_source='quizbank', bank_build_id='b1')
bank = copy.deepcopy(doc['bank_snapshot'])
with SessionLocal() as db:
    db.add(QuizBank(subject='test', run_id='demo', build_id='b1', status='ready', bank=copy.deepcopy(bank),
                    validation={'pass': True}, raw_response='raw ChatGPT text', open_to_students=True))
    db.commit()
publish(client, user, doc)
sid = start(client)
assert view(client, sid)['task'] is not None


def availability():
    with SessionLocal() as db:
        row = db.get(RootContent, ('test', 'demo', 'v1'))
        statements.clear()
        return content.availability(db, row, 'a')


def per_task_reference():
    """The previous per-task lookup, for equality."""
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        questions = {q['question_id']: q for q in row.bank['questions']}
        return {t['task_id'] for t in doc['tasks']
                if bank_personal.apply(db, row, 'a', questions[t['question_id']]).get('personalEdited')}


# 1. 개인 수정은 과제 수와 무관하게 한 번 읽는다. 판정은 과제별 조회와 같다.
assert len(doc['tasks']) == 3
available, problems = availability()
assert available == {'task1', 'task2', 'task3'} and problems == {}, (available, problems)
assert len(selects('bank_personal_edit')) == 1, selects('bank_personal_edit')
# 은행 행을 읽을 때 쓰지 않는 큰 칼럼은 싣지 않는다.
bank_select = selects('quiz_bank')
assert len(bank_select) == 1 and 'raw_response' not in bank_select[0] and 'quiz_bank.review' not in bank_select[0], bank_select

with SessionLocal() as db:
    q = bank['questions'][1]
    db.add(BankPersonalEdit(user_id='a', subject='test', run_id='demo', question_id=q['question_id'], original=q,
                            question=q['question'], answer='Private correction', comment='keep'))
    # 다른 사용자의 수정은 섞이지 않는다.
    db.add(BankPersonalEdit(user_id='b', subject='test', run_id='demo', question_id='Q3', original=bank['questions'][2],
                            question=bank['questions'][2]['question'], answer='Other user', comment=''))
    db.commit()
available, problems = availability()
assert len(selects('bank_personal_edit')) == 1
assert problems == {'task2': '개인 수정본과 연결 목표의 일치 미확인'}, problems
assert available == {'task1', 'task3'}
assert set(problems) == per_task_reference() == {'task2'}

# 2. 은행 지문은 행이 바뀔 때만 다시 계산한다.
calls = []
original_hash = content.document_hash
content.document_hash = lambda value: calls.append(1) or original_hash(value)
content._BANK_HASHES.clear()
availability(); availability()
assert len(calls) == 1, calls
with SessionLocal() as db:
    row = db.get(QuizBank, ('test', 'demo'))
    changed = copy.deepcopy(bank); changed['questions'][0]['question'] = 'Changed shared wording'
    row.bank = changed; db.commit()
available, problems = availability()
assert len(calls) == 2 and available == set(), (calls, available)
assert set(problems.values()) == {'원래 문항 판 변경 · 연결 재검토 필요'}, problems
with SessionLocal() as db:
    row = db.get(QuizBank, ('test', 'demo')); row.bank = copy.deepcopy(bank); db.commit()
available, problems = availability()
assert len(calls) == 3 and available == {'task1', 'task3'}, (calls, available)
# build_id가 바뀌면 지문을 쓰기 전에 막는다.
with SessionLocal() as db:
    row = db.get(QuizBank, ('test', 'demo')); row.build_id = 'b2'; db.commit()
available, problems = availability()
assert available == set() and set(problems.values()) == {'원래 문항 판 변경 · 연결 재검토 필요'}
with SessionLocal() as db:
    row = db.get(QuizBank, ('test', 'demo')); row.build_id = 'b1'; db.commit()
content.document_hash = original_hash
# 학습자 화면의 응답은 같다.
assert view(client, sid)['task'] is not None

# 3. 판 목록은 문서 전체를 싣지 않는다.
second = copy.deepcopy(doc); second.update(revision='v2', title='Second synthetic revision')
user('admin', True)
assert client.post(ADMIN, json=second).status_code == 200
statements.clear()
response = client.get(ADMIN)
assert response.status_code == 200, response.text
content_select = selects('root_content')
with SessionLocal() as db:
    expected = [{'revision': r.revision, 'title': r.document['title'], 'reviewed': r.reviewed, 'digest': r.digest}
                for r in sorted(db.query(RootContent).filter_by(subject='test', run_id='demo'),
                                key=lambda r: r.created_at, reverse=True)]
body = response.json()
assert body['versions'] == expected, body['versions']
assert [v['title'] for v in body['versions']] == ['Second synthetic revision', 'Synthetic root lecture']
assert body['enabled'] is True and body['activeRevision'] == 'v1'
assert len(content_select) == 1, content_select
# 제목만 JSON에서 뽑는다. 그 밖에 document 칼럼을 통째로 고르지 않는다.
assert 'root_content.document' not in content_select[0].replace('JSON_EXTRACT(root_content.document,', ''), content_select[0]
user('a')

# 4. 참고 PDF용 생성 판 조회는 result·web_response를 싣지 않고, 필요하면 읽힌다.
with SessionLocal() as db:
    job = PrequizJob(subject='test', run_id='demo', kind='bank', state='done', stage='', message='')
    db.add(job); db.flush()
    db.add(RootGeneration(id='g' * 32, job_id=job.id, subject='test', run_id='demo', user_id='admin', request_id='r',
        input_digest='i' * 64, baseline='b' * 64, packet={'revision': 'v1', 'sources': []}, result={'large': 'x' * 1000},
        result_digest='d' * 64, web_dispatch={'policy': 'none'}, web_response={'large': 'y' * 1000}))
    db.commit()
with SessionLocal() as db:
    active = db.get(RootContent, ('test', 'demo', 'v1'))
    statements.clear()
    light = root_learning.active_generation(db, active, light=True)
    query = selects('root_generation')
    assert len(query) == 1 and 'root_generation.result,' not in query[0] and 'web_response' not in query[0], query
    assert light.packet == {'revision': 'v1', 'sources': []} and light.web_dispatch == {'policy': 'none'}
    assert light.result == {'large': 'x' * 1000}
with SessionLocal() as db:
    active = db.get(RootContent, ('test', 'demo', 'v1'))
    statements.clear()
    full = root_learning.active_generation(db, active)
    assert 'web_response' in selects('root_generation')[0] and full.result == {'large': 'x' * 1000}

print('PASS: one personal-edit query per availability with identical blocking; bank hash reused until build/content changes; '
      'version list and source lookup skip large JSON with identical responses')
