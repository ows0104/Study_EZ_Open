"""Optional 계산 제외(docs/changes/2026-11-13-exclude-optional).

Off: every count is the former value. On: Optional tasks (by 「내 중요도」, else the revision's tier) count as if
absent in the rate, card counts and target summary, on every exit. Questions, records, availability and the
plan are untouched. The choice is per account, stored as an append-only root_event."""
import copy
from datetime import date, timedelta
from unittest.mock import patch

from tests.root_support import setup, publish, start, view, action, document, BASE, POLICY, NOW
client, user, SessionLocal = setup()
from app.models import Lecture, TimetableEvent
from app.root_learning import content
from app.root_learning.policy import target_parameters
from app.root_learning.score import lecture_score
from app.root_learning.state import optional_tasks, question_progress, summary

OPTIONAL = '/api/root-learning/optional'
PARAMS = target_parameters()


def rated(task_id, direction_id, at, revision, policy='root-generation/4'):
    return [{'id': 'reveal-' + task_id + str(at), 'kind': 'reveal', 'revision': revision, 'at': at,
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'attempted': True, 'policy': POLICY}},
            {'id': 'rate-' + task_id + str(at), 'kind': 'rate', 'revision': revision, 'at': at + timedelta(seconds=1),
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'grade': 'independent', 'helped': False,
                         'policy': POLICY, 'exam_date': '2026-12-20', 'selfRating': 'Good',
                         'ratingPolicy': 'roots-four-rating/2', 'targetParameters': PARAMS}}]


def tier(doc, qid, value):
    for q in doc['bank_snapshot']['questions']:
        if q['question_id'] == qid:
            q['tier'] = value


def per_task_doc():
    """/4: D1 has Q1·Q4, D2 has Q2, D3 has Q3. Targets T1=D1+D2, T2=D3, T3=D4 (no task, never ready)."""
    doc = copy.deepcopy(document())
    doc['generation_policy'] = 'root-generation/4'
    q4 = copy.deepcopy(doc['bank_snapshot']['questions'][0]); q4['question_id'] = 'Q4'
    doc['bank_snapshot']['questions'].append(q4)
    doc['tasks'].append({'task_id': 'task4', 'question_id': 'Q4', 'direction_id': 'D1'})
    return doc


# ── Unit: which tasks are Optional (personal tier wins, Must-Know = Essential, absent = Core) ──
doc = per_task_doc()
tier(doc, 'Q4', 'Optional')
tier(doc, 'Q1', 'Must-Know')
assert optional_tasks(doc, []) == {'task4'}
mine = [{'id': 't', 'kind': 'tier', 'revision': doc['revision'], 'at': NOW,
         'payload': {'question_id': 'Q4', 'tier': 'Core', 'originalTier': 'Optional', 'seq': 1}},
        {'id': 'u', 'kind': 'tier', 'revision': doc['revision'], 'at': NOW,
         'payload': {'question_id': 'Q3', 'tier': 'Optional', 'originalTier': None, 'seq': 2}}]
assert optional_tasks(doc, mine) == {'task3'}

# ── Unit: off = former values; on = Optional absent ──
available = {'task1', 'task2', 'task3', 'task4'}
events = rated('task1', 'D1', NOW, doc['revision'])
at = NOW + timedelta(minutes=1)
plain = lecture_score(doc, events, POLICY, at)
assert lecture_score(doc, events, POLICY, at, skip_optional=False) == plain
skipped = lecture_score(doc, events, POLICY, at, skip_optional=True)
# D1 is averaged over Q1 only (Q4 Optional), so the same rating weighs more.
assert skipped['targetCount'] == plain['targetCount'] and skipped['value'] > plain['value'], (plain, skipped)
assert summary(doc, events, available, at, POLICY) == summary(doc, events, available, at, POLICY, False)
progress = question_progress(doc, events, available, at, POLICY)
assert progress['total'] == 4 and progress['unseen'] == 3
narrowed = question_progress(doc, events, available, at, POLICY, skip_optional=True)
assert narrowed['total'] == 3 and narrowed['unseen'] == 2, narrowed

# A target whose only direction is all Optional leaves every count.
tier(doc, 'Q3', 'Optional')
base, cut = summary(doc, events, available, at, POLICY), summary(doc, events, available, at, POLICY, True)
assert base['total'] == 3 and cut['total'] == 2 and cut['unseen'] == base['unseen'] - 1, (base, cut)
assert [t['id'] for t in cut['targets']] == ['T1', 'T3']
assert lecture_score(doc, events, POLICY, at, skip_optional=True)['targetCount'] == 2
# Records on an Optional task do not count while it is excluded.
optional_only = rated('task3', 'D3', NOW, doc['revision'])
assert summary(doc, optional_only, available, at, POLICY, True)['learned'] == 0
assert summary(doc, optional_only, available, at, POLICY)['learned'] == 1

# Every task Optional: nothing to measure, as with no target.
everything = per_task_doc()
for qid in ('Q1', 'Q2', 'Q3', 'Q4'):
    tier(everything, qid, 'Optional')
# T3 (D4) has no task at all, so it is not Optional and stays, as before.
assert lecture_score(everything, [], POLICY, at, skip_optional=True)['targetCount'] == 1
everything['adopted_target_ids'] = ['T1', 'T2']
assert lecture_score(everything, [], POLICY, at, skip_optional=True)['score'] is None
assert lecture_score(everything, [], POLICY, at)['targetCount'] == 2
assert question_progress(everything, [], available, at, POLICY, skip_optional=True)['total'] == 0

# Older documents keep state per direction: only a direction whose every task is Optional is dropped.
old = copy.deepcopy(document())
old['tasks'].append({'task_id': 'task4', 'question_id': 'Q2', 'direction_id': 'D1'})  # D1 also served by Q2
tier(old, 'Q1', 'Optional')
old_events = rated('task1', 'D1', NOW, old['revision'], policy=None)
assert summary(old, old_events, available, at, POLICY, True)['total'] == 3      # D1 still has task4
assert summary(old, old_events, available, at, POLICY, True)['learned'] == 1
tier(old, 'Q2', 'Optional')                                                       # D1 and D2 all Optional
assert [t['id'] for t in summary(old, old_events, available, at, POLICY, True)['targets']] == ['T2', 'T3']

# ── API: per account, append-only, idempotent; every exit follows it ──
with SessionLocal() as db:
    db.add(TimetableEvent(id='event', date=date(2026, 11, 3), start_time='09:00', end_time='10:00',
                          title='Synthetic', category='lecture', course='test'))
    db.get(Lecture, ('test', 'demo')).timetable_event_id = 'event'
    db.commit()
publish(client, user)
user('a')
assert client.get(OPTIONAL).json() == {'exclude': False}


def overview():
    r = client.get(BASE); assert r.status_code == 200, r.text
    return r.json()


def rates():
    with patch('app.lecture_mastery.datetime') as clock:
        clock.now.return_value = NOW + timedelta(minutes=1)
        timetable = client.get('/api/timetable').json()['events'][0]['lectures'][0]['mastery']
        detail = client.get('/api/lectures/test/demo').json()['mastery']
    return timetable, detail


sid = start(client)
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', selfRating='Good').status_code == 200
assert client.put(BASE + '/questions/Q3/tier', json={'requestId': 't3', 'tier': 'Optional'}).status_code == 200
before, before_rates = overview(), rates()
assert before['summary']['total'] == 3 and before['questionProgress']['total'] == 3

r = client.put(OPTIONAL, json={'requestId': 'o1', 'exclude': True})
assert r.status_code == 200 and r.json() == {'exclude': True}, r.text
assert client.put(OPTIONAL, json={'requestId': 'o1', 'exclude': True}).status_code == 200
assert client.put(OPTIONAL, json={'requestId': 'o1', 'exclude': False}).status_code == 409
assert client.put(OPTIONAL, json={'requestId': 't3', 'exclude': False}).status_code == 409  # a tier request
assert client.put(OPTIONAL, json={'requestId': 'o2'}).status_code == 422
on = overview()
assert on['summary']['total'] == 2 and on['questionProgress']['total'] == 2, (on['summary'], on['questionProgress'])
assert [t['id'] for t in on['summary']['targets']] == ['T1', 'T3']
on_rates = rates()
assert on_rates[0] == on_rates[1] and on_rates[0]['targetCount'] == before_rates[0]['targetCount'] - 1
assert on_rates[0]['score'] >= before_rates[0]['score']
with patch('app.routes.root_learning.now', return_value=NOW + timedelta(minutes=1)):
    assert overview()['summary']['score'] == on_rates[0]['score']
assert view(client, sid)['summary']['total'] == 2
catalog = client.get('/api/root-learning').json()['lectures'][0]
assert catalog['summary']['total'] == 2 and catalog['questionProgress']['total'] == 2

# Not counted is not removed: availability, plan, focus counts and the question itself stay.
assert on['plan'] == before['plan'] and on['focus'] == before['focus']
assert on['preparationProblems'] == before['preparationProblems']
assert sorted(t['question_id'] for t in on['plan']['tasks']) == sorted(t['question_id'] for t in before['plan']['tasks'])

# Another account is unaffected; turning it off restores every former value.
user('b')
assert client.get(OPTIONAL).json() == {'exclude': False} and overview()['summary']['total'] == 3
user('a')
assert client.put(OPTIONAL, json={'requestId': 'o3', 'exclude': False}).json() == {'exclude': False}
off = overview()
assert off['summary'] == before['summary'] and off['questionProgress'] == before['questionProgress']
assert rates() == before_rates
with SessionLocal() as db:
    assert content.optional_excluded(db, 'a') is False
    assert len(content.optional_events(db, 'a')) == 2
    # Lecture events never include the account-level rows.
    assert all(e['kind'] != 'optional' for e in content.events_for(db, 'test', 'demo', 'a'))
print('PASS: Optional 계산 제외 — off unchanged, on drops Optional from rate/cards/summary on every exit, plan and records kept')
