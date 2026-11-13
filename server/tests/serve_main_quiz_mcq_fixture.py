"""Owned synthetic revision with 객관식 모드 선지(root-mcq/1) on isolated local study data only."""
import json, os, uuid
from fastapi import Request
from tests.root_support import setup, publish, document
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import mcq as contract

client, user, SessionLocal = setup()
doc = document()
questions = doc['bank_snapshot']['questions']
questions[0].update(question='Which ion does the enzyme bind?', answer='Fe2+', answer_units=['Fe2+'])
questions[1].update(format='list', question='List the vectors of epidemic typhus and murine typhus.', answer='Body louse; Rat flea',
                    answer_units=['Body louse', 'Rat flea'])
questions[2].update(format='ox', question='Rickettsia are obligate intracellular bacteria.', answer='O', answer_units=['O'])
doc['review']['bank_sha256'] = document_hash(doc['bank_snapshot'])
for m, q in zip(doc['review']['mappings'], questions):
    m['question_sha256'] = question_hash(q, doc['bank_snapshot'])
publish(client, user, doc)


def w(text, kind='subtle', basis='Fe2+→Fe3+'):
    return {'text': text, 'parts': [], 'kind': kind, 'basis': basis, 'why_wrong': 'not the answer here'}


WRONG = {'Q1': [w('Fe3+'), w('Cu2+', 'block', 'Wilson'), w('Zn2+', 'block', 'other'), w('Mg2+')],
         'Q2': [w('Chigger mite', 'block', 'Orientia'), w('Hard tick', 'block', 'RMSF'), w('Mosquito', 'block', 'Malaria')]}
asset = {'schema': contract.SCHEMA, 'revision': doc['revision'], 'skipped': {}, 'questions': {
    q['question_id']: contract.entry(q, WRONG[q['question_id']]) for q in questions[:2]}}
contract.validate(asset, doc)
from app.main import app
from app.models import Asset
from app.storage import ObjectStorage
from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN
body = json.dumps(asset).encode()
key = f"lectures/test/demo/root_mcq/{doc['revision']}.json"
ObjectStorage().put_bytes(key, body)
with SessionLocal() as db:
    db.add(Asset(id=str(uuid.uuid4()), subject='test', run_id='demo', kind='root_mcq', filename=f"{doc['revision']}.json",
                 object_key=key, size_bytes=len(body)))
    db.commit()


def test_user(request: Request):
    uid = request.headers.get('X-Root-Test-User', 'a')
    return CurrentUser(id=uid, email=f'{uid}@example.com', is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


app.dependency_overrides[get_current_user] = test_user
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('MAIN_QUIZ_UI_PORT', '8027')), log_level='warning')
