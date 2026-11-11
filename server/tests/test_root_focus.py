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

# ── R5: a narrowed session is its own; it is resumed only under the same choice ──
narrowed_sid = start(client, 's1')
v = view(client, narrowed_sid)
assert v['count'] == 2
with SessionLocal() as db:
    assert db.get(RootSession, narrowed_sid).state['focus'] == ['Essential', 'Core', 'Important']
assert overview()['sessionId'] == narrowed_sid
assert focus('f2', ALL).status_code == 200
everything = overview()
assert everything['sessionId'] is None and plan_questions(everything) == ['Q1', 'Q2', 'Q3']
full_sid = start(client, 's2')
assert full_sid != narrowed_sid and view(client, full_sid)['count'] == 3
with SessionLocal() as db:
    assert 'focus' not in db.get(RootSession, full_sid).state
assert focus('f3', ['Essential', 'Core', 'Important']).status_code == 200
assert overview()['sessionId'] == narrowed_sid

# Records made under a narrowed choice are ordinary learning events.
assert action(client, narrowed_sid, 'r1', 'reveal', attempted=True).status_code == 200
assert overview()['summary']['total'] == base_total

# ── Only Optional: the one Optional task ──
assert focus('f4', ['Optional']).status_code == 200
assert plan_questions(overview()) == ['Q3']

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
print('root focus ok')
