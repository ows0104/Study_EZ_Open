"""Explicit administrator replacement, independently reviewed; no learner writes."""
import copy
import re
from datetime import datetime, UTC
from sqlalchemy import select
from app.models import Lecture, PrequizJob, JOB_BANK, JOB_BUTTON, JOB_DONE
from app.models.root_learning import RootContent, RootControl, RootEvent
from app.models.root_generation import RootGeneration
from app.root_learning.content import validate_registration
from studyez_contracts.roots import document_hash, task_supplement as contract
from studyez_contracts.roots.automation import packet_hash
from studyez_contracts.learning_links.validate import require

POLICY=contract.POLICY


def report(result):
    last=result['rounds'][-1];source=last['sourceReview'];medical=last['medicalReview']
    notes=[]
    for r in source['reviews']:
        verdict=max((r['source_verdict'],r['goal_verdict'],r['importance_verdict']),key=('ok','doubt','wrong').index)
        if verdict!='ok':notes.append({'source':'원본·회상목표 검수','question_id':r['question_id'],'verdict':verdict,'note':r['reason'],'suggested_answer':''})
    notes +=[{'source':'독립 정답 검수',**r}for r in medical['reviews']if r['verdict']!='ok']
    return {'repairRounds':result['repairRounds'],'taskCount':len(result['document']['tasks']),
        'targetCount':len(result['document']['review']['targets']),'issues':source['coverage_findings'],
        'questionNotes':notes,'coverage':result['document']['review']['coverage']}


def register(db,parent_id,value,*,expected_control_hash):
    parent=db.get(RootGeneration,parent_id)
    require(parent and parent.result and parent.result_digest==document_hash(parent.result),'replacement: missing/changed historical generation')
    contract.validate(parent.result,value);require(value['ready'],'replacement: unresolved review cannot be published')
    gid=value['runId'];require(type(gid)is str and re.fullmatch('[0-9a-f]{32}',gid),'replacement: invalid new generation ID')
    digest=document_hash(value);prior=db.get(RootGeneration,gid)
    if prior:
        require(prior.result_digest==digest and prior.result==value,'replacement: changed previous replacement')
        return {'generationId':gid,'revision':value['document']['revision'],'reused':True}
    subject,rid=parent.subject,parent.run_id;lecture=db.get(Lecture,(subject,rid));require(lecture is not None,'replacement: lecture missing')
    db.refresh(lecture,with_for_update=True)
    control=db.get(RootControl,(subject,rid))
    require(control is not None and document_hash([control.revision,control.enabled,control.allowed_users])==expected_control_hash
        and control.revision==parent.result['document']['revision'],'replacement: active content/visibility changed')
    old=db.get(RootContent,(subject,rid,control.revision))
    require(old and old.reviewed and old.document==parent.result['document']and old.digest==document_hash(old.document),'replacement: changed current parent document')
    doc=validate_registration(db,subject,rid,value['document'])
    require(not db.get(RootContent,(subject,rid,doc['revision'])),'replacement: preserve existing version')
    from .reviewed_import import source_records
    snapshots=copy.deepcopy(source_records(parent));packet=copy.deepcopy(parent.packet)
    packet.update(generationId=gid,revision=doc['revision'],owner='runner')
    packet['scope']=packet.get('scope','')+'\n이번 대체판: 문항별 회상 범위와 실제 원본 그림을 확인한 새 문제은행.'
    packet['inputHash']=packet_hash(packet)
    job=PrequizJob(subject=subject,run_id=rid,kind=JOB_BANK,origin=JOB_BUTTON,state=JOB_DONE,requested_by='runner: explicit replacement authorized 2026-11-07',
        message='새 Main Quiz 실제 CLI 작성·독립 검수 완료 · '+str(len(doc['tasks']))+'과제 · 새 수정'+str(value['repairRounds'])+'of3',finished_at=datetime.now(UTC))
    db.add(job);db.flush()
    row=RootGeneration(id=gid,job_id=job.id,subject=subject,run_id=rid,user_id='runner',request_id='replacement-'+gid,
        input_digest=document_hash({'policy':POLICY,'runId':gid}),packet=packet,baseline=expected_control_hash,result=value,result_digest=digest,
        web_dispatch={'policy':POLICY,'parentGenerationId':parent_id,'parentResultHash':value['parentResultHash'],
            'packetHash':packet['inputHash'],'sourceSnapshots':snapshots,'newRun':True,'historicalRepairRounds':value['historicalRepairRounds']})
    source_records(row)
    db.add(row);db.add(RootContent(subject=subject,run_id=rid,revision=doc['revision'],document=doc,digest=document_hash(doc),reviewed=True))
    # Existing content/events/sessions stay archived; visibility never expands here.
    control.revision=doc['revision']
    db.add(RootEvent(user_id='runner',request_id='replacement-published-'+gid,session_id='',subject=subject,run_id=rid,revision=doc['revision'],kind='publication',
        payload={'policy':POLICY,'generationId':gid,'parentGenerationId':parent_id},result={'revision':doc['revision'],'newRepairRounds':value['repairRounds']}))
    db.commit()
    return {'generationId':gid,'revision':doc['revision'],'reused':False,'privatePilot':bool(control.allowed_users),'tasks':len(doc['tasks'])}
