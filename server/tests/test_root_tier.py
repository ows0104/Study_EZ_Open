"""「내 중요도」(2026-11-09): a Main-Quiz learner's own tier is shown, kept per revision and re-times only that question."""
from math import ceil
from sqlalchemy import select
from tests.root_support import setup, publish, start, view, action, document, BASE, POLICY, NOW
client, user, SessionLocal = setup()
from app.models import Profile
from app.models.root_learning import RootContent, RootEvent
from app.root_learning import content, policy, state
with SessionLocal() as db:
    db.add(Profile(id='a', email='a@example.com', is_admin=False)); db.commit()
doc = document(); doc['exam_date'] = '2026-12-31'  # far enough that the exam cap does not hide the interval
publish(client, user, doc)
sid = start(client)
first = view(client, sid)['task']
qid = first['question']['question_id']
# No tier in the revision: shown as Core, nothing personal yet.
assert first['question']['tier'] == 'Core' and 'personalTier' not in first['question'], first['question']
TIER = BASE + '/questions/' + qid + '/tier'


def put(request, tier, path=TIER):
    return client.put(path, json={'requestId': request, 'tier': tier})


r = put('t1', 'Essential'); assert r.status_code == 200, r.text
body = r.json()
assert body['question']['tier'] == 'Essential' and body['question']['personalTier'] is True
assert body['question']['originalTier'] == 'Core' and body['rescheduled'] is False
assert 'answer' not in body['question'] and 'Secret answer' not in r.text
# Same request again is the same result; a different body under that ID is refused.
assert put('t1', 'Essential').json() == body
assert put('t1', 'Optional').status_code == 409
assert put('bad', 'Must-Know').status_code == 422
assert put('missing', 'Core', BASE + '/questions/NOPE/tier').status_code == 404
# Session view, look-ahead and the personal-edit answer all show the learner's tier.
assert view(client, sid)['task']['question']['tier'] == 'Essential'
frames = client.get('/api/root-learning/sessions/' + sid + '/prepare').json()['frames']
assert [f['task']['question']['tier'] for f in frames if f['task']['question']['question_id'] == qid] == ['Essential']
assert all(f['task']['question']['tier'] == 'Core' for f in frames if f['task']['question']['question_id'] != qid)

# Every choice here is saved at the same fixed instant with request IDs that sort against
# the save order (z2 > y3 > x4 > w5), so only the saved sequence decides which one holds.
# Rate it once with the four buttons; the tier then re-times only this question.
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', selfRating='Good').status_code == 200
with SessionLocal() as db:
    row = db.scalars(select(RootContent)).first()
    doc = row.document
did = next(t['direction_id'] for t in doc['tasks'] if t['task_id'] == first['id'])


def due():
    with SessionLocal() as db:
        events = content.events_for(db, 'test', 'demo', 'a')
    return state.replay(doc, events, NOW, POLICY)[1][did]


default = due()
assert put('z2', 'Optional').json()['rescheduled'] is True
later = due()
factor = policy.tier_factor('Optional', 'Core')
assert round(factor, 2) == 4.64, factor
limit = policy.exam_limit(doc['exam_date'], later['lastAt'], POLICY)
expected = min(ceil(default['ratingDays'] * factor), POLICY['max_days'])
expected = min(expected, limit) if limit is not None else expected
assert later['scheduledDays'] == expected and later['ratingDays'] == default['ratingDays'], (default, later)
assert later['scheduledDays'] > default['scheduledDays'], (default, later)
# Choosing the revision's own tier is 원래대로; so is null. The schedule returns to the default.
r = put('y3', 'Core'); assert r.status_code == 200 and 'personalTier' not in r.json()['question'], r.text
assert due() == default
assert put('x4', 'Important').status_code == 200 and put('w5', None).json()['question']['tier'] == 'Core'
assert due() == default
with SessionLocal() as db:
    kinds = [e.payload['tier'] for e in db.scalars(select(RootEvent).where(RootEvent.kind == 'tier').order_by(RootEvent.created_at))]
assert len(kinds) == 5  # every choice stays as an event; nothing is overwritten

# Another revision's tier events are never read (an ID alone carries no choice).
other = {'id': 'x', 'revision': 'older', 'kind': 'tier', 'at': NOW,
         'payload': {'question_id': qid, 'tier': 'Optional', 'originalTier': None, 'factor': 4.6}}
assert state.personal_tiers(doc, [other]) == {}
# Older three-grade events are never re-timed by a tier.
legacy = {'learned': False, 'rating': 'independent', 'stage': 0, 'baseDays': 1, 'lastAt': NOW, 'lastDay': NOW.date(), 'due': 'x'}
assert policy.personal_due(legacy, 4.6, POLICY, None) == legacy

user('admin', True)
activities = client.get('/api/admin/usage/a').json()['lectures'][0]['activities']
assert activities['root_tier']['count'] == 5, activities['root_tier']
print('PASS: personal tier shown/kept per revision, re-times only its four-rating schedule, reset restores it, usage counted')
