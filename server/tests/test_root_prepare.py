"""The look-ahead the page draws from is read-only and matches what the events produce."""
from datetime import timedelta
from sqlalchemy import select, func
from tests.root_support import setup, publish, start, view, action, NOW
client, user, SessionLocal = setup()
publish(client, user)
from app.models.root_learning import RootEvent, RootSession
from app.routes import root_learning

sid = start(client)
PREPARE = '/api/root-learning/sessions/' + sid + '/prepare'


def events():
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(RootEvent))


before, state = events(), view(client, sid)
r = client.get(PREPARE); assert r.status_code == 200, r.text
body = r.json()
assert body['sessionId'] == sid and body['revision'] == state['revision']
positions = [f['position'] for f in body['frames']]
assert positions == list(range(min(state['count'], root_learning.PREPARE_AHEAD))), positions
first = body['frames'][0]
assert first['taskId'] == state['task']['id'] and first['task']['question'] == state['task']['question']
assert first['task']['answer']['answer'] == 'Secret answer 1'
assert first['task']['helped'] == state['task']['helped']
# Preparing records nothing and reveals nothing.
assert events() == before
after = view(client, sid)
assert after['version'] == state['version'] and after['task']['answer'] is None
with SessionLocal() as db:
    assert db.get(RootSession, sid).state['reveals'] == {}

# The prepared answer is the answer the reveal event then shows.
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert view(client, sid)['task']['answer'] == first['task']['answer']
# The prepared next question is the question the rating then shows.
second = body['frames'][1]
assert action(client, sid, 'rate1', 'rate', selfRating='Good').status_code == 200
moved = view(client, sid)
assert moved['position'] == 1 and moved['task']['id'] == second['taskId'] and moved['task']['question'] == second['task']['question']

# start= reads ahead of the server's index (the page confirms events behind the screen).
ahead = client.get(PREPARE, params={'start': 2, 'count': 1}).json()['frames']
assert [f['position'] for f in ahead] == ([2] if state['count'] > 2 else [])
assert client.get(PREPARE, params={'start': state['count']}).json()['frames'] == []
assert client.get(PREPARE, params={'start': -1}).status_code == 422
assert client.get(PREPARE, params={'count': 9}).status_code == 422

user('b')
assert client.get(PREPARE).status_code == 404
user('a')
root_learning.now = lambda: NOW + timedelta(days=1)
assert client.get(PREPARE).json()['frames'] == []
root_learning.now = lambda: NOW
print('PASS: prepare is read-only, matches reveal/rate projections, reads ahead, private, empty after rollover')
