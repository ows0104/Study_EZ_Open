"""Synthetic replacement publication: real contracts, no production credentials."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import generation_v2_fixture as f,task_supplement_fixture as sf
from tests.root_support import setup,BASE,ADMIN
client,user,SessionLocal=setup()
from app.models import PrequizJob,JOB_BANK,JOB_BUTTON,JOB_DONE
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent,RootControl,RootEvent,RootSession
from app.root_learning import replacement_import as imp,reviewed_import
from app.routes.root_learning import revealed_answer
from app.routes.root_generation import public_job
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

base,value=sf.result();value['runId']='b'*32
packet=f.packet();subject,rid=packet['subject'],packet['runId'];doc=base['document'];gid='a'*32
snapshots=[{**{k:v for k,v in s.items()if k not in('localPath','downloadUrl','snapshotKey')},
    'snapshotKey':'lectures/root-reviewed-import/'+s['sha256']+'/'+s['id']}for s in packet['sources']]
from automation_fixture import BODY
ObjectStorage().put_bytes(snapshots[0]['snapshotKey'],BODY)
with SessionLocal()as db:
    job=PrequizJob(subject=subject,run_id=rid,kind=JOB_BANK,origin=JOB_BUTTON,state=JOB_DONE,requested_by='synthetic')
    db.add(job);db.flush()
    parent=RootGeneration(id=gid,job_id=job.id,subject=subject,run_id=rid,user_id='runner',request_id='synthetic-parent',input_digest='a'*64,
        packet=packet,baseline=document_hash(None),result=base,result_digest=document_hash(base),
        web_dispatch={'policy':reviewed_import.POLICY,'packetHash':packet['inputHash'],'sourceSnapshots':snapshots})
    db.add(parent);db.add(RootContent(subject=subject,run_id=rid,revision=doc['revision'],document=doc,digest=document_hash(doc),reviewed=True))
    db.add(RootControl(subject=subject,run_id=rid,revision=doc['revision'],enabled=True,allowed_users=['runner']));db.commit()
    oldbytes=document_hash(parent.result);control=db.get(RootControl,(subject,rid));baseline=document_hash([control.revision,control.enabled,control.allowed_users])
    # A failed/partial review must not alter the active version.
    bad=copy.deepcopy(value);bad['ready']=False
    try:imp.register(db,gid,bad,expected_control_hash=baseline);raise AssertionError('Held review accepted')
    except ValueError:db.rollback()
    try:imp.register(db,gid,value,expected_control_hash='0'*64);raise AssertionError('Stale control accepted')
    except ValueError:db.rollback()
    result=imp.register(db,gid,value,expected_control_hash=baseline)
    assert result['tasks']==2 and result['privatePilot']
    assert db.get(RootContent,(subject,rid,doc['revision'])).document==doc
    assert document_hash(db.get(RootGeneration,gid).result)==oldbytes
    assert db.get(RootControl,(subject,rid)).allowed_users==['runner']
    assert db.query(RootEvent).count()==1 and db.query(RootSession).count()==0
    row=db.get(RootGeneration,value['runId']);shown=public_job(db,row)
    assert shown['published']and shown['report']['taskCount']==2 and shown['report']['repairRounds']==0
    content=db.get(RootContent,(subject,rid,value['document']['revision']))
    answer=revealed_answer(db,content,content.document['bank_snapshot']['questions'][0])
    assert answer['reviewNotes']==[]and answer['reviewIssues']==[]
    assert client.get(answer['sourceLinks'][0]['url']).content==BODY
    assert imp.register(db,gid,value,expected_control_hash=baseline)['reused']
    assert db.query(RootEvent).count()==1
    changed=copy.deepcopy(value);changed['document']['title']='tamper'
    try:imp.register(db,gid,changed,expected_control_hash=baseline);raise AssertionError('Changed replacement accepted')
    except ValueError:db.rollback()
user('member')
assert client.get(BASE).status_code==404
user('admin',True)
assert client.get(BASE).status_code==200
from app.root_learning.content import learner_scope
screen=copy.deepcopy(value['document'])
screen['review']['scope']['limitations']=['Synthetic low-resolution source photo remains limited','Python checker permission denied',
    '새 외부 문헌 검색·독립 의료 검수는 시행하지 않았다.']
assert learner_scope(screen)['limitations']==['Synthetic low-resolution source photo remains limited']
assert len(screen['review']['scope']['limitations'])==3
print('replacement: independent proofs, stale/held rejection, old content/event preservation, private scope, source/notes/report readback passed')
