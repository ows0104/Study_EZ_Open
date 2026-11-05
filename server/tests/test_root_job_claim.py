"""Only an actual received explicit root request gets an out-of-block binding."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import automation_fixture as f
from tests.root_support import setup,ADMIN
client,user,SessionLocal=setup()
from app.main import app
from app.auth import CurrentUser,require_runner
from app.models import Asset,PrequizJob
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.routes.prequiz_jobs import claimed_job
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('source.txt',f.BODY)
with SessionLocal() as db:
    db.add(Asset(id='s',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='source.txt'));db.commit()
user('admin',True)
r=client.post(ADMIN+'/generation',json={'requestId':'root-claim','inputMode':'source'});assert r.status_code==200,r.text
g=r.json()['generation'];base='/api/admin/root-generation/'+g['id']
with SessionLocal() as db:
    assert 'rootGenerationId' not in claimed_job(db,db.get(PrequizJob,g['jobId']))
assert client.post('/api/admin/prequiz-jobs/claim').json()['job'] is None
assert client.post(base+'/web-dispatch',json={'promptVersion':'1.79','promptHash':'a'*64}).status_code==200
assert client.put(base+'/web-response',json=f.web_response(g['id'])).status_code==200
claimed=client.post('/api/admin/prequiz-jobs/claim?worker=w2').json()['job']
assert claimed['id']==g['jobId'] and claimed['rootGenerationId']==g['id']
assert client.post('/api/admin/prequiz-jobs/claim?worker=w2').json()['job']['rootGenerationId']==g['id']
with SessionLocal() as db:
    job=db.get(PrequizJob,g['jobId']);root=db.get(RootGeneration,g['id'])
    for field,value in [('cancel_requested',True),('origin','auto'),('kind','pre'),('state','canceled'),('state','held'),('state','done')]:
        old=getattr(job,field);setattr(job,field,value)
        assert 'rootGenerationId' not in claimed_job(db,job)
        setattr(job,field,old)
    packet=root.packet
    for patch in ({'owner':'other'},{'runId':'other'},{'generationId':'b'*32}):
        root.packet={**packet,**patch}
        assert 'rootGenerationId' not in claimed_job(db,job)
    root.packet=packet;root.result_digest='done'
    assert 'rootGenerationId' not in claimed_job(db,job)
    db.rollback()
assert claimed_job(None,None) is None
print('PASS genuine received root claim and same-worker replay bind exact ID; ordinary/automatic/canceled/unreceived/mismatched/published jobs never gain an exception')
