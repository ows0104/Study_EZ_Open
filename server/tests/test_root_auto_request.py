"""올해 필기 첫 업로드 → Main-Quiz 자동 요청 (docs/changes/2026-11-24-auto-main-quiz-on-notes).

Isolated sqlite and local storage (root_support.setup); no runner, model or production data."""
import os
import sys
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(1, str(ROOT))
os.environ['RUNNER_TOKEN'] = 'runner-token'
from tests.root_support import setup
client, user, SessionLocal = setup()
import httpx
from app.models import Asset, Lecture, PrequizJob
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootControl
from app.routes import root_generation
from studyez_contracts.roots import map_tree

RUNNER = {'Authorization': 'Bearer runner-token'}
NEW = {'conceptMap': '', 'points': '', 'scope': '', 'examDate': None, 'inputMode': 'source', 'authoring': 'cli',
       'parallelAuthoring': False, 'pipeline': map_tree.PIPELINE3, 'privatePilot': False, 'resume': False}

with SessionLocal() as db:
    for slot, (run, title) in enumerate([('cbl', 'CBL 2'), ('pub', 'Published lecture'), ('md', 'Markdown notes'),
                                         ('cap', 'Over the cap')], 2):
        db.add(Lecture(subject='test', run_id=run, uid='root-' + run, date=date(2026, 11, 3), slot=slot, slot_end=slot,
                       start_time='09:00', title=title, professors=[], author='', version=1))
    db.add(RootControl(subject='test', run_id='pub', revision='manual-1', enabled=True, allowed_users=[]))
    db.commit()


def upload(run, *files, headers=RUNNER):
    """The runner's three calls: presign, PUT to the signed URL, complete."""
    base = f'/api/admin/lectures/test/{run}/uploads'
    body = [{'kind': kind, 'filename': name, 'sizeBytes': 24, 'contentType': 'application/pdf'} for kind, name in files]
    for entry in client.post(base, headers=headers, json=body).json()['files']:
        client.put(httpx.URL(entry['uploadUrl']).path, content=b'%PDF-1.4 synthetic source')
    r = client.post(base + '/complete', headers=headers, json=body); assert r.status_code == 200, r.text
    assert (r.json()['stored'], r.json()['missing']) == (len(files), []), r.text
    return r.json()['queued']


def jobs(run=None):
    with SessionLocal() as db:
        rows = db.query(PrequizJob).order_by(PrequizJob.id).all()
        return [(j.run_id, j.kind, j.state, j.origin) for j in rows if run in (None, j.run_id)]


# Other materials alone never ask.
assert upload('demo', ('jokbo', 'jokbo.pdf')) is None and jobs() == []

# The first upload of this year's notes asks once, as the button does: map-tree/3 from the lecture's own sources, public.
queued = upload('demo', ('notes_current', 'notes.pdf'))
assert queued and (queued['kind'], queued['state'], queued['origin'], queued['requestedBy']) == ('bank', 'queued', 'auto', ''), queued
assert queued['stage'].startswith(root_generation.AUTO_WHY), queued
with SessionLocal() as db:
    row = db.query(RootGeneration).one()
    first = row.id
    packet = row.packet
    assert (row.user_id, packet['owner'], row.job_id) == ('runner', 'runner', queued['id'])
    assert (packet['pipeline'], packet['authoring'], packet['inputMode'], packet['privatePilot']) == (map_tree.PIPELINE3, 'cli', 'source', False)
    assert [s['kind'] for s in packet['sources']] == ['notes_current', 'jokbo'], packet['sources']
    assert row.request_id.startswith('auto-')

# The runner's sweep re-confirms the same files; replaced notes are a new asset. Neither asks again.
assert upload('demo', ('notes_current', 'notes.pdf')) is None
assert upload('demo', ('notes_current', 'notes-v2.pdf')) is None
assert jobs() == [('demo', 'bank', 'queued', 'auto')]
with SessionLocal() as db:
    assert [a.filename for a in db.query(Asset).filter_by(run_id='demo', kind='notes_current')] == ['notes-v2.pdf']

# The claim binds the automatic job to its own request, like a button job.
claimed = client.post('/api/admin/prequiz-jobs/claim', headers=RUNNER).json()['job']
assert claimed['id'] == queued['id'] and claimed['rootGenerationId'] == first, claimed

# Practice·CBL·PBL keep the existing automatic-review exclusion; a published revision is never replaced.
assert upload('cbl', ('notes_current', 'notes.pdf')) is None
assert upload('pub', ('notes_current', 'notes.pdf')) is None
# A request that cannot be made (map-tree reads PDF pages) does not fail the upload.
assert upload('md', ('notes_current', 'notes.md')) is None
with SessionLocal() as db:
    assert db.query(Asset).filter_by(run_id='md').count() == 1
assert jobs() == [('demo', 'bank', 'running', 'auto')]

# Over the daily automatic cap the request is kept and its job waits for a person.
cap = root_generation.JOB_AUTO_DAILY_CAP
root_generation.JOB_AUTO_DAILY_CAP = 1
held = upload('cap', ('notes_current', 'notes.pdf'))
root_generation.JOB_AUTO_DAILY_CAP = cap
assert held and held['state'] == 'held' and '자동 상한' in held['stage'], held

# Any administrator continues a runner-owned request (with a reason) ...
user('admin', True)
URL = '/api/admin/root-learning/lectures/test/cap/generation'
r = client.post(URL, json={**NEW, 'requestId': 'by-admin', 'resume': True}); assert r.status_code == 422, r.text
r = client.post(URL, json={**NEW, 'requestId': 'by-admin', 'resume': True, 'resumeReason': 'start it today'})
assert r.status_code == 200 and r.json()['reused'] and r.json()['generation']['state'] == 'queued', r.text
assert jobs('cap') == [('cap', 'bank', 'queued', 'auto')]
# ... and starts it over once it ended.
with SessionLocal() as db:
    db.get(PrequizJob, held['id']).state = 'failed'; db.commit()
r = client.post(URL, json={**NEW, 'requestId': 'again', 'restart': True, 'resumeReason': 'start over'})
assert r.status_code == 200 and not r.json()['reused'], r.text
with SessionLocal() as db:
    again = db.get(RootGeneration, r.json()['generation']['id'])
    assert again.packet['owner'] == 'admin' and db.get(PrequizJob, again.job_id).origin == 'button'
print('ok: automatic Main-Quiz request on the first notes upload')
