"""Old open jobs remain visible beyond the recent-history window."""
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-job-board-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  RUNNER_TOKEN="local-runner-token")

from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import PrequizJob


def main():
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with SessionLocal() as db:
        for i, state in enumerate(("running", "queued", "held")):
            db.add(PrequizJob(subject="test", run_id=f"old-{state}", kind="bank", state=state,
                              created_at=now-timedelta(days=10), queue_rank=-i))
        for i in range(55):
            db.add(PrequizJob(subject="test", run_id=f"done-{i}", kind="bank", state="done",
                              created_at=now+timedelta(seconds=i)))
        db.commit()
    client = TestClient(app)
    headers = {"Authorization": "Bearer local-test-token"}
    response = client.get("/api/admin/prequiz-jobs", headers=headers)
    assert response.status_code == 200, response.text
    board = response.json()
    assert [j["runId"] for j in board["running"]] == ["old-running"]
    assert [j["runId"] for j in board["waiting"]] == ["old-queued"]
    assert [j["runId"] for j in board["held"]] == ["old-held"]
    assert len(board["jobs"]) == 53
    queued = board["waiting"][0]
    moved = client.post(f"/api/admin/prequiz-jobs/{queued['id']}/move", headers=headers,
                        json={"to": "back"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["waiting"][0]["runId"] == "old-queued"
    print("PASS: old running, queued and held jobs remain visible and movable after 55 newer completions")


if __name__ == "__main__":
    main()
