"""Owned local browser fixture for Main-Quiz 모아풀기: a fresh isolated database and two synthetic lectures."""
import os
from datetime import date
from fastapi import Request
from tests.root_support import setup, publish, document
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash

client, user, SessionLocal = setup()
publish(client, user)

from app.models import Lecture
with SessionLocal() as db:
    db.add(Lecture(subject='test', run_id='demo2', uid='root-demo2', date=date(2026, 11, 4), slot=1, slot_end=1,
                   start_time='09:00', title='Second synthetic lecture', professors=[], author='', version=1)); db.commit()

# Same synthetic shape, its own questions and title, so the page can tell the two lectures apart.
second = document()
second['title'] = 'Second root lecture'
second['bank_snapshot']['lecture_id'] = second['review']['lecture_id'] = 'test/demo2'
for q in second['bank_snapshot']['questions']:
    q['question'] = q['question'].replace('Synthetic question', 'Second question')
second['review']['bank_sha256'] = document_hash(second['bank_snapshot'])
for m, q in zip(second['review']['mappings'], second['bank_snapshot']['questions']):
    m['question_sha256'] = question_hash(q, second['bank_snapshot'])
user('admin', True)
ADMIN = '/api/admin/root-learning/lectures/test/demo2'
response = client.post(ADMIN, json=second); assert response.status_code == 200, response.text
response = client.put(ADMIN + '/publication', json={'revision': second['revision'], 'reviewed': True, 'enabled': True})
assert response.status_code == 200, response.text

from app.main import app
from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN


def test_user(request: Request):
    uid = request.headers.get('X-Root-Test-User', 'a')
    return CurrentUser(id=uid, email=f'{uid}@example.com', is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


app.dependency_overrides[get_current_user] = test_user
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('MAIN_QUIZ_BATCH_PORT', '8029')), log_level='warning')
