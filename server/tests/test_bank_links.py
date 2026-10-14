"""Link-only saving, independent CLI sessions, and private data boundaries."""
import os
import tempfile
from pathlib import Path
from datetime import date

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-links-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
                  PUBLIC_API_BASE_URL="http://testserver", RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, PrequizJob, Preview, QuizBank

ADMIN = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
KEY = ("test", "261013_01")
BASE = "/api/lectures/test/261013_01"
ADMIN_BASE = "/api/admin/lectures/test/261013_01"
SHARE = "https://chatgpt.com/share/bank-links"
MINE = "https://chatgpt.com/c/bank-links"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=KEY[0], run_id=KEY[1], uid="links-test", date=date(2026, 10, 13),
                       slot=1, slot_end=1, start_time="10:00", title="링크 분리 검사", professors=[]))
        db.commit()
    client = TestClient(app)
    links = ADMIN_BASE + "/bank/links"
    assert client.put(links, headers=ADMIN, json={"conversationUrl": MINE}).status_code == 200
    assert client.put(links, headers=ADMIN, json={"shareUrl": SHARE}).json() == {
        "conversationUrl": MINE, "shareUrl": SHARE}
    with SessionLocal() as db:
        row = db.get(QuizBank, KEY)
        assert row.status == "linked" and row.responded_at is None and not row.raw_response
        assert db.query(PrequizJob).count() == 0 and db.get(Preview, KEY) is None
    detail = client.get(BASE, headers=ADMIN).json()["bank"]
    assert detail["conversationUrl"] == MINE and detail["shareUrl"] == SHARE and not detail["usable"]
    assert client.put(links, headers=ADMIN, json={"shareUrl": "https://evil.example/share/test"}).status_code == 422
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student", email="s@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    student = client.get(BASE).json()["bank"]
    assert student["shareUrl"] == SHARE and not student["usable"] and "conversationUrl" not in student
    assert client.get(BASE + "/bank").status_code == 404
    assert client.put(links, json={"shareUrl": SHARE}).status_code == 403
    app.dependency_overrides.clear()
    jobs = ADMIN_BASE + "/prequiz-job?kind=bank"
    assert client.post(jobs, headers=ADMIN, json={"force": True}).status_code == 400
    with SessionLocal() as db:
        db.add(Asset(id="notes", subject=KEY[0], run_id=KEY[1], kind="notes_current",
                     filename="notes.pdf", object_key="notes.pdf", content_type="application/pdf"))
        db.commit()
    assert client.post(jobs, headers=ADMIN, json={"force": True}).status_code == 400
    raw = "Web response " * 30 + "STUDYEZ_BANK_COMPLETE"
    requested = client.put(ADMIN_BASE + '/bank-response', headers=ADMIN, json={'raw': raw})
    assert requested.status_code == 200
    assert client.post(jobs, headers=ADMIN).json()["job"]["id"] == requested.json()["jobId"]
    got = client.get(ADMIN_BASE + "/bank-response", headers=RUNNER).json()
    assert got["respondedAt"] and got["raw"] == raw  # CLI reviews the WEB questions.
    for validation in (None, {"pass": False, "errors": ["CLI validation failed"]}):
        payload = {"respondedAt": got["respondedAt"], "message": "CLI failure"}
        if validation:
            payload.update(bank={"questions": [], "concepts": []}, validation=validation)
        assert client.put(ADMIN_BASE + "/bank", headers=RUNNER, json=payload).status_code == 200
        assert client.put(links, headers=ADMIN, json={"conversationUrl": MINE + "-updated"}).status_code == 200
        detail = client.get(BASE, headers=ADMIN).json()["bank"]
        assert detail["shareUrl"] == SHARE and detail["conversationUrl"] == MINE + "-updated"
        assert detail["respondedAt"] == got["respondedAt"]
    # Existing raw-response clients cannot implicitly erase independently saved links.
    raw = "Old response " * 30 + "STUDYEZ_BANK_COMPLETE"
    assert client.put(ADMIN_BASE + "/bank-response", headers=ADMIN, json={"raw": raw}).status_code == 200
    detail = client.get(BASE, headers=ADMIN).json()["bank"]
    assert detail["shareUrl"] == SHARE and detail["conversationUrl"] == MINE + "-updated"
    assert client.put(links, headers=ADMIN, json={"shareUrl": ""}).json()["conversationUrl"] == MINE + "-updated"
    with SessionLocal() as db:
        assert db.query(PrequizJob).count() == 1
    print("Problem bank links and WEB-to-CLI Main-Quiz handoff passed")


if __name__ == "__main__":
    main()
