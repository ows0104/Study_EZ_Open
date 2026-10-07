"""예습의 두 선택은 모두 한 번만 진행하고, 청취 목표와 되돌리기를 보존한다."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from datetime import UTC, date, datetime, timedelta

_TMP = Path(tempfile.mkdtemp(prefix="studyez-preview-once-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
                  RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, QuizAttempt, PreReviewLog
from app.routes.common import prequiz_progress

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "preview", "261006_01"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid=f"{RUN}#preview", date=date(2026, 10, 6),
                       slot=1, slot_end=1, start_time="09:00", title="Preview", professors=[], author="", version=1))
        db.commit()
    client = TestClient(app)
    items = [{"id": f"c{i}", "qtype": "basic", "stem": f"Question {i}", "answer": f"Answer {i}",
              "challenge": i == 6, "learning_support": {"hint": "A clue", "scope": f"Scope {i}",
              "lecture_focus": f"Listen for {i}",
              **({"difficulty": "basic"} if i == 1 else {"difficulty": "advanced"} if i == 2
                 else {"difficulty": "challenge"} if i == 6 else {})}} for i in range(1, 7)]
    assert client.put(f"/api/admin/lectures/{SUBJECT}/{RUN}/pre-items", json={"items": items}, headers=RUNNER).status_code == 200
    assert client.post(f"{BASE}/prequiz/check", json={"itemId": "c1", "understood": True}).status_code == 401
    front = client.get(f"{BASE}/prequiz", headers=USER).json()
    assert len(front["items"]) == 6 and not front["items"][0]["learningScope"]
    assert "answer" not in front["items"][0]
    assert [entry["difficulty"] for entry in front["items"]] == ["basic", "advanced", None, None, None, "challenge"]
    reveal = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c1"}, headers=USER).json()
    assert reveal["learningScope"] == "Scope 1"
    assert all(value == {"days": 0, "seconds": 0} for value in reveal["next"].values())
    assert client.get(f"{BASE}/prequiz", headers=USER).json()["answered"] == 0
    for i in range(1, 7):
        response = client.post(f"{BASE}/prequiz/check", json={"itemId": f"c{i}", "understood": i == 1}, headers=USER)
        assert response.status_code == 200, response.text
        assert response.json()["attempt"]["dueAt"] is None
        if i == 5:
            partial = client.get(BASE, headers=USER).json()["prequiz"]
            assert partial["itemCount"] == 6 and partial["answered"] == 5 and partial["due"] == 1
            assert partial["missed"] == []  # the challenge badge still needs a choice
    detail = client.get(BASE, headers=USER).json()["prequiz"]
    assert detail["itemCount"] == detail["answered"] == 6, detail
    assert detail["due"] == detail["learning"] == detail["review"] == detail["later"] == 0
    assert len(detail["missed"]) == 5  # includes the challenge; no old three-card cap
    assert detail["missed"][0]["lectureFocus"] == "Listen for 2"
    assert detail["missed"][0]["difficulty"] == "advanced"
    with SessionLocal() as db:
        attempt = db.scalar(select(QuizAttempt))
        user_id = attempt.user_id
        for row in db.scalars(select(PreReviewLog)):
            row.reviewed_at = datetime.now(UTC) - timedelta(days=3)
        # Legacy scheduled attempts must not re-enter the preview queue.
        attempt.due_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
        assert prequiz_progress(db, user_id, [(SUBJECT, RUN)])[(SUBJECT, RUN)] == {"total": 6, "answered": 6}
    detail = client.get(BASE, headers=USER).json()["prequiz"]
    assert len(detail["missed"]) == 5 and detail["due"] == 0
    persisted = client.get(f"{BASE}/prequiz", headers=USER).json()
    assert persisted["items"][1]["lectureFocus"] == "Listen for 2"
    assert persisted["answered"] == 6
    assert persisted["items"][5]["attempt"]["correct"] is False
    assert persisted["items"][5]["lectureFocus"] == "Listen for 6"
    assert persisted["items"][5]["difficulty"] == "challenge"
    # Rereading changes the chosen target without clearing other completed cards.
    client.post(f"{BASE}/prequiz/check", json={"itemId": "c2", "understood": True}, headers=USER)
    assert len(client.get(BASE, headers=USER).json()["prequiz"]["missed"]) == 4
    undone = client.post(f"{BASE}/prequiz/undo", headers=USER).json()
    assert undone["itemId"] == "c2" and undone["attempt"]["correct"] is False
    undone = client.post(f"{BASE}/prequiz/undo", headers=USER).json()
    assert undone["itemId"] == "c6" and undone["attempt"] is None
    assert client.get(BASE, headers=USER).json()["prequiz"]["due"] == 1
    assert client.get(f"{BASE}/prequiz", headers=USER).json()["answered"] == 5
    with SessionLocal() as db:
        assert prequiz_progress(db, user_id, [(SUBJECT, RUN)])[(SUBJECT, RUN)] == {"total": 6, "answered": 5}
    # A challenge uses the same saved choice and undo path as every other question.
    for suffix, body in [("check", {"understood": True}), ("grade", {"grade": "easy"})]:
        response = client.post(f"{BASE}/prequiz/{suffix}", json={"itemId": "c6", **body}, headers=USER)
        assert response.status_code == 200 and response.json()["attempt"]["dueAt"] is None
        assert client.get(f"{BASE}/prequiz", headers=USER).json()["answered"] == 6
        assert client.post(f"{BASE}/prequiz/undo", headers=USER).json()["itemId"] == "c6"
    # Old clients can still save their choice, but no preview schedule is created.
    old = client.post(f"{BASE}/prequiz/grade", json={"itemId": "c5", "correct": False}, headers=USER).json()
    assert old["attempt"]["dueAt"] is None
    print("PASS: one-pass preview, durable targets, legacy due dates, challenge progress, calendar, undo, auth")


if __name__ == "__main__":
    main()
