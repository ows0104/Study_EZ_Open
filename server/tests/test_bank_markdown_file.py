"""File imports reject partial/misattributed content before altering a bank or queue."""
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='bank-file-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(TMP / "db.sqlite").as_posix()}',
                  RUNNER_TOKEN='runner-token', STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'))
from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, QuizBank, BankState, PrequizJob
from app.bank_validation.markdown_file import validate, required
from app import bank_shared_response


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='약리학', run_id='261006_02', uid='cns', date=date(2026,10,6), slot=2,
                       slot_end=2, start_time='10:00', title='중추신경계 약리 기초(성지혜)'))
        db.commit()
        db.add(QuizBank(subject='약리학', run_id='261006_02', build_id='old-build', raw_response='old raw',
                        bank={'preserved': True}, status='ready', open_to_students=True))
        db.add(BankState(user_id='learner', subject='약리학', run_id='261006_02', build_id='old-build', state={'history':[1]}))
        db.commit()
    raw = (Path(__file__).resolve().parents[2] / 'tests/fixtures/bank-file-valid.md').read_text(encoding='utf-8')
    name = 'study-ez-261006_02-bank.md'
    meta = validate(raw, name, '약리학', '261006_02')
    packet = {'raw': raw, 'source':'manual', 'promptVersion':'1.76',
              'responseFile': {key:meta[key] for key in ('filename','sha256','byteLength')}}
    c = TestClient(app)
    base = '/api/admin/lectures/약리학/261006_02'
    admin = {'Authorization':'Bearer local-test-token'}
    assert c.put(base+'/bank-response',json=packet).status_code==401
    for wrong in [{**packet,'responseFile':None},
                  {**packet,'raw':raw.replace('STUDYEZ_BANK_COMPLETE','')},
                  {**packet,'responseFile':{**packet['responseFile'],'sha256':'0'*64}},
                  {**packet,'raw':raw.replace('"question_count":8','"question_count":9')},
                  {**packet,'promptVersion':'1.75'},
                  {'raw':'legacy text '*30+'\nSTUDYEZ_BANK_COMPLETE','promptVersion':'1.76'}]:
        result=c.put(base+'/bank-response',json=wrong,headers=admin)
        assert result.status_code==422,result.text
        with SessionLocal() as db:
            assert db.get(QuizBank,('약리학','261006_02')).raw_response=='old raw'
            assert db.query(PrequizJob).count()==0
    result=c.put(base+'/bank-response',json=packet,headers=admin)
    assert result.status_code==200,result.text
    with SessionLocal() as db:
        row=db.get(QuizBank,('약리학','261006_02'))
        assert row.raw_response==raw and row.bank=={'preserved':True} and row.build_id=='old-build'
        assert row.validation['responseFile']['sha256']==hashlib.sha256(raw.encode()).hexdigest()
        assert row.validation['responseFile']['questionCount']==8
        assert db.get(BankState,('learner','약리학','261006_02')).state=={'history':[1]}
        assert db.query(PrequizJob).count()==1
    assert c.put(base+'/bank-response',json=packet,headers=admin).json()['reused']
    source=c.get(base+'/bank/shared-source',headers={'Authorization':'Bearer runner-token'}).json()
    assert source['responseFile']['validated'] and not source['importShare']
    assert c.put(base+'/bank/links',json={'shareUrl':'https://chatgpt.com/share/file-only'},headers=admin).status_code==200
    with SessionLocal() as db:
        assert db.query(PrequizJob).count()==1
        row=db.get(QuizBank,('약리학','261006_02'))
        assert bank_shared_response.file_source(row) and not bank_shared_response.pending(row)
        row.responded_by='extension-user'
        db.commit()
    assert bank_shared_response.file_source(row)
    for subject, run_id in [('약리학', '261012_02'), ('병리학', '261019_01')]:
        assert required(subject, run_id, '1.78')
        assert not required(subject, run_id, '1.77')
        with SessionLocal() as db:
            db.add(Lecture(subject=subject, run_id=run_id, uid=run_id, date=date(2026,10,19),
                           slot=1, slot_end=1, start_time='09:00', title='일반 강의'))
            db.commit()
        value = raw.replace('261006_02', run_id).replace('1.76', '1.78').replace('약리학', subject)
        filename = f'study-ez-{run_id}-bank.md'
        metadata = validate(value, filename, subject, run_id)
        request = {'raw': value, 'source': 'manual', 'promptVersion': '1.78',
                   'responseFile': {key: metadata[key] for key in ('filename', 'sha256', 'byteLength')}}
        endpoint = f'/api/admin/lectures/{subject}/{run_id}/bank-response'
        assert c.put(endpoint, json={k:v for k,v in request.items() if k != 'responseFile'}, headers=admin).status_code == 422
        assert c.put(endpoint, json={'raw': 'legacy text '*30+'\nSTUDYEZ_BANK_COMPLETE',
                                    'promptVersion': '1.78'}, headers=admin).status_code == 422
        response = c.put(endpoint, json=request, headers=admin)
        assert response.status_code == 200, response.text
        assert c.put(endpoint, json=request, headers=admin).json()['reused']
        with SessionLocal() as db:
            row = db.get(QuizBank, (subject, run_id))
            assert row.raw_response == value
            assert row.validation['responseFile']['sha256'] == hashlib.sha256(value.encode()).hexdigest()
            assert row.validation['responseFile']['questionCount'] == 8
    print('PASS: all-lecture real-file import, identity, structure, hash, idempotency, original bank and learning preservation')


if __name__=='__main__':main()
