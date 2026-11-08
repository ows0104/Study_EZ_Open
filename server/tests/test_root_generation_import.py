"""root-generation/2 import: re-validated result, frozen snapshots, revision switch, visibility unchanged."""
import copy, json
from pathlib import Path
from tests.root_support import setup, BASE
client, user, SessionLocal = setup()
from app.models import PrequizJob
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent, RootControl, RootEvent, RootSession
from app.root_learning import generation_import as imp
from app.root_learning.reviewed_import import source_records
from app.routes.root_learning import revealed_answer
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

fixture = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))
p, value = fixture['packet'], fixture['result']
snapshot = [{**{k: v for k, v in s.items() if k != 'snapshotKey'}, 'snapshotKey': imp.snapshot_key(s)} for s in p['sources']]
ObjectStorage().put_bytes(snapshot[0]['snapshotKey'], fixture['sourceBody'].encode('latin-1'))
old_doc = copy.deepcopy(value['document']); old_doc['revision'] = 'older-reviewed-version'

with SessionLocal() as db:
    # An existing reviewed version that learners used stays as it is.
    db.add(RootContent(subject='test', run_id='demo', revision='older-reviewed-version', document=old_doc,
                       digest=document_hash(old_doc), reviewed=True))
    db.add(RootControl(subject='test', run_id='demo', revision='older-reviewed-version', enabled=True, allowed_users=['runner']))
    db.add(RootEvent(user_id='u1', request_id='r1', session_id='s', subject='test', run_id='demo',
                     revision='older-reviewed-version', kind='rating', payload={}, result={}))
    db.commit()
    seen = document_hash(['older-reviewed-version', True, ['runner']])

    # A tampered result is rejected by the contract before anything is written.
    bad = copy.deepcopy(value); bad['document']['bank_snapshot']['questions'][0]['tier'] = 'Essential'
    try:
        imp.register(db, p, bad, snapshot, expected_control_hash=seen, authorized_by='test'); raise AssertionError('tampered accepted')
    except ValueError:
        db.rollback()
    # The control changed since preflight → refused.
    try:
        imp.register(db, p, value, snapshot, expected_control_hash=document_hash(None), authorized_by='test'); raise AssertionError('stale preflight')
    except ValueError:
        db.rollback()

    result = imp.register(db, p, value, snapshot, expected_control_hash=seen, authorized_by='test approval')
    assert result['previousRevision'] == 'older-reviewed-version' and result['privatePilot'] and not result['reused']
    control = db.get(RootControl, ('test', 'demo'))
    assert control.revision == p['revision'] and control.enabled and control.allowed_users == ['runner']
    assert db.get(RootContent, ('test', 'demo', 'older-reviewed-version')).document == old_doc
    row = db.get(RootGeneration, result['generationId'])
    assert row.result == value and source_records(row) == snapshot and db.get(PrequizJob, row.job_id).state == 'done'
    kinds = sorted(e.kind for e in db.query(RootEvent).all())
    assert kinds == ['publication', 'rating'] and db.query(RootSession).count() == 0
    assert imp.register(db, p, value, snapshot, expected_control_hash=seen, authorized_by='again')['reused']
    content = db.get(RootContent, ('test', 'demo', p['revision']))
    assert content.document['bank_snapshot']['build_meta']['schema_version'] == '3.3'
    answer = revealed_answer(db, content, content.document['bank_snapshot']['questions'][0])
    assert len(answer['sourceLinks']) == 1
user('member')
assert client.get(BASE).status_code == 404
user('admin', True)
assert client.get(BASE).status_code == 200
print('root-generation import: contract recheck, stale preflight refusal, revision switch, old version and events kept, visibility unchanged passed')
