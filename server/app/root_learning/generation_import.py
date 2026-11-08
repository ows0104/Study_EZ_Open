"""Explicit administrator import of a completed root-generation/2 run (Map pipeline, run by hand).

The packet and result come from a local run (`runs/_e2e/<id>/generation*`); the result contract is
re-validated here. A new version is added and the active revision switches to it. The previous
version, its events and sessions stay; visibility (enabled/allowed_users) is never widened.
"""
import copy
from datetime import datetime, UTC
from app.models import Lecture, PrequizJob, JOB_BANK, JOB_BUTTON, JOB_DONE
from app.models.root_learning import RootContent, RootControl, RootEvent
from app.models.root_generation import RootGeneration
from app.root_learning.content import validate_registration
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result, packet_hash
from studyez_contracts.roots.generation_v2 import POLICY as GENERATION_POLICY
from studyez_contracts.learning_links.validate import require

POLICY = 'verified-root-generation-import/1'
SNAPSHOT_PREFIX = 'lectures/root-reviewed-import/'


def snapshot_key(source):
    return SNAPSHOT_PREFIX + source['sha256'] + '/' + source['id']


def register(db, packet, result, snapshots, *, expected_control_hash, authorized_by):
    """One transaction. Requires the exact control state seen at preflight."""
    require(packet_hash(packet) == packet['inputHash'], 'generation import: changed packet')
    require(result['manifest'].get('pipelineVersion', GENERATION_POLICY) == GENERATION_POLICY
            or result['document'].get('generation_policy') == GENERATION_POLICY, 'generation import: not root-generation/2')
    validate_result(result, packet)
    require(type(authorized_by) is str and authorized_by.strip(), 'generation import: explicit authorization required')
    subject, rid = packet['subject'], packet['runId']
    lecture = db.get(Lecture, (subject, rid)); require(lecture is not None, 'generation import: missing lecture')
    db.refresh(lecture, with_for_update=True)
    doc = validate_registration(db, subject, rid, result['document']); digest = document_hash(result)
    require(doc['tasks'], 'generation import: no prepared tasks')
    gid = document_hash({'policy': POLICY, 'inputHash': packet['inputHash'], 'resultHash': digest})[:32]
    prior = db.get(RootGeneration, gid)
    if prior:
        require(prior.result_digest == digest and prior.result == result, 'generation import: changed existing result')
        return {'generationId': gid, 'revision': doc['revision'], 'reused': True}
    control = db.get(RootControl, (subject, rid))
    actual = document_hash([control.revision, control.enabled, control.allowed_users] if control else None)
    require(actual == expected_control_hash, 'generation import: active content/visibility changed since preflight')
    require(not db.get(RootContent, (subject, rid, doc['revision'])), 'generation import: preserve the existing version')
    frozen = copy.deepcopy(packet)
    for s in frozen['sources']:
        s.pop('localPath', None); s.pop('downloadUrl', None)
    require(len(snapshots) == len(frozen['sources']), 'generation import: one snapshot per source')
    for source, snap in zip(frozen['sources'], snapshots):
        expected = {k: v for k, v in source.items() if k != 'snapshotKey'}  # same rule as reviewed_import.source_records
        require({k: v for k, v in snap.items() if k != 'snapshotKey'} == expected and snap['snapshotKey'] == snapshot_key(source),
                'generation import: snapshot differs from the packet source')
    metadata = {'policy': POLICY, 'packetHash': packet['inputHash'], 'sourceSnapshots': snapshots,
                'resultHash': digest, 'authorizedBy': authorized_by,
                'previousRevision': control.revision if control else None}
    now = datetime.now(UTC)
    job = PrequizJob(subject=subject, run_id=rid, kind=JOB_BANK, origin=JOB_BUTTON, state=JOB_DONE,
                     requested_by='runner: explicit root-generation import — ' + authorized_by,
                     message=f"Map 파이프라인 실행 결과 반입 · {len(doc['tasks'])}과제 · 수정 {result['manifest']['repairRounds']}of3",
                     finished_at=now)
    db.add(job); db.flush()
    row = RootGeneration(id=gid, job_id=job.id, subject=subject, run_id=rid, user_id='runner',
                         request_id='generation-import-' + gid, input_digest=document_hash({'policy': POLICY, 'inputHash': packet['inputHash']}),
                         packet=frozen, baseline=expected_control_hash, result=result, result_digest=digest, web_dispatch=metadata)
    from .reviewed_import import source_records
    source_records(row)
    db.add(row)
    db.add(RootContent(subject=subject, run_id=rid, revision=doc['revision'], document=doc, digest=document_hash(doc), reviewed=True))
    if control is None:
        # A first version stays an administrator pilot, like the reviewed import.
        db.add(RootControl(subject=subject, run_id=rid, revision=doc['revision'], enabled=True, allowed_users=['runner']))
        private = True
    else:
        control.revision = doc['revision']  # enabled/allowed_users unchanged: visibility never widens here
        private = bool(control.allowed_users)
    db.add(RootEvent(user_id='runner', request_id='generation-import-' + gid, session_id='', subject=subject, run_id=rid,
                     revision=doc['revision'], kind='publication',
                     payload={'policy': POLICY, 'generationId': gid, 'previousRevision': metadata['previousRevision']},
                     result={'revision': doc['revision'], 'inputHash': packet['inputHash'], 'resultHash': digest}))
    db.commit()
    return {'generationId': gid, 'revision': doc['revision'], 'reused': False, 'privatePilot': private,
            'tasks': len(doc['tasks']), 'previousRevision': metadata['previousRevision']}
