"""Named administrator replacement after exact code deployment; no learner actions."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'server'),str(ROOT)]
from dotenv import load_dotenv
load_dotenv(ROOT.parents[1]/'server/.env',override=False)
from sqlalchemy import select
from app.database import SessionLocal
from app.models import QuizBank,BankState
from app.models.root_learning import RootContent,RootControl,RootEvent,RootSession
from app.models.root_generation import RootGeneration
from app.root_learning import replacement_import
from app.root_learning.reviewed_import import source_records
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

OUT=ROOT/'runs/_replacement/261104_02-v1'
API='https://studyez-api-97999573571.asia-northeast3.run.app'
PARENT='382c53909ad28529243208029e82bbf1'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def snapshot(db,subject,rid):
    def rows(model):return list(db.scalars(select(model).where(model.subject==subject,model.run_id==rid)))
    control=db.get(RootControl,(subject,rid));bank=db.get(QuizBank,(subject,rid));events=rows(RootEvent);sessions=rows(RootSession)
    return {'subject':subject,'runId':rid,'control':{'revision':control.revision,'enabled':control.enabled,'allowedUsers':control.allowed_users},
        'controlHash':document_hash([control.revision,control.enabled,control.allowed_users]),
        'versions':{r.revision:r.digest for r in rows(RootContent)},'bank':document_hash(bank.bank)if bank else None,
        'bankStates':{r.user_id:document_hash(r.state)for r in rows(BankState)},
        'events':{r.user_id+'/'+r.request_id:document_hash({'kind':r.kind,'revision':r.revision,'payload':r.payload,'result':r.result})for r in events},
        'sessions':{r.id:document_hash({'revision':r.revision,'tasks':r.tasks,'state':r.state,'version':r.version})for r in sessions},
        'humanEvents':sum(r.user_id!='runner'and r.kind not in('generated','publication')for r in events),
        'humanSessions':sum(r.user_id!='runner'for r in sessions)}


def main(revision,verify_only=False):
    value=read(OUT/'result.json');checked=read(OUT/'checked-for-publication.json');packet=read(OUT/'packet.json')
    assert checked['verified']and value['ready']and checked['resultSha256']==hashlib.sha256((OUT/'result.json').read_bytes()).hexdigest()
    assert checked['runId']==value['runId']
    with urllib.request.urlopen(API+'/api/health',timeout=30)as r:health=json.load(r)
    assert health['revision']==revision and health['environment']=='production','Reviewed code must be deployed first'
    r=subprocess.run(['gcloud','run','services','describe','studyez-api','--project','meddeck-503318','--region','asia-northeast3','--format=json'],capture_output=True,text=True,encoding='utf-8',shell=True,check=True)
    config=json.loads(r.stdout)
    flags={x['name']:x.get('value')for x in config['spec']['template']['spec']['containers'][0]['env']if x['name']in('STUDYEZ_ROOT_LEARNING_ENABLED','STUDYEZ_REVISION')}
    assert flags=={'STUDYEZ_ROOT_LEARNING_ENABLED':'true','STUDYEZ_REVISION':revision}
    os.environ['STUDYEZ_ROOT_LEARNING_ENABLED']='true'
    before=read(OUT/'production-preflight.json');subject,rid=before['subject'],before['runId']
    with SessionLocal()as db:
        if not verify_only:
            assert snapshot(db,subject,rid)==before,'Current lecture/records/control changed after preflight'
            response=replacement_import.register(db,PARENT,value,expected_control_hash=before['controlHash'])
        else:response={'generationId':value['runId'],'revision':value['document']['revision'],'verifiedExisting':True}
        after=snapshot(db,subject,rid)
        assert after['bank']==before['bank']and after['bankStates']==before['bankStates']and after['sessions']==before['sessions']
        assert all(after['events'].get(k)==v for k,v in before['events'].items())
        assert set(after['events'])-set(before['events'])=={'runner/replacement-published-'+value['runId']}
        assert after['humanEvents']==before['humanEvents']and after['humanSessions']==before['humanSessions']
        assert all(after['versions'].get(k)==v for k,v in before['versions'].items())
        assert after['control']['revision']==value['document']['revision']
        assert after['control']['allowedUsers']==before['control']['allowedUsers']and after['control']['enabled']==before['control']['enabled']
        row=db.get(RootContent,(subject,rid,value['document']['revision']));assert row.document==value['document']and row.reviewed
        generation=db.get(RootGeneration,value['runId']);assert generation.result==value
        assert document_hash(db.get(RootGeneration,PARENT).result)==value['parentResultHash']
        assert len(row.document['tasks'])==len(row.document['bank_snapshot']['questions'])
        from app.routes.root_learning import main_quiz_entry,revealed_answer
        from app.auth import CurrentUser
        entry=main_quiz_entry(subject,rid,user=CurrentUser(id='runner',email='',is_admin=True),db=db)
        assert entry['mode']=='structured'and entry['overview']['revision']==row.revision
        from app.routes.root_generation import public_job
        assert public_job(db,generation)['report']['taskCount']==len(row.document['tasks'])
        q=next(q for q in row.document['bank_snapshot']['questions']if q.get('stimuli'))
        answer=revealed_answer(db,row,q);assert 'reviewNotes'in answer and 'reviewIssues'in answer
        for link,source in zip(answer['sourceLinks'],packet['sources']):
            with urllib.request.urlopen(link['url'],timeout=45)as r:body=r.read()
            assert hashlib.sha256(body).hexdigest()==source['sha256']and len(body)==source['sizeBytes']
        assert len(answer['sourceLinks'])==len(packet['sources'])
        # Validate every published image byte, not just the first rendered question.
        for q in row.document['bank_snapshot']['questions']:
            for s in q.get('stimuli',[]):
                import base64
                assert hashlib.sha256(base64.b64decode(s['png_base64'])).hexdigest()==s['sha256']
    receipt={'publishedVerified':True,'response':response,'apiRevision':revision,'health':health,'productionFlags':flags,
        'resultSha256':checked['resultSha256'],'questions':checked['questions'],'tasks':checked['tasks'],'visualQuestions':checked['visualQuestions'],'images':checked['images'],
        'freshRepairRounds':value['repairRounds'],'historicalRepairRounds':3,'oldVersionsArchived':True,'oldBankAndPeopleRecordsUnchanged':True,
        'humanEvents':after['humanEvents'],'humanSessions':after['humanSessions'],'learnerWrites':0,'privatePilot':bool(after['control']['allowedUsers']),
        'actualSignedOriginalPdfReadback':True,'allImageHashesVerified':True,'sameMainQuizEntry':True}
    target=OUT/('publication-readback.json'if verify_only else'publication-receipt.json')
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args();main(a.revision,a.verify_only)
