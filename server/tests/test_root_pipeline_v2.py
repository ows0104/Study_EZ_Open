"""Default /2 HTTP publication and readiness use an isolated DB and synthetic A/B."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/contracts'))
import generation_v2_fixture as f
from tests.root_support import setup,ADMIN,BASE,start,view,action
client,user,SessionLocal=setup()
from app.main import app
from app.auth import CurrentUser,require_runner
from app.models import Asset,QuizBank
from app.models.root_learning import RootContent
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as c
app.dependency_overrides[require_runner]=lambda:CurrentUser(id='runner',email='',is_admin=True)
ObjectStorage().put_bytes('original.txt',f.old.BODY)
with SessionLocal()as db:
    db.add(Asset(id='v2-source',subject='test',run_id='demo',kind='notes_current',filename='synthetic.txt',object_key='original.txt'))
    db.add(QuizBank(subject='test',run_id='demo',status='ready',build_id='legacy-preserved',bank=f.old.bank()));db.commit()
user('admin',True)
from app.routes import root_generation
from app.models import PrequizJob
# A code/protocol upgrade must not create a fresh budget for the same input.
root_generation.SOURCE_FORMAT='source-assessment/1'
old_request={'requestId':'legacy-frozen','conceptMap':'Synthetic A/B','points':'Synthetic','authoring':'cli'}
old=client.post(ADMIN+'/generation',json=old_request).json()['generation']
root_generation.SOURCE_FORMAT=c.VERSION
same=client.post(ADMIN+'/generation',json={**old_request,'requestId':'after-upgrade'})
assert same.status_code==200 and same.json()['generation']['id']==old['id']
assert client.get('/api/admin/root-generation/'+old['id']+'/input').json()['packet']['sourceAssessmentFormat']=='source-assessment/1'
with SessionLocal()as db:
    job=db.get(PrequizJob,old['jobId']);job.state='canceled';job.cancel_requested=True;db.commit()
r=client.post(ADMIN+'/generation',json={'requestId':'v2-default','conceptMap':'Synthetic new A/B input','points':'Synthetic','authoring':'cli'})
assert r.status_code==200,r.text
base='/api/admin/root-generation/'+r.json()['generation']['id'];p=client.get(base+'/input').json()['packet']
assert p['sourceAssessmentFormat']==c.VERSION
value=f.result(p)
# Initial source-map faults are retained; the first map correction uses one of
# the same three rounds, with no extra source/medical review invented.
initial=copy.deepcopy(value['brief'])
initial['prerequisites']=[{'before_target':'missing','after_target':'T1','relation_id':'R1'}]
meta=value['manifest'];meta['initialBrief']=initial
meta['initialMapCorrection']={'errors':c.brief_findings(initial),'consumedRounds':1};meta['repairRounds']=1
meta['mapChangeReason']='Synthetic initial prerequisite correction'
meta['briefRevisions'][0]['reason']=meta['mapChangeReason']
normalize=next(s for s in meta['stages']if s['name']=='normalize')
normalize.update(outputHash=document_hash(initial),rawOutputHash=document_hash(initial))
author={'bank':value['document']['bank_snapshot'],'brief':value['brief'],'visual_stimuli':meta['visualStimuli'],
        'clinical_conflicts':meta['clinicalConflicts'],'map_change_reason':meta['mapChangeReason']}
generate=next(s for s in meta['stages']if s['name']=='generate')
generate.update(outputHash=document_hash(author),rawOutputHash=document_hash(author))
c.validate_result(value,p)
bad=copy.deepcopy(value);bad['manifest']['repairRounds']=0
assert client.put(base+'/result',json=bad).status_code==422
bad=copy.deepcopy(value);bad['manifest']['normalizationRecoveries']=[{'proof':{'priorLedger':None},'proofHash':'a'*64}]
assert client.put(base+'/result',json=bad).status_code==422
bad=copy.deepcopy(value);bad['sourceAudit']['assessment']['assessment']['direction_evidence'][0]['components'][0]['location']='explanation'
assert client.put(base+'/result',json=bad).status_code==422
bad=copy.deepcopy(value);bad['manifest']['clinicalConflicts']=[{'conflict_id':'forged','facts':'Other clinical input'}]
assert client.put(base+'/result',json=bad).status_code==422
# A preserved wrong verdict cannot remain a prepared task under the new policy.
value['medical']['reviews'][0]['verdict']='wrong';value['medical']['reviews'][0]['note']='Synthetic rejected answer'
next(s for s in value['manifest']['stages']if s['name']=='medical-0')['outputHash']=document_hash(value['medical'])
assert client.put(base+'/result',json=value).status_code==422
value['document']=c.make_document(value['brief'],value['document']['bank_snapshot'],value['sourceAudit'],
    revision=p['revision'],title=p['title'],exam_date=p['examDate'],medical=value['medical'])
assert [t['question_id']for t in value['document']['tasks']]==['Q2']
r=client.put(base+'/result',json=value);assert r.status_code==200,r.text
assert client.put(base+'/result',json=value).json()['reused']is True
sid=start(client,'v2-session');front=view(client,sid)
assert front['task']['question']['question_id']=='Q2'and 'Secret answer'not in str(front)
assert front['summary']['unready']==1
assert action(client,sid,'v2-answer','reveal',attempted=True).status_code==200
assert view(client,sid)['task']['answer']['answer']=='Secret answer 2'
from app.root_learning.content import front
masked=front({'question_id':'mask-test','format':'cloze','question':'Synthetic {MASKED_SECRET}',
    'answer':'MASKED_SECRET','answer_units':['MASKED_SECRET'],'options':[]})
assert 'MASKED_SECRET'not in str(masked)
with SessionLocal()as db:
    assert db.get(QuizBank,('test','demo')).build_id=='legacy-preserved'
    assert len(db.get(RootContent,('test','demo',p['revision'])).document['tasks'])==1
print('PASS default v2, retained/counted initial correction, malformed recovery and projection rejection, wrong answer excluded, original verdict/bank preserved, private question/reveal')
