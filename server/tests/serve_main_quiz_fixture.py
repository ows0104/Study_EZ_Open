"""Owned localhost UI fixture; never connects to production or invokes a model."""
import json
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from fastapi import Request
from tests.root_support import setup,publish,document
from tests.bank_fixtures import example_bank
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash

client,user,SessionLocal=setup()
doc=document()
for q in doc['bank_snapshot']['questions'][:2]:
    q.update(format='mcq',options=[{'id':'A','text':'Choice A'},{'id':'B','text':'Choice B'}],correct_option_ids=['A'],
             mcq_mode='comparison' if q['question_id']=='Q1' else 'recall_first')
doc['review']['bank_sha256']=document_hash(doc['bank_snapshot'])
for m,q in zip(doc['review']['mappings'],doc['bank_snapshot']['questions']):m['question_sha256']=question_hash(q,doc['bank_snapshot'])
publish(client,user,doc)
from app.main import app
from app.models import Lecture,QuizBank
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
with SessionLocal() as db:
    db.add(Lecture(subject='test',run_id='legacy',uid='main-quiz-legacy',date=date(2026,11,3),slot=2,slot_end=2,
                   start_time='10:00',title='기존 Main Quiz 호환 확인',professors=[],author='',version=1))
    db.add(QuizBank(subject='test',run_id='legacy',build_id='preserved',status='ready',bank=example_bank(),validation={'pass':True},open_to_students=True))
    db.commit()
if path:=os.environ.get('STUDYEZ_MAIN_QUIZ_TRIAL'):
    trial=json.loads(Path(path).read_text(encoding='utf-8'))
    subject,run_id=trial['review']['lecture_id'].split('/',1)
    with SessionLocal() as db:
        db.add(Lecture(subject=subject,run_id=run_id,uid='main-quiz-clinical',date=date(2026,11,3),slot=3,slot_end=3,
                       start_time='11:00',title=trial['title'],professors=[],author='',version=1));db.commit()
    user('admin',True)
    base=f'/api/admin/root-learning/lectures/{subject}/{run_id}'
    r=client.post(base,json=trial);assert r.status_code==200,r.text
    r=client.put(base+'/publication',json={'revision':trial['revision'],'reviewed':True,'enabled':True,'allowedUsers':['technical-main']});assert r.status_code==200,r.text
def test_user(request:Request):
    uid=request.headers.get('X-Root-Test-User','technical-main')
    return CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=False,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
app.dependency_overrides[get_current_user]=test_user
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8037,log_level='warning')
