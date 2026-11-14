"""객관식 모드 선지: 판별 asset(root_mcq)이 있을 때만 mcq_choices가 붙고, 정답은 답을 편 뒤에만, 풀이 기록은 주관식과 같다."""
import json
import uuid
from unittest.mock import patch

from tests.root_support import setup, publish, start, view, action, document
from studyez_contracts.roots import mcq as contract

client, user, SessionLocal = setup()
from app.models import Asset
from app.root_learning import mcq

doc = document()
publish(client, user, doc)
questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}


def wrong(qid, q):
    need = contract.parts_needed(q)
    return [{'text': '' if need else f'{qid} wrong {k}', 'parts': [f'{qid} p{k}{j}' for j in range(need)],
             'kind': 'subtle' if k % 2 else 'block', 'basis': 'Fe2+→Fe3+', 'why_wrong': 'other concept'} for k in range(3)]


def asset(revision=doc['revision'], only=None):
    rows = {qid: contract.entry(q, wrong(qid, q)) for qid, q in questions.items()
            if contract.eligible(q) and (only is None or qid in only)}
    return {'schema': contract.SCHEMA, 'revision': revision, 'questions': rows, 'skipped': {}}


storage = {'body': b''}
patcher = patch('app.root_learning.mcq.ObjectStorage')
patcher.start().return_value.get_bytes.side_effect = lambda key: storage['body']

sid = start(client)
first = view(client, sid)
assert 'mcq_choices' not in first['task']['question']
qid = first['task']['question']['question_id']
assert contract.eligible(questions[qid]), questions[qid]['format']


def upload(body):
    mcq._CACHE.clear()
    storage['body'] = json.dumps(body).encode()
    with SessionLocal() as db:
        for row in db.query(Asset).filter(Asset.kind == 'root_mcq').all():
            db.delete(row)
        db.flush()
        db.add(Asset(id=str(uuid.uuid4()), subject='test', run_id='demo', kind='root_mcq', filename=f"{doc['revision']}.json",
                     object_key=f'lectures/test/demo/root_mcq/{uuid.uuid4()}.json', size_bytes=len(storage['body'])))
        db.commit()


upload(asset(revision='other'))
assert 'mcq_choices' not in view(client, sid)['task']['question']
stale = asset()
stale['questions'][qid]['question_hash'] = 'x' * 64
upload(stale)
assert 'mcq_choices' not in view(client, sid)['task']['question']

upload(asset())
shown = view(client, sid)
front = shown['task']['question']
assert front['options'] == [] and len(front['mcq_choices']) >= 4
assert set(front['mcq_choices'][0]) == {'id', 'text'}
text = json.dumps(shown, ensure_ascii=False)
assert 'correct_ids' not in text and 'mcqCorrectIds' not in text and 'why_wrong' not in text and 'basis' not in text

# 객관식 모드: 화면은 덧붙인 선지에 choicesShown=false를 보낸다 — 주관식과 같은 풀이로 센다(사용자 2026-11-14 「분리하지 말고」).
assert action(client, sid, 'open', 'reveal', attempted=True, choicesShown=False).status_code == 200
after = view(client, sid)['task']
right = after['answer']['mcqCorrectIds']
assert not after['helped'] and right
assert sorted(c['text'] for c in front['mcq_choices'] if c['id'] in right) == sorted(contract.correct_texts(questions[qid]))
assert action(client, sid, 'open-rate4', 'rate', grade='independent', selfRating='Good').status_code == 200

# ── v2(2026-11-14 choices-merge): 오답 풀에서 사용자·문항·날로 고른 4~5개, 답면에 「왜 틀렸나」, 주관식 V도 같은 선지 ──
NO_JOKBO = {k: '' for k in contract.JOKBO_KEYS}


def pool(qid, q, n=7):
    need = contract.parts_needed(q)
    same = contract.script(contract.correct_texts(q)[0])
    word = 'wrong' if same in ('en', 'mixed') else '오답'
    rows = []
    for k in range(n):
        parts = [f'{qid} {word} p{k}{j}' for j in range(need)]
        if q['format'] == 'sequence':
            order = list(q['correct_order'])
            parts = order[k % len(order):] + order[:k % len(order)]
        rows.append({'text': '' if need else f'{qid} {word} {k}', 'parts': parts, 'source': 'jokbo' if k == 0 else 'made',
                     'basis': 'b', 'why_tempting': 't', 'why_wrong': f'{qid} why {k}',
                     'jokbo': {**NO_JOKBO, 'year': '2022', 'number': '45'} if k == 0 else NO_JOKBO})
    return rows


def asset_v2():
    rows = {}
    for qid, q in questions.items():
        if contract.eligible(q):
            try:
                rows[qid] = contract.entry_v2(q, pool(qid, q))
            except ValueError:
                pass
    return {'schema': contract.SCHEMA_V2, 'revision': doc['revision'], 'questions': rows, 'skipped': {}}


patcher = patch('app.root_learning.mcq.ObjectStorage')
patcher.start().return_value.get_bytes.side_effect = lambda key: storage['body']
upload(asset_v2())
sid2 = start(client)
page = view(client, sid2)
task = page['task']
qid2 = task['question']['question_id']
row = asset_v2()['questions'].get(qid2)
assert row, questions[qid2]['format']
front2 = task['question']['mcq_choices']
assert front2 == view(client, sid2)['task']['question']['mcq_choices']   # 같은 날 다시 불러도 같다
correct_n = len(contract.correct_texts(questions[qid2]))
assert len(front2) == correct_n + min(len(row['wrong']), contract.show_count(questions[qid2]))
assert all(c['id'].startswith('k') for c in front2)
text = json.dumps(page, ensure_ascii=False)
assert 'why' not in text and 'mcqWrongNotes' not in text and '족보' not in text
# 주관식에서 V로 같은 선지를 편 풀이는 도움받은 풀이다.
assert action(client, sid2, 'open-v2', 'reveal', attempted=True, choicesShown=True).status_code == 200
after = view(client, sid2)['task']
assert after['helped']
answer = after['answer']
assert sorted(c['text'] for c in front2 if c['id'] in answer['mcqCorrectIds']) == sorted(contract.correct_texts(questions[qid2]))
notes = answer['mcqWrongNotes']
assert {c['id'] for c in front2} - set(answer['mcqCorrectIds']) <= set(notes)
assert any(n['source'] == '2022 족보 45번' for n in notes.values())
patcher.stop()
print('PASS: mcq choices attach by revision and question text, hide answers on the front, count attempts the same as recall; '
      'v2 picks 4-5 wrong options per user and day, explains them on the answer side, and V uses the same choices')
