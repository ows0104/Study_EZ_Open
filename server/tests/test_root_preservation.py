import copy
from tests.root_support import setup,publish,start,view,action,document,BASE,ADMIN
client,user,SessionLocal=setup()
from app.models import QuizBank,BankState,BankPersonalEdit
from app.models.root_learning import RootEvent,RootContent
doc=document();doc.update(bank_source='quizbank',bank_build_id='b1')
with SessionLocal() as db:
    db.add(QuizBank(subject='test',run_id='demo',build_id='b1',status='ready',bank=copy.deepcopy(doc['bank_snapshot']),validation={'pass':True},open_to_students=True))
    db.add(BankState(user_id='a',subject='test',run_id='demo',build_id='b1',state={'suspended_question_ids':[],'personal-note':'keep'}));db.commit()
publish(client,user,doc);sid=start(client)
assert action(client,sid,'attempt','reveal',attempted=True,response='Preserve this').status_code==200
assert view(client,sid)['summary']['learned']==1
with SessionLocal() as db:
    row=db.get(QuizBank,('test','demo'));assert row.bank==doc['bank_snapshot'] and row.validation=={'pass':True}
    assert db.get(BankState,('a','test','demo')).state=={'suspended_question_ids':[],'personal-note':'keep'}
    q=doc['bank_snapshot']['questions'][0]
    db.add(BankPersonalEdit(user_id='a',subject='test',run_id='demo',question_id='Q1',original=q,question=q['question'],answer='Private correction',comment='keep'));db.commit()
assert view(client,sid)['task'] is None and view(client,sid)['blocked']
assert action(client,sid,'blocked','rate',grade='independent').status_code==409
assert action(client,sid,'skip','skip').status_code==200
with SessionLocal() as db:
    assert db.get(BankPersonalEdit,('a','test','demo','Q1')).answer=='Private correction'
    assert db.get(BankState,('a','test','demo')).state['personal-note']=='keep'
    row=db.get(QuizBank,('test','demo'));row.open_to_students=False;db.commit()
assert view(client,sid)['task'] is None
with SessionLocal() as db:
    row=db.get(QuizBank,('test','demo'));row.open_to_students=True;db.commit()
new=copy.deepcopy(doc);new['revision']='v2'
publish(client,user,new)
assert client.get(BASE).json()['summary']['learned']==0
assert client.get('/api/root-learning/sessions/'+sid).status_code==409
linked=copy.deepcopy(doc);linked.update(revision='v3',equivalences=[{'revision':'v1','from_direction':'D1','to_direction':'D1','reason':'Reviewed identical source and question'}])
publish(client,user,linked)
assert client.get(BASE).json()['summary']['learned']==1
changed=copy.deepcopy(linked);changed['revision']='v4';changed['review']['targets'][0]['directions'][0]['answer_scope']='Different scope'
user('admin',True);assert client.post(ADMIN,json=changed).status_code==422
with SessionLocal() as db:
    assert db.get(RootContent,('test','demo','v1')).document==doc
    assert db.get(RootEvent,('a','attempt')).payload['response']=='Preserve this'
    assert db.get(QuizBank,('test','demo')).bank==doc['bank_snapshot']
print('PASS: original bank/state/private corrections retained; unavailable tasks block grading; old events/content preserved; same IDs never auto-transfer; reviewed identical mapping only')
