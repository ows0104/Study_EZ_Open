"""Explicit import preserves sealed inputs, private scope and prior content."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import generation_v2_fixture as f,chunked_fixture as cf
from tests.root_support import setup,ADMIN,BASE
client,user,SessionLocal=setup()
from app.models import PrequizJob
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent,RootControl,RootEvent,RootSession
from app.root_learning import reviewed_import as imp
from app.routes.root_learning import revealed_answer
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import packet_hash

p=f.packet();p.update(subject='test',runId='demo');p['inputHash']=packet_hash(p);value=cf.result(p)
snapshot=[{**{k:v for k,v in s.items()if k not in('localPath','downloadUrl')},'snapshotKey':'lectures/root-reviewed-import/'+s['sha256']+'/'+s['id']}for s in p['sources']]
from app.storage import ObjectStorage
ObjectStorage().put_bytes(snapshot[0]['snapshotKey'],f.old.BODY)
with SessionLocal()as db:
    # A complete review is required, not a raw authoring candidate.
    bad=copy.deepcopy(value);bad['manifest'].pop('chunkedReview')
    try:imp.register(db,p,bad,snapshot,expected_control_hash=document_hash(None));raise AssertionError('Incomplete proof accepted')
    except ValueError:db.rollback()
    result=imp.register(db,p,value,snapshot,expected_control_hash=document_hash(None))
    row=db.get(RootGeneration,result['generationId']);assert row.result==value and packet_hash(row.packet)==p['inputHash']
    assert imp.source_records(row)==snapshot and row.web_dispatch['policy']==imp.POLICY
    assert db.get(PrequizJob,row.job_id).state=='done'
    control=db.get(RootControl,('test','demo'));assert control.allowed_users==['runner']and control.enabled
    assert db.query(RootSession).count()==0 and db.query(RootEvent).count()==1
    assert imp.register(db,p,value,snapshot,expected_control_hash=document_hash(None))['reused']
    assert db.query(RootEvent).count()==1
    other=copy.deepcopy(p);other['revision']='another-frozen-revision';other['inputHash']=packet_hash(other)
    try:
        imp.register(db,other,cf.result(other),snapshot,expected_control_hash=document_hash([control.revision,control.enabled,control.allowed_users]))
        raise AssertionError('Existing active content was replaced')
    except ValueError:db.rollback()
    content=db.get(RootContent,('test','demo',p['revision']))
    answer=revealed_answer(db,content,content.document['bank_snapshot']['questions'][0])
    assert len(answer['sourceLinks'])==1 and 'reviewNotes'in answer and 'reviewIssues'in answer
    assert client.get(answer['sourceLinks'][0]['url']).content==f.old.BODY
    row.web_dispatch={**row.web_dispatch,'sourceSnapshots':[{**snapshot[0],'sha256':'0'*64}]}
    try:imp.source_records(row);raise AssertionError('Tampered source accepted')
    except ValueError:db.rollback()
user('member')
assert client.get(BASE).status_code==404
user('admin',True)
assert client.get(BASE).status_code==200
print('reviewed import: sealed input/result, snapshot binding, completed-only, admin scope, notes and human event preservation passed')
