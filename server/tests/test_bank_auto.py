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
        assert _auto_main_job(db, lecture, {"notes_current"}) is None
        assert db.get(QuizBank, ("test", "261008_01")) is None
        assert db.query(PrequizJob).count() == 0
        db.add(Asset(id="notes", subject="test", run_id="261008_01", kind="notes_current",
                     filename="notes.pdf", object_key="notes.pdf", content_type="application/pdf"))
        db.commit()

    client = TestClient(app)
    base = "/api/admin/lectures/test/261008_01"
    assert client.post(base + '/prequiz-job?kind=bank', headers=ADMIN).status_code == 400
    request = {"raw": RAW, "conversationUrl": "https://chatgpt.com/c/web-test"}
    saved = client.put(base + '/bank-response', headers=ADMIN, json=request)
    assert saved.status_code == 200
    duplicate = client.put(base + '/bank-response', headers=ADMIN, json=request)
    assert duplicate.json()['reused']
    assert duplicate.json()['respondedAt'] == saved.json()['respondedAt']
    with SessionLocal() as db:
        job = db.query(PrequizJob).filter_by(kind='bank').one()
        job.state = 'running'
        db.commit()
    newer = {**request, 'raw': '새 문항 ' * 100 + '\nSTUDYEZ_BANK_COMPLETE'}
    assert client.put(base + '/bank-response', headers=ADMIN, json=newer).status_code == 409
    with SessionLocal() as db:
        assert db.get(QuizBank, ('test', '261008_01')).raw_response == RAW
        job = db.query(PrequizJob).filter_by(kind='bank').one()
        job.state = 'done'
        db.commit()
    assert client.put(base + '/bank-response', headers=ADMIN, json=newer).status_code == 200
    with SessionLocal() as db:
        assert db.query(PrequizJob).filter_by(kind='bank').count() == 2
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
    print("웹 응답 자동 검수·게시 및 중복·경합 검사 통과")


if __name__ == "__main__":
    main()
