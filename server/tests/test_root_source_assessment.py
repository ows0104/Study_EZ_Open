"""Synthetic HTTP producer/consumer agreement for compiled source judgments."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import automation_fixture as f
from tests.root_support import setup,ADMIN
client,user,SessionLocal=setup()
from app.routes import root_generation
root_generation.SOURCE_FORMAT='source-assessment/1'
from app.main import app
from app.auth import CurrentUser,require_runner
from app.models import Asset,QuizBank
from app.storage import ObjectStorage
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('lectures/source.txt',f.BODY)
with SessionLocal()as db:
    db.add(Asset(id='s',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='lectures/source.txt'))
    db.add(QuizBank(subject='test',run_id='demo',status='ready',build_id='preserved',bank=f.bank()));db.commit()
user('admin',True)
r=client.post(ADMIN+'/generation',json={'requestId':'compiled','conceptMap':'Synthetic A/B','points':'Synthetic','authoring':'cli'})
assert r.status_code==200,r.text
base='/api/admin/root-generation/'+r.json()['generation']['id']
packet=client.get(base+'/input').json()['packet'];value=f.assessed_result(packet)
assert packet['sourceAssessmentFormat']=='source-assessment/1'
bad=copy.deepcopy(value);bad['manifest']['sourceAssessment']['assessment']['question_reviews'][0]['verdict']='wrong'
assert client.put(base+'/result',json=bad).status_code==422
bad=copy.deepcopy(value);del bad['manifest']['sourceAssessment']
for row in bad['manifest']['stages']:
    row.pop('sourceFormat',None);row.pop('rawOutputHash',None)
assert client.put(base+'/result',json=bad).status_code==422
bad=copy.deepcopy(value);del bad['manifest']['sourceAssessment']
assert client.put(base+'/result',json=bad).status_code==422
assert client.put(base+'/result',json=value).status_code==200
with SessionLocal()as db:assert db.get(QuizBank,('test','demo')).build_id=='preserved'
print('PASS compiled assessment HTTP publication in isolated fixture, tamper/missing evidence rejection, preserved legacy bank')
