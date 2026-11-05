import copy
import os
from datetime import timedelta
from tests.root_support import setup,publish,start,view,action,document,BASE,ADMIN,NOW
client,user,SessionLocal=setup()
user('a')
assert client.get(BASE).status_code==404
assert client.post(ADMIN,json=document()).status_code==403
user('admin',True)
assert client.post(ADMIN,json=document()).status_code==200
assert client.post(ADMIN,json={**document(),'title':'changed'}).status_code==409
assert client.put(ADMIN+'/publication',json={'revision':'v1','reviewed':False,'enabled':True}).status_code==409
publish(client,user)
sid=start(client)
assert start(client)==sid
v=view(client,sid)
assert v['task']['id']=='task1' and 'Secret' not in str(v) and 'Synthetic target' not in str(v)
assert action(client,sid,'too-soon','rate',grade='independent').status_code==409
r=action(client,sid,'r1','reveal',attempted=True,response='My attempt');assert r.status_code==200,r.text
assert view(client,sid)['task']['answer']['answer']=='Secret answer 1'
request={'requestId':'r1','version':0,'kind':'reveal','attempted':True,'response':'My attempt'}
assert client.post('/api/root-learning/sessions/'+sid+'/events',json=request).json()==r.json()
assert client.post('/api/root-learning/sessions/'+sid+'/events',json={**request,'response':'different'}).status_code==409
assert client.post('/api/root-learning/sessions/'+sid+'/events',json={**request,'requestId':'stale'}).status_code==409
assert action(client,sid,'rate1','rate',grade='independent').status_code==200
assert view(client,sid)['position']==1 and view(client,sid)['task']['answer'] is None
assert action(client,sid,'undo1','undo').status_code==200
assert view(client,sid)['position']==0 and view(client,sid)['summary']['learned']==1
assert action(client,sid,'map1','map').status_code==200
assert client.get('/api/root-learning/sessions/'+sid+'/map').status_code==200
assert action(client,sid,'help-conflict','rate',grade='independent').status_code==422
assert action(client,sid,'help-rate','rate',grade='partial').status_code==200
assert action(client,sid,'answer-only','reveal',attempted=False).status_code==200
assert action(client,sid,'answer-only-rate','rate',grade='independent').status_code==422
user('b')
assert client.get('/api/root-learning/sessions/'+sid).status_code==404
assert client.get(BASE).json()['summary']['learned']==0
user('a')
from app.routes import root_learning
root_learning.now=lambda:NOW+timedelta(days=1)
assert view(client,sid)['blocked']
assert action(client,sid,'expired','skip').status_code==409
new=start(client,'next-day');assert new!=sid
os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']='false'
assert client.get(BASE).status_code==404
assert client.get('/api/root-learning/sessions/'+new).status_code==404
os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']='true'
user('admin',True)
assert client.put(ADMIN+'/publication',json={'revision':'v1','reviewed':True,'enabled':True,'allowedUsers':['a']}).status_code==200
user('b');assert client.get(BASE).status_code==404
user('a');assert client.get(BASE).status_code==200
print('PASS: admin/draft/publication/flags, finite session, hidden answers, ordering, idempotency, collisions, undo, map help, answer-only, account isolation, date rollover, cohort gating')
