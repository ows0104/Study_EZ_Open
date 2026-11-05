"""Independent process setup and synthetic root content shared by server checks."""
import importlib.util
import json
import os
from copy import deepcopy
from pathlib import Path
import tempfile
from datetime import date, datetime, UTC

spec = importlib.util.spec_from_file_location('root_fixture', Path(__file__).resolve().parents[2] / 'tests/contracts/root_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
from app.root_learning.policy import CONFIGURED_POLICY
POLICY = deepcopy(CONFIGURED_POLICY)
LEGACY_POLICY = fixture.POLICY
document = fixture.document
NOW = datetime(2026, 11, 3, 1, tzinfo=UTC)


def setup():
    parent = Path(__file__).resolve().parents[1] / 'local_test_data'; parent.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='roots-', dir=parent))
    os.environ.update(ENVIRONMENT='local-test',DATABASE_URL=f'sqlite:///{(folder / "test.db").as_posix()}',
        STUDYEZ_LOCAL_STORAGE_DIR=str(folder/'storage'),STUDYEZ_ROOT_LEARNING_ENABLED='true',STUDYEZ_ROOT_POLICY=json.dumps(POLICY))
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN
    from app.database import Base, engine, SessionLocal
    from app.models import Lecture
    from app.routes import root_learning
    Base.metadata.create_all(engine)
    root_learning.now=lambda:NOW
    with SessionLocal() as db:
        db.add(Lecture(subject='test',run_id='demo',uid='root-demo',date=date(2026,11,3),slot=1,slot_end=1,
                       start_time='09:00',title='Synthetic lecture',professors=[],author='',version=1));db.commit()
    def user(uid='a',admin=False):
        app.dependency_overrides[get_current_user]=lambda:CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=admin,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
    return TestClient(app), user, SessionLocal


BASE='/api/root-learning/lectures/test/demo'
ADMIN='/api/admin/root-learning/lectures/test/demo'


def publish(client,user,doc=None):
    user('admin',True)
    doc=doc or document()
    response=client.post(ADMIN,json=doc);assert response.status_code==200,response.text
    response=client.put(ADMIN+'/publication',json={'revision':doc['revision'],'reviewed':True,'enabled':True});assert response.status_code==200,response.text
    user('a')


def start(client,request='start'):
    r=client.post(BASE+'/sessions',json={'requestId':request});assert r.status_code==200,r.text
    return r.json()['sessionId']


def view(client,sid):
    r=client.get('/api/root-learning/sessions/'+sid);assert r.status_code==200,r.text
    return r.json()


def action(client,sid,request,kind,**kwargs):
    return client.post('/api/root-learning/sessions/'+sid+'/events',json={
        'requestId':request,'version':view(client,sid)['version'],'kind':kind,**kwargs})
