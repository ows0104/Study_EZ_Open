"""New first-pass roots and existing reviewed cards through real HTTP routes."""
import copy
import datetime
from unittest.mock import patch
from tests.test_bank import STUDENT
from tests.test_question_order import make_bank, NOW
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine import empty_state, record_review
from app.study_engine.policy import DEFAULT
from app.study_engine.memory import DAY_MS


def main():
    Base.metadata.create_all(engine)
    bank = make_bank([('detail', 'A', 'mechanism', 2, []),
                      ('known', 'B', 'direct', 3, []), ('root', 'A', 'direct', 20, [])])
    old_policy = copy.deepcopy(DEFAULT); old_policy['version'] = '3.11.0'
    prior = record_review(bank, empty_state(), 'known', 'Easy', NOW - DAY_MS, old_policy)
    # Keep an older completed session and unrelated personal settings intact.
    prior['sessions'] = [{'session_id': 'old', 'status': 'complete', 'reviewed': 1}]
    prior['excluded_question_decisions'] = {'unrelated-archive': 'deleted'}
    with SessionLocal() as db:
        for rid in ['single', 'batch']:
            db.add(Lecture(subject='connections', run_id=rid, uid='connections-' + rid,
                title='기초 연결', date=datetime.date(2026, 10, 18), slot=1, slot_end=1, start_time='09:00'))
            db.flush()
            db.add(QuizBank(subject='connections', run_id=rid, build_id='preserved',
                bank=bank, validation={'pass': True}, open_to_students=True))
            db.add(BankState(user_id=STUDENT.id, subject='connections', run_id=rid,
                build_id='preserved', state=copy.deepcopy(prior), previous={'keep': 'older build'}))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)
    def post(url, data=None):
        response = client.post(url, json=data or {})
        assert response.status_code == 200, response.text
        return response.json()
    with patch('app.routes.bank.engine.now_ms', return_value=NOW):
        for rid in ['single', 'batch']:
            base = '/api/lectures/connections/' + rid + '/bank'
            selection = {'lectures': [{'subject': 'connections', 'runId': rid}]}
            def next_card():
                return post('/api/bank/batch/next', selection) if rid == 'batch' else post(base + '/next')
            root = next_card()
            assert root['question']['question_id'] == 'root'
            assert next_card()['reviewToken'] == root['reviewToken']
            post(base + '/reveal', {'reviewToken': root['reviewToken']})
            post(base + '/rate', {'reviewToken': root['reviewToken'], 'rating': 'Again'})
            detail = next_card()
            assert detail['question']['question_id'] == 'detail', 'failed root must not force repetition'
            # Returning to this card remains stable despite the new ordering policy.
            assert next_card()['reviewToken'] == detail['reviewToken']
            with SessionLocal() as db:
                row = db.get(QuizBank, ('connections', rid))
                saved = db.get(BankState, (STUDENT.id, 'connections', rid))
                assert row.bank == bank and row.build_id == saved.build_id == 'preserved'
                assert saved.previous == {'keep': 'older build'}
                assert saved.state['history'][0] == prior['history'][0]
                assert saved.state['items']['known'] == prior['items']['known']
                assert saved.state['sessions'] == prior['sessions']
                assert saved.state['excluded_question_decisions'] == prior['excluded_question_decisions']
                assert saved.state['history'][-1]['policy_version'] == DEFAULT['version']
    print('PASS: HTTP single/batch roots before details, failed-root progress, refresh tokens, original bank/build/history/due/session/private decisions')


if __name__ == '__main__':
    main()
