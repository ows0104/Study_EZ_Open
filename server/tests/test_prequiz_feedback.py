"""예습 제보의 원문 보존·권한·충돌 검사와 학습 기록 분리를 로컬 DB에서 확인한다."""
import os
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import quote

_TMP = Path(tempfile.mkdtemp(prefix="studyez-prequiz-feedback-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver")

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.auth import CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, PreItem, QuizAttempt, PreReviewLog, SiteFeedback

SUBJECT, RUN = "약리학", "261012_01"
ADMIN = {"Authorization": "Bearer local-test-token"}


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid=f"{RUN}#feedback", date=date(2026, 10, 12),
                       slot=1, slot_end=1, start_time="09:00", title="약물수송체", professors=[], author="", version=1))
        db.flush()
        db.add(PreItem(subject=SUBJECT, run_id=RUN, item_id="c001", qtype="basic", stem="어떤 수송체인가?",
                       answer="NCC", explanation="공동수송체", why_asked="기전을 이해하기 위해",
                       source_anchor="p12", slide_no=12, learning_support={
                           "hint": "표적을 떠올린다", "scope": "수송체 구분", "lecture_focus": "억제 기전",
                           "study_track": "extra"}))
        db.commit()
    client = TestClient(app)
    payload = {"subject": SUBJECT, "runId": RUN, "itemId": "c001", "category": "wording",
               "stem": "어떤 수송체인가?", "message": "  약물명이 빠져 있어요.  ", "page": "/untrusted-page"}
    assert client.post("/api/feedback/prequiz", json=payload).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("pending", "p@example.com", False)
    assert client.post("/api/feedback/prequiz", json=payload).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("student", "s@example.com", False, {"studyez": "member"})
    response = client.post("/api/feedback/prequiz", json=payload)
    assert response.status_code == 201, response.text
    assert set(response.json()) == {"id"}  # 답을 안 펴도 제보할 수 있으나 답을 응답하지 않는다.
    assert client.get("/api/admin/feedback").status_code == 403
    for change, status in [({"message": "  "}, 422), ({"message": "x" * 4001}, 422),
                           ({"category": "bad"}, 422), ({"itemId": "missing"}, 404),
                           ({"runId": "another"}, 404), ({"subject": "다른 과목"}, 404),
                           ({"stem": "옛 질문"}, 409), ({"answer": "옛 답"}, 409),
                           ({"explanation": "옛 설명"}, 409)]:
        actual = client.post("/api/feedback/prequiz", json={**payload, **change})
        assert actual.status_code == status, (change, actual.text)
    response = client.post("/api/feedback/prequiz", json={**payload, "category": "content", "answer": "NCC",
                                                         "explanation": "공동수송체", "message": "x" * 4000})
    assert response.status_code == 201, response.text  # 스냅샷은 의견의 길이 제한에 포함하지 않는다.
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SiteFeedback)) == 2
        assert db.scalar(select(func.count()).select_from(QuizAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(PreReviewLog)) == 0
        item = db.get(PreItem, (SUBJECT, RUN, "c001"))
        item.answer = "수정된 답"
        db.commit()
    app.dependency_overrides.clear()
    rows = client.get("/api/admin/feedback", headers=ADMIN).json()
    row = next(row for row in rows if row["id"] == response.json()["id"])
    assert "답: NCC" in row["message"] and "수정된 답" not in row["message"]
    assert len(row["message"]) > 4000
    first = rows[-1]
    assert first["email"] == "s@example.com"
    assert first["page"] == f"/prequiz/{quote(SUBJECT, safe='')}/{RUN}"
    for text in ["[예습 퀴즈 문항 제보]", "문항 ID: c001", "유형: 질문이 모호해요"]:
        assert text in first["message"]
    for text in ["학습 구분: 추가 학습", "설명: 공동수송체", "힌트: 표적을 떠올린다", "근거: p12", "슬라이드: 12"]:
        assert text in first["message"]
    assert first["status"] == "open" and first["screenshots"] == []
    print("예습 제보: 원문 보존·권한·문항 충돌·긴 내용·학습 기록 분리 통과")


if __name__ == "__main__":
    main()
