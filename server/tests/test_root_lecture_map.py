"""개념 지도 without a session (docs/changes/2026-11-12-map-without-session).

Isolated sqlite and local storage (root_support.setup); no runner, model or production data."""
from datetime import timedelta
from sqlalchemy import select
from tests.root_support import setup, publish, start, view, action, BASE, NOW
client, user, SessionLocal = setup()
from app.models.root_learning import RootEvent, RootSession
from app.routes import root_learning

MAP = BASE + '/map'


def lecture_map(request):
    return client.post(MAP, json={'requestId': request})


def map_views(uid='a'):
    with SessionLocal() as db:
        return db.scalars(select(RootEvent).where(RootEvent.user_id == uid, RootEvent.kind == 'map_view')).all()


def overview():
    r = client.get(BASE); assert r.status_code == 200, r.text
    return r.json()


def finish(sid, prefix):
    i = 0
    while not view(client, sid)['finished']:
        r = action(client, sid, f'{prefix}-reveal{i}', 'reveal', attempted=True, response='x'); assert r.status_code == 200, r.text
        r = action(client, sid, f'{prefix}-rate{i}', 'rate', grade='partial'); assert r.status_code == 200, r.text
        i += 1


# ── Not published: 404, nothing recorded ──
user('a')
assert lecture_map('m0').status_code == 404
assert map_views() == []
publish(client, user)

# ── Day 1: no map viewed → the session starts as before (mapSeen False) ──
sid = start(client, 'day1')
assert view(client, sid)['mapSeen'] is False
finish(sid, 'd1')

# Today's list is done: starting again is refused, the map still opens without a session.
assert overview()['sessionId'] is None
assert client.post(BASE + '/sessions', json={'requestId': 'day1-again'}).status_code == 409
r = lecture_map('m1'); assert r.status_code == 200, r.text
data = r.json()
assert data['currentConceptIds'] == [] and data['concepts'] and data['targets']
with SessionLocal() as db:
    sessions_before = db.scalars(select(RootSession)).all()
assert len(sessions_before) == 1  # the map made no session

# Repeated views the same study day keep one record.
assert lecture_map('m2').status_code == 200
assert lecture_map('m1').status_code == 200
views = map_views(); assert len(views) == 1 and views[0].session_id == '' and views[0].payload['day']
# The finished session itself is unchanged.
assert view(client, sid)['finished'] is True

# ── Day 2: map first, then a session → it starts as mapSeen ──
root_learning.now = lambda: NOW + timedelta(days=1)
assert overview()['plan']['tasks'], 'day 2 needs review tasks for this check'
assert lecture_map('m3').status_code == 200
assert len(map_views()) == 2
sid2 = start(client, 'day2')
assert sid2 != sid and view(client, sid2)['mapSeen'] is True
# The session map works at once (mapSeen already set).
assert client.get('/api/root-learning/sessions/' + sid2 + '/map').status_code == 200

# ── Another learner and another day are not affected ──
user('b')
sid_b = start(client, 'b-day2')
assert view(client, sid_b)['mapSeen'] is False
user('a')
root_learning.now = lambda: NOW + timedelta(days=2)
if overview()['plan']['tasks'] and overview()['sessionId'] is None:
    assert view(client, start(client, 'day3'))['mapSeen'] is False

# ── Request shape ──
assert client.post(MAP, json={}).status_code == 422
assert client.post(MAP, json={'requestId': 'bad id!'}).status_code == 422
print('ok')
