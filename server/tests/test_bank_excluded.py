"""Exclusions remain browseable; personal decisions never rewrite banks or ratings."""
import copy
import datetime
from dataclasses import replace
from tests.test_bank import STUDENT, example_bank
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app import bank_personal, study_engine


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    excluded = bank['questions'].pop()
    excluded['prerequisites'] = ['missing', bank['questions'][0]['question_id']]
    qid = excluded['question_id']
    validation = {'pass': True, 'excludedQuestions': [{'question': excluded, 'reason': '세부 식별 문제',
        'medicalReview': {'question_id': qid, 'verdict': 'doubt', 'note': '기존 의심 보존', 'suggested_answer': ''}}]}
    original = copy.deepcopy(bank)
    state = study_engine.empty_state()
    state['history'] = [{'keep': 'prior rating'}]
    state['items'] = {qid: {'reviews': 2, 'due_at': 12345}}
    with SessionLocal() as db:
        db.add(Lecture(subject='excluded', run_id='one', uid='excluded-one', title='제외 보관',
            date=datetime.date(2026, 10, 17), slot=1, slot_end=1, start_time='09:00'))
        db.flush()
        db.add(QuizBank(subject='excluded', run_id='one', build_id='v1', bank=bank,
            validation=validation, open_to_students=True))
        db.add(BankState(user_id=STUDENT.id, subject='excluded', run_id='one', build_id='v1', state=state))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)
    base = '/api/lectures/excluded/one/bank'
    def catalog():
        response = client.get(base + '/catalog')
        assert response.status_code == 200, response.text
        return response.json()
    def decision(value, build='v1'):
        return client.put(base + '/excluded/' + qid, json={'buildId': build, 'decision': value})
    archived = next(r for r in catalog()['questions'] if r['question']['question_id'] == qid)
    assert archived['excludedStatus'] == 'excluded' and archived['excludedReason']
    assert 'answer' not in archived['question']
    detail = client.get(base + '/catalog/' + qid + '?buildId=v1').json()
    assert detail['answer']['answer'] == excluded['answer']
    assert detail['answer']['medicalReview']['verdict'] == 'doubt'
    with SessionLocal() as db:
        assert len(bank_personal.augment(db, db.get(QuizBank, ('excluded', 'one')), STUDENT.id)['questions']) == 2
        assert db.get(BankState, (STUDENT.id, 'excluded', 'one')).state == state
    assert decision('restored', 'old').status_code == 409
    assert decision('restored').status_code == 200
    with SessionLocal() as db:
        row = db.get(QuizBank, ('excluded', 'one'))
        restored = bank_personal.augment(db, row, STUDENT.id)
        q = next(q for q in restored['questions'] if q['question_id'] == qid)
        assert q['answer'] == excluded['answer'] and q['prerequisites'] == [bank['questions'][0]['question_id']]
        saved = db.get(BankState, (STUDENT.id, 'excluded', 'one')).state
        assert saved['history'] == state['history'] and saved['items'] == state['items']
        assert row.bank == original and row.validation == validation
    for value in ['deleted', 'excluded', 'restored', 'excluded']:
        assert decision(value).status_code == 200
        assert next(r for r in catalog()['questions'] if r['question']['question_id'] == qid)['excludedStatus'] == value
    app.dependency_overrides[get_current_user] = lambda: replace(STUDENT, id='another')
    assert next(r for r in catalog()['questions'] if r['question']['question_id'] == qid)['excludedStatus'] == 'excluded'
    with SessionLocal() as db:
        row = db.get(QuizBank, ('excluded', 'one'))
        row.open_to_students = False
        db.commit()
    assert decision('restored').status_code == 404
    assert client.get(base + '/catalog/' + qid + '?buildId=v1').status_code == 404
    print('PASS: excluded browse, review preservation, restore/delete/revert, user isolation, publication and unchanged history')


if __name__ == '__main__':
    main()
