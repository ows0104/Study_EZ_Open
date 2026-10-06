"""Main Quiz 전환: 구 생성 중단, 기존 큐 종료, 은행 공개 범위."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-main-migration-"))
os.environ.update(
    ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver", RUNNER_TOKEN="runner-token",
)

from datetime import date

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.jobs.queue import ensure_auto_job
from app.main import app
from app.models import Asset, Lecture, PrequizJob, QuizBank
from app.routes.common import material_marks
from app.routes.admin import _checklist

ADMIN = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
KEY = ("약리학", "261002_02")


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=KEY[0], run_id=KEY[1], uid="migration-test", date=date(2026, 10, 2),
                       slot=2, slot_end=2, start_time="10:00", title="전환 검사", professors=[]))
        db.add(Asset(id="old-deck", subject=KEY[0], run_id=KEY[1], kind="main_apkg",
                     filename="old.apkg", object_key="old.apkg"))
        db.commit()
        assert ensure_auto_job(db, *KEY, "main", "필기 도착") is None
        assert not material_marks(db, [KEY])[KEY]["quiz"]
        assert _checklist({"main_apkg"}, None, {"main_apkg"})["bank"] == "todo"
        assert _checklist(set(), None, set(), {"usable": True, "open": False})["bank"] == "todo"
        assert _checklist(set(), None, set(), {"usable": True, "open": True})["bank"] == "done"
        bank = QuizBank(subject=KEY[0], run_id=KEY[1], bank={"questions": [{"question_id": "Q1"}]},
                        validation={"pass": True}, open_to_students=False)
        db.add(bank)
        db.commit()
        assert material_marks(db, [KEY], is_admin=True)[KEY]["quiz"]
        assert not material_marks(db, [KEY])[KEY]["quiz"]
        bank.open_to_students = True
        db.commit()
        assert material_marks(db, [KEY])[KEY]["quiz"]
        bank.validation = {"pass": False}
        db.commit()
        assert not material_marks(db, [KEY])[KEY]["quiz"]

        jobs = [PrequizJob(subject=KEY[0], run_id=KEY[1], kind="main", state=state)
                for state in ("queued", "held", "running")]
        jobs[-1].worker = "w1"
        db.add_all(jobs)
        db.commit()
        ids = [job.id for job in jobs]

    client = TestClient(app)
    overview = client.get("/api/admin/overview", headers=ADMIN).json()["lectures"][0]
    assert overview["bank"]["usable"] is False
    assert overview["checklist"]["bank"] == "todo"
    base = f"/api/admin/lectures/{KEY[0]}/{KEY[1]}/prequiz-job"
    assert client.post(base + "?kind=main", headers=ADMIN).status_code == 410
    # 다른 일꾼이 새 작업을 요청하면 옛 대기 건을 정리하고 실행 중 건에 중단 신호를 남긴다.
    assert client.post("/api/admin/prequiz-jobs/claim?worker=w2", headers=RUNNER).json()["job"] is None
    with SessionLocal() as db:
        assert [db.get(PrequizJob, i).state for i in ids[:2]] == ["canceled", "canceled"]
        assert db.get(PrequizJob, ids[-1]).cancel_requested
        assert db.get(Asset, "old-deck") is not None
        db.get(PrequizJob, ids[-1]).cancel_requested = False
        db.commit()
    heartbeat = client.put(f"/api/admin/prequiz-jobs/{ids[-1]}", headers=RUNNER, json={})
    assert heartbeat.json()["job"]["cancelRequested"]
    client.put(f"/api/admin/prequiz-jobs/{ids[-1]}", headers=RUNNER, json={"state": "canceled"})
    assert client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER).json()["job"] is None
    print("Main Quiz 전환 검사 통과")


if __name__ == "__main__":
    main()
