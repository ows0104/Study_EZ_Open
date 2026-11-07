"""Uncertain facts stay held; uncertain priority is not a positive importance claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
from quiz_curation_fixture import fixture
import generation_v2_fixture as f
from tests.root_support import setup,BASE
client,user,SessionLocal=setup()
from app.models import PrequizJob,JOB_BANK,JOB_BUTTON,JOB_DONE
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent,RootControl,RootEvent,RootSession
from app.root_learning import replacement_import as imp,reviewed_import
from app.routes.root_learning import revealed_answer
from app.routes.root_generation import public_job
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash
from automation_fixture import BODY

base,value=fixture();packet=f.packet();subject,rid=packet['subject'],packet['runId'];doc=base['document'];gid='a'*32
snapshots=[{**{k:v for k,v in s.items()if k not in('localPath','downloadUrl','snapshotKey')},
    'snapshotKey':'lectures/root-reviewed-import/'+s['sha256']+'/'+s['id']}for s in packet['sources']]
ObjectStorage().put_bytes(snapshots[0]['snapshotKey'],BODY)
with SessionLocal()as db:
    job=PrequizJob(subject=subject,run_id=rid,kind=JOB_BANK,origin=JOB_BUTTON,state=JOB_DONE,requested_by='synthetic');db.add(job);db.flush()
    db.add(RootGeneration(id=gid,job_id=job.id,subject=subject,run_id=rid,user_id='runner',request_id='synthetic-curation-parent',input_digest='a'*64,
        packet=packet,baseline=document_hash(None),result=base,result_digest=document_hash(base),
        web_dispatch={'policy':reviewed_import.POLICY,'packetHash':packet['inputHash'],'sourceSnapshots':snapshots}))
    db.add(RootContent(subject=subject,run_id=rid,revision=doc['revision'],document=doc,digest=document_hash(doc),reviewed=True))
    db.add(RootControl(subject=subject,run_id=rid,revision=doc['revision'],enabled=True,allowed_users=['runner']));db.commit()
    result=imp.register(db,gid,value,expected_control_hash=document_hash([doc['revision'],True,['runner']]))
    assert result['tasks']==1 and db.query(RootEvent).count()==1 and db.query(RootSession).count()==0
    row=db.get(RootGeneration,value['runId']);assert row.result['candidate']['ready']is False
    shown=public_job(db,row);assert shown['report']['taskCount']==1
    notes=shown['report']['questionNotes'];assert any(n['source']=='중요도 근거 미확정'and n['question_id']=='Q1'for n in notes)
    content=db.get(RootContent,(subject,rid,value['document']['revision']));assert [q['question_id']for q in content.document['bank_snapshot']['questions']]==['Q1']
    answer=revealed_answer(db,content,content.document['bank_snapshot']['questions'][0])
    assert any(n['source']=='중요도 근거 미확정'for n in answer['reviewNotes'])
    assert client.get(answer['sourceLinks'][0]['url']).content==BODY
user('admin',True)
overview=client.get(BASE);assert overview.status_code==200,overview.text
assert overview.json()['summary']['total']==1 and overview.json()['summary']['unready']==0
assert overview.json()['summary']['importantUnseen']==0
started=client.post(BASE+'/sessions',json={'requestId':'synthetic-curated-start'});assert started.status_code==200,started.text
session=client.get('/api/root-learning/sessions/'+started.json()['sessionId']);assert session.status_code==200
assert session.json()['count']==1 and session.json()['task']['question']['question_id']=='Q1'
print('curation: held facts excluded verbatim, unverified priority neutral, one-question/one-task, original scope and technical session readback passed')
