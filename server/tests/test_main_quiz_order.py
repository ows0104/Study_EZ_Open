"""순서 맞추기(2026-11-18 ordering-screen): 판정 asset(root_order)이 맞을 때만 order_items가 붙고 선지는 빠진다.
정답 순서는 답을 편 뒤에만, 판·문항 글이 어긋나면 지금처럼 선지로 나온다."""
import json
import uuid
from unittest.mock import patch

from tests.root_support import setup, publish, start, view, action, document
from studyez_contracts.roots import mcq as contract
from studyez_contracts.roots import order as ordering

client, user, SessionLocal = setup()
from app.models import Asset
from app.root_learning import mcq, order

STEPS = {'Q1': ['세포 진입', '초기 전사', '추가 탈외피', 'DNA 복제'], 'Q2': ['흡착', '침입', '탈외피'], 'Q3': ['접촉', '비말', '공기']}
doc = document()
for q in doc['bank_snapshot']['questions']:
    units = STEPS[q['question_id']]
    q.update(format='list', answer='; '.join(units), answer_units=units)
# 문항을 바꿨으니 검토 문서의 지문도 다시 맞춘다(root_fixture.document와 같은 계산).
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash
bank = doc['bank_snapshot']
doc['review']['bank_sha256'] = document_hash(bank)
for m in doc['review']['mappings']:
    m['question_sha256'] = question_hash(next(q for q in bank['questions'] if q['question_id'] == m['question_id']), bank)
publish(client, user, doc)
questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
assert all(ordering.eligible(q) for q in questions.values())

storage = {}


def body_of(key):
    return storage[key.split('/')[4]]


patch('app.root_learning.mcq.ObjectStorage').start().return_value.get_bytes.side_effect = body_of
patch('app.root_learning.order.ObjectStorage').start().return_value.get_bytes.side_effect = body_of


def upload(kind, body):
    mcq._CACHE.clear()
    order._CACHE.clear()
    storage[kind] = json.dumps(body).encode()
    with SessionLocal() as db:
        for row in db.query(Asset).filter(Asset.kind == kind).all():
            db.delete(row)
        db.flush()
        db.add(Asset(id=str(uuid.uuid4()), subject='test', run_id='demo', kind=kind, filename=f"{doc['revision']}.json",
                     object_key=f'lectures/test/demo/{kind}/{kind}/{uuid.uuid4()}.json', size_bytes=len(storage[kind])))
        db.commit()


def pool(qid, q, n=5):
    return [{'id': contract.choice_id(qid, f'{qid} 오답 {k}'), 'text': f'{qid} 오답 {k}', 'source': 'made',
             'basis': 'b', 'why_tempting': 't', 'why_wrong': 'w'} for k in range(n)]


mcq_asset = {'schema': contract.SCHEMA_V2, 'revision': doc['revision'], 'skipped': {},
             'questions': {qid: {'question_hash': contract.authored_hash(q), 'wrong': pool(qid, q)} for qid, q in questions.items()}}
upload('root_mcq', mcq_asset)

sid = start(client)
first = view(client, sid)
qid = first['task']['question']['question_id']
assert first['task']['question']['mcq_choices'] and 'order_items' not in first['task']['question']   # 판정 없음: 지금처럼 선지


def order_asset(revision=doc['revision'], rows=None):
    rows = rows if rows is not None else {k: ordering.entry(q, list(range(len(q['answer_units']))), '차례가 내용이다')
                                          for k, q in questions.items() if k != 'Q3'}
    return {'schema': ordering.SCHEMA, 'revision': revision, 'questions': rows, 'not_ordered': {'Q3': '독립된 경로'}}


upload('root_order', order_asset(revision='other'))
assert 'order_items' not in view(client, sid)['task']['question']
stale = order_asset()
stale['questions'][qid]['question_hash'] = 'x' * 64
upload('root_order', stale)
assert 'order_items' not in view(client, sid)['task']['question']
broken = order_asset()
broken['questions'][qid]['order'] = [0, 0, 1, 2][:len(questions[qid]['answer_units'])]
upload('root_order', broken)
assert 'order_items' not in view(client, sid)['task']['question']

upload('root_order', order_asset())
shown = view(client, sid)
front = shown['task']['question']
items = front['order_items']
assert 'mcq_choices' not in front and 'mcq_groups' not in front
assert sorted(i['text'] for i in items) == sorted(questions[qid]['answer_units'])
assert [i['text'] for i in items] != questions[qid]['answer_units']            # 앞면은 정답 순서가 아니다
assert view(client, sid)['task']['question']['order_items'] == items           # 같은 날은 같은 순서
text = json.dumps(shown, ensure_ascii=False)
assert 'orderCorrectIds' not in text and '차례가 내용이다' not in text and '"order"' not in text

# 순서 화면에서 놓아 본 풀이는 객관식 모드처럼 주관식과 같은 풀이로 센다(choicesShown=false).
assert action(client, sid, 'open', 'reveal', attempted=True, choicesShown=False, response='순서: x').status_code == 200
after = view(client, sid)['task']
right = after['answer']['orderCorrectIds']
by_id = {i['id']: i['text'] for i in items}
assert [by_id[i] for i in right] == questions[qid]['answer_units']
assert 'mcqCorrectIds' not in after['answer'] and not after['helped']

# 주관식 V로 순서 화면을 편 풀이는 도움받은 풀이다(덧붙인 선지와 같다).
with SessionLocal() as db:
    from app.models import RootContent
    stored_doc = db.query(RootContent).filter_by(revision=doc['revision']).one()
    assert mcq.entry(db, stored_doc, questions[qid])[0] == 'order'
    assert mcq.entry(db, stored_doc, questions['Q3'])[0] == 2        # 순서형 아님: 선지 칸 그대로

print('main-quiz order: ok')
