"""Exercise real file storage and queueing without the platform's HTTP event loop."""
import hashlib
import os
import tempfile
from datetime import date
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='md-storage-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(TMP / "db.sqlite").as_posix()}',
                  RUNNER_TOKEN='runner-token', STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'))
from fastapi import HTTPException
from app.auth import CurrentUser
from app.database import Base, SessionLocal, engine
from app.models import Lecture, QuizBank, BankState, PrequizJob
from app.routes.bank import ResponseIn, put_bank_response, get_bank_shared_source
from app.bank_validation.markdown_file import validate


def main():
    Base.metadata.create_all(engine)
    fixture = (Path(__file__).resolve().parents[2] / 'tests/fixtures/bank-file-valid.md').read_text(encoding='utf-8')
    actor = CurrentUser(id='test-admin', email='admin@example.test', is_admin=True)
    for subject, run_id in [('약리학', '261012_02'), ('병리학', '261019_01')]:
        with SessionLocal() as db:
            db.add(Lecture(subject=subject, run_id=run_id, uid=run_id, date=date(2026,10,19),
                           slot=1, slot_end=1, start_time='09:00', title='MD import fixture'))
            db.commit()
            db.add(QuizBank(subject=subject, run_id=run_id, build_id='old', raw_response='old',
                            bank={'preserved': True}, status='ready', open_to_students=True))
            db.add(BankState(user_id='learner', subject=subject, run_id=run_id, build_id='old', state={'history':[1]}))
            db.commit()
            raw = fixture.replace('261006_02', run_id).replace('1.76', '1.78').replace('약리학', subject)
            name = f'study-ez-{run_id}-bank.md'
            info = validate(raw, name, subject, run_id)
            packet = {'raw':raw, 'promptVersion':'1.78', 'source':'manual',
                      'responseFile':{k:info[k] for k in ('filename','sha256','byteLength')}}
            invalid = [
                {k:v for k,v in packet.items() if k != 'responseFile'},
                {**packet, 'responseFile':{**packet['responseFile'], 'sha256':'0'*64}},
                {**packet, 'raw':raw.replace('STUDYEZ_BANK_COMPLETE','')},
                {**packet, 'raw':raw.replace('"question_count":8','"question_count":9')},
                {**packet, 'raw':raw.replace('"run_id":"'+run_id+'"','"run_id":"wrong"')},
            ]
            for value in invalid:
                try:
                    put_bank_response(subject, run_id, ResponseIn.model_validate(value), actor, db)
                except HTTPException as error:
                    assert error.status_code == 422
                else:
                    raise AssertionError('Invalid file accepted')
                assert db.get(QuizBank,(subject,run_id)).raw_response == 'old'
                assert db.query(PrequizJob).filter_by(subject=subject,run_id=run_id).count() == 0
            put_bank_response(subject,run_id,ResponseIn.model_validate(packet),actor,db)
            assert put_bank_response(subject,run_id,ResponseIn.model_validate(packet),actor,db)['reused']
            stored = get_bank_shared_source(subject,run_id,actor,db)
            assert stored['raw'] == raw and stored['responseFile']['questionCount'] == 8
            assert stored['responseFile']['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
            row = db.get(QuizBank,(subject,run_id))
            assert row.bank == {'preserved':True} and row.build_id == 'old'
            assert db.get(BankState,('learner',subject,run_id)).state == {'history':[1]}
            assert db.query(PrequizJob).filter_by(subject=subject,run_id=run_id).count() == 1
    print('PASS: two subjects, real 8-format files, reject invalid identity/count/hash/completion, idempotency, stored bytes and learning preservation')


if __name__ == '__main__':
    main()
