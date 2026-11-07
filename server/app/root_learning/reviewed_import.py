"""Explicit import of a completed frozen review, without inventing a queued run."""
import copy
from datetime import datetime,UTC
from sqlalchemy import select
from app.models import Lecture,PrequizJob,JOB_BANK,JOB_BUTTON,JOB_DONE
from app.models.root_learning import RootContent,RootControl,RootEvent
from app.models.root_generation import RootGeneration
from app.root_learning.content import validate_registration
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result,packet_hash
from studyez_contracts.learning_links.validate import require

POLICY='frozen-reviewed-import/1'

def source_records(generation):
    metadata=generation.web_dispatch or {}
    if metadata.get('policy')not in(POLICY,'verified-main-quiz-replacement/1'):return generation.packet['sources']
    records=metadata['sourceSnapshots'];sources=generation.packet['sources']
    require(metadata['packetHash']==generation.packet['inputHash']and len(records)==len(sources),'reviewed import: changed source mapping')
    for original,snapshot in zip(sources,records):
        expected={k:v for k,v in original.items()if k not in('localPath','downloadUrl','snapshotKey')}
        require({k:v for k,v in snapshot.items()if k!='snapshotKey'}==expected
            and snapshot['snapshotKey']=='lectures/root-reviewed-import/'+original['sha256']+'/'+original['id'],
            'reviewed import: changed frozen source')
    return records

def register(db,packet,result,snapshots,*,expected_control_hash):
    """One transaction, admin-only pilot; existing active content is not replaced."""
    require(packet_hash(packet)==packet['inputHash']and result['manifest'].get('chunkedReview'),'reviewed import: missing frozen proof')
    validate_result(result,packet)
    subject,rid=packet['subject'],packet['runId'];lecture=db.get(Lecture,(subject,rid))
    require(lecture is not None,'reviewed import: missing lecture');db.refresh(lecture,with_for_update=True)
    control=db.get(RootControl,(subject,rid))
    actual=document_hash([control.revision,control.enabled,control.allowed_users]if control else None)
    doc=validate_registration(db,subject,rid,result['document']);digest=document_hash(result)
    require(doc['tasks'],'reviewed import: no prepared tasks')
    gid=document_hash({'policy':POLICY,'inputHash':packet['inputHash']})[:32]
    prior=db.get(RootGeneration,gid)
    if prior:
        require(prior.result_digest==digest and prior.result==result,'reviewed import: changed existing result')
        source_records(prior);return {'generationId':gid,'revision':doc['revision'],'reused':True}
    require(actual==expected_control_hash,'reviewed import: active content changed')
    require(control is None and not list(db.scalars(select(RootContent).where(RootContent.subject==subject,RootContent.run_id==rid))),
        'reviewed import: preserve prior versions; explicit replacement plan required')
    frozen=copy.deepcopy(packet)
    for s in frozen['sources']:s.pop('localPath',None);s.pop('downloadUrl',None)
    metadata={'policy':POLICY,'packetHash':packet['inputHash'],'sourceSnapshots':snapshots,
        'reviewProofHash':result['manifest'].get('planRepair',result['manifest']['chunkedReview'])['proofHash'],'originFailurePreserved':True}
    now=datetime.now(UTC)
    job=PrequizJob(subject=subject,run_id=rid,kind=JOB_BANK,origin=JOB_BUTTON,state=JOB_DONE,
        requested_by='runner: explicit reviewed import authorized 2026-11-07',
        message='실제 CLI 검수 완료 자료 반입 · 원래 실패/수정'+str(result['manifest']['repairRounds'])+'of3 보존 · 신규 문항 출제 없음',finished_at=now)
    db.add(job);db.flush()
    row=RootGeneration(id=gid,job_id=job.id,subject=subject,run_id=rid,user_id='runner',
        request_id='reviewed-import-'+packet['generationId'],input_digest=document_hash({'policy':POLICY,'inputHash':packet['inputHash']}),
        packet=frozen,baseline=expected_control_hash,result=result,result_digest=digest,web_dispatch=metadata)
    source_records(row)
    db.add(row);db.add(RootContent(subject=subject,run_id=rid,revision=doc['revision'],document=doc,digest=document_hash(doc),reviewed=True))
    # As with the original private pilot, administrators can inspect it; this
    # does not expand visibility to all students or create learner events.
    db.add(RootControl(subject=subject,run_id=rid,revision=doc['revision'],enabled=True,allowed_users=['runner']))
    db.add(RootEvent(user_id='runner',request_id='reviewed-import-'+gid,session_id='',subject=subject,run_id=rid,
        revision=doc['revision'],kind='publication',payload={'policy':POLICY,'generationId':gid,'privatePilot':True},
        result={'revision':doc['revision'],'inputHash':packet['inputHash'],'reviewProofHash':metadata['reviewProofHash']}))
    db.commit()
    return {'generationId':gid,'revision':doc['revision'],'reused':False,'privatePilot':True}
