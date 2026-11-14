"""오늘 학습 중요도 필터(2026-11-12, docs/changes/2026-11-12-tier-filter).

Only today's plan is filtered by the chosen tiers. Summary, progress, records and the all-tier session stay as before."""
from copy import deepcopy
from sqlalchemy import select
from tests.root_support import setup, publish, start, view, action, document, BASE
client, user, SessionLocal = setup()
from app.models.root_learning import RootSession
from app.root_learning import content
publish(client, user)
FOCUS = BASE + '/focus'
ALL = ['Essential', 'Core', 'Important', 'Optional']


def overview():
    r = client.get(BASE); assert r.status_code == 200, r.text
    return r.json()


def focus(request, tiers):
    return client.put(FOCUS, json={'requestId': request, 'tiers': tiers})


def plan_questions(info):
    return sorted(t['question_id'] for t in info['plan']['tasks'])


# ── R1 task tier: personal tier, else the revision's tier (Must-Know = Essential), else Core ──
doc = document()
tiered = deepcopy(doc)
tiered['bank_snapshot']['questions'][0]['tier'] = 'Must-Know'
tiered['bank_snapshot']['questions'][1]['tier'] = 'Optional'
assert content.task_tiers(tiered, {}) == {'task1': 'Essential', 'task2': 'Optional', 'task3': 'Core'}
assert content.task_tiers(tiered, {'Q2': {'tier': 'Important', 'originalTier': 'Optional'}})['task2'] == 'Important'

# ── Default: every tier, the former plan and session ID ──
user('a')
before = overview()
assert before['focus'] == {'tiers': ALL, 'counts': {'Essential': 0, 'Core': 3, 'Important': 0, 'Optional': 0}}
assert plan_questions(before) == ['Q1', 'Q2', 'Q3']
base_total = before['summary']['total']

# Q3 marked Optional with 「내 중요도」; counts follow it.
r = client.put(BASE + '/questions/Q3/tier', json={'requestId': 't3', 'tier': 'Optional'}); assert r.status_code == 200, r.text
assert overview()['focus']['counts'] == {'Essential': 0, 'Core': 2, 'Important': 0, 'Optional': 1}

# ── Validation and idempotence ──
assert focus('f0', []).status_code == 422
assert focus('f0', ['Bogus']).status_code == 422
assert focus('f0', ['Core', 'Core']).status_code == 422
r = focus('f1', ['Optional', 'Essential', 'Core', 'Important'][1:])  # Essential, Core, Important (any order)
assert r.status_code == 200, r.text
saved = r.json()
assert saved['focus']['tiers'] == ['Essential', 'Core', 'Important']
assert focus('f1', ['Essential', 'Core', 'Important']).status_code == 200
assert focus('f1', ['Core']).status_code == 409  # same request ID, other content
assert client.put(BASE + '/questions/Q3/tier', json={'requestId': 'f1', 'tier': 'Core'}).status_code == 409

# ── R2/R3: plan excludes Optional, summary and progress do not ──
info = overview()
assert plan_questions(info) == ['Q1', 'Q2'], info['plan']['tasks']
assert info['summary']['total'] == base_total
assert info['questionProgress'] == before['questionProgress']

# ── One stream a day (2026-11-14 continuous-today, replaces 11-12 R5): a tier change keeps the session ──
def tasks_of(sid):
    with SessionLocal() as db:
        return [t['question_id'] for t in db.get(RootSession, sid).tasks]


narrowed_sid = start(client, 's1')
assert view(client, narrowed_sid)['count'] == 2
with SessionLocal() as db:
    assert db.get(RootSession, narrowed_sid).state['focus'] == ['Essential', 'Core', 'Important']
assert overview()['sessionId'] == narrowed_sid and overview()['todayDone'] == 0
assert focus('f2', ALL).status_code == 200
assert overview()['sessionId'] == narrowed_sid and tasks_of(narrowed_sid) == ['Q1', 'Q2', 'Q3']
assert focus('f3', ['Essential', 'Core', 'Important']).status_code == 200
assert overview()['sessionId'] == narrowed_sid and tasks_of(narrowed_sid) == ['Q1', 'Q2']

# Records made under a narrowed choice are ordinary learning events.
assert action(client, narrowed_sid, 'r1', 'reveal', attempted=True).status_code == 200
assert overview()['summary']['total'] == base_total

# ── Only Optional: the one Optional task ──
assert focus('f4', ['Optional']).status_code == 200
assert plan_questions(overview()) == ['Q3']

# ── Saves at the same instant (the clock is frozen here): the later save wins, whatever its request ID ──
assert focus('zz-first', ['Core']).status_code == 200
assert focus('aa-second', ['Essential', 'Optional']).status_code == 200
assert overview()['focus']['tiers'] == ['Essential', 'Optional']
assert focus('mm-third', ALL).status_code == 200
assert overview()['focus']['tiers'] == ALL
assert focus('f5', ['Optional']).status_code == 200

# ── Per learner and per subject: another account keeps every tier ──
user('b')
other = overview()
assert other['focus']['tiers'] == ALL and plan_questions(other) == ['Q1', 'Q2', 'Q3']

# The all-tier session of a learner without a choice has the former ID (no focus in its key or state).
sid_b = start(client, 'b1')
with SessionLocal() as db:
    row = db.get(RootSession, sid_b)
    assert 'focus' not in row.state
    from studyez_contracts.roots import document_hash
    assert sid_b == document_hash(['b', 'test', 'demo', row.revision, row.day, row.policy, row.tasks])

# ── Continuous today (2026-11-14): tier changes re-choose only the unsolved rest of the one stream ──
user('c')
NARROW = ['Essential', 'Core', 'Important']
assert client.put(BASE + '/questions/Q3/tier', json={'requestId': 'c-t3', 'tier': 'Optional'}).status_code == 200
assert focus('c-f1', NARROW).status_code == 200
sid = start(client, 'c-s1')
assert tasks_of(sid) == ['Q1', 'Q2']
assert focus('c-f2', ALL).status_code == 200
assert tasks_of(sid) == ['Q1', 'Q2', 'Q3']
assert action(client, sid, 'c-r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'c-g1', 'rate', selfRating='Good').status_code == 200
assert action(client, sid, 'c-r2', 'reveal', attempted=True).status_code == 200
# Optional off: the solved Q1, the revealed Q2 and the position stay; Q3 leaves the rest.
assert focus('c-f3', NARROW).status_code == 200
assert tasks_of(sid) == ['Q1', 'Q2']
v = view(client, sid)
assert v['position'] == 1 and v['task']['answer'] is not None and v['count'] == 2
assert overview()['sessionId'] == sid and overview()['todayDone'] == 1
# Optional on again: the same list as if it had never been turned off (no added goals).
assert focus('c-f4', ALL).status_code == 200
assert tasks_of(sid) == ['Q1', 'Q2', 'Q3'] and view(client, sid)['position'] == 1
# Z still walks back through the kept part.
assert action(client, sid, 'c-u1', 'undo').status_code == 200
assert action(client, sid, 'c-u2', 'undo').status_code == 200
assert view(client, sid)['position'] == 0
assert action(client, sid, 'c-g1b', 'rate', selfRating='Good').status_code == 200
assert action(client, sid, 'c-r2b', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'c-g2', 'rate', selfRating='Good').status_code == 200
# Narrowing at the end finishes the stream; widening again brings Q3 back to the same stream.
assert focus('c-f5', NARROW).status_code == 200
assert tasks_of(sid) == ['Q1', 'Q2'] and view(client, sid)['finished']
info = overview()
assert info['sessionId'] is None and info['todayDone'] == 2
r = client.post(BASE + '/sessions', json={'requestId': 'c-s2'})
assert r.status_code == 409 and '더 풀 과제' in r.json()['detail'], r.text
assert focus('c-f6', ALL).status_code == 200
assert tasks_of(sid) == ['Q1', 'Q2', 'Q3'] and overview()['sessionId'] == sid
v = view(client, sid)
assert v['position'] == 2 and not v['finished']
# A write from another tab in between: the list change is refused like a stale rating (optimistic lock).
from fastapi import HTTPException
from sqlalchemy import update
from app.routes import root_learning as routes
with SessionLocal() as db:
    row = db.get(RootSession, sid); db.expunge(row)
    db.execute(update(RootSession).where(RootSession.id == sid).values(version=row.version + 1)); db.commit()
    try:
        routes.replace_tasks(db, row, row.tasks[:2])
        raise AssertionError('stale list change accepted')
    except HTTPException as error:
        assert error.status_code == 409
assert tasks_of(sid) == ['Q1', 'Q2', 'Q3']

# ── 더 풀기: a finished stream grows at its end; numbering continues; a later tier change keeps the extra goal ──
lone = document()
lone['revision'] = 'v2'
lone['prerequisites'] = []
lone['exam_date'] = '2026-12-31'
publish(client, user, lone)
user('e')
sid = start(client, 'e-s1')
first = tasks_of(sid)
assert first == ['Q3'], first  # one new goal today; the exam-important T2 comes first
assert action(client, sid, 'e-r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'e-g1', 'rate', selfRating='Good').status_code == 200
info = overview()
assert info['sessionId'] is None and info['todayDone'] == 1 and plan_questions(info) == ['Q1', 'Q2']
assert start(client, 'e-s2') == sid
v = view(client, sid)
assert tasks_of(sid) == ['Q3', 'Q1', 'Q2'] and v['position'] == 1 and v['count'] == 3
with SessionLocal() as db:
    assert db.get(RootSession, sid).state['extraGoals'] == 1
assert focus('e-f1', ['Core']).status_code == 200  # Q1–Q3 are Core for this learner: nothing changes
assert tasks_of(sid) == ['Q3', 'Q1', 'Q2']
assert focus('e-f2', ALL).status_code == 200
assert tasks_of(sid) == ['Q3', 'Q1', 'Q2'] and view(client, sid)['position'] == 1
print('root focus ok')
