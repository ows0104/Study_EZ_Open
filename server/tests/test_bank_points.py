"""Button-triggered original-only preparation is independent of WEB responses."""
import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-points-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, PrequizJob, QuizBank

ADMIN = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
KEY = ("test", "261014_01")
BASE_URL = "/api/admin/lectures/test/261014_01"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=KEY[0], run_id=KEY[1], uid="points-test", date=date(2026, 10, 14),
                       slot=1, slot_end=1, start_time="10:00", title="원본 독립 추출", professors=[]))
        db.commit()
    client = TestClient(app)
    jobs = BASE_URL + "/prequiz-job?kind=points"
    assert client.post(jobs, headers=ADMIN).status_code == 400
    with SessionLocal() as db:
        db.add(Asset(id="notes", subject=KEY[0], run_id=KEY[1], kind="notes_current", filename="notes.pdf",
                     object_key="notes.pdf", content_type="application/pdf"))
        db.commit()
    first = client.post(jobs, headers=ADMIN)
    assert first.status_code == 200 and first.json()["created"]
    again = client.post(jobs, headers=ADMIN)
    assert again.json()["job"]["id"] == first.json()["job"]["id"] and not again.json()["created"]
    with SessionLocal() as db:
        assert db.query(PrequizJob).count() == 1 and db.get(QuizBank, KEY) is None
        db.add(QuizBank(subject=KEY[0], run_id=KEY[1], status="linked", raw_response="private WEB data",
                       bank={"questions": [{"private": "bank data"}]}))
        db.commit()
    response = client.get(BASE_URL + "/bank/source-context", headers=RUNNER)
    assert response.status_code == 200
    context = response.json()
    assert set(context) == {"title", "sources"}
    assert context["sources"] == [{"id": "S1", "kind": "notes_current", "filename": "notes.pdf"}]
    assert "private" not in response.text
    with SessionLocal() as db:
        assert db.get(QuizBank, KEY).status == "linked"
    claimed = client.post("/api/admin/prequiz-jobs/claim?worker=w1", headers=RUNNER).json()["job"]
    assert claimed["kind"] == "points" and claimed["state"] == "running"
    again = client.post(jobs, headers=ADMIN)
    assert again.json()['job']['id'] == claimed['id'] and not again.json()['created']
    # The normal content job waits for preparation on the same lecture.
    raw = '문항 본문 ' * 100 + '\nSTUDYEZ_BANK_COMPLETE'
    response = client.put(BASE_URL + '/bank-response', headers=ADMIN,
                          json={'raw': raw, 'conversationUrl': 'https://chatgpt.com/c/test-complete'})
    assert response.status_code == 200, response.text
    first_time = response.json()['respondedAt']
    duplicate = client.put(BASE_URL + '/bank-response', headers=ADMIN,
                           json={'raw': raw, 'conversationUrl': 'https://chatgpt.com/c/test-complete'})
    assert duplicate.json()['reused'] and duplicate.json()['respondedAt'] == first_time
    with SessionLocal() as db:
        assert db.query(PrequizJob).filter_by(kind='bank').count() == 1
    assert client.post("/api/admin/prequiz-jobs/claim?worker=w2", headers=RUNNER).json()["job"] is None
    with SessionLocal() as db:
        db.get(PrequizJob, claimed['id']).state = 'done'
        db.commit()
    completed = client.post(jobs, headers=ADMIN, json={'force': True})
    assert completed.json()['job']['id'] == claimed['id'] and not completed.json()['created']
    with SessionLocal() as db:
        assert db.query(PrequizJob).filter_by(kind='points').count() == 1
        db.get(Asset, 'notes').size_bytes = 99
        db.commit()
    changed = client.post(jobs, headers=ADMIN)
    assert changed.json()['created'] and changed.json()['job']['id'] != claimed['id']
    print("Independent point job and original-only source context passed")


if __name__ == "__main__":
    main()
