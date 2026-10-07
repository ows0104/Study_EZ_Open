"""새 필기 자동 출제, 중복·취소·상한, 수동 응답과의 경합 검사."""
import os
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-auto-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
                  PUBLIC_API_BASE_URL="http://testserver", RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, PrequizJob, QuizBank
from app.routes.admin import _auto_main_job
from tests.bank_fixtures import example_bank

ADMIN = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
RAW = "문제은행 응답 " * 50 + "\nSTUDYEZ_BANK_COMPLETE"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for n in range(1, 7):
            lecture = Lecture(subject="test", run_id=f"261008_{n:02}", uid=f"auto-{n}",
                              date=date(2026, 10, 8), slot=n, slot_end=n, start_time="10:00", title="자동 출제", professors=[])
            db.add(lecture)
        db.commit()
        lecture = db.get(Lecture, ("test", "261008_01"))
        assert _auto_main_job(db, lecture, {"notes_prev", "jokbo"}) is None
        job = _auto_main_job(db, lecture, {"notes_current"})
        assert job["kind"] == "bank" and job["state"] == "queued" and job["origin"] == "auto"
        db.commit()
        assert _auto_main_job(db, lecture, {"notes_current"}) is None
        assert _auto_main_job(db, lecture, set()) is None
        row = db.get(QuizBank, ("test", "261008_01"))
        assert row.responded_at and not row.raw_response and not row.open_to_students
        db.add(Asset(id="notes", subject="test", run_id="261008_01", kind="notes_current",
                     filename="notes.pdf", object_key="notes.pdf", content_type="application/pdf"))
        # 저장된 답과 완성된 은행은 자동 업로드로 덮지 않는다.
        db.add(QuizBank(subject="test", run_id="261008_02", raw_response=RAW))
        db.add(QuizBank(subject="test", run_id="261008_03", bank={"questions": []}))
        db.add(PrequizJob(subject="test", run_id="261008_04", kind="bank", state="canceled"))
        db.commit()
        for n in (2, 3, 4):
            assert _auto_main_job(db, db.get(Lecture, ("test", f"261008_{n:02}")), {"notes_current"}) is None
        with patch("app.jobs.queue.auto_used_today", return_value=999):
            held = _auto_main_job(db, db.get(Lecture, ("test", "261008_05")), {"notes_current"})
            assert held["state"] == "held"
        db.commit()

    client = TestClient(app)
    base = "/api/admin/lectures/test/261008_01"
    got = client.get(base + "/bank-response", headers=RUNNER)
    assert got.status_code == 200 and got.json()["raw"] == ""
    assert got.json()["sources"][0]["id"] == "S1"
    token = got.json()["respondedAt"]
    payload = {"respondedAt": token, "raw": RAW, "promptVersion": "1.15"}
    assert client.put(base + "/bank-generated-response", headers=RUNNER,
                      json={**payload, "raw": "미완성 " * 50}).status_code == 422
    assert client.put(base + "/bank-generated-response", headers=RUNNER,
                      json={**payload, "respondedAt": "stale"}).status_code == 409
    assert client.put(base + "/bank-generated-response", headers=RUNNER, json=payload).status_code == 200
    assert client.put(base + "/bank-generated-response", headers=RUNNER, json=payload).status_code == 409
    assert client.get(base + "/bank-response", headers=RUNNER).json()["raw"] == RAW
    manual = client.put(base + "/bank-response", headers=ADMIN, json={"raw": RAW + "手動"})
    assert manual.status_code == 200
    assert client.put(base + "/bank-generated-response", headers=RUNNER, json=payload).status_code == 409
    with SessionLocal() as db:
        assert len(db.scalars(select(PrequizJob).where(PrequizJob.run_id == "261008_01")).all()) == 1
        row = db.get(QuizBank, ("test", "261008_01"))
        assert row.raw_response == RAW + "手動" and not row.open_to_students
    token = client.get(base + "/bank-response", headers=RUNNER).json()["respondedAt"]
    result = {"respondedAt": token, "bank": example_bank(),
              "validation": {"pass": True, "errors": [], "warnings": []}}
    assert client.put(base + "/bank", headers=RUNNER, json=result).json()["status"] == "ready"
    assert client.get(base + "/bank", headers=ADMIN).json()["summary"]["open"] is True
    # 업로드의 검증 실패는 공개 상태로 남기지 않는다.
    result["validation"] = {"pass": False, "errors": ["invalid"], "warnings": []}
    assert client.put(base + "/bank", headers=RUNNER, json=result).json()["status"] == "invalid"
    assert client.get(base + "/bank", headers=ADMIN).json()["summary"]["open"] is False
    assert client.put(base + "/bank/open", headers=ADMIN, json={"open": True}).status_code == 409
    assert client.put(base + "/bank", headers=RUNNER,
                      json={"respondedAt": token, "message": "출제 실패"}).json()["status"] == "failed"
    assert client.get(base + "/bank", headers=ADMIN).json()["summary"]["open"] is False
    print("Quiz Bank 자동 출제 검사 통과")


if __name__ == "__main__":
    main()
