"""A feedback edit preserves unrelated published findings and rejects new failures."""
import copy
import datetime
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='studyez-feedback-edit-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'), RUNNER_TOKEN='runner-token')

from fastapi.testclient import TestClient
from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_bank
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank
from tests.bank_fixtures import example_bank


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='test', run_id='demo', uid='feedback-edit-test',
            date=datetime.date(2026, 10, 15), slot=1, slot_end=1, start_time='09:00',
            title='Feedback edit test', professors=[], author='', version=1))
        db.add(Asset(id='notes', subject='test', run_id='demo', kind='notes_current',
            filename='notes.pdf', object_key='notes.pdf', content_type='application/pdf'))
        db.commit()
    client = TestClient(app)
    admin = '/api/admin/lectures/test/demo'
    headers = {'Authorization': 'Bearer local-test-token'}
    response = client.put(admin + '/bank-response', headers=headers,
        json={'raw': 'test ' * 60 + 'STUDYEZ_BANK_COMPLETE'}).json()
    bank = without_retired(example_bank())
    bank['build_meta']['schema_version'] = '3.1'
    bank['questions'][0]['question'] = bank['questions'][0]['answer']
    checked = validate_bank(bank, ['S1'])
    assert not checked['pass'] and validate_bank(bank, ['S1'], check_quality=False)['pass']
    review = {'counts': {'wrong': 1}, 'reviews': [
        {'question_id': 'Q1', 'verdict': 'wrong', 'note': 'Preserved unrelated finding'}]}
    uploaded = client.put(admin + '/bank', headers={'Authorization': 'Bearer runner-token'},
        json={'respondedAt': response['respondedAt'], 'bank': bank, 'validation': checked,
              'review': review, 'allowUnresolved': True})
    assert uploaded.status_code == 200 and uploaded.json()['status'] == 'ready', uploaded.text
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        original = copy.deepcopy(row.bank)
        build_id = row.build_id
    target = copy.deepcopy(original['questions'][1])
    edited = {**target, 'question': target['question'] + ' (수정)'}
    route = admin + '/bank/cards/' + target['question_id']
    def put(question, expected=target, build=build_id):
        return client.put(route, headers=headers, json={'buildId': build,
            'expectedQuestion': expected, 'action': 'edit', 'question': question})
    assert put(edited, build='stale-build').status_code == 409
    assert put(edited, expected={**target, 'question': 'stale text'}).status_code == 409
    bad_structure = {**edited, 'prerequisites': ['missing-id']}
    assert put(bad_structure).status_code == 422
    bad_content = {**edited, 'question': edited['answer']}
    assert put(bad_content).status_code == 422
    success = put(edited)
    assert success.status_code == 200, success.text
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        assert not row.validation['pass'] and row.validation['publication']['allowed']
        assert row.validation['errors'] == checked['errors'] and row.review == review
        assert row.bank['questions'][0] == original['questions'][0]
        assert row.bank['questions'][1] == edited
    print('PASS feedback edit preserves unrelated published findings; stale and invalid edits rejected')


if __name__ == '__main__':
    main()
