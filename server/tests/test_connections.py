"""Isolated product API checks; synthetic content is not medical validation."""
import os
import tempfile
from pathlib import Path
from datetime import date
test_root = Path(__file__).resolve().parent.parent / 'local_test_data'
test_root.mkdir(exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix='connections-', dir=test_root))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(tmp / "test.db").as_posix()}', STUDYEZ_LOCAL_STORAGE_DIR=str(tmp / 'storage'))
from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, ConnectionEvent, ConnectionState
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(Lecture(subject='test',run_id='demo',uid='demo',date=date(2026,11,3),slot=1,slot_end=1,start_time='09:00',title='test',professors=[],author='',version=1))
    db.commit()
client=TestClient(app)
def user(uid,admin=False):
    app.dependency_overrides[get_current_user]=lambda:CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=admin,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
base='/api/lectures/test/demo/connections'
admin='/api/admin/lectures/test/demo/connections'
b={k:k for k in ['id','title','type','structure','role','connection','next','sources','original','structural','exam','clinical','gap']}
b.update(root={'question':'Root?','answers':['Secret root'],'explanation':'Explanation'},follow={'question':'Hidden follow?','answers':['Secret follow'],'explanation':'Follow explanation'})
doc={'revision':'v1','title':'Example','scope':'One bundle','bundles':[b]}
user('admin',True)
assert client.post(admin,json=doc).status_code==200
assert client.post(admin,json={**doc,'title':'changed'}).status_code==409
assert client.post(admin,json={**doc,'revision':'dup','bundles':[b,b]}).status_code==422
user('a')
assert client.post(admin,json=doc).status_code==403
assert client.get(base).json()['versions']==[]
assert client.get(base+'/v1').status_code==404
user('admin',True)
assert client.put(admin+'/v1/publication',json={'published':True}).status_code==200
user('a')
view=client.get(base+'/v1').json()
assert 'Secret' not in str(view) and 'Hidden follow' not in str(view)
payload={'requestId':'one','version':0,'kind':'reveal','step':'follow'}
assert client.post(base+'/v1/actions',json=payload).status_code==409
payload.update(step='root',response='My attempt')
r=client.post(base+'/v1/actions',json=payload)
assert r.status_code==200,r.text
assert r.json()['task']['root']['answers']==['Secret root']
assert 'answers' not in r.json()['task']['follow']
assert client.post(base+'/v1/actions',json=payload).json()==r.json()
assert client.post(base+'/v1/actions',json={**payload,'response':'different'}).status_code==409
assert client.post(base+'/v1/actions',json={**payload,'requestId':'stale'}).status_code==409
with SessionLocal() as db:
    assert db.query(ConnectionEvent).count()==1
    assert db.get(ConnectionState,('a','test','demo','v1')).version==1
assert client.get(base+'/v1').json()['task']['root']['response']=='My attempt'
user('b')
assert client.get(base+'/v1').json()['version']==0
user('a')
r=client.post(base+'/v1/actions',json={'requestId':'map','version':1,'kind':'map'})
assert r.json()['state']['reviewSeen'] and r.json()['map'][0]['root']['answers']
r=client.post(base+'/v1/actions',json={'requestId':'follow','version':2,'kind':'reveal','step':'follow'})
assert r.status_code==200
r=client.post(base+'/v1/actions',json={'requestId':'rate','version':3,'kind':'rate','step':'follow','marks':['recalled']})
assert r.status_code==200 and r.json()['state']['entries']['id']['root']['marks']==['']
user('admin',True)
assert client.put(admin+'/v1/publication',json={'published':False}).status_code==200
user('a')
assert client.get(base+'/v1').status_code==404
assert client.post(base+'/v1/actions',json=payload).status_code==404
with SessionLocal() as db:
    assert db.get(ConnectionState,('a','test','demo','v1')).version==4
print('PASS: registration, immutability, validation, permissions, answer hiding, stage order, idempotency, conflicts, resume, account isolation, exposure, partial ratings, unpublish preservation')
