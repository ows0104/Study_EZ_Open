"""Named-lecture operational preflight; never initialize DB or modify source banks."""
import hashlib
import io
import json
import os
import sys
import argparse
import urllib.request
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'server'));sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT.parents[1]/'server/.env',override=False)
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Lecture,Asset,QuizBank,BankState
from app.models.root_learning import RootContent,RootControl,RootEvent,RootSession
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash
from app.root_learning import reviewed_import
OUT=ROOT/'runs/_final-plan/261104_02'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def inspect(db,packet):
    subject,rid=packet['subject'],packet['runId'];lecture=db.get(Lecture,(subject,rid))
    assert lecture is not None,'Named lecture must exist'
    source=packet['sources'][0]
    assets=list(db.scalars(select(Asset).where(Asset.subject==subject,Asset.run_id==rid,
        Asset.kind=='notes_current',Asset.filename==source['filename'])))
    assert len(assets)==1,'Exact requested original asset must be unique'
    asset=assets[0];body=ObjectStorage().get_bytes(asset.object_key)
    assert body is not None and len(body)==source['sizeBytes']and hashlib.sha256(body).hexdigest()==source['sha256'],'Published original differs'
    control=db.get(RootControl,(subject,rid));bank=db.get(QuizBank,(subject,rid))
    def scoped(model):return list(db.scalars(select(model).where(model.subject==subject,model.run_id==rid)))
    return {'subject':subject,'runId':rid,'title':lecture.title,'sourceVerified':True,'assetId':asset.id,
        'sourceObjectKey':asset.object_key,'sourceSha256':source['sha256'],
        'control':{'revision':control.revision,'enabled':control.enabled,'allowedUsers':control.allowed_users}if control else None,
        'versions':{v.revision:{'digest':v.digest,'reviewed':v.reviewed}for v in scoped(RootContent)},
        'bank':{'buildId':bank.build_id,'hash':document_hash(bank.bank)}if bank else None,
        'bankStates':{v.user_id:document_hash(v.state)for v in scoped(BankState)},
        'rootEvents':{v.user_id+'/'+v.request_id:document_hash({'kind':v.kind,'revision':v.revision,'payload':v.payload,'result':v.result})for v in scoped(RootEvent)},
        'rootSessions':{v.id:document_hash({'revision':v.revision,'tasks':v.tasks,'state':v.state,'version':v.version})for v in scoped(RootSession)}}

def publish(api,revision):
    result=read(OUT/'result.json');packet=read(OUT/'packet.json');checked=read(OUT/'checked-for-publication.json')
    assert checked['verified']and checked['resultSha256']==hashlib.sha256((OUT/'result.json').read_bytes()).hexdigest()
    assert checked['reviewProofHash']==result['manifest']['planRepair']['proofHash']and checked['visualQuestions']>0
    with urllib.request.urlopen(api.rstrip('/')+'/api/health',timeout=30)as response:health=json.load(response)
    assert health['revision']==revision and health['environment']=='production','Reviewed server candidate must be deployed first'
    observed=subprocess.run(['gcloud','run','services','describe','studyez-api','--project','meddeck-503318','--region','asia-northeast3','--format=json'],
        capture_output=True,text=True,encoding='utf-8',check=True,shell=True)
    config=json.loads(observed.stdout)
    flags={v['name']:v.get('value')for v in config['spec']['template']['spec']['containers'][0].get('env',[])if v['name']in('STUDYEZ_ROOT_LEARNING_ENABLED','STUDYEZ_REVISION')}
    assert flags=={'STUDYEZ_ROOT_LEARNING_ENABLED':'true','STUDYEZ_REVISION':revision},'Production feature/revision must match'
    os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']=flags['STUDYEZ_ROOT_LEARNING_ENABLED']
    before=read(OUT/'publication-preflight.json')
    with SessionLocal()as db:
        current=inspect(db,packet)
        assert current==before,'Named lecture changed after preflight; preserve current content'
        snapshots=[];storage=ObjectStorage()
        for source in packet['sources']:
            body=Path(source['localPath']).read_bytes()
            assert hashlib.sha256(body).hexdigest()==source['sha256']and len(body)==source['sizeBytes']
            key='lectures/root-reviewed-import/'+source['sha256']+'/'+source['id']
            prior=storage.get_bytes(key)
            if prior is None:storage.upload_fileobj(io.BytesIO(body),key,content_type=source.get('mimeType','application/pdf'))
            else:assert prior==body,'Never overwrite different original snapshot'
            assert storage.get_bytes(key)==body,'Snapshot readback failed'
            snapshots.append({**{k:v for k,v in source.items()if k not in('localPath','downloadUrl','snapshotKey')},'snapshotKey':key})
        response=reviewed_import.register(db,packet,result,snapshots,expected_control_hash=document_hash(None))
        after=inspect(db,packet)
        assert after['bank']==before['bank']and after['bankStates']==before['bankStates']and after['rootSessions']==before['rootSessions']
        assert all(after['rootEvents'].get(k)==v for k,v in before['rootEvents'].items())
        assert set(after['rootEvents'])-set(before['rootEvents'])=={'runner/reviewed-import-'+response['generationId']}
        row=db.get(RootContent,(packet['subject'],packet['runId'],packet['revision']))
        assert row.document==result['document']and row.digest==document_hash(result['document'])
        from app.routes.root_learning import revealed_answer,overview
        from app.auth import CurrentUser
        user=CurrentUser(id='runner',email='',is_admin=True)
        visible=overview(packet['subject'],packet['runId'],user=user,db=db)
        assert visible['revision']==packet['revision']
        visual=next(q for q in row.document['bank_snapshot']['questions']if q.get('stimuli'))
        answer=revealed_answer(db,row,visual)
        assert len(answer['sourceLinks'])==len(packet['sources'])and 'reviewNotes'in answer and 'reviewIssues'in answer
    receipt={'publishedVerified':True,'response':response,'apiRevision':revision,'health':health,
        'resultSha256':checked['resultSha256'],'bankUnchanged':True,'humanRootEventsUnchanged':True,
        'humanSessionsUnchanged':True,'privatePilot':True,'sourceLinksVerified':True,'productionWrites':True,'productionFlags':flags}
    (OUT/'publication-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');parser.add_argument('--api');parser.add_argument('--revision');args=parser.parse_args()
    if args.publish:
        assert args.api and args.revision
        publish(args.api,args.revision);raise SystemExit(0)
    target=OUT/'publication-preflight.json'
    assert not target.exists(),'Preserve original preflight'
    with SessionLocal()as db:value=inspect(db,read(OUT/'packet.json'))
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sourceVerified':value['sourceVerified'],'priorVersions':len(value['versions']),
        'active':value['control'],'existingBank':value['bank']is not None,'humanRootEvents':len(value['rootEvents'])},ensure_ascii=False))
