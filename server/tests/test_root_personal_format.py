"""Main-Quiz 「문제 수정·제보」에서 형식 바꾸기(2026-11-17, docs/changes/2026-11-17-personal-edit-format).

사용자 「주관식 -> cloze. 유형을 바꾸는 선택지가 없었어」, 「유형은 전부 다 바꿀 수 있도록. 다만 적당한 형식 제한이
걸리긴 하겠지」. 여섯 형식 사이를 바꾸고, 형식마다 판 문항의 최소 조건을 지킨다. 내 계정에만 보인다.
"""
import copy
from tests.root_support import setup, publish, start, view, BASE

client, user, SessionLocal = setup()
publish(client, user)
from app.models import BankFeedback, BankPersonalEdit
from app.models.root_learning import RootContent
from sqlalchemy import select

PERSONAL = BASE + '/questions/Q1/personal'

user('a')
sid = start(client)
snap = client.get(PERSONAL).json()
assert snap['formats'] == ['basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select']
assert snap['original']['format'] == 'basic' and snap['draft'] == snap['original']
base = {'revision': snap['revision'], 'question': 'Synthetic question 1?', 'answer': 'Secret answer 1'}


def put(**body):
    return client.put(PERSONAL, json={**base, **body})


def reject(structure, message, **body):
    r = put(structure=structure, **body)
    assert r.status_code == 422 and message in r.text, r.text


# 형식마다 최소 조건.
reject({'format': 'cloze'}, '중괄호', question='No blank here')
reject({'format': 'cloze'}, '한 겹', question='{{c1}} and {x}')
reject({'format': 'ox'}, 'O 또는 X', answer='maybe')
reject({'format': 'list'}, '2개 이상', answer='only one')
two = [{'id': '1', 'text': 'A'}, {'id': '2', 'text': 'B'}]
reject({'format': 'mcq', 'options': two[:1], 'correct_option_ids': ['1']}, '보기를 2개')
reject({'format': 'mcq', 'options': two, 'correct_option_ids': []}, '정답 보기')
reject({'format': 'mcq', 'options': two, 'correct_option_ids': ['1', '2']}, '보기 하나')
reject({'format': 'multi_select', 'options': two, 'correct_option_ids': ['1', '2']}, '모든 보기')
with SessionLocal() as db:
    assert db.scalars(select(BankPersonalEdit)).all() == []

# 주관식 → 빈칸: 발문의 {…}가 빈칸, 답을 열면 채워진다. 해설은 내가 적은 것.
saved = put(question='The answer is {Secret} and {answer 1}.', answer='',
            structure={'format': 'cloze', 'explanation': 'my note'})
assert saved.status_code == 200, saved.text
q, a = saved.json()['question'], saved.json()['answer']
assert q['format'] == 'cloze' and q['question'] == 'The answer is {{c1}} and {{c1}}.' and q['personalEdited']
assert a['answerUnits'] == ['Secret', 'answer 1'] and not a['personalAnswer'] and a['explanation'] == 'my note'
assert view(client, sid)['task']['question']['format'] == 'cloze'
again = client.get(PERSONAL).json()
assert again['edited'] and again['draft']['format'] == 'cloze' and again['original']['format'] == 'basic'
assert again['draft']['question'] == 'The answer is {Secret} and {answer 1}.'
with SessionLocal() as db:
    fb = db.scalars(select(BankFeedback)).all()[-1]
    assert '형식: 주관식 → 빈칸' in fb.comment and 'format' in fb.correction['changedFields']
    assert fb.correction['proposed']['format'] == 'cloze'

# 주관식 → OX(소문자도 받는다), 객관식, 복수 선택, 나열.
r = put(answer='x', structure={'format': 'ox', 'explanation': 'because'})
assert r.status_code == 200 and r.json()['question']['format'] == 'ox' and r.json()['answer']['answer'] == 'X'
r = put(structure={'format': 'mcq', 'options': two, 'correct_option_ids': ['2']})
q, a = r.json()['question'], r.json()['answer']
assert q['format'] == 'mcq' and q['mcq_mode'] == 'comparison' and [o['text'] for o in q['options']] == ['A', 'B']
assert a['correctOptionIds'] == ['2'] and a['answer'] == 'B'
three = [*two, {'id': '3', 'text': 'C'}]
r = put(structure={'format': 'multi_select', 'mcq_mode': 'recall_first', 'options': three, 'correct_option_ids': ['1', '3']})
assert r.status_code == 200 and r.json()['question']['mcq_mode'] == 'recall_first'
r = put(answer='first\n\nsecond', structure={'format': 'list'})
assert r.json()['question']['format'] == 'list' and r.json()['answer']['answerUnits'] == ['first', 'second']

# 원래와 같은 형식이면 구조는 버리고 지금처럼 글만 고친다.
r = put(question='Edited question 1?', structure={'format': 'basic'})
assert r.status_code == 200 and r.json()['question']['format'] == 'basic'
with SessionLocal() as db:
    assert db.get(BankPersonalEdit, ('a', 'test', 'demo', 'Q1')).structure is None

# 다른 계정은 원래 형식, 되돌리기는 형식도 되돌린다.
put(question='{Secret} is it', structure={'format': 'cloze'})
user('b')
assert client.get(PERSONAL).json()['draft']['format'] == 'basic'
user('a')
reset = put(action='reset')
assert reset.status_code == 200 and reset.json()['question']['format'] == 'basic'
with SessionLocal() as db:
    assert db.scalars(select(BankPersonalEdit)).all() == []

# 문제은행과 연결된 판은 형식도 못 바꾼다(제보만).
with SessionLocal() as db:
    row = db.get(RootContent, ('test', 'demo', 'v1'))
    doc = copy.deepcopy(row.document); doc['bank_source'] = 'quizbank'; row.document = doc
    from app.root_learning import light
    row.light = light.stored(doc); light.clear()
    db.commit()
linked = client.get(PERSONAL).json()
assert linked['formats'] == []
assert put(revision=linked['revision'], answer='o', structure={'format': 'ox'}).status_code == 409
print('PASS: Main-Quiz personal edit changes format among six with per-format limits, private, reset restores, linked versions refuse')
