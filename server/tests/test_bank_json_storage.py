"""Real JSON ingestion and preservation, using only isolated SQLite/storage."""
import copy
import json
from datetime import date
from pathlib import Path
from tests.root_support import setup

client,user,SessionLocal=setup()
from app.models import Lecture,QuizBank,BankState,PrequizJob
from studyez_contracts.bank.response_file import validate

fixture=Path(__file__).resolve().parents[2]/'tests/fixtures/bank-file-valid.json'
doc=json.loads(fixture.read_text(encoding='utf-8'))
user('admin',True)
with SessionLocal() as db:
    db.add(Lecture(subject='약리학',run_id='261006_02',uid='synthetic-json',date=date(2026,11,5),slot=1,slot_end=1,start_time='09:00',title='Synthetic JSON'))
    db.add(QuizBank(subject='약리학',run_id='261006_02',build_id='old',raw_response='old',bank={'preserved':True},status='ready'))
    db.add(BankState(user_id='learner',subject='약리학',run_id='261006_02',build_id='old',state={'history':[1]}));db.commit()
raw=json.dumps(doc,ensure_ascii=False)
info=validate(raw,'study-ez-261006_02-bank.json','약리학','261006_02')
payload={'raw':raw,'source':'manual','promptVersion':'1.80','responseFile':{k:info[k]for k in ('filename','sha256','byteLength')}}
base='/api/admin/lectures/약리학/261006_02'
invalid=[{k:v for k,v in payload.items()if k!='responseFile'},
    {**payload,'promptVersion':'1.81'},
    {**payload,'responseFile':{**payload['responseFile'],'sha256':'0'*64}},
    {**payload,'raw':raw+'\nSTUDYEZ_BANK_COMPLETE'}]
for value in invalid:
    response=client.put(base+'/bank-response',json=value)
    assert response.status_code==422,response.text
with SessionLocal() as db:
    assert db.get(QuizBank,('약리학','261006_02')).raw_response=='old'
response=client.put(base+'/bank-response',json=payload)
assert response.status_code==200,response.text
assert client.put(base+'/bank-response',json=payload).json()['reused']
with SessionLocal() as db:
    row=db.get(QuizBank,('약리학','261006_02'))
    assert row.raw_response==raw and row.bank=={'preserved':True} and row.build_id=='old'
    assert row.validation['responseFile']['questionCount']==6
    assert db.get(BankState,('learner','약리학','261006_02')).state=={'history':[1]}
    assert db.query(PrequizJob).filter_by(subject='약리학',run_id='261006_02').count()==1
print('PASS pure JSON storage, metadata/hash/version/completion rejection, replay and preserved bank/learning')
