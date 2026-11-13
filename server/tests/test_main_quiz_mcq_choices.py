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

assert action(client, sid, 'open', 'reveal', attempted=True, choicesShown=True).status_code == 200
after = view(client, sid)['task']
right = after['answer']['mcqCorrectIds']
# 객관식 모드 풀이는 주관식과 같게 센다(사용자 2026-11-14 「분리하지 말고」): 객관식 선지가 있어도 도움받은 풀이가 아니다.
assert not after['helped'] and right
assert sorted(c['text'] for c in front['mcq_choices'] if c['id'] in right) == sorted(contract.correct_texts(questions[qid]))
assert action(client, sid, 'open-rate4', 'rate', grade='independent', selfRating='Good').status_code == 200
patcher.stop()
print('PASS: mcq choices attach by revision and question text, hide answers on the front, count attempts the same as recall')
