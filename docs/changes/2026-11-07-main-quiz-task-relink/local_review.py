"""Real replacement in a fresh isolated app; only a technical test learner."""
import argparse,json,os,sys
from datetime import date,datetime,UTC
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'server'),str(ROOT)]
OUT=ROOT/'runs/_replacement/261104_02-v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);a=p.parse_args()
os.environ['PUBLIC_API_BASE_URL']='http://127.0.0.1:'+str(a.port)
checked=read(OUT/'checked-for-publication.json');value=read(OUT/checked.get('resultFile','result.json'));base=read(OUT/'parent-result.json');packet=read(OUT/'packet.json')
assert checked['verified']and value['ready']
from tests.root_support import setup
client,user,SessionLocal=setup()
assert os.environ['ENVIRONMENT']=='local-test'and os.environ['DATABASE_URL'].startswith('sqlite:')
from app.main import app
from app.models import Lecture,Profile,PrequizJob,JOB_BANK,JOB_BUTTON,JOB_DONE
from app.models.root_learning import RootContent,RootControl
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.root_learning import reviewed_import,replacement_import
from app.routes import root_learning
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import packet_hash
import uvicorn
root_learning.now=lambda:datetime.now(UTC)
with SessionLocal()as db:
    db.add(Lecture(subject=packet['subject'],run_id=packet['runId'],uid='technical-new-pathology-review',date=date(2026,11,4),
        slot=2,slot_end=2,start_time='10:00',title=packet['title'],professors=['김지은'],author='박준원',version=2))
    db.add(Profile(id='local-pilot',email='local-pilot@example.invalid',is_admin=True));db.commit()
    snapshots=[]
    for s in packet['sources']:
        key='lectures/root-reviewed-import/'+s['sha256']+'/'+s['id'];body=Path(s['localPath']).read_bytes()
        import hashlib
        assert hashlib.sha256(body).hexdigest()==s['sha256']
        ObjectStorage().put_bytes(key,body)
        snapshots.append({**{k:v for k,v in s.items()if k not in('localPath','downloadUrl','snapshotKey')},'snapshotKey':key})
    frozen=json.loads(json.dumps(packet))
    for s in frozen['sources']:s.pop('localPath',None);s.pop('downloadUrl',None)
    assert packet_hash(frozen)==packet['inputHash']
    parent_id='382c53909ad28529243208029e82bbf1'
    job=PrequizJob(subject=packet['subject'],run_id=packet['runId'],kind=JOB_BANK,origin=JOB_BUTTON,state=JOB_DONE,requested_by='technical fixture of actual historical generation')
    db.add(job);db.flush()
    db.add(RootGeneration(id=parent_id,job_id=job.id,subject=packet['subject'],run_id=packet['runId'],user_id='runner',request_id='technical-actual-parent',
        input_digest=document_hash({'technicalActualParent':packet['inputHash']}),packet=frozen,baseline=document_hash(None),result=base,result_digest=document_hash(base),
        web_dispatch={'policy':reviewed_import.POLICY,'packetHash':packet['inputHash'],'sourceSnapshots':snapshots}))
    doc=base['document']
    db.add(RootContent(subject=packet['subject'],run_id=packet['runId'],revision=doc['revision'],document=doc,digest=document_hash(doc),reviewed=True))
    db.add(RootControl(subject=packet['subject'],run_id=packet['runId'],revision=doc['revision'],enabled=True,allowed_users=['runner']));db.commit()
    registered=replacement_import.register(db,parent_id,value,expected_control_hash=document_hash([doc['revision'],True,['runner']]))
user('local-pilot',True)
(OUT/'local-review.json').write_text(json.dumps({'api':'http://127.0.0.1:'+str(a.port),'technicalUser':'local-pilot',
    'database':os.environ['DATABASE_URL'],'registration':registered,'productionWrites':0},ensure_ascii=False,indent=2),encoding='utf-8')
uvicorn.run(app,host='127.0.0.1',port=a.port,log_level='warning')
