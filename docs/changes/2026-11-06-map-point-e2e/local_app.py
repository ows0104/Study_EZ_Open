"""Actual StudyEZ API against persistent experiment-only SQLite and disk storage."""
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE=Path(__file__).resolve().parent
# Server dependencies take precedence; fill missing pure-contract dependencies
# from the existing authoring environment without installing or changing it.
sys.path.append(str(HERE.parents[4]/'.venv/Lib/site-packages'))
sys.path.insert(0,str(HERE))
from experiment import ROOT, RUNTIME_ROOT, OUT, LECTURES, read, sha, check_inputs

STATE=OUT/'local-app';STATE.mkdir(exist_ok=True)
os.environ.update(ENVIRONMENT='local-test',DATABASE_URL='sqlite:///'+(STATE/'study.db').as_posix(),
    STUDYEZ_LOCAL_STORAGE_DIR=str(STATE/'storage'),STUDYEZ_ROOT_LEARNING_ENABLED='true',
    RUNNER_TOKEN='e2e-local-only',PUBLIC_API_BASE_URL='',
    CORS_ALLOWED_ORIGINS='http://127.0.0.1:5196')
sys.path[:0]=[str(ROOT/'server'),str(RUNTIME_ROOT)]
from fastapi import Request
from fastapi.testclient import TestClient
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from app.main import app
from app.database import Base,engine,SessionLocal
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
from app.models import Lecture
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result

def account(uid,admin=False):
    return CurrentUser(id=uid,email=uid+'@example.com',is_admin=admin,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))

def bootstrap():
    check_inputs();Base.metadata.create_all(engine)
    store=ObjectStorage();loaded=[]
    seal=read(OUT/'generation-verification.json')if (OUT/'generation-verification.json').exists()else{'results':[]}
    verified={row['slug']:row['resultSha256']for row in seal['results']}
    app.dependency_overrides[get_current_user]=lambda:account('experiment-admin',True)
    client=TestClient(app)
    for index,(slug,title,*_)in enumerate(LECTURES):
        folder=OUT/slug
        if slug not in verified:continue
        assert sha(folder/'result.json')==verified[slug],'Result differs from completed native verification'
        packet=read(folder/'packet.json');result=read(folder/'result.json')
        validate_result(result,packet)
        with SessionLocal()as db:
            if not db.get(Lecture,('map-point-e2e',slug)):
                db.add(Lecture(subject='map-point-e2e',run_id=slug,uid='e2e-'+slug,
                    date=date(2026,11,6),slot=index+1,slot_end=index+1,start_time='09:00',
                    title=title,professors=['서윤성'],author='E2E 실험',version=1));db.commit()
            generation_id='e2e-'+slug
            old=db.get(RootGeneration,generation_id)
            if old:
                assert old.result_digest==document_hash(result),'Existing experiment result changed'
            else:
                snapshot=json.loads(json.dumps(packet))
                for source in snapshot['sources']:
                    key='e2e/'+slug+'/'+source['id']+'.pdf'
                    body=Path(source['localPath']).read_bytes();assert sha(Path(source['localPath']))==source['sha256']
                    store.put_bytes(key,body);source['snapshotKey']=key
                db.add(RootGeneration(id=generation_id,job_id=-(index+1),subject='map-point-e2e',run_id=slug,
                    user_id='experiment-admin',request_id=generation_id,input_digest=packet['inputHash'],
                    packet=snapshot,baseline='standalone',result=result,result_digest=document_hash(result)))
                db.commit()
        endpoint='/api/admin/root-learning/lectures/map-point-e2e/'+slug
        r=client.post(endpoint,json=result['document']);assert r.status_code==200,r.text
        r=client.put(endpoint+'/publication',json={'revision':packet['revision'],'reviewed':True,'enabled':True,
            'allowedUsers':['learner','technical-check']});assert r.status_code==200,r.text
        loaded.append({'slug':slug,'title':title,'resultSha256':sha(folder/'result.json')})
    def local_user(request:Request):
        uid='technical-check'if (request.headers.get('X-E2E-Account')=='technical-check'
            or request.cookies.get('e2e-account')=='technical-check')else'learner'
        return account(uid)
    app.dependency_overrides[get_current_user]=local_user
    return loaded

LOADED=bootstrap()
@app.get('/api/e2e-status')
def experiment_status():
    return {'localExperiment':True,'productionConnected':False,'lectures':LOADED}

@app.get('/api/e2e/account/{account_id}')
def local_account(account_id:str):
    from fastapi import HTTPException
    if account_id not in ('technical-check','learner'):raise HTTPException(404)
    response=RedirectResponse('/bank/map-point-e2e/endocarditis/roots')
    response.set_cookie('e2e-account',account_id,httponly=True,samesite='strict')
    return response

if __name__=='__main__':
    if '--check-bootstrap'in sys.argv:
        print(json.dumps({'isolatedDatabase':str(STATE/'study.db'),'loaded':LOADED},ensure_ascii=True))
    else:
        import uvicorn
        uvicorn.run(app,host='127.0.0.1',port=8036,log_level='warning')
