"""Owned synthetic revision with 공용 선지(root-mcq/2, 2026-11-14 choices-merge) on isolated local study data only.

화면 확인용: 오답 풀(족보 출처 포함)에서 4~5개가 보이고, 주관식 V·객관식 모드가 같은 선지를 쓰고, 답면에 「왜 틀렸나」가 나온다.
아무 폴더에서 띄워도 되게 server/와 저장소 루트를 import 경로에 넣는다(격리 sqlite·로컬 저장소, 운영 DB를 부르지 않는다).

    server/.venv/Scripts/python.exe server/tests/serve_main_quiz_choices_v2_fixture.py   # 127.0.0.1:8000(웹 개발 프록시 기본값)
"""
import json
import os
import sys
import uuid
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
os.chdir(SERVER)
sys.path[:0] = [str(SERVER), str(SERVER.parent)]

from fastapi import Request  # noqa: E402
from tests.root_support import setup, publish, document  # noqa: E402
from studyez_contracts.learning_links import question_hash  # noqa: E402
from studyez_contracts.roots import document_hash  # noqa: E402
from studyez_contracts.roots import mcq as contract  # noqa: E402

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

NO_JOKBO = {k: '' for k in contract.JOKBO_KEYS}


def w(text, source='made', why='not the answer here', jokbo=None):
    return {'text': text, 'parts': [], 'source': source, 'basis': 'b', 'why_tempting': 'looks close',
            'why_wrong': why, 'jokbo': jokbo or NO_JOKBO}


WRONG = {'Q1': [w('Fe3+', why='Fe3+ is the oxidized form; this enzyme binds the reduced ion.',
                  source='jokbo', jokbo={**NO_JOKBO, 'year': '2022', 'number': '45', 'professor': 'Kim'}),
                w('Cu2+', 'block', 'Copper is the Wilson disease ion, not this cofactor.'), w('Zn2+', 'lecture', 'Zinc fingers bind DNA.'),
                w('Mg2+', why='Magnesium stabilises ATP, not this site.'), w('Mn2+', why='Manganese belongs to SOD2.'),
                w('Ca2+', why='Calcium is the second messenger here.'), w('Co2+', why='Cobalt sits in B12.')],
         'Q2': [w('Chigger mite', 'block', 'Chiggers carry Orientia (scrub typhus).'), w('Hard tick', 'block', 'Ticks carry RMSF.'),
                w('Mosquito', 'block', 'Mosquitoes carry malaria, not typhus.'), w('Sand fly', why='Sand flies carry Leishmania.'),
                w('Tsetse fly', why='Tsetse flies carry trypanosomes.')]}
asset = {'schema': contract.SCHEMA_V2, 'revision': doc['revision'], 'skipped': {}, 'questions': {
    q['question_id']: contract.entry_v2(q, WRONG[q['question_id']]) for q in questions[:2]}}
contract.validate_v2(asset, doc)
from app.main import app  # noqa: E402
from app.models import Asset  # noqa: E402
from app.storage import ObjectStorage  # noqa: E402
from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN  # noqa: E402
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
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('MAIN_QUIZ_UI_PORT', '8000')), log_level='warning')
