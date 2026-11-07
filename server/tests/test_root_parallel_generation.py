"""Explicit parallel request, frozen identity and claim binding; isolated DB/storage."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import generation_v2_fixture as f
from tests.root_support import setup,ADMIN
client,user,SessionLocal=setup()
from app.models import Asset,PrequizJob,QuizBank
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.main import app
from app.auth import CurrentUser,require_runner
from app.routes.prequiz_jobs import claimed_job
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('parallel-original.txt',f.old.BODY)
with SessionLocal()as db:
    db.add(Asset(id='parallel-source',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='parallel-original.txt'))
    db.add(QuizBank(subject='test',run_id='demo',status='ready',build_id='preserved',bank=f.old.bank()));db.commit()
user('admin',True)
payload={'requestId':'parallel-1','authoring':'cli','parallelAuthoring':True,'inputMode':'source'}
r=client.post(ADMIN+'/generation',json=payload);assert r.status_code==200,r.text
job=r.json()['generation'];assert job['state']=='queued'and job['parallelAuthoring']and not job['awaitingWeb']
base='/api/admin/root-generation/'+job['id']
p=client.get(base+'/input').json()['packet'];assert p['parallelAuthoring']and p['authoring']=='cli'
assert 'webResponse'not in p
assert p['sourceAssessmentFormat']=='source-assessment/2-parallel/1'
same=client.post(ADMIN+'/generation',json={**payload,'requestId':'parallel-2'})
assert same.status_code==200 and same.json()['generation']['id']==job['id']
assert client.post(ADMIN+'/generation',json={**payload,'authoring':'web'}).status_code==422
assert client.post(ADMIN+'/generation',json={**payload,'inputMode':'provided','conceptMap':'X','points':'Y'}).status_code==422
assert client.post(ADMIN+'/generation',json={**payload,'authoring':'web','parallelAuthoring':False}).status_code==409
with SessionLocal()as db:
    row=db.get(PrequizJob,job['jobId']);row.state='running';db.commit()
    assert claimed_job(db,row)['rootGenerationId']==job['id']
    row.cancel_requested=True;db.commit();assert 'rootGenerationId'not in claimed_job(db,row)
    assert db.get(QuizBank,('test','demo')).build_id=='preserved'
user('student')
assert client.post(ADMIN+'/generation',json=payload).status_code==403
print('PASS CLI-only source mode, queued without bridge, request replay, claim identity, cancellation, old bank and admin authorization')
