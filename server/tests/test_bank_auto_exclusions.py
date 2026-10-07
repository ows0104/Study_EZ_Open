"""실습·CBL·PBL의 자동 복습 제외와 관리자 직접 생성 검사."""
import os
import tempfile
from pathlib import Path
from datetime import date

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-exclusions-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
                  PUBLIC_API_BASE_URL="http://testserver", RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank, TimetableEvent
from app.jobs.queue import auto_review_excluded
from app.routes.admin import _auto_main_job


def main():
    Base.metadata.create_all(engine)
    cases = [("알코올 약력학 실습", True), ("CBL 2", True), ("pbl(1)", True),
             ("ＣＢＬ 3", True), ("C.B.L. 학습", True), ("P B L 1", True),
             ("순환기 약리 기초", False), ("ABCBL 약물 수송", False),
             ("현미경 관찰", True), ("증례 토의", True), ("파일 분류", True)]
    with SessionLocal() as db:
        db.add(TimetableEvent(id="practical", date=date(2026, 10, 8), start_time="09:00",
                             end_time="10:00", title="현미경 관찰", category="practice"))
        db.add(TimetableEvent(id="case-study", date=date(2026, 10, 8), start_time="10:00",
                             end_time="11:00", title="증례 토의", details="CBL", category="lecture"))
        for n, (title, _) in enumerate(cases, 1):
            key = f"261008_{n:02}"
            db.add(Lecture(subject="test", run_id=key, uid=key, date=date(2026, 10, 8),
                           slot=n, slot_end=n, start_time="09:00", title=title, professors=[],
                           timetable_event_id={9:"practical", 10:"case-study"}.get(n)))
        db.commit()
        db.add(Asset(id="file-category", subject="test", run_id="261008_11", kind="notes_current",
                     filename="[261008_11] PBL_필기.pdf", object_key="pbl.pdf"))
        db.commit()
        for n, (_, excluded) in enumerate(cases, 1):
            key = f"261008_{n:02}"
            assert auto_review_excluded(db, "test", key) is excluded
            job = _auto_main_job(db, db.get(Lecture, ("test", key)), {"notes_current"})
            assert (job is None) is excluded
            if excluded:
                assert db.get(QuizBank, ("test", key)) is None
        db.commit()
    client = TestClient(app)
    headers = {"Authorization": "Bearer local-test-token"}
    # 관리자의 출제 버튼에서 저장하는 응답 경로는 제외 규칙을 적용하지 않는다.
    for n in (1, 2, 3):
        base = f"/api/admin/lectures/test/261008_{n:02}"
        saved = client.put(base + "/bank-response", headers=headers,
                           json={"raw": "관리자 직접 출제 " * 40 + "STUDYEZ_BANK_COMPLETE"})
        assert saved.status_code == 200 and saved.json()["jobId"]
    print("실습·CBL·PBL 자동 제외와 관리자 직접 생성 검사 통과")


if __name__ == "__main__":
    main()
