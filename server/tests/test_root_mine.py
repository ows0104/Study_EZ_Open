"""Main-Quiz 내 문제(추가·복사 후 수정)와 뒷면 메모(docs/changes/2026-11-15-root-personal-questions).

내 계정·이 판에만. 기준 문항 옆에서 복습 일정은 받고 학습률·카드 수·목표 요약에는 세지 않는다."""
import copy
import json
from pathlib import Path
from sqlalchemy import select
from tests.root_support import setup, publish, start, view, action, document, BASE
client, user, SessionLocal = setup()
from app.models import Profile
from app.models.root_learning import RootEvent, RootSession
from app.root_learning import mine
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash

with SessionLocal() as db:
    db.add(Profile(id='a', email='a@example.com', is_admin=False))
    db.add(Profile(id='b', email='b@example.com', is_admin=False)); db.commit()
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document(revision='v4a'):
    """The /2 import fixture as root-generation/4 with three tasks on D1 (as test_root_learning_v4)."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=revision)
    bank = doc['bank_snapshot']
    for i in (3, 4):
        q = copy.deepcopy(bank['questions'][0])
        q.update(question_id=f'Q{i}', question=f'Synthetic part {i} of goal 1?', answer=f'Secret part {i}', answer_units=[f'Secret part {i}'])
        bank['questions'].append(q)
        m = copy.deepcopy(doc['review']['mappings'][0]); m['question_id'] = f'Q{i}'
        doc['review']['mappings'].append(m)
    doc['tasks'] = [{'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
                    {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
                    {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'},
                    {'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'}]
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return validate_document(doc)


def create(request, anchor, copied=False, question='My question?', answer='My answer', explanation=''):
    return client.post(BASE + '/mine', json={'requestId': request, 'anchorQuestionId': anchor, 'copy': copied,
                                             'question': question, 'answer': answer, 'explanation': explanation})


def edit(request, mine_id, **body):
    return client.put(BASE + '/mine/' + mine_id, json={'requestId': request, **body})


def memo(request, qid, text):
    return client.put(BASE + '/questions/' + qid + '/memo', json={'requestId': request, 'text': text})


def session_tasks(sid):
    with SessionLocal() as db:
        return [t['task_id'] for t in db.get(RootSession, sid).tasks]


publish(client, user, v4_document())
before = client.get(BASE).json()
sid = start(client)
first = view(client, sid)
assert first['mineEnabled'] is True and first['task']['question']['question_id'] == 'Q1', first['task']
assert 'personalAdded' not in first['task']['question']

# ── 복사 초안: 내게 보이는 글 그대로 ─────────────────────────────────────────
draft = client.get(BASE + '/questions/Q1/mine-draft').json()
assert draft == {'question': 'Synthetic question 1?', 'answer': 'Secret answer 1', 'explanation': 'Synthetic explanation 1',
                 'mine': False, 'enabled': True}, draft
assert client.get(BASE + '/questions/NOPE/mine-draft').status_code == 404
assert mine.draft_text({'format': 'cloze', 'question': 'A {B} C', 'answer': 'B',
                        'options': [{'id': 'o1', 'text': 'x'}, {'id': 'o2', 'text': 'y'}]})['question'] == 'A ____ C\n1) x\n2) y'

# ── 만들기: 멱등·거절 ────────────────────────────────────────────────────────
r = create('m1', 'Q1', copied=True, question='  My copy?  ', answer='My answer', explanation='why')
assert r.status_code == 201, r.text
mid = r.json()['mineId']
assert mid.startswith('mine-') and r.json()['question']['personalAdded'] is True
assert r.json()['question']['question'] == 'My copy?' and 'My answer' not in json.dumps(r.json()['question'])
assert create('m1', 'Q1', copied=True, question='  My copy?  ', answer='My answer', explanation='why').json() == r.json()
assert create('m1', 'Q1', question='Other').status_code == 409          # same request ID, another body
assert create('blank', 'Q1', question='   ').status_code == 422
assert create('nope', 'NOPE').status_code == 404
with SessionLocal() as db:
    stored = db.get(RootEvent, ('a', 'm1'))
    assert stored.kind == 'mine' and stored.session_id == '' and stored.revision == 'v4a'
    assert stored.payload['anchor_task_id'] == 'task-q1' and stored.payload['source_question_id'] == 'Q1'
    assert stored.payload['tier'] == 'Core' and stored.payload['action'] == 'save'
# A question made from my own question sits at that one's anchor; a fresh one has no source.
second = create('m2', mid).json()['mineId']
with SessionLocal() as db:
    assert db.get(RootEvent, ('a', 'm2')).payload['anchor_task_id'] == 'task-q1'
    assert db.get(RootEvent, ('a', 'm2')).payload['source_question_id'] is None
assert client.get(BASE + '/questions/' + mid + '/mine-draft').json() == {
    'question': 'My copy?', 'answer': 'My answer', 'explanation': 'why', 'mine': True, 'enabled': True}

# ── 계획에는 나오고, 학습률·카드 수·요약·칩 개수에는 안 센다 ────────────────
after = client.get(BASE).json()
planned = [t['task_id'] for t in after['plan']['tasks']]
assert mid in planned and second in planned, planned
assert after['summary'] == before['summary'] and after['questionProgress'] == before['questionProgress']
assert after['focus']['counts'] == before['focus']['counts']
# Today's flow re-picked its unsolved tail (refocus): both of my questions are in it now.
assert {mid, second} <= set(session_tasks(sid)), session_tasks(sid)
# Another learner sees neither, and cannot touch mine.
user('b')
assert mid not in [t['task_id'] for t in client.get(BASE).json()['plan']['tasks']]
assert edit('b1', mid, question='x', answer='y').status_code == 404
assert client.get(BASE + '/questions/' + mid + '/mine-draft').status_code == 404
user('a')

# ── 메모: 나만, 답면에 ───────────────────────────────────────────────────────
assert memo('n1', 'Q1', '  내 말로 정리  ').json() == {'memo': '내 말로 정리'}
assert memo('n1', 'Q1', '  내 말로 정리  ').json() == {'memo': '내 말로 정리'}
assert memo('n1', 'Q1', 'other').status_code == 409
assert memo('n2', 'NOPE', 'x').status_code == 404
assert view(client, sid)['task']['answer'] is None                     # the front never carries it
frames = client.get('/api/root-learning/sessions/' + sid + '/prepare').json()['frames']
assert frames[0]['task']['answer']['memo'] == '내 말로 정리'

# ── 풀기: 내 문제도 평가를 받고 기록은 task_id = mine_id ──────────────────────
seen = []
for step in range(12):
    current = view(client, sid)
    if current['finished']:
        break
    task = current['task']
    assert task is not None, current
    seen.append(task['id'])
    assert action(client, sid, f'r{step}', 'reveal', attempted=True).status_code == 200
    shown = view(client, sid)['task']
    if task['id'] == 'task-q1':
        assert shown['answer']['memo'] == '내 말로 정리'
    if task['id'] == mid:
        assert shown['question']['personalAdded'] is True and shown['answer']['answer'] == 'My answer'
        assert shown['answer']['memo'] == '' and shown['answer']['explanation'] == 'why' and not shown['answer']['personalAnswer']
        assert memo('n3', mid, '내 문제에도 메모').status_code == 200
        assert client.get('/api/root-learning/sessions/' + sid + '/prepare?start=' + str(current['position'])).json()[
            'frames'][0]['task']['answer']['memo'] == '내 문제에도 메모'
    assert action(client, sid, f'g{step}', 'rate', selfRating='Good').status_code == 200
assert mid in seen and second in seen, seen
with SessionLocal() as db:
    rated = [e.payload for e in db.scalars(select(RootEvent).where(RootEvent.user_id == 'a', RootEvent.kind == 'rate'))]
assert any(p['task_id'] == mid and p['question_sha256'] for p in rated)
done = client.get(BASE).json()
user('b'); other = client.get(BASE).json(); user('a')
# Rating my questions changed none of the counted values beyond what rating the lecture's own did.
mine_free = [e for e in rated if not mine.is_mine(e['task_id'])]
assert len(mine_free) == len(rated) - 2
assert done['questionProgress']['unseen'] == 0 and sum(done['questionProgress'][k] for k in
       ('unseen', 'recognized', 'retrieving', 'retained')) == sum(before['questionProgress'][k] for k in
       ('unseen', 'recognized', 'retrieving', 'retained'))
assert other['summary'] == before['summary']

# ── 고치기·지우기 ────────────────────────────────────────────────────────────
r = edit('e1', mid, question='Edited?', answer='A2', explanation='')
assert r.status_code == 200 and r.json()['question']['question'] == 'Edited?'
assert edit('e1', mid, question='Edited?', answer='A2', explanation='').json() == r.json()
assert edit('e2', mid, question='Edited?', answer=' ').status_code == 422
assert edit('d1', mid, action='delete').json() == {'question': None}
assert edit('d2', mid, action='delete').status_code == 404
assert client.get(BASE + '/questions/' + mid + '/mine-draft').status_code == 404
assert mid not in [t['task_id'] for t in client.get(BASE).json()['plan']['tasks']]
with SessionLocal() as db:   # every save and the delete stay as events
    assert len([e for e in db.scalars(select(RootEvent).where(RootEvent.kind == 'mine'))]) == 4
# The other one is still there; the 「내 중요도」 and 개인 수정 APIs never take a question of mine.
assert client.get(BASE + '/questions/' + second + '/mine-draft').status_code == 200
assert client.put(BASE + '/questions/' + second + '/tier', json={'requestId': 't1', 'tier': 'Core'}).status_code == 404
assert client.get(BASE + '/questions/' + second + '/personal').status_code == 404

# ── 상한 ─────────────────────────────────────────────────────────────────────
limit, mine.LIMIT = mine.LIMIT, 1
assert create('full', 'Q2').status_code == 409
mine.LIMIT = limit

# ── 덧붙인 사본은 캐시된 판 사본을 고치지 않는다 ──────────────────────────────
from app.root_learning import light
row = light.revision_row(SessionLocal(), 'test', 'demo', 'v4a')
assert not any(mine.is_mine(t['task_id']) for t in row.document['tasks'])
# 이전 판 기록 승계 표(replace-carry-records)는 덧붙인 사본에도 그대로 간다.
row.document.carried_questions = {('v3', 'Q9'): 'Q1'}
from app.root_learning.content import events_for
live, _ = mine.current(events_for(SessionLocal(), 'test', 'demo', 'a'), 'v4a')
assert live
assert mine.with_mine(row, live).document.carried_questions == {('v3', 'Q9'): 'Q1'}
del row.document.carried_questions

# ── 이전 정책 판: 내 문제는 409, 메모는 된다. 새 판으로 옮기지 않는다 ─────────
old = document()
publish(client, user, old)
assert old.get('generation_policy') != 'root-generation/4'
osid = start(client, 'old-start')
assert view(client, osid)['mineEnabled'] is False
assert create('old1', 'Q1').status_code == 409
assert client.get(BASE + '/questions/Q1/mine-draft').json()['enabled'] is False
assert memo('old-n', 'Q1', '옛 판 메모').json() == {'memo': '옛 판 메모'}
assert not any(mine.is_mine(t['task_id']) for t in client.get(BASE).json()['plan']['tasks'])
print('root mine ok')
