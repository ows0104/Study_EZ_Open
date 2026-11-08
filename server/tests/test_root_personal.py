"""Main-Quiz 「문제 수정·제보」(2026-11-08): 기존 Quiz Bank와 같은 개인 수정본·관리자 제보.

- 개인 수정본은 내 계정의 풀이·미리받기에만 보이고, 다른 계정·원문·학습 사건은 그대로다.
- 저장하면 관리자 신고함(bank_feedback)에 build_id `root:<판>`으로 남고, 신고함이 Main-Quiz 문면을 싣는다.
- 문제은행과 연결된 판은 개인 수정을 받지 않고 제보만 받는다.
"""
import copy
from tests.root_support import setup, publish, start, view, action, BASE

client, user, SessionLocal = setup()
publish(client, user)
from app.models import BankFeedback, BankPersonalEdit
from app.models.root_learning import RootContent, RootEvent
from sqlalchemy import select, func

PERSONAL = BASE + '/questions/Q1/personal'

user('a')
sid = start(client)
assert view(client, sid)['task']['question']['question'] == 'Synthetic question 1?'
snap = client.get(PERSONAL).json()
assert snap['editable'] is True and snap['edited'] is False and snap['draft'] == snap['original']
assert client.get(BASE + '/questions/NOPE/personal').status_code == 404

body = {'revision': snap['revision'], 'question': 'Edited question 1?', 'answer': 'Edited answer 1',
        'comment': '정답이 슬라이드와 다릅니다', 'report': True, 'category': 'content'}
assert client.put(PERSONAL, json={**body, 'revision': '0' * 64}).status_code == 409
assert client.put(PERSONAL, json={**body, 'category': 'bogus'}).status_code == 422
events_before = SessionLocal().scalar(select(func.count()).select_from(RootEvent))
saved = client.put(PERSONAL, json=body)
assert saved.status_code == 200, saved.text
out = saved.json()
assert out['reported'] and out['highlighted']
assert out['question']['question'] == 'Edited question 1?' and out['question']['personalEdited']
assert out['answer']['answer'] == 'Edited answer 1' and out['answer']['personalAnswer']

# The learner's own session and look-ahead show the edit; no learning event was written.
v = view(client, sid)
assert v['task']['question']['question'] == 'Edited question 1?' and v['task']['question'].get('personalEdited')
frames = client.get(f'/api/root-learning/sessions/{sid}/prepare?start=0&count=1').json()['frames']
assert frames[0]['task']['question']['question'] == 'Edited question 1?'
assert frames[0]['task']['answer']['answer'] == 'Edited answer 1'
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert view(client, sid)['task']['answer']['answer'] == 'Edited answer 1'
assert SessionLocal().scalar(select(func.count()).select_from(RootEvent)) == events_before + 1  # only the reveal

with SessionLocal() as db:
    fb = db.scalars(select(BankFeedback)).all()
    assert len(fb) == 1 and fb[0].build_id == 'root:v1' and fb[0].question_id == 'Q1' and fb[0].highlighted
    assert '[개인 수정 제안]' in fb[0].comment and fb[0].correction['changedFields'] == ['question', 'answer']
    original_doc = db.get(RootContent, ('test', 'demo', 'v1')).document
    assert original_doc['bank_snapshot']['questions'][0]['question'] == 'Synthetic question 1?'

# Another account still sees the reviewed original.
user('b')
sid_b = start(client, 'b-start')
assert view(client, sid_b)['task']['question']['question'] == 'Synthetic question 1?'
assert client.get(PERSONAL).json()['edited'] is False

# Admin inbox lists the Main-Quiz report with its question text.
user('admin', True)
inbox = client.get('/api/admin/bank-feedback').json()['questions']
group = next(g for g in inbox if g['questionId'] == 'Q1')
assert group['question'] and 'Synthetic question 1?' in str(group['question'])
assert all(isinstance(group['question'][k], list) for k in ('options', 'answer_pairs', 'correct_option_ids', 'correct_order'))
assert group['reports'][0]['mainQuiz'] is True and group['reports'][0]['stale'] is False

# Reset brings the original back and keeps the report history.
user('a')
again = client.get(PERSONAL).json()
assert again['edited'] and again['draft']['question'] == 'Edited question 1?'
reset = client.put(PERSONAL, json={**body, 'revision': again['revision'], 'action': 'reset'})
assert reset.status_code == 200 and reset.json()['question']['question'] == 'Synthetic question 1?'
with SessionLocal() as db:
    assert db.scalars(select(BankPersonalEdit)).all() == []
    assert len(db.scalars(select(BankFeedback)).all()) == 1

# A version linked to a Quiz Bank takes reports only.
with SessionLocal() as db:
    row = db.get(RootContent, ('test', 'demo', 'v1'))
    doc = copy.deepcopy(row.document); doc['bank_source'] = 'quizbank'; row.document = doc
    db.commit()
linked = client.get(PERSONAL).json()
assert linked['editable'] is False
assert client.put(PERSONAL, json={**body, 'revision': linked['revision']}).status_code == 409
report_only = client.put(PERSONAL, json={**body, 'revision': linked['revision'], 'question': 'Synthetic question 1?',
                                         'answer': linked['original']['answer'], 'comment': '발문이 애매합니다', 'category': 'wording'})
assert report_only.status_code == 200, report_only.text
with SessionLocal() as db:
    assert db.scalars(select(BankPersonalEdit)).all() == []
    assert len(db.scalars(select(BankFeedback)).all()) == 2
# 이용현황: 저장 한 번이 「문제 수정·제보 저장」 한 건이다(되돌리기는 세지 않는다).
from app.models import Profile
with SessionLocal() as db:
    db.add(Profile(id='a', email='a@example.com')); db.commit()
user('admin', True)
detail = client.get('/api/admin/usage/a').json()
row = next(l for l in detail['lectures'] if l['runId'] == 'demo')
assert row['questionReports']['count'] == 2, row['questionReports']
assert any(a['key'] == 'question_report' for a in detail['activityCatalog'])
print('PASS: Main-Quiz personal edit is private, shown in session and look-ahead, reported to the admin inbox with question text, reset keeps history, linked versions take reports only')
