"""Collect all open reports without exposing contacts or reused stale questions."""

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-feedback-collection-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import BankFeedback, Lecture, QuizBank, SiteFeedback  # noqa: E402
from app.storage import ObjectStorage  # noqa: E402
from runner.feedback import collect, reconcile  # noqa: E402


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="검증", run_id="261008_01", uid="lecture", date=date(2026, 10, 8),
                       slot=1, slot_end=1, start_time="09:00", title="검증"))
        db.flush()
        db.add(QuizBank(subject="검증", run_id="261008_01", build_id="new", status="ready",
                        bank={"questions": [{"question_id": "Q1", "question": "현재 문항"}]}))
        for build_id in ("new", "old"):
            db.add(BankFeedback(user_id="private-user", subject="검증", run_id="261008_01",
                                build_id=build_id, question_id="Q1", category="wording", comment="제보",
                                highlighted=build_id == "old",
                                correction={"original": {"question": f"{build_id} 원문", "answer": "원래 정답"},
                                            "proposed": {"question": "수정 발문", "answer": "수정 정답"},
                                            "changedFields": ["question", "answer"]}))
        db.add(BankFeedback(user_id="private-user", subject="검증", run_id="261008_01",
                            build_id="new", question_id="Q1", category="good"))
        for i in range(205):
            db.add(SiteFeedback(user_id="private-user", email="private@example.com", message=f"제보 {i}"))
        db.add(SiteFeedback(user_id="private-user", email="private@example.com", message="닫힌 제보", status="resolved"))
        db.commit()
    items = collect(_TMP / "home")
    assert len(items) == 207
    assert len([item for item in items if item["kind"] == "site"]) == 205
    bank = [item for item in items if item["kind"] == "question"]
    assert bank[0]["question"]["question"] == "현재 문항"
    assert bank[1]["stale"] and bank[1]["question"] is None
    assert not bank[0]["highlighted"] and bank[1]["highlighted"]
    assert bank[0]["correction"]["proposed"]["answer"] == "수정 정답"
    assert bank[1]["correction"]["original"]["question"] == "old 원문"
    ledger = reconcile({}, items)
    assert all(ledger["items"][item["id"]]["state"] == "pending" for item in bank)
    assert ledger["items"][bank[0]["id"]]["source"]["correction"] == bank[0]["correction"]
    assert "private@example.com" not in str(items) and "private-user" not in str(items)
    with engine.connect() as connection:
        try:
            connection.execute(text("UPDATE site_feedback SET message = 'must not write'"))
        except OperationalError:
            pass
        else:
            raise AssertionError("Collection connection allowed a database write")
        connection.rollback()
        connection.execute(text("PRAGMA query_only = OFF"))
    with SessionLocal() as db:
        assert db.scalar(select(SiteFeedback.message).where(SiteFeedback.id == 1)) == "제보 0"
    print("수집: 200건 초과·닫힌/좋은 신고 제외·연락처 제거·오래된 빌드·DB 읽기 전용 모두 통과")


if __name__ == "__main__":
    main()
