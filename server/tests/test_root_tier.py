"""「내 중요도」 and Quiz Bank target retention for new Main-Quiz ratings (2026-11-09).

사용자 결정: 「새 평가부터 적용」 — a four-rating event saved from now on is scheduled by Quiz Bank's
target retention (mastery EMA, tier target, t=9S(M/target-1)); earlier events keep their schedule."""
from copy import deepcopy
from datetime import timedelta
from math import ceil
from sqlalchemy import select
from tests.root_support import setup, publish, start, view, action, document, BASE, POLICY, NOW
client, user, SessionLocal = setup()
from app.models import Profile
from app.models.root_learning import RootContent, RootEvent
from app.root_learning import content, policy, state
from app.study_engine import engine
from app.study_engine.policy import DEFAULT
with SessionLocal() as db:
    db.add(Profile(id='a', email='a@example.com', is_admin=False)); db.commit()
doc = document(); doc['exam_date'] = '2027-12-31'  # far enough that the exam cap does not hide the interval
publish(client, user, doc)
sid = start(client)
first = view(client, sid)['task']
qid = first['question']['question_id']
# No tier in the revision: shown as Core, nothing personal yet.
assert first['question']['tier'] == 'Core' and 'personalTier' not in first['question'], first['question']
assert first['question']['targetMastery'] == 0.85  # no plan/importance: the Core tier target
TIER = BASE + '/questions/' + qid + '/tier'


def put(request, tier, path=TIER):
    return client.put(path, json={'requestId': request, 'tier': tier})


# ── API: choice, idempotence, refusals, every view shows it ──────────────────
r = put('t1', 'Essential'); assert r.status_code == 200, r.text
body = r.json()
assert body['question']['tier'] == 'Essential' and body['question']['personalTier'] is True
assert body['question']['originalTier'] == 'Core' and body['rescheduled'] is False
assert body['question']['targetMastery'] == 0.9
assert 'answer' not in body['question'] and 'Secret answer' not in r.text
assert put('t1', 'Essential').json() == body
assert put('t1', 'Optional').status_code == 409
assert put('bad', 'Must-Know').status_code == 422
assert put('missing', 'Core', BASE + '/questions/NOPE/tier').status_code == 404
assert view(client, sid)['task']['question']['tier'] == 'Essential'
frames = client.get('/api/root-learning/sessions/' + sid + '/prepare').json()['frames']
assert [f['task']['question']['tier'] for f in frames if f['task']['question']['question_id'] == qid] == ['Essential']
assert all(f['task']['question']['tier'] == 'Core' for f in frames if f['task']['question']['question_id'] != qid)

# A rating saved now carries Quiz Bank's mastery policy; the tier then reschedules it.
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', selfRating='Good').status_code == 200
with SessionLocal() as db:
    rated = db.get(RootEvent, ('a', 'g1')).payload
    stored = db.scalars(select(RootContent)).first().document
assert rated['ratingPolicy'] == 'roots-four-rating/2' and rated['targetParameters']['tierTargets'] == DEFAULT['mastery']['tierTargets']
# Choices saved at one fixed instant with IDs sorting against save order (z2 > y3 > x4 > w5): only seq decides.
assert put('z2', 'Optional').json()['rescheduled'] is True
with SessionLocal() as db:
    events = content.events_for(db, 'test', 'demo', 'a')
assert state.personal_tiers(stored, events)[qid]['tier'] == 'Optional'  # z2 sorts last by ID, first by seq
assert 'personalTier' not in put('y3', 'Core').json()['question']  # the revision's own tier = 원래대로
assert put('x4', 'Important').status_code == 200 and put('w5', None).json()['question']['tier'] == 'Core'
with SessionLocal() as db:
    events = content.events_for(db, 'test', 'demo', 'a')
assert state.personal_tiers(stored, events) == {}  # w5 (null) holds although its ID sorts first
assert len([e for e in events if e['kind'] == 'tier']) == 5  # every choice stays as an event

# ── Same target as Quiz Bank target_for, for every tier / private / plan case ─
params = policy.target_parameters()
bank = {'retrieval_plan': [{'concept_id': 'C1', 'target_mastery': 0.7}]}
for tier in policy.TIERS:
    for importance in (2, 3, 4, 5):
        for concept in ('C1', 'C2'):
            q = {'question_id': 'X', 'concept_id': concept, 'tier': tier, 'importance': importance}
            mine = policy.target_retention(q, {p['concept_id']: p for p in bank['retrieval_plan']}.get(concept), params)
            assert mine == engine.target_for(bank, q)['effective'], (tier, importance, concept)
            for personal in policy.TIERS:
                theirs = engine.target_for(bank, {**q, 'tier': personal, 'personalTier': True})['effective']
                assert policy.target_retention(q, None, params, personal) == theirs, (tier, personal)
assert policy.target_retention({'question_id': 'X', 'tier': 'Must-Know'}, None, params) == 0.9

# ── Interval = Quiz Bank review_schedule, rounded up to study days, Main-Quiz caps kept ──
S, M = 3.0, 0.93
at = int(NOW.timestamp() * 1000)
example = {'question_id': 'X', 'concept_id': 'C', 'tier': 'Core', 'importance': 4}
qb = engine.review_schedule({'retrieval_plan': []}, example, {'reviewed_at': at, 'mastery_after': M, 'stability_days': S})
value = {'ratingDays': S, 'lastAt': NOW, 'lastDay': NOW.date()}
target = policy.target_retention(example, None, params)
assert target == qb['target_schedule']['target'] == 0.78
mine = policy.target_due(value, M, target, POLICY, None)
assert mine['scheduledDays'] == ceil(qb['interval'] / engine.DAY_MS) == 6, (mine, qb['interval'] / engine.DAY_MS)
assert policy.target_due({**value, 'ratingDays': 10.0}, 0.99, 0.55, POLICY, None)['scheduledDays'] == POLICY['max_days'] == 30  # 72 days, Main-Quiz cap

# ── Replay: a run of Goods; tiers order the intervals; old events are untouched ──
task = stored['tasks'][0]


def goods(count, rating_policy=True):
    out, when, value = [], NOW, {}
    for i in range(count):
        p = {'task_id': task['task_id'], 'direction_id': task['direction_id'], 'grade': 'independent', 'helped': False,
             'selfRating': 'Good', 'policy': POLICY, 'exam_date': stored['exam_date'],
             'ratingParameters': deepcopy(policy.FOUR_RATING_PARAMETERS)}
        if rating_policy:
            p.update(ratingPolicy='roots-four-rating/2', targetParameters=params)
        out.append({'id': f'g{i:02d}', 'revision': stored['revision'], 'kind': 'rate', 'payload': p, 'at': when})
        value = state.replay(stored, out, when, POLICY)[1][task['direction_id']]
        when = when + timedelta(days=value['scheduledDays'])
    return out, when


def tier_event(name, tier):
    return {'id': name, 'revision': stored['revision'], 'kind': 'tier', 'at': NOW,
            'payload': {'question_id': task['question_id'], 'tier': tier, 'originalTier': None, 'seq': 1}}


rated, end = goods(8)
schedule = {}
for tier in (None, 'Essential', 'Important', 'Optional'):
    extra = [tier_event('choice', tier)] if tier else []
    schedule[tier] = state.replay(stored, rated + extra, end, POLICY)[1][task['direction_id']]
core, essential, important, optional = (schedule[t] for t in (None, 'Essential', 'Important', 'Optional'))
assert core['target'] == 0.85 and optional['target'] == 0.55 and essential['target'] == 0.9
assert essential['scheduledDays'] <= core['scheduledDays'] <= important['scheduledDays'] <= optional['scheduledDays']
assert essential['scheduledDays'] < optional['scheduledDays'], schedule
assert core['ratingDays'] == optional['ratingDays'] and core['mastery'] == optional['mastery']  # only the target moves
# Before this change a four-rating event has no targetParameters: its interval stays ceil(S), tier or not.
old, end = goods(4, rating_policy=False)
plain = state.replay(stored, old, end, POLICY)[1][task['direction_id']]
assert plain == {**state.replay(stored, old + [tier_event('o', 'Optional')], end, POLICY)[1][task['direction_id']]}
assert plain['scheduledDays'] == min(POLICY['max_days'], max(1, ceil(plain['ratingDays']))) and 'target' not in plain
# A tier event of another revision is never read (an ID alone carries no choice).
assert state.personal_tiers(stored, [{**tier_event('x', 'Optional'), 'revision': 'older'}]) == {}

user('admin', True)
activities = client.get('/api/admin/usage/a').json()['lectures'][0]['activities']
assert activities['root_tier']['count'] == 5, activities['root_tier']
print('PASS: 내 중요도 kept per revision; new ratings use Quiz Bank targets/intervals; old ratings unchanged; usage counted')
