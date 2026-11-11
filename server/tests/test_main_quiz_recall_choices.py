"""단답·나열 「선지 보기」: 판별 asset이 있을 때만 붙고, 정답은 답을 편 뒤에만, 편 풀이만 도움으로 남는다."""
import json
import uuid
from unittest.mock import patch

from tests.root_support import setup, publish, start, view, action, document
from studyez_contracts.roots import choices as contract

client, user, SessionLocal = setup()
from app.models import Asset
from app.root_learning import choices

doc = document()
publish(client, user, doc)
questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}


def wrong(qid):
    return [{'text': f'{qid} wrong {k}', 'why_wrong': 'belongs to another concept'} for k in range(3)]


def asset(revision=doc['revision'], only=None):
    rows = {qid: contract.entry(q, wrong(qid)) for qid, q in questions.items() if only is None or qid in only}
    return {'schema': contract.SCHEMA, 'revision': revision, 'questions': rows, 'skipped': {}}


storage = {'body': b''}
patcher = patch('app.root_learning.choices.ObjectStorage')
patcher.start().return_value.get_bytes.side_effect = lambda key: storage['body']

# 1. asset이 없으면 지금과 같다.
sid = start(client)
first = view(client, sid)
assert 'recall_choices' not in first['task']['question']
qid = first['task']['question']['question_id']


def upload(body, name=None):
    choices._CACHE.clear()
    storage['body'] = json.dumps(body).encode()
    with SessionLocal() as db:
        for row in db.query(Asset).filter(Asset.kind == 'root_choices').all():
            db.delete(row)
        db.flush()
        db.add(Asset(id=str(uuid.uuid4()), subject='test', run_id='demo', kind='root_choices', filename=name or f"{doc['revision']}.json",
                     object_key=f'lectures/test/demo/root_choices/{uuid.uuid4()}.json', size_bytes=len(storage['body'])))
        db.commit()


# 2. 다른 판의 선지·깨진 파일·다른 문항 글은 붙지 않는다.
upload(asset(revision='other'))
assert 'recall_choices' not in view(client, sid)['task']['question']
upload({'schema': 'root-choices/1', 'revision': doc['revision'], 'questions': 'broken'})
assert 'recall_choices' not in view(client, sid)['task']['question']
stale = asset()
stale['questions'][qid]['question_hash'] = 'x' * 64
upload(stale)
assert 'recall_choices' not in view(client, sid)['task']['question']

# 3. 맞는 선지는 앞면에 글만 붙고 정답 표시는 없다.
upload(asset())
shown = view(client, sid)
front = shown['task']['question']
assert front['options'] == [] and len(front['recall_choices']) == 4
assert set(front['recall_choices'][0]) == {'id', 'text'}
assert 'correct_ids' not in json.dumps(shown) and 'recallCorrectIds' not in json.dumps(shown) and 'why_wrong' not in json.dumps(shown)
assert not shown['task']['helped']
prepared = client.get(f'/api/root-learning/sessions/{sid}/prepare').json()
assert all('recall_choices' in f['task']['question'] for f in prepared['frames'] if f['task'])

# 4. 선지를 펴고 답을 보면 도움받은 풀이로 남고, 답면에 정답 ID가 온다.
assert action(client, sid, 'open', 'reveal', attempted=True, choicesShown=True).status_code == 200
after = view(client, sid)['task']
right = after['answer']['recallCorrectIds']
assert after['helped'] and len(right) == 1
assert next(c['text'] for c in front['recall_choices'] if c['id'] == right[0]) == questions[qid]['answer']
assert action(client, sid, 'open-rate', 'rate', grade='independent').status_code == 422
assert action(client, sid, 'open-rate4', 'rate', grade='independent', selfRating='Good').status_code == 200

# 5. 선지를 안 편 풀이는 지금과 같다(선지가 있어도 도움이 아니다).
user('closed'); sid2 = start(client, 'closed')
assert 'recall_choices' in view(client, sid2)['task']['question']
assert action(client, sid2, 'plain', 'reveal', attempted=True, choicesShown=False).status_code == 200
assert not view(client, sid2)['task']['helped']
assert action(client, sid2, 'plain-rate', 'rate', grade='independent').status_code == 200

# 6. 옛 화면(choicesShown 없음)은 단답에서 도움으로 세지 않는다.
user('legacy'); sid3 = start(client, 'legacy')
r = client.post(f'/api/root-learning/sessions/{sid3}/events', json={'requestId': 'old', 'version': 0, 'kind': 'reveal', 'attempted': True})
assert r.status_code == 200 and not view(client, sid3)['task']['helped']

# 7. 선지가 없는 문항에 choicesShown을 보내도 도움이 아니다.
upload(asset(only=[]))
user('none'); sid4 = start(client, 'none')
assert 'recall_choices' not in view(client, sid4)['task']['question']
assert action(client, sid4, 'claim', 'reveal', attempted=True, choicesShown=True).status_code == 200
assert not view(client, sid4)['task']['helped']
patcher.stop()
print('PASS: recall choices attach by revision and question text, hide answers on the front, record help only when opened')
