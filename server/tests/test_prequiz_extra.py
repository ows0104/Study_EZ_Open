"""선택 추가 학습은 저장되지만 필수 완료·캘린더·미완료 수에 섞이지 않는다."""
import os
import tempfile
from pathlib import Path
from datetime import date

_TMP = Path(tempfile.mkdtemp(prefix="studyez-extra-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
                  RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, QuizAttempt
from app.routes.common import prequiz_progress

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "extra", "261007_01"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid=f"{RUN}#extra", date=date(2026, 10, 7),
                       slot=1, slot_end=1, start_time="09:00", title="Extra", professors=[], author="", version=1))
        db.commit()
    client = TestClient(app)
    items = [{"id": f"c{i}", "qtype": "basic", "stem": f"Question {i}", "answer": f"Answer {i}",
              "learning_support": {"difficulty": "basic", **({"study_track": "extra"} if i > 8 else {})}}
             for i in range(1, 14)]
    response = client.put(f"/api/admin/lectures/{SUBJECT}/{RUN}/pre-items", json={"items": items}, headers=RUNNER)
    assert response.status_code == 200, response.text
    front = client.get(f"{BASE}/prequiz", headers=USER).json()
    assert len(front["items"]) == 13 and front["answered"] == 0
    assert sum(row["studyTrack"] == "extra" for row in front["items"]) == 5
    detail = client.get(BASE, headers=USER).json()["prequiz"]
    assert detail["itemCount"] == detail["due"] == 8, detail
    for i in range(1, 9):
        assert client.post(f"{BASE}/prequiz/check", json={"itemId": f"c{i}", "understood": i != 1}, headers=USER).status_code == 200
    detail = client.get(BASE, headers=USER).json()["prequiz"]
    assert detail["itemCount"] == detail["answered"] == 8 and detail["due"] == 0, detail
    assert [row["itemId"] for row in detail["missed"]] == ["c1"] and detail["extraMissed"] == []
    client.post(f"{BASE}/prequiz/check", json={"itemId": "c9", "understood": False}, headers=USER)
    front = client.get(f"{BASE}/prequiz", headers=USER).json()
    assert front["answered"] == 8 and front["correct"] == 7
    assert next(row for row in front["items"] if row["itemId"] == "c9")["attempt"]["correct"] is False
    detail = client.get(BASE, headers=USER).json()["prequiz"]
    assert detail["due"] == 0 and detail["answered"] == 8
    assert [row["itemId"] for row in detail["extraMissed"]] == ["c9"]
    with SessionLocal() as db:
        user_id = db.scalar(select(QuizAttempt.user_id))
        assert prequiz_progress(db, user_id, [(SUBJECT, RUN)])[(SUBJECT, RUN)] == {"total": 8, "answered": 8}
    undone = client.post(f"{BASE}/prequiz/undo", headers=USER).json()
    assert undone["itemId"] == "c9" and undone["attempt"] is None
    assert client.get(BASE, headers=USER).json()["prequiz"]["due"] == 0
    undone = client.post(f"{BASE}/prequiz/undo", headers=USER).json()
    assert undone["itemId"] == "c8"
    assert client.get(BASE, headers=USER).json()["prequiz"]["due"] == 1
    print("PASS: optional extras persist independently of required completion, calendar and undo")


if __name__ == "__main__":
    main()
