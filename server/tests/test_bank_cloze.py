"""Four-blank cards survive runner upload, student reveal, and admin edits."""
import datetime
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='studyez-cloze-four-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(TMP / "bank.db").as_posix()}',
                  STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'), RUNNER_TOKEN='runner-token')
from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture
from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_dropping
from tests.bank_fixtures import example_bank

def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='test', run_id='261001_02', uid='cloze-four', date=datetime.date(2026, 10, 1),
                       slot=2, slot_end=2, start_time='10:00', title='Cloze four', professors=[], author='', version=1))
        db.add(Asset(id='notes', subject='test', run_id='261001_02', kind='notes_current', filename='notes.pdf',
                     object_key='notes.pdf', content_type='application/pdf'))
        db.commit()
    client = TestClient(app)
    admin = '/api/admin/lectures/test/261001_02'
    base = '/api/lectures/test/261001_02'
    headers = {'Authorization': 'Bearer local-test-token'}
    response = client.put(f'{admin}/bank-response', headers=headers,
                          json={'raw': 'test ' * 60 + 'STUDYEZ_BANK_COMPLETE'})
    assert response.status_code == 200, response.text
    bank = without_retired(example_bank())
    q = bank['questions'][0]
    q.update(format='cloze', question='흡수 {{c1}}, F {{c1}}; 흡수 {{c1}}, F {{c1}}.',
             answer='감소, 감소; 증가, 증가.', answer_units=['감소', '감소', '증가', '증가'])
    clean, validation = validate_dropping(bank, ['S1'])
    assert validation['pass'] and validation['dropped'] == []
    uploaded = client.put(f'{admin}/bank', headers={'Authorization': 'Bearer runner-token'},
                          json={'respondedAt': response.json()['respondedAt'], 'bank': clean, 'validation': validation})
    assert uploaded.status_code == 200 and uploaded.json()['status'] == 'ready', uploaded.text
    started = client.post(f'{base}/bank/session/start', headers=headers, json={'target': 90})
    assert started.status_code == 200, started.text
    served = client.post(f'{base}/bank/next', headers=headers).json()
    assert served['question']['question_id'] == 'Q1', served
    assert served['question']['question'].count('{{c1}}') == 4
    revealed = client.post(f'{base}/bank/reveal', headers=headers, json={'reviewToken': served['reviewToken']})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()['answerUnits'] == ['감소', '감소', '증가', '증가']
    print('PASS: runner accepts four blanks; reveal returns all four ordered answers')

if __name__ == '__main__':
    main()
