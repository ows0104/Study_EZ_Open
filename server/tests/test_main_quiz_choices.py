"""Visible comparison is the task; recall choices are help. Old retries stay identical."""
from tests.root_support import setup,publish,start,view,action,document
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash

client,user,SessionLocal=setup()
from app.root_learning.content import front,answer
for kind,inputs,secret in [
    ('matching',{'matching_left':['Left'],'matching_right':['Right']},{'answer_pairs':[{'left':'Left','right':'Right'}]}),
    ('sequence',{'sequence_items':['First','Second']},{'correct_order':['Second','First']})]:
    q={**document()['bank_snapshot']['questions'][0],'format':kind,**inputs,**secret}
    shown=front(q)
    assert all(shown[k]==v for k,v in inputs.items())
    assert not set(secret)&set(shown)
    revealed=answer(q)
    assert revealed['answerPairs' if kind=='matching' else 'correctOrder']==next(iter(secret.values()))
doc=document()
for q in doc['bank_snapshot']['questions'][:2]:
    q.update(format='mcq',options=[{'id':'A','text':'Choice A'},{'id':'B','text':'Choice B'}],correct_option_ids=['A'],
             mcq_mode='comparison' if q['question_id']=='Q1' else 'recall_first')
doc['review']['bank_sha256']=document_hash(doc['bank_snapshot'])
for m,q in zip(doc['review']['mappings'],doc['bank_snapshot']['questions']):m['question_sha256']=question_hash(q,doc['bank_snapshot'])
publish(client,user,doc)
sid=start(client)
v=view(client,sid)
assert v['task']['question']['mcq_mode']=='comparison' and 'correct_option_ids' not in str(v)
assert action(client,sid,'compare','reveal',attempted=True,choicesShown=True).status_code==200
assert not view(client,sid)['task']['helped']
assert action(client,sid,'compare-grade','rate',grade='independent').status_code==200
assert view(client,sid)['task']['question']['mcq_mode']=='recall_first'
assert action(client,sid,'recall','reveal',attempted=True,choicesShown=False).status_code==200
assert not view(client,sid)['task']['helped']
assert action(client,sid,'recall-grade','rate',grade='independent').status_code==200

user('shown');sid=start(client,'shown')
action(client,sid,'first','reveal',attempted=True,choicesShown=True)
action(client,sid,'first-grade','rate',grade='independent')
assert action(client,sid,'second','reveal',attempted=True,choicesShown=True).status_code==200
assert view(client,sid)['task']['helped']
assert action(client,sid,'second-grade','rate',grade='independent').status_code==422

user('legacy');sid=start(client,'old-client')
request={'requestId':'old-reveal','version':0,'kind':'reveal','attempted':True}
url='/api/root-learning/sessions/'+sid+'/events'
r=client.post(url,json=request);assert r.status_code==200,r.text
assert view(client,sid)['task']['helped']  # Old clients conservatively keep their previous behavior.
assert client.post(url,json=request).json()==r.json()
assert client.post(url,json={**request,'choicesShown':None}).json()==r.json()
assert client.post(url,json={**request,'choicesShown':True}).status_code==409

user('map');sid=start(client,'map')
action(client,sid,'map-open','map')
action(client,sid,'map-reveal','reveal',attempted=True,choicesShown=False)
assert view(client,sid)['task']['helped']
assert action(client,sid,'map-grade','rate',grade='independent').status_code==422
print('PASS: comparison/hidden/shown recall choices, map help, optional field old retries and request conflict')
