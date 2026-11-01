"""An unresolved authoring verdict is published without forging a passed review."""
import copy
import datetime
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='studyez-bank-publication-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'), RUNNER_TOKEN='runner-token')

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_bank
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank
from tests.bank_fixtures import example_bank


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='test', run_id='demo', uid='publication-test', date=datetime.date(2026, 10, 14),
            slot=1, slot_end=1, start_time='09:00', title='Publication test', professors=[], author='', version=1))
        db.add(Asset(id='notes', subject='test', run_id='demo', kind='notes_current', filename='notes.pdf',
            object_key='notes.pdf', content_type='application/pdf'))
        db.commit()
    client = TestClient(app)
    admin = '/api/admin/lectures/test/demo'
    base = '/api/lectures/test/demo/bank'
    response = client.put(admin + '/bank-response', headers={'Authorization': 'Bearer local-test-token'},
        json={'raw': 'test ' * 60 + 'STUDYEZ_BANK_COMPLETE'}).json()
    bank = without_retired(example_bank())
    bank['build_meta']['schema_version'] = '3.1'
    bank['questions'][0]['question'] = bank['questions'][0]['answer']
    bank['questions'][2]['prerequisites'] = []
    validation = validate_bank(bank, ['S1'])
    assert not validation['pass'] and validate_bank(bank, ['S1'], check_quality=False)['pass']
    issue = {'question_id': 'Q1', 'severity': 'error', 'issue': 'answer disclosed', 'reason': 'Authored answer in stem'}
    review = {'counts': {'wrong': 1}, 'reviews': [{'question_id': 'Q1', 'verdict': 'wrong', 'note': 'Saved verdict'}]}
    payload = {'respondedAt': response['respondedAt'], 'bank': bank, 'validation': validation,
        'review': review, 'revision': {'audit': {'question_issues': [issue]}}, 'allowUnresolved': True}
    posted = client.put(admin + '/bank', headers={'Authorization': 'Bearer runner-token'}, json=payload)
    assert posted.status_code == 200 and posted.json()['status'] == 'ready', posted.text
    with SessionLocal() as db:
        saved = db.get(QuizBank, ('test', 'demo'))
        assert saved.open_to_students and not saved.validation['pass'] and saved.review == review
        assert len(saved.bank['questions']) == len(bank['questions'])
    user = CurrentUser(id='student', email='student@example.com', is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    app.dependency_overrides[get_current_user] = lambda: user
    read = client.get(base).json()
    assert read['summary']['usable'] and read['summary']['publicationWarning']
    assert read['conceptMap']
    assert client.post(base + '/session/start', json={'size': 10}).status_code == 200
    first = client.post(base + '/next').json()
    assert first['question']['question_id'] == 'Q1' and first['answer'] is None
    shown = client.post(base + '/reveal', json={'reviewToken': first['reviewToken']}).json()
    assert shown['medicalReview']['verdict'] == 'wrong' and shown['reviewIssues'] == [issue['reason']]
    app.dependency_overrides.pop(get_current_user)
    # Editing a healthy card must retain unrelated unresolved integration issues.
    headers = {'Authorization': 'Bearer local-test-token'}
    route = admin + '/bank/cards/Q2'
    with SessionLocal() as db:
        saved = db.get(QuizBank, ('test', 'demo'))
        original_bank = copy.deepcopy(saved.bank)
        original_validation = copy.deepcopy(saved.validation)
        build_id = saved.build_id
    target = next(q for q in original_bank['questions'] if q['question_id'] == 'Q2')
    changed = {**target, 'question': 'Updated independent recall question?'}
    def edit(question, expected=target):
        return client.put(route, headers=headers, json={'action': 'edit',
            'buildId': build_id, 'expectedQuestion': expected, 'question': question})
    edited = edit(changed)
    assert edited.status_code == 200, edited.text
    with SessionLocal() as db:
        saved = db.get(QuizBank, ('test', 'demo'))
        edited_bank = copy.deepcopy(saved.bank)
        edited_validation = copy.deepcopy(saved.validation)
        assert saved.build_id == build_id and saved.open_to_students
        assert saved.review == review and not saved.validation['pass']
        assert saved.validation['errors'] == original_validation['errors']
        assert 'Q3: integration의 기초 문항 필요' in saved.validation['errors']
        assert saved.validation['revision'] == original_validation['revision']
        assert saved.validation['publication']['allowed']
        assert saved.validation['edits']['Q2']['original'] == target
        assert saved.bank['questions'] == [changed if q['question_id'] == 'Q2' else q
                                           for q in original_bank['questions']]
    for invalid in ({**changed, 'prerequisites': ['missing-id']},
                    {**changed, 'question': changed['answer']},
                    {**changed, 'retrieval_direction': 'integration', 'prerequisites': []}):
        rejected = edit(invalid, expected=changed)
        assert rejected.status_code == 422, rejected.text
        with SessionLocal() as db:
            saved = db.get(QuizBank, ('test', 'demo'))
            assert saved.bank == edited_bank and saved.validation == edited_validation
    print('PASS common edits retain unrelated integration issues and review records; invalid edits remain atomic')
    # A runner cannot bypass broken runtime references or forge a publication stamp.
    broken = copy.deepcopy(payload)
    broken['bank']['questions'][0]['prerequisites'] = ['missing-id']
    broken['validation'] = {'pass': True, 'publication': {'allowed': True}}
    failed = client.put(admin + '/bank', headers={'Authorization': 'Bearer runner-token'}, json=broken)
    assert failed.status_code == 200 and failed.json()['status'] == 'invalid', failed.text
    print('PASS publication retains errors and wrong verdicts; student study works; broken references are rejected')


if __name__ == '__main__':
    main()
