import sys,copy
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import automation_fixture as f
from tests.root_support import setup,ADMIN
client,user,SessionLocal=setup()
from app.main import app
from app.auth import CurrentUser,require_runner
from app.models import Asset,TimetableEvent,Lecture,PrequizJob,JOB_BANK,JOB_BUTTON
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.routes.root_generation import registered_exam_date,generation_input,retain_duplicate,DUPLICATE_STAGE
from studyez_contracts.roots.automation import packet_hash
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('lectures/source.txt',f.BODY)
with SessionLocal() as db:
    db.add(Asset(id='s',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='lectures/source.txt'))
    assert registered_exam_date(db,db.get(Lecture,('test','demo'))) is None
    for ident,category,course,day in [('lecture','lecture','Synthetic course',3),('other','exam','Other course',4),('exam','exam','Synthetic course',7)]:
        db.add(TimetableEvent(id=ident,date=date(2026,11,day),start_time='09:00',end_time='09:50',title=course,category=category,course=course))
    db.flush();db.get(Lecture,('test','demo')).timetable_event_id='lecture';db.commit()
user('admin',True)
payload={'requestId':'source-1','inputMode':'source'}
r=client.post(ADMIN+'/generation',json=payload);assert r.status_code==200,r.text
job=r.json()['generation'];assert job['input']['inputMode']=='source' and job['input']['examDate'] is None
assert job['requestId']==payload['requestId']
assert job['input']['conceptMap']==job['input']['points']=='' and job['awaitingWeb']
assert client.post(ADMIN+'/generation',json=payload).json()['generation']['id']==job['id']
# Reopening an older UI used to turn an inferred date into an explicit date and
# accidentally create a fresh generation with a fresh repair budget.
same=client.post(ADMIN+'/generation',json={**payload,'requestId':'effective-date','examDate':'2026-11-07'})
assert same.status_code==200 and same.json()['reused'] and same.json()['generation']['id']==job['id'],same.text
assert client.post(ADMIN+'/generation',json={**payload,'inputMode':'provided'}).status_code==422
assert client.post(ADMIN+'/generation',json={**payload,'points':'supplied'}).status_code==422
assert client.post(ADMIN+'/generation',json={**payload,'authoring':'cli'}).status_code==422
base='/api/admin/root-generation/'+job['id']
assert client.get(base+'/input').status_code==409
assert client.post(base+'/web-dispatch',json={'promptVersion':'1.79','promptHash':'a'*64}).json()['send']
assert client.put(base+'/web-response',json=f.web_response(job['id'])).status_code==200
packet=client.get(base+'/input').json()['packet'];assert packet['inputMode']=='source'
assert packet['examDate']=='2026-11-07' and packet['requestedExamDate'] is None

# Preserve a duplicate already dispatched by an older client, but never queue it.
duplicate_id='d'*32
with SessionLocal() as db:
    original=db.get(RootGeneration,job['id']);duplicate_packet=copy.deepcopy(original.packet)
    duplicate_packet.update(generationId=duplicate_id,revision='auto-'+duplicate_id,requestedExamDate='2026-11-07')
    duplicate_packet['inputHash']=packet_hash(duplicate_packet)
    duplicate_job=PrequizJob(subject='test',run_id='demo',kind=JOB_BANK,origin=JOB_BUTTON,state='held',stage='ChatGPT 응답 대기')
    db.add(duplicate_job);db.flush();duplicate_job_id=duplicate_job.id
    db.add(RootGeneration(id=duplicate_id,job_id=duplicate_job.id,subject='test',run_id='demo',user_id=original.user_id,
        request_id='old-client-duplicate',input_digest='d'*64,packet=duplicate_packet,baseline=original.baseline,
        web_dispatch=copy.deepcopy(original.web_dispatch),created_at=original.created_at+timedelta(seconds=1)))
    db.commit()
duplicate_response=f.web_response(duplicate_id)
with SessionLocal() as db:
    assert retain_duplicate(db,db.get(RootGeneration,duplicate_id)).id==job['id']
    db.commit()
    # An ordinary cancellation still refuses a new response, even for this row.
    db.get(PrequizJob,duplicate_job_id).stage='';db.commit()
assert client.put('/api/admin/root-generation/'+duplicate_id+'/web-response',json=duplicate_response).status_code==409
with SessionLocal() as db:
    db.get(PrequizJob,duplicate_job_id).stage=DUPLICATE_STAGE;db.commit()
saved=client.put('/api/admin/root-generation/'+duplicate_id+'/web-response',json=duplicate_response)
assert saved.status_code==200 and saved.json()['held'] and saved.json()['generationId']==job['id'],saved.text
with SessionLocal() as db:
    duplicate=db.get(RootGeneration,duplicate_id)
    assert duplicate.web_response['raw']==duplicate_response['raw'] and duplicate.packet['supersededBy']==job['id']
    assert duplicate.packet['inputHash']==packet_hash(duplicate.packet)
    assert db.get(PrequizJob,duplicate_job_id).state=='canceled'
    assert db.get(RootGeneration,job['id']).web_response['raw']==f.web_response(job['id'])['raw']
assert client.get(ADMIN+'/generation').json()['generation']['id']==job['id']
assert client.put('/api/admin/root-generation/'+duplicate_id+'/web-response',json=duplicate_response).json()['reused']
# The normal callback also detects a previously unmarked old-client duplicate.
with SessionLocal() as db:
    original=db.get(RootGeneration,job['id']);new_packet=copy.deepcopy(duplicate_packet)
    new_packet.update(generationId='e'*32,revision='auto-'+'e'*32);new_packet['inputHash']=packet_hash(new_packet)
    late_job=PrequizJob(subject='test',run_id='demo',kind=JOB_BANK,origin=JOB_BUTTON,state='held',stage='ChatGPT 응답 대기')
    db.add(late_job);db.flush();late_job_id=late_job.id
    db.add(RootGeneration(id='e'*32,job_id=late_job.id,subject='test',run_id='demo',user_id=original.user_id,
        request_id='late-duplicate',input_digest='e'*64,packet=new_packet,baseline=original.baseline,
        web_dispatch=copy.deepcopy(original.web_dispatch),created_at=original.created_at+timedelta(seconds=2)))
    db.commit()
saved=client.put('/api/admin/root-generation/'+'e'*32+'/web-response',json=f.web_response('e'*32))
assert saved.status_code==200 and saved.json()['held'],saved.text
with SessionLocal() as db:assert db.get(PrequizJob,late_job_id).state=='canceled'
assert client.post(ADMIN+'/generation',json={**payload,'requestId':'old-client-duplicate','examDate':'2026-11-07','resume':True}).status_code==409
with SessionLocal() as db:
    # Defense in depth: even a manually requeued superseded job cannot fetch input.
    db.get(PrequizJob,duplicate_job_id).state='queued';db.commit()
assert client.get('/api/admin/root-generation/'+duplicate_id+'/input').status_code==409
with SessionLocal() as db:
    db.get(PrequizJob,duplicate_job_id).state='canceled'
    db.get(PrequizJob,job['jobId']).state='failed'
    db.get(TimetableEvent,'exam').date=date(2026,11,9);db.commit()
with patch('app.routes.root_generation.assets_now',side_effect=AssertionError('resume must reuse frozen inputs')):
    resumed=client.post(ADMIN+'/generation',json={**job['input'],'requestId':job['requestId'],'resume':True,'authoring':job['authoring'],'privatePilot':job['privatePilot']})
assert resumed.status_code==200 and resumed.json()['generation']['id']==job['id'] and resumed.json()['generation']['state']=='queued',resumed.text
assert resumed.json()['generation']['message']==''
# New source/scope/resolved exam inputs must never be merged as the same request.
for key,value in [('scope','changed scope'),('examDate','2026-11-11')]:
    changed={**packet,key:value};assert generation_input(changed)!=generation_input(packet)
changed=copy.deepcopy(packet);changed['sources'][0]['sha256']='f'*64
assert generation_input(changed)!=generation_input(packet)
assert client.put(base+'/result',json=f.result(packet)).status_code==200
with SessionLocal() as db:
    assert db.get(RootGeneration,job['id']).result['brief']['provenance']['independent_points']=='confirmed'
    row=db.get(TimetableEvent,'exam');row.date=date(2026,11,9);db.commit()
assert client.post(ADMIN+'/generation',json=payload).json()['generation']['id']==job['id']
print('PASS no-map/points one-click request, course-specific exam inference, unknown exam, request replay across timetable change, held/response binding and source-only publication')
print('PASS original date/request identity, effective-date dedupe, frozen resume across timetable change, retained duplicate MD without new rounds, canonical latest, and superseded input/resume refusal')

# Exercise the actual cloud branch of ObjectStorage, not its local-only put_bytes.
import io
from unittest.mock import patch
from botocore.exceptions import EndpointConnectionError
class CloudClient:
    def __init__(self):self.objects={'lectures/source.txt':f.BODY};self.uploads=[];self.fail=False
    def get_object(self,**kwargs):return {'Body':io.BytesIO(self.objects[kwargs['Key']])}
    def upload_fileobj(self,stream,bucket,key,ExtraArgs):
        if self.fail:raise EndpointConnectionError(endpoint_url='https://synthetic.invalid')
        body=stream.read();self.objects[key]=body;self.uploads.append((key,body,ExtraArgs))
cloud=ObjectStorage.__new__(ObjectStorage);cloud.local_root=None;cloud.bucket='synthetic-bucket';cloud.client=CloudClient()
with patch('app.routes.root_generation.ObjectStorage',return_value=cloud):
    r=client.post(ADMIN+'/generation',json={'requestId':'cloud-1','inputMode':'source','scope':'Cloud adapter check'})
    assert r.status_code==200,r.text
    uploaded=cloud.client.uploads;assert len(uploaded)==1 and uploaded[0][1]==f.BODY
    assert uploaded[0][2]=={'ContentType':'text/plain; charset=utf-8'}
    with SessionLocal() as db:
        job=db.get(PrequizJob,r.json()['generation']['jobId']);job.state='canceled';db.commit()
    cloud.client.fail=True
    r=client.post(ADMIN+'/generation',json={'requestId':'cloud-failure','inputMode':'source','scope':'Cloud failure check'})
    assert r.status_code==503 and '전송은 시작하지 않았습니다' in r.json()['detail'],r.text
    with SessionLocal() as db:
        from sqlalchemy import select
        assert db.scalars(select(RootGeneration).where(RootGeneration.request_id=='cloud-failure')).first() is None
print('PASS production-shaped R2 upload_fileobj snapshot with MIME; cloud failure gives a recoverable 503 and never queues/sends')
