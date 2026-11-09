"""사슬알균(감염과 면역 261105_01) generation-4 판의 운영 반입 — preflight·publish.

User approval 2026-11-09: 「반입해줘」 (운영 등록). Opening to students is a separate decision: a lecture
without a RootControl gets the administrator pilot (allowed_users ['runner']) from generation_import.
Writes: R2 source snapshots (only when absent; never overwrite different bytes), one RootGeneration,
one RootContent, the RootControl, one publication RootEvent, one PrequizJob. Nothing else may change.
Adapted from docs/changes/2026-11-08-importance-basis/publication.py (감염병리1).

  python publication.py preflight     # read-only; records the state to compare against
  python publication.py publish <api-revision-sha>
"""
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT.parents[1] if ROOT.parent.name == '.worktrees' else ROOT
sys.path.insert(0, str(ROOT / 'server')); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(MAIN / 'server/.env', override=False)
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Lecture, QuizBank, BankState
from app.models.root_learning import RootContent, RootControl, RootEvent, RootSession
from app.storage import ObjectStorage
from app.root_learning import generation_import
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result

GEN = MAIN / 'runs/_e2e/26110901/generation-4'
OUT = MAIN / 'runs/_e2e/26110901/publication'
API = 'https://studyez-api-97999573571.asia-northeast3.run.app'
AUTH = '2026-11-09 사용자 「반입해줘」 — 사슬알균 generation-4 운영 등록(관리자 시범, 학생 공개 아님)'
PILOT = {'enabled': True, 'allowedUsers': ['runner']}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inspect(db, packet):
    subject, rid = packet['subject'], packet['runId']
    assert db.get(Lecture, (subject, rid)) is not None, 'Named lecture must exist'
    def scoped(model):
        return list(db.scalars(select(model).where(model.subject == subject, model.run_id == rid)))
    control = db.get(RootControl, (subject, rid)); bank = db.get(QuizBank, (subject, rid))
    return {'control': {'revision': control.revision, 'enabled': control.enabled, 'allowedUsers': control.allowed_users} if control else None,
            'controlHash': document_hash([control.revision, control.enabled, control.allowed_users] if control else None),
            'versions': {v.revision: {'digest': v.digest, 'reviewed': v.reviewed} for v in scoped(RootContent)},
            'bank': {'buildId': bank.build_id, 'hash': document_hash(bank.bank)} if bank else None,
            'bankStates': {v.user_id: document_hash(v.state) for v in scoped(BankState)},
            'rootEvents': {v.user_id + '/' + v.request_id: document_hash({'kind': v.kind, 'revision': v.revision, 'payload': v.payload, 'result': v.result}) for v in scoped(RootEvent)},
            'rootSessions': {v.id: document_hash({'revision': v.revision, 'tasks': v.tasks, 'state': v.state, 'version': v.version}) for v in scoped(RootSession)},
            # other lectures: their Main-Quiz rows must not move
            'elsewhere': {'contents': db.scalar(select(func.count()).select_from(RootContent).where((RootContent.subject != subject) | (RootContent.run_id != rid))),
                          'controls': sorted([c.subject, c.run_id, c.revision, c.enabled, list(c.allowed_users or [])]
                                             for c in db.scalars(select(RootControl)) if (c.subject, c.run_id) != (subject, rid))}}


def load():
    packet, result = read(GEN / 'packet.json'), read(GEN / 'result.json')
    validate_result(result, packet)
    for s in packet['sources']:
        body = Path(s['localPath']).read_bytes()
        assert len(body) == s['sizeBytes'] and hashlib.sha256(body).hexdigest() == s['sha256'], 'Frozen source changed'
    return packet, result


def preflight():
    packet, result = load()
    OUT.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        state = inspect(db, packet)
    assert packet['revision'] not in state['versions'], 'Revision already registered'
    state['resultSha256'] = hashlib.sha256((GEN / 'result.json').read_bytes()).hexdigest()
    (OUT / 'preflight.json').write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: state[k] for k in ('control', 'controlHash', 'bank')} | {'versions': list(state['versions']),
          'rootEvents': len(state['rootEvents']), 'rootSessions': len(state['rootSessions']), 'bankStates': len(state['bankStates']),
          'elsewhere': {'contents': state['elsewhere']['contents'], 'controls': len(state['elsewhere']['controls'])},
          'tasks': len(result['document']['tasks']), 'revision': packet['revision']}, ensure_ascii=False))


def publish(revision):
    packet, result = load()
    before = read(OUT / 'preflight.json')
    assert before['resultSha256'] == hashlib.sha256((GEN / 'result.json').read_bytes()).hexdigest(), 'Result changed after preflight'
    with urllib.request.urlopen(API + '/api/health', timeout=30) as r:
        health = json.load(r)
    assert health['revision'] == revision and health['environment'] == 'production', ('Deploy the import code first', health)
    with SessionLocal() as db:
        current = inspect(db, packet)
        assert current == {k: v for k, v in before.items() if k != 'resultSha256'}, 'Lecture changed after preflight'
        storage = ObjectStorage(); snapshots = []
        for s in packet['sources']:
            body = Path(s['localPath']).read_bytes(); key = generation_import.snapshot_key(s)
            prior = storage.get_bytes(key)
            if prior is None:  # R2 (put_bytes is local-storage only)
                storage.upload_fileobj(io.BytesIO(body), key, content_type='application/pdf')
            else:
                assert prior == body, 'Never overwrite a different original snapshot'
            assert storage.get_bytes(key) == body, 'Snapshot readback failed'
            snapshots.append({**{k: v for k, v in s.items() if k not in ('localPath', 'downloadUrl', 'snapshotKey')}, 'snapshotKey': key})
        response = generation_import.register(db, packet, result, snapshots, expected_control_hash=before['controlHash'], authorized_by=AUTH)
        after = inspect(db, packet)
        for k in ('bank', 'bankStates', 'rootSessions', 'elsewhere'):
            assert after[k] == before[k], 'Changed ' + k
        assert all(after['rootEvents'].get(k) == v for k, v in before['rootEvents'].items())
        assert set(after['rootEvents']) - set(before['rootEvents']) == {'runner/generation-import-' + response['generationId']}
        assert all(after['versions'].get(k) == v for k, v in before['versions'].items()), 'An existing version changed'
        assert after['control']['revision'] == packet['revision']
        visibility = {k: after['control'][k] for k in ('enabled', 'allowedUsers')}
        expected = PILOT if before['control'] is None else {k: before['control'][k] for k in ('enabled', 'allowedUsers')}
        assert visibility == expected, ('Visibility changed', visibility)
        row = db.get(RootContent, (packet['subject'], packet['runId'], packet['revision']))
        assert row.document == result['document'] and row.digest == document_hash(result['document'])
    record = {'response': response, 'before': before, 'after': after, 'apiRevision': revision}
    (OUT / 'published.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(response, ensure_ascii=False))


if __name__ == '__main__':
    {'preflight': preflight, 'publish': lambda: publish(sys.argv[2])}[sys.argv[1]]()
