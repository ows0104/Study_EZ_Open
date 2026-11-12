"""「새로 출제」: a new map-tree request with fresh budgets beside an ended, unpublished one (docs/changes/2026-11-11-main-quiz-start-over).

Isolated sqlite and local storage (root_support.setup); no runner, model or production data."""
import sys
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(1, str(ROOT))
from tests.root_support import setup, ADMIN
client, user, SessionLocal = setup()
from app.models import Asset, Lecture, PrequizJob
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootControl
from app.storage import ObjectStorage
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import packet_hash

storage = ObjectStorage()
storage.put_bytes('rs/notes.pdf', b'%PDF-1.4 synthetic notes'); storage.put_bytes('rs/jokbo.pdf', b'%PDF-1.4 synthetic jokbo')
with SessionLocal() as db:
    db.add(Lecture(subject='test', run_id='pub', uid='root-pub', date=date(2026, 11, 3), slot=1, slot_end=1,
                   start_time='09:00', title='Published lecture', professors=[], author='', version=1))
    for run in ('demo', 'pub'):
        db.add(Asset(id='notes-' + run, subject='test', run_id=run, kind='notes_current', filename='notes.pdf', object_key='rs/notes.pdf'))
        db.add(Asset(id='jokbo-' + run, subject='test', run_id=run, kind='jokbo', filename='jokbo.pdf', object_key='rs/jokbo.pdf'))
    db.commit()
user('admin', True)
URL = ADMIN + '/generation'
NEW = {'conceptMap': '', 'points': '', 'scope': '', 'examDate': None, 'inputMode': 'source', 'authoring': 'cli',
       'parallelAuthoring': False, 'pipeline': map_tree.PIPELINE3, 'privatePilot': False, 'resume': False}
RESTART = {**NEW, 'restart': True, 'resumeReason': 'pipeline changed; start over'}


def set_state(job_id, state):
    with SessionLocal() as db:
        db.get(PrequizJob, job_id).state = state; db.commit()


# Nothing to restart yet.
assert client.post(URL, json={**RESTART, 'requestId': 'none'}).status_code == 409
r = client.post(URL, json={**NEW, 'requestId': 'first'}); assert r.status_code == 200, r.text
first = r.json()['generation']; assert first['restartOf'] is None
# Request shape refusals.
for bad in ({'resume': True}, {'resumeReason': '  '}):
    assert client.post(URL, json={**RESTART, 'requestId': 'bad', **bad}).status_code == 422
# A queued, running or held request is not set aside.
for state in ('queued', 'running', 'held'):
    set_state(first['jobId'], state)
    assert client.post(URL, json={**RESTART, 'requestId': 'busy-' + state}).status_code == 409, state
# Without restart the ended request is reused, as before.
set_state(first['jobId'], 'failed')
with SessionLocal() as db:
    row = db.get(RootGeneration, first['id'])
    row.packet = {**row.packet, 'operatorResumes': [{'reason': 'earlier resume', 'at': 'x', 'by': 'admin'}]}; db.commit()
    before = (dict(row.packet), row.input_digest, row.request_id)
same = client.post(URL, json={**NEW, 'requestId': 'again'}).json()
assert same['reused'] and same['generation']['id'] == first['id']
# Another administrator cannot set it aside.
user('other-admin', True)
assert client.post(URL, json={**RESTART, 'requestId': 'other'}).status_code == 409
user('admin', True)

# ---------------------------------------------------------------- restart
r = client.post(URL, json={**RESTART, 'requestId': 'restart-1'}); assert r.status_code == 200, r.text
second = r.json()['generation']
assert not r.json()['reused'] and second['id'] != first['id'] and second['jobId'] != first['jobId']
assert second['state'] == 'queued' and second['pipeline'] == map_tree.PIPELINE3 and second['restartOf'] == first['id']
assert second['operatorResumes'] == 0  # a new request: its budgets start over
with SessionLocal() as db:
    old = db.get(RootGeneration, first['id']); new = db.get(RootGeneration, second['id'])
    assert (old.packet, old.input_digest, old.request_id) == before  # the earlier request is kept as it was
    assert db.get(PrequizJob, first['jobId']).state == 'failed'
    assert new.packet['restartOf'] == first['id'] and new.packet['restartReason'] == 'pipeline changed; start over'
    assert new.input_digest != old.input_digest and packet_hash(new.packet) == new.packet['inputHash']
    assert new.packet['sources'][0]['snapshotKey'].startswith('lectures/root-generation/' + second['id'] + '/')
# The same request ID returns the same restart, not another one.
again = client.post(URL, json={**RESTART, 'requestId': 'restart-1'}).json()
assert again['reused'] and again['generation']['id'] == second['id']
# The screen shows the newest request.
assert client.get(URL).json()['generation']['id'] == second['id']
# While it runs nothing else is started; once it has failed it can be restarted again (a chain).
assert client.post(URL, json={**RESTART, 'requestId': 'restart-2'}).status_code == 409
set_state(second['jobId'], 'canceled')
r = client.post(URL, json={**RESTART, 'requestId': 'restart-2'}); assert r.status_code == 200, r.text
assert r.json()['generation']['restartOf'] == second['id']
# Resuming the newest one still works the old way.
third = r.json()['generation']; set_state(third['jobId'], 'failed')
r = client.post(URL, json={**RESTART, 'requestId': 'restart-2', 'restart': False, 'resume': True, 'resumeReason': 'retry'})
assert r.status_code == 200 and r.json()['generation']['id'] == third['id'] and r.json()['generation']['state'] == 'queued'

# ---------------------------------------------------------------- a published lecture is still refused
PUB = '/api/admin/root-learning/lectures/test/pub/generation'
r = client.post(PUB, json={**NEW, 'requestId': 'pub-1'}); assert r.status_code == 200, r.text
set_state(r.json()['generation']['jobId'], 'failed')
with SessionLocal() as db:
    db.add(RootControl(subject='test', run_id='pub', revision='published-pub', enabled=True, allowed_users=[])); db.commit()
assert client.post(PUB, json={**RESTART, 'requestId': 'pub-restart'}).status_code == 409
# ---------------------------------------------------------------- the administrator's explicit replacement
assert client.post(PUB, json={**NEW, 'requestId': 'pub-flag-only', 'replacePublished': True}).status_code == 422
r = client.post(PUB, json={**RESTART, 'requestId': 'pub-replace', 'replacePublished': True}); assert r.status_code == 200, r.text
replacing = r.json()['generation']; assert replacing['state'] == 'queued' and replacing['restartOf'] is not None
with SessionLocal() as db:
    control = db.get(RootControl, ('test', 'pub'))
    assert control.revision == 'published-pub' and control.enabled  # students keep the old revision until the new one publishes
    assert db.get(RootGeneration, replacing['id']).packet['replacePublished'] is True
# A request that itself published (job done) can be replaced the same way once the replacement above has ended.
set_state(replacing['jobId'], 'done')
with SessionLocal() as db:
    db.get(RootGeneration, replacing['id']).result_digest = 'd' * 64; db.commit()
assert client.post(PUB, json={**RESTART, 'requestId': 'pub-done'}).status_code == 409
r = client.post(PUB, json={**RESTART, 'requestId': 'pub-done', 'replacePublished': True}); assert r.status_code == 200, r.text
assert r.json()['generation']['restartOf'] == replacing['id']
user('student')
assert client.post(URL, json={**RESTART, 'requestId': 'student'}).status_code == 403
print('PASS restart: refusals, earlier request kept, fresh request, idempotent, chain, resume unchanged, published refused')
