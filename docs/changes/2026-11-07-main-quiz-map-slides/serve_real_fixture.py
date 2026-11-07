"""Isolated local API with the published 감염병리1 (261104_02) Main-Quiz document and its frozen PDF.

Read-only inputs (never modified): the curated result and S1.pdf kept by the publication run.
Everything written goes to a fresh SQLite DB and local storage under server/local_test_data/.
No production DB, R2 or learning record is touched (server/.env is not loaded: setup() fixes env).

  cd server && ../server/.venv/Scripts/python.exe ../docs/changes/2026-11-07-main-quiz-map-slides/serve_real_fixture.py <curated-result.json> <S1.pdf>
"""
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'server'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.root_support import setup
from fastapi import Request

result_path, pdf_path = Path(sys.argv[1]), Path(sys.argv[2])
client, user, SessionLocal = setup()
from app.main import app
from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent, RootControl
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

doc = json.loads(result_path.read_text(encoding='utf-8'))['document']
body = pdf_path.read_bytes()
source = doc['review']['sources'][0]
assert hashlib.sha256(body).hexdigest() == source['sha256'], 'frozen PDF does not match the reviewed source'
key = f"lectures/root-reviewed-import/{source['sha256']}/{source['source_id']}"
ObjectStorage().put_bytes(key, body)
with SessionLocal() as db:
    db.add(RootContent(subject='test', run_id='demo', revision=doc['revision'], document=doc, digest=document_hash(doc), reviewed=True))
    db.add(RootControl(subject='test', run_id='demo', revision=doc['revision'], enabled=True, allowed_users=[]))
    db.add(RootGeneration(id='r' * 32, job_id=30001, subject='test', run_id='demo', user_id='fixture', request_id='fixture',
        input_digest=source['sha256'], baseline='0' * 64, packet={'revision': doc['revision'], 'sources': [
            {'id': source['source_id'], 'sha256': source['sha256'], 'filename': source['label'], 'snapshotKey': key,
             'pageCount': source['page_count'], 'contentType': 'application/pdf'}]},
        result={'sourceAudit': {'question_checks': {'reviews': []}, 'input_issues': []}, 'medical': {'reviews': []},
                'validation': {'errors': [], 'warnings': []}}, result_digest='1' * 64))
    db.commit()


def test_user(request: Request):
    uid = request.headers.get('X-Root-Test-User', 'a')
    return CurrentUser(id=uid, email=f'{uid}@example.com', is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


app.dependency_overrides[get_current_user] = test_user
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('MAIN_QUIZ_REAL_PORT', '8037')), log_level='warning')
