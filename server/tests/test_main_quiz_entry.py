"""Canonical Main Quiz routing is read-only and respects every publication guard."""
import os
from sqlalchemy import select
from tests.root_support import setup, publish, document, ADMIN

client,user,SessionLocal=setup()
from app.models import QuizBank, BankState
from app.models.root_learning import RootContent, RootControl, RootEvent, RootSession

ENTRY='/api/main-quiz/lectures/test/demo/entry'
user('a')
assert client.get(ENTRY).json()=={'mode':'legacy'}
assert client.get(ENTRY.replace('/demo/','/missing/')).status_code==404
with SessionLocal() as db:
    db.add(QuizBank(subject='test',run_id='demo',build_id='old',status='ready',bank={'preserve':'original'},validation={'pass':True},open_to_students=True))
    db.add(BankState(user_id='a',subject='test',run_id='demo',build_id='old',state={'personal-note':'keep'}));db.commit()
publish(client,user)
response=client.get(ENTRY)
assert response.status_code==200,response.text
assert response.json()['mode']=='structured'
assert response.json()['overview']['summary']['learned']==0
assert 'Secret' not in response.text and 'bank_snapshot' not in response.text
user('admin',True)
assert client.put(ADMIN+'/publication',json={'revision':'v1','reviewed':True,'enabled':True,'allowedUsers':['a']}).status_code==200
user('b');assert client.get(ENTRY).json()=={'mode':'legacy'}
user('a');assert client.get(ENTRY).json()['mode']=='structured'
user('admin',True);assert client.get(ENTRY).json()['mode']=='structured'
os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']='false'
assert client.get(ENTRY).json()=={'mode':'legacy'}
os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']='true'
with SessionLocal() as db:
    row=db.get(RootContent,('test','demo','v1'));row.reviewed=False;db.commit()
assert client.get(ENTRY).json()=={'mode':'legacy'}
with SessionLocal() as db:
    row=db.get(RootContent,('test','demo','v1'));row.reviewed=True
    db.get(RootControl,('test','demo')).enabled=False;db.commit()
assert client.get(ENTRY).json()=={'mode':'legacy'}
with SessionLocal() as db:
    assert {e.kind for e in db.scalars(select(RootEvent))}=={'publication'}
    assert len(db.scalars(select(RootEvent)).all())==2
    assert not db.scalars(select(RootSession)).all()
    assert db.get(BankState,('a','test','demo')).state=={'personal-note':'keep'}
    assert db.get(QuizBank,('test','demo')).bank=={'preserve':'original'}
print('PASS: canonical entry, draft/private/stop/feature guards, hidden answers, no events or legacy writes')
