import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import automation_fixture as f
from tests.root_support import setup,ADMIN
client,user,SessionLocal=setup()
from app.models import Asset,PrequizJob,QuizBank
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.main import app
from app.auth import CurrentUser,require_runner
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('lectures/original.txt',f.BODY)
with SessionLocal() as db:
    db.add(Asset(id='s',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='lectures/original.txt'))
    db.add(QuizBank(subject='test',run_id='demo',bank=f.bank(),build_id='old',status='ready',share_url='https://chatgpt.com/share/old'));db.commit()
user('admin',True)
payload={'requestId':'web-1','conceptMap':'Synthetic A/B','points':'Synthetic point'}
r=client.post(ADMIN+'/generation',json=payload);assert r.status_code==200,r.text
job=r.json()['generation'];assert job['awaitingWeb'] and job['state']=='held'
base='/api/admin/root-generation/'+job['id']
assert client.get(base+'/input').status_code==409
assert client.get(base+'/web-input').status_code==200
user('another',True);assert client.get(base+'/web-input').status_code==404
user('admin',True)
dispatch={'promptVersion':'1.79','promptHash':'a'*64}
assert client.post(base+'/web-dispatch',json=dispatch).json()['send']
assert not client.post(base+'/web-dispatch',json=dispatch).json()['send']
assert client.post(base+'/web-dispatch',json={**dispatch,'promptHash':'b'*64}).status_code==409
assert client.put('/api/admin/lectures/test/demo/bank/links',json={'shareUrl':'https://chatgpt.com/share/new'}).status_code==200
response=f.web_response(job['id'])
wrong=copy.deepcopy(response);wrong['responseFile']['sha256']='f'*64
assert client.put(base+'/web-response',json=wrong).status_code==422
wrong=f.web_response('f'*32)
assert client.put(base+'/web-response',json=wrong).status_code==422
assert client.put(base+'/web-response',json=response).status_code==200
assert client.put(base+'/web-response',json=response).json()['reused']
with SessionLocal() as db:
    assert db.get(QuizBank,('test','demo')).share_url=='https://chatgpt.com/share/old'
    assert db.get(PrequizJob,job['jobId']).state=='queued'
    assert db.get(RootGeneration,job['id']).web_response['raw']==response['raw']
packet=client.get(base+'/input').json()['packet']
assert packet['webResponse']==response
result=f.result(packet)
assert client.put(base+'/result',json=result).status_code==200
print('PASS web request held, owned input, single dispatch, file/header/hash binding, queued after real MD, replay, old bank links preserved and publication')
