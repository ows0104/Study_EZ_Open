"""map-tree/1 administrator request → claim → runner front stages → generation → publication to students.

docs/changes/2026-11-09-main-quiz-runner-pipeline R1·R6·R7. Isolated DB/storage; the runner side runs in-process
with synthetic model answers (tests/contracts/map_tree_fixture.py). Needs PyMuPDF like the runner (CI installs the
root requirements in the same environment)."""
import copy
import json
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/contracts')); sys.path.insert(1, str(ROOT))
import map_tree_fixture as mf
from tests.root_support import setup, ADMIN
client, user, SessionLocal = setup()
from datetime import date
from sqlalchemy import select
from app.models import Asset, Lecture, PrequizJob, QuizBank
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootControl, RootEvent
from app.storage import ObjectStorage
from app.main import app
from app.auth import CurrentUser, require_runner
from app.routes.prequiz_jobs import claimed_job
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import packet_hash
app.dependency_overrides[require_runner] = lambda: CurrentUser(id='runner', email='', is_admin=True)

storage = ObjectStorage()
storage.put_bytes('mt/notes.pdf', mf.pdf_bytes('notes', 2)); storage.put_bytes('mt/jokbo.pdf', mf.pdf_bytes('jokbo', 1))
storage.put_bytes('mt/notes.md', b'# Synthetic notes')
with SessionLocal() as db:
    for run, title in (('other', 'Other lecture'), ('second', mf.TITLE), ('text', mf.TITLE)):
        db.add(Lecture(subject='test', run_id=run, uid='root-' + run, date=date(2026, 11, 3), slot=1, slot_end=1,
                       start_time='09:00', title=title, professors=[], author='', version=1))
    for run in ('demo', 'second'):
        db.add(Asset(id='notes-' + run, subject='test', run_id=run, kind='notes_current', filename='notes.pdf', object_key='mt/notes.pdf'))
        db.add(Asset(id='jokbo-' + run, subject='test', run_id=run, kind='jokbo', filename='jokbo.pdf', object_key='mt/jokbo.pdf'))
    db.add(Asset(id='notes-text', subject='test', run_id='text', kind='notes_current', filename='notes.md', object_key='mt/notes.md'))
    db.add(RootControl(subject='test', run_id='other', revision='published-other', enabled=True, allowed_users=[]))
    db.add(QuizBank(subject='test', run_id='demo', status='ready', build_id='preserved', bank={'questions': []}))
    db.commit()
user('admin', True)
REQUEST = {'requestId': 'mt-1', 'authoring': 'cli', 'inputMode': 'source', 'pipeline': map_tree.PIPELINE, 'privatePilot': False}

# ---------------------------------------------------------------- request
r = client.post(ADMIN + '/generation', json=REQUEST); assert r.status_code == 200, r.text
job = r.json()['generation']
assert job['state'] == 'queued' and job['pipeline'] == map_tree.PIPELINE and not job['privatePilot'] and not job['awaitingWeb']
assert job['stage'] == 'Main-Quiz 앞 단계(개념 지도·포인트) 대기'
assert [(s['id'], s['filename']) for s in job['sources']] == [('S1', 'notes.pdf'), ('S2', 'jokbo.pdf')]
for bad in ({'authoring': 'web'}, {'parallelAuthoring': True}, {'inputMode': 'provided', 'conceptMap': 'X', 'points': 'Y'}):
    assert client.post(ADMIN + '/generation', json={**REQUEST, 'requestId': 'bad', **bad}).status_code == 422
assert client.post('/api/admin/root-learning/lectures/test/other/generation', json={**REQUEST, 'requestId': 'o'}).status_code == 409
assert client.post('/api/admin/root-learning/lectures/test/text/generation', json={**REQUEST, 'requestId': 't'}).status_code == 422
same = client.post(ADMIN + '/generation', json={**REQUEST, 'requestId': 'mt-2'})
assert same.status_code == 200 and same.json()['generation']['id'] == job['id']  # same input reuses the request

base = '/api/admin/root-generation/' + job['id']
with SessionLocal() as db:
    row = db.get(PrequizJob, job['jobId']); row.state = 'running'; db.commit()
    assert claimed_job(db, row)['rootGenerationId'] == job['id']
packet = client.get(base + '/input').json()['packet']
assert packet['pipeline'] == map_tree.PIPELINE and packet['sourceAssessmentFormat'] == map_tree.FORMAT and packet['privatePilot'] is False
assert packet_hash(packet) == packet['inputHash']

# ---------------------------------------------------------------- runner, in-process
work = Path(tempfile.mkdtemp(prefix='map-tree-runner-'))
for s in packet['sources']:
    path = work / (s['id'] + '.pdf'); path.write_bytes(storage.get_bytes(s['snapshotKey']))
    del s['downloadUrl']; s['localPath'] = str(path)
from runner.root_front import Front
from quizbank import connection_generate as g
derived = Front(packet, work / 'front', invoke=mf.fake_codex([])).run()
result = g.run(derived, work / 'generation', invoke=mf.generation_model)

forged = copy.deepcopy(result); forged['manifest']['derivedPacket']['scope'] += ' forged'
assert client.put(base + '/result', json=forged).status_code == 422
missing = copy.deepcopy(result); del missing['manifest']['derivedPacket']
assert client.put(base + '/result', json=missing).status_code == 422
with SessionLocal() as db:
    before_other = (db.get(RootControl, ('test', 'other')).revision, db.get(RootControl, ('test', 'other')).allowed_users)
    before_events = len(db.scalars(select(RootEvent).where(RootEvent.run_id == 'demo')).all())
r = client.put(base + '/result', json=json.loads(json.dumps(result))); assert r.status_code == 200, r.text
assert r.json()['revision'] == packet['revision'] and client.put(base + '/result', json=json.loads(json.dumps(result))).json()['reused']
with SessionLocal() as db:
    control = db.get(RootControl, ('test', 'demo'))
    assert control.revision == packet['revision'] and control.enabled and control.allowed_users == []  # students, decision 4
    other = db.get(RootControl, ('test', 'other'))
    assert (other.revision, other.allowed_users) == before_other
    assert db.get(QuizBank, ('test', 'demo')).build_id == 'preserved'
    events = db.scalars(select(RootEvent).where(RootEvent.run_id == 'demo')).all()
    assert len(events) == before_events + 1 and events[-1].kind == 'generated'
# The lecture is now published: a new map-tree request is refused (replacing a published revision is separate).
assert client.post(ADMIN + '/generation', json={**REQUEST, 'requestId': 'mt-3', 'scope': 'another try'}).status_code == 409

# ---------------------------------------------------------------- administrator resume with a reason
SECOND = '/api/admin/root-learning/lectures/test/second/generation'
r = client.post(SECOND, json={**REQUEST, 'requestId': 'mt-second'}); assert r.status_code == 200, r.text
second = r.json()['generation']
with SessionLocal() as db:
    row = db.get(PrequizJob, second['jobId']); row.state = 'failed'; db.commit()
    stored = db.get(RootGeneration, second['id']).packet['inputHash']
assert client.post(SECOND, json={**REQUEST, 'requestId': 'mt-second', 'resume': True}).status_code == 422
r = client.post(SECOND, json={**REQUEST, 'requestId': 'mt-second', 'resume': True, 'resumeReason': 'runner laptop slept'})
assert r.status_code == 200 and r.json()['generation']['state'] == 'queued' and r.json()['generation']['operatorResumes'] == 1
with SessionLocal() as db:
    row = db.get(RootGeneration, second['id'])
    assert row.packet['inputHash'] == stored == packet_hash(row.packet)
    assert [x['reason'] for x in row.packet['operatorResumes']] == ['runner laptop slept'] and row.packet['operatorResumes'][0]['by'] == 'admin'
    db.get(PrequizJob, second['jobId']).state = 'running'; db.commit()
assert client.get('/api/admin/root-generation/' + second['id'] + '/input').json()['packet']['operatorResumes'][0]['reason'] == 'runner laptop slept'
user('student')
assert client.post(ADMIN + '/generation', json={**REQUEST, 'requestId': 'student'}).status_code == 403
print('PASS map-tree request, refusals, claim, runner front+generation, derived-packet re-derivation, publication to students, other lectures preserved, resume reason')
