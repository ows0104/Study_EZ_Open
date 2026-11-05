"""Real isolated DB/storage/API; synthetic nonmedical authoring artifacts."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import automation_fixture as f
from tests.root_support import setup,publish,start,view,action,BASE,ADMIN
client,user,SessionLocal=setup()
# Historical /1 publication, including its preserved non-ok task behavior.
# New requests/default /2 readiness gates are covered by test_root_pipeline_v2.
from app.routes import root_generation
root_generation.SOURCE_FORMAT='source-assessment/1'
from app.main import app
from app.auth import require_runner,CurrentUser
from app.storage import ObjectStorage
from app.models import Asset,QuizBank,BankState,BankPersonalEdit,PrequizJob,Profile
from app.models.root_learning import RootContent,RootEvent,RootControl
from app.models.root_generation import RootGeneration
from studyez_contracts.roots import document_hash
from sqlalchemy import select,func
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
GEN=ADMIN+'/generation'

with SessionLocal() as db:
    db.add(Asset(id='asset',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='original.txt',size_bytes=len(f.BODY)))
    db.add(QuizBank(subject='test',run_id='demo',build_id='old',status='ready',bank=f.bank(),validation={'pass':True},open_to_students=True))
    db.add(BankState(user_id='a',subject='test',run_id='demo',build_id='old',state={'excluded_question_decisions':{'Q1':'excluded'},'private-note':'keep'}))
    db.add(BankPersonalEdit(user_id='a',subject='test',run_id='demo',question_id='Q1',original=f.bank()['questions'][0],question='private question',answer='private answer',comment='keep'))
    db.add(Profile(id='admin',email='admin@example.com',is_admin=True));db.commit()
ObjectStorage().put_bytes('original.txt',f.BODY)
publish(client,user);old_sid=start(client)
assert action(client,old_sid,'original-attempt','reveal',attempted=True,response='Private old response').status_code==200
user('admin',True)

def request(n,**extra):
    payload={'requestId':'request-'+str(n),'conceptMap':f'A -> B {n}','points':'Synthetic point','scope':'Synthetic only','authoring':'cli',**extra}
    response=client.post(GEN,json=payload);assert response.status_code==200,response.text
    return response.json()['generation'],payload

def packet(job):
    response=client.get('/api/admin/root-generation/'+job['id']+'/input');assert response.status_code==200,response.text
    return response.json()['packet']

def post(job,result):return client.put('/api/admin/root-generation/'+job['id']+'/result',json=result)

def terminate(job,state='failed',cancel=False):
    with SessionLocal() as db:
        row=db.get(PrequizJob,job['jobId']);row.state=state;row.cancel_requested=cancel;db.commit()

job,payload=request(1)
assert client.post(GEN,json=payload).json()['generation']['id']==job['id']
assert client.post(GEN,json={**payload,'points':'changed'}).status_code==409
assert client.post(GEN,json={**payload,'requestId':'duplicate'}).json()['generation']['id']==job['id']
assert client.post(GEN,json={**payload,'requestId':'audience-change','privatePilot':False}).status_code==409
assert client.put('/api/admin/lectures/test/demo/bank-response',json={'raw':'x'*210+'\nSTUDYEZ_BANK_COMPLETE','source':'manual'}).status_code==409
response=client.get('/api/admin/lectures/test/demo/bank-response');assert response.status_code==200,response.text
assert response.json()['connectionGeneration']==job['id']
with SessionLocal() as db:assert db.get(QuizBank,('test','demo')).status=='ready'
frozen=packet(job)
assert client.get(frozen['sources'][0]['downloadUrl']).content==f.BODY
result=f.result(frozen)
bad=copy.deepcopy(result);bad['medical']['reviews'].pop()
assert post(job,bad).status_code==422
with SessionLocal() as db:assert db.get(RootContent,('test','demo',frozen['revision'])) is None
result['medical']['reviews'][0]['verdict']='wrong'
result['medical']['reviews'][0]['note']='Preserved unresolved synthetic issue'
next(s for s in result['manifest']['stages'] if s['name']=='medical-0')['outputHash']=document_hash(result['medical'])
assert post(job,result).status_code==200
assert post(job,result).json()['reused'] is True
assert post(job,bad).status_code==409
with SessionLocal() as db:
    assert db.get(PrequizJob,job['jobId']).state=='done'
    assert db.get(RootContent,('test','demo','v1'))
    assert db.get(RootEvent,('a','original-attempt')).payload['response']=='Private old response'
    assert db.get(BankState,('a','test','demo')).state['private-note']=='keep'
    assert db.get(BankPersonalEdit,('a','test','demo','Q1')).answer=='private answer'
    assert db.get(QuizBank,('test','demo')).bank==f.bank()
    assert 'downloadUrl' not in str(db.get(RootGeneration,job['id']).packet)
user('a')
assert client.get(BASE).status_code==404
assert client.get(GEN).status_code==403
assert client.post(GEN,json={**payload,'requestId':'student'}).status_code==403
user('admin',True)
sid=start(client,'new-start');before=view(client,sid)
assert 'reviewNotes' not in str(before) and 'sourceLinks' not in str(before) and 'Secret answer' not in str(before)
assert action(client,sid,'new-reveal','reveal',attempted=True,response='Synthetic recall').status_code==200
answer=view(client,sid)['task']['answer']
assert answer['reviewNotes'][0]['verdict']=='wrong'
assert 'Preserved unresolved' in answer['reviewNotes'][0]['note']
assert client.get(answer['sourceLinks'][0]['url']).content==f.BODY
assert client.get('/api/root-learning/sessions/'+sid+'/map').status_code==409
assert action(client,sid,'map','map').status_code==200
mapped=client.get('/api/root-learning/sessions/'+sid+'/map').json()
assert len(mapped['points'])==1 and mapped['coverage'][0]['status']=='covered'
usage=client.get('/api/admin/usage/admin');assert usage.status_code==200,usage.text
activities=usage.json()['lectures'][0]['activities']
assert activities['root_generation']['count']==1 and activities['root_generated']['count']==1
assert 'A -> B 1' not in usage.text and 'Synthetic recall' not in usage.text
print('PASS: queue, immutable source, duplicate requests/results, standalone publication, preserved history/private edits, cohort, reveal notes, map points and usage')

# Source changes, control changes, cancellation and interrupted job reuse never publish.
job,payload=request(2);frozen=packet(job);result=f.result(frozen)
ObjectStorage().put_bytes('original.txt',b'changed source')
assert client.get(frozen['sources'][0]['downloadUrl']).content==f.BODY
assert post(job,result).status_code==409
ObjectStorage().put_bytes('original.txt',f.BODY);terminate(job)
resumed=client.post(GEN,json={**payload,'requestId':'resume-2','resume':True})
assert resumed.json()['generation']['id']==job['id'] and resumed.json()['generation']['state']=='queued'
terminate(job)
resumed=client.post(GEN,json={**payload,'resume':True})
assert resumed.json()['generation']['id']==job['id'] and resumed.json()['generation']['state']=='queued'
terminate(job)
job,payload=request(3);result=f.result(packet(job))
with SessionLocal() as db:
    control=db.get(RootControl,('test','demo'));control.allowed_users=['another'];db.commit()
assert post(job,result).status_code==409;terminate(job)
job,payload=request(4);result=f.result(packet(job));terminate(job,'running',True)
assert post(job,result).status_code==409
assert client.get('/api/admin/root-generation/'+job['id']+'/input').status_code==409
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(RootContent))==2
    assert db.scalar(select(func.count()).select_from(RootEvent).where(RootEvent.kind=='generated'))==1
print('PASS: changed source/control and cancel conflicts leave prior active content unchanged; resume reuses same generation and budget')
