"""map-tree/2 administrator request → claim → runner front (+ independent bank) → root-generation/3 → publication.

docs/changes/2026-11-10-root-generation-3 (PR C). Isolated DB/storage; the runner side runs in-process with synthetic
model answers (tests/runner/test_root_front_v3.py). Needs PyMuPDF like the runner (CI installs the root requirements
in the same environment)."""
import copy
import json
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/contracts')); sys.path.insert(0, str(ROOT / 'tests/quizbank'))
sys.path.insert(0, str(ROOT / 'tests/runner')); sys.path.insert(1, str(ROOT))
import map_tree_fixture as mf
from tests.root_support import setup, ADMIN
client, user, SessionLocal = setup()
from datetime import date
from app.models import Asset, Lecture, PrequizJob
from app.models.root_learning import RootControl
from app.storage import ObjectStorage
from app.main import app
from app.auth import CurrentUser, require_runner
from app.routes.prequiz_jobs import claimed_job
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import packet_hash
import test_root_front_v3 as front_v3
app.dependency_overrides[require_runner] = lambda: CurrentUser(id='runner', email='', is_admin=True)

storage = ObjectStorage()
storage.put_bytes('mt/notes.pdf', mf.pdf_bytes('notes', 2)); storage.put_bytes('mt/jokbo.pdf', mf.pdf_bytes('jokbo', 1))
with SessionLocal() as db:
    db.add(Asset(id='notes-demo', subject='test', run_id='demo', kind='notes_current', filename='notes.pdf', object_key='mt/notes.pdf'))
    db.add(Asset(id='jokbo-demo', subject='test', run_id='demo', kind='jokbo', filename='jokbo.pdf', object_key='mt/jokbo.pdf'))
    db.commit()
user('admin', True)
REQUEST = {'requestId': 'v3-1', 'authoring': 'cli', 'inputMode': 'source', 'pipeline': map_tree.PIPELINE2, 'privatePilot': True}

# ---------------------------------------------------------------- request
r = client.post(ADMIN + '/generation', json=REQUEST); assert r.status_code == 200, r.text
job = r.json()['generation']
assert job['state'] == 'queued' and job['pipeline'] == map_tree.PIPELINE2 and job['privatePilot']
assert client.post(ADMIN + '/generation', json={**REQUEST, 'requestId': 'bad', 'pipeline': 'map-tree/9'}).status_code == 422
base = '/api/admin/root-generation/' + job['id']
with SessionLocal() as db:
    row = db.get(PrequizJob, job['jobId']); row.state = 'running'; db.commit()
    assert claimed_job(db, row)['rootGenerationId'] == job['id']
packet = client.get(base + '/input').json()['packet']
assert packet['pipeline'] == map_tree.PIPELINE2 and packet['sourceAssessmentFormat'] == map_tree.FORMAT2
assert packet_hash(packet) == packet['inputHash']

# ---------------------------------------------------------------- runner, in-process
work = Path(tempfile.mkdtemp(prefix='map-tree-v3-runner-'))
for s in packet['sources']:
    path = work / (s['id'] + '.pdf'); path.write_bytes(storage.get_bytes(s['snapshotKey']))
    del s['downloadUrl']; s['localPath'] = str(path)
from runner.root_front import Front
from quizbank import connection_generate as g
derived = Front(packet, work / 'front', invoke=front_v3.front_codex([])).run()
assert derived['generationPolicy'] == 'root-generation/3'
model = front_v3.Model(); model.points = derived['points']
result = g.run(derived, work / 'generation', invoke=model)
assert result['manifest']['pipelineVersion'] == 'root-generation/3'

forged = copy.deepcopy(result); forged['manifest']['derivedPacket']['intakeBank']['bank']['questions'][0]['answer'] = 'forged'
assert client.put(base + '/result', json=forged).status_code == 422
replay = copy.deepcopy(result); replay['manifest']['addRounds'] = 2
assert client.put(base + '/result', json=replay).status_code == 422
r = client.put(base + '/result', json=json.loads(json.dumps(result))); assert r.status_code == 200, r.text
with SessionLocal() as db:
    control = db.get(RootControl, ('test', 'demo'))
    assert control.revision == packet['revision'] and control.allowed_users == ['admin']   # private pilot: the requester only
report = client.get(ADMIN + '/generation').json()['generation']['report']
assert report['pipelineVersion'] == 'root-generation/3' and report['addRounds'] == 1 and report['fixCount'] == 1 and report['notReady'] == 0
assert report['taskCount'] == len(result['document']['tasks'])
print('PASS map-tree/2 request, claim, front with independent bank, root-generation/3 result check, private publication, report')
