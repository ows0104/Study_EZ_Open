"""Real review queues: every rating commits its prepared solo/batch question once."""

import copy
import datetime
from unittest.mock import patch

from tests.test_bank import STUDENT as USER
from tests.bank_fixtures import simulation_bank
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine as db_engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine import empty_state, record_review
from app.study_engine.memory import DAY_MS

NOW = 1792112400000


def main():
    Base.metadata.create_all(db_engine)
    app.dependency_overrides[get_current_user] = lambda: USER
    bank = simulation_bank()
    bank['questions'] = [q for q in bank['questions'] if q['retrieval_direction'] == 'direct']
    old = empty_state()
    for question in bank['questions']:
        old = record_review(bank, old, question['question_id'], 'Good', NOW - 30 * DAY_MS)
    client = TestClient(app)

    def post(path, body=None):
        response = client.post(path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()

    def snapshot():
        with SessionLocal() as db:
            return {row.run_id: copy.deepcopy(row.state) for row in db.scalars(select(BankState))}

    for batch in (False, True):
        for rating in ('Again', 'Hard', 'Good', 'Easy'):
            names = [f'{batch}-{rating}-{i}' for i in range(2 if batch else 1)]
            with SessionLocal() as db:
                for name in names:
                    db.add(Lecture(subject='prepared', run_id=name, uid='prepared-'+name,
                        date=datetime.date(2026, 10, 16), slot=1, slot_end=1, start_time='09:00', title=name))
                    db.flush()
                    db.add(QuizBank(subject='prepared', run_id=name, build_id='v1', status='ready',
                        open_to_students=True, bank=bank, validation={'pass': True}, pages={}))
                    db.flush()
                    db.add(BankState(user_id=USER.id, subject='prepared', run_id=name, build_id='v1', state=copy.deepcopy(old)))
                db.commit()
            lectures = [{'subject': 'prepared', 'runId': name} for name in names] if batch else None
            base = '/api/lectures/prepared/'+names[0]+'/bank'
            with patch('app.routes.bank.engine.now_ms', return_value=NOW):
                current = post('/api/bank/batch/next', {'lectures': lectures}) if batch else post(base+'/next?choiceProtocol=true')
                if batch:
                    base = '/api/lectures/prepared/'+current['lecture']['runId']+'/bank'
                body = {'reviewToken': current['reviewToken'], 'lectures': lectures}
                before = snapshot()
                frames = post(base+'/prepare-buffer', body)['frames']
                again = post(base+'/prepare-buffer', body)['frames']
                assert snapshot() == before, 'preparation wrote study state'
                def draws(window):
                    return {token: (frame['next']['question'], {grade: (nxt.get('question'), nxt.get('reviewToken'), nxt.get('selectionTicket'))
                            for grade, nxt in frame['previews'].items()}) for token, frame in window.items()}
                assert draws(frames) == draws(again), 'repeated preparation redrew rating branches'
                expected = frames[current['reviewToken']]['previews'][rating]
                assert expected.get('selectionTicket')
            with patch('app.routes.bank.engine.now_ms', return_value=NOW + 300_000):
                post(base+'/reveal', body)
                # Any additional weighted draw would fail /rate's advancement.
                with patch('app.study_engine.ordering.random.Random', side_effect=AssertionError('redraw')):
                    result = post(base+'/rate', {**body, 'rating': rating, 'advance': True, 'retrySafe': True,
                        'selectionTicket': expected['selectionTicket']})
                actual = result['next']
                assert actual['question'] == expected['question'], (batch, rating, result)
                assert actual['reviewToken'] == expected['reviewToken']
                assert actual.get('lecture') == expected.get('lecture')
                saved = snapshot()
                retry = post(base+'/rate', {**body, 'rating': rating, 'advance': True, 'retrySafe': True,
                    'selectionTicket': expected['selectionTicket']})['next']
                assert retry['question'] == actual['question'] and snapshot() == saved
                # All ratings have a second prepared step; Good retains three.
                steps = ('Easy',) * 5 if rating == 'Easy' else ('Good', 'Hard') if rating == 'Good' else ('Hard',)
                if steps:
                    for grade in steps:
                        current = actual
                        if batch:
                            base = '/api/lectures/prepared/'+current['lecture']['runId']+'/bank'
                        expected = frames[current['reviewToken']]['previews'][grade]
                        body = {'reviewToken': current['reviewToken'], 'lectures': lectures}
                        post(base+'/reveal', body)
                        with patch('app.study_engine.ordering.random.Random', side_effect=AssertionError('deep redraw')):
                            actual = post(base+'/rate', {**body, 'rating': grade, 'advance': True,
                                'selectionTicket': expected.get('selectionTicket')})['next']
                        assert actual.get('question') == expected.get('question')
                        if not actual.get('question'):
                            break
                        assert actual['reviewToken'] == expected['reviewToken']
    print('PASS: review-only solo/batch, all four ratings, stable repeated lookahead, five-minute delay, zero redraws, no preparation writes, idempotent retry')


if __name__ == '__main__':
    main()
