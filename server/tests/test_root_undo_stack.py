"""Main-Quiz Z: every reveal, rating and skip of the session undoes step by step, and nothing undone counts (2026-11-11)."""
from tests.root_support import setup, publish, start, view, action
client, user, SessionLocal = setup()
publish(client, user)
sid = start(client)


def ok(request, kind, **kwargs):
    r = action(client, sid, request, kind, **kwargs); assert r.status_code == 200, r.text


def at():
    v = view(client, sid)
    return v['position'], v['task']['answer'] is not None if v['task'] else None, v['canUndo']


assert at() == (0, False, False)
assert action(client, sid, 'u0', 'undo').status_code == 409
ok('r1', 'reveal', attempted=True); assert at() == (0, True, True)
ok('g1', 'rate', selfRating='Good'); assert at() == (1, False, True)
ok('r2', 'reveal', attempted=True); assert at() == (1, True, True)   # the next answer no longer clears undo
ok('g2', 'rate', selfRating='Again')
ok('s3', 'skip'); assert view(client, sid)['finished'] and view(client, sid)['canUndo']
assert view(client, sid)['summary']['learned'] >= 1

# Back to the very start, one step per Z: skip, rating, reveal, rating, reveal.
steps = []
for i in range(5):
    ok(f'z{i}', 'undo'); steps.append(at())
assert steps == [(2, False, True), (1, True, True), (1, False, True), (0, True, True), (0, False, False)], steps
assert action(client, sid, 'z5', 'undo').status_code == 409
# Undone reveals are not learned/seen, undone ratings not recalled.
summary = view(client, sid)['summary']
assert summary['learned'] == 0 and summary['recalled'] == 0, summary

# The question can be revealed again and the session moves on normally.
ok('r1b', 'reveal', attempted=True); ok('g1b', 'rate', selfRating='Good')
assert at() == (1, False, True) and view(client, sid)['summary']['learned'] >= 1

# A session saved by the previous code (one `undo` slot) still undoes that rating.
from app.models.root_learning import RootSession
with SessionLocal() as db:
    row = db.get(RootSession, sid); state = dict(row.state)
    state.pop('undoStack'); state['undo'] = {'requestId': 'g1b', 'index': 0}
    row.state = state; db.commit()
ok('zl', 'undo'); assert at() == (0, True, False)
with SessionLocal() as db:
    assert db.get(RootSession, sid).state['undoStack'] == []
# The old slot mirrors the top rating/skip so a rollback keeps one-step undo; a reveal on top leaves it empty.
ok('g1c', 'rate', selfRating='Hard')
with SessionLocal() as db:
    assert db.get(RootSession, sid).state['undo'] == {'requestId': 'g1c', 'index': 0}
ok('r2c', 'reveal', attempted=True)
with SessionLocal() as db:
    saved = db.get(RootSession, sid).state
    assert saved['undoStack'][-1]['kind'] == 'reveal' and saved['undo'] is None
print('PASS: unlimited step-by-step undo of reveal/rate/skip, undone events excluded, legacy slot')
