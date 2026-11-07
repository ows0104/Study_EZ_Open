"""Local-only presentation of a validated pilot; synthetic account, isolated DB."""
import argparse
import json
import os
import sys
from datetime import date,datetime,UTC
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'server'));sys.path.insert(0,str(ROOT))
OUT=ROOT/'runs/_parallel-pilot/261104_02'
result=json.loads((OUT/'result.json').read_text(encoding='utf-8'))
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
packet=json.loads((OUT/'packet.json').read_text(encoding='utf-8'))
assert summary['completed']and summary['productionWrites']==0

from tests.root_support import setup
client,user,SessionLocal=setup()
from app.main import app
from app.models import Lecture,Profile,Asset
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
from app.storage import ObjectStorage
from app.routes import root_learning
from fastapi import Request
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse
import uvicorn

root_learning.now=lambda:datetime.now(UTC)
subject,rid=packet['subject'],packet['runId'];uid='local-pilot'
with SessionLocal()as db:
    db.add(Lecture(subject=subject,run_id=rid,uid='local-pathology-26110402',date=date(2026,11,4),
        slot=2,slot_end=2,start_time='10:00',title=packet['title'],professors=['김지은'],author='박준원',version=2))
    db.add(Profile(id=uid,email='local-pilot@example.invalid',is_admin=True))
    db.add(Asset(id='local-pilot-source',subject=subject,run_id=rid,kind='notes_current',filename=packet['sources'][0]['filename'],
        object_key='local-pilot/pathology.pdf',size_bytes=packet['sources'][0]['sizeBytes'],content_type='application/pdf'))
    db.commit()
ObjectStorage().put_bytes('local-pilot/pathology.pdf',Path(packet['sources'][0]['localPath']).read_bytes())
user(uid,True)
base='/api/admin/root-learning/lectures/'+quote(subject,safe='')+'/'+rid
r=client.post(base,json=result['document']);assert r.status_code==200,r.text
r=client.put(base+'/publication',json={'revision':result['document']['revision'],'reviewed':True,'enabled':True,'allowedUsers':[uid]})
assert r.status_code==200,r.text


def local_user(request:Request):
    return CurrentUser(id=uid,email='local-pilot@example.invalid',is_admin=True,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
app.dependency_overrides[get_current_user]=local_user


@app.get('/api/__pilot/source.pdf')
def source():
    return FileResponse(packet['sources'][0]['localPath'],media_type='application/pdf',filename=packet['sources'][0]['filename'])


@app.middleware('http')
async def attach_local_source(request,call_next):
    response=await call_next(request)
    # The canonical clinical document is unchanged. This local presentation adds
    # the frozen original PDF link after answer disclosure, without a fake generation row.
    if request.url.path.startswith('/api/root-learning/sessions/')and response.status_code==200:
        body=b''.join([chunk async for chunk in response.body_iterator])
        value=json.loads(body)
        answer=(value.get('task')or{}).get('answer')
        if answer is not None:answer['sourceMaterials']=[{'filename':packet['sources'][0]['filename'],'url':'/api/__pilot/source.pdf'}]
        return JSONResponse(value,status_code=response.status_code)
    return response


@app.get('/__pilot')
def info():
    path='/bank/'+quote(subject,safe='')+'/'+rid
    return HTMLResponse('<meta charset="utf-8"><title>Main Quiz 로컬 시범</title><h1>감염성 질환의 병리 1 · 로컬 시범</h1>'
        '<p>운영 문제은행과 사람의 학습 기록은 변경하지 않았습니다. 이 화면은 격리된 기술 계정을 사용합니다.</p>'
        '<p><a href="'+os.environ['PILOT_WEB_URL']+path+'">Main Quiz 풀기</a></p><p><a href="/api/__pilot/source.pdf">동일 원본 PDF 확인</a></p>')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);args=p.parse_args()
    (OUT/'local-review.json').write_text(json.dumps({'api':'http://127.0.0.1:'+str(args.port),'web':os.environ['PILOT_WEB_URL'],
        'database':os.environ['DATABASE_URL'],'localOnly':True,'technicalUser':uid,'productionWrites':0},ensure_ascii=False,indent=2),encoding='utf-8')
    uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning')
