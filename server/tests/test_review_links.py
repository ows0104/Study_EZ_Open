"""개인 복습 저장은 예습·다른 사용자·다른 강의와 독립적이다."""
from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-review-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'review.db').as_posix()}")

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Lecture  # noqa: E402


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="약리학", run_id="261006_01", uid="review-test",
                       date=date(2026, 10, 6), slot=1, slot_end=1, start_time="09:00", title="약동학"))
        db.commit()
    client = TestClient(app)
    base = "/api/lectures/약리학/261006_01"
    user = CurrentUser(id="student-a", email="a@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    app.dependency_overrides[get_current_user] = lambda: user
    preview = {"provider": "gemini", "conversationUrl": "https://gemini.google.com/app/preview"}
    review = {"provider": "chatgpt", "conversationUrl": "https://chatgpt.com/c/review"}
    assert client.put(f"{base}/my-preview", json=preview).status_code == 200
    assert client.put(f"{base}/my-review", json=review).status_code == 200
    detail = client.get(base).json()
    assert detail["myPreview"] == preview
    assert detail["myReview"] == review
    assert detail["preview"] is None
    print("PASS: 학생 복습 링크 저장 · 예습 및 기본 링크 보존")

    user = CurrentUser(id="student-b", email="b@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    detail = client.get(base).json()
    assert detail["myReview"] is None and detail["myPreview"] is None
    other = {"provider": "claude", "conversationUrl": "https://claude.ai/chat/review-b"}
    assert client.put(f"{base}/my-review", json=other).status_code == 200
    assert client.get(base).json()["myReview"] == other
    print("PASS: 다른 계정은 자기 복습 링크만 저장 및 조회")

    user = CurrentUser(id="student-a", email="a@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    assert client.get(base).json()["myReview"] == review
    assert client.put(f"{base}/my-review", json=other | {"provider": "gemini"}).status_code == 422
    assert client.put(f"{base}/my-review", json=review | {"conversationUrl": "https://chatgpt.com/share/public"}).status_code == 422
    assert client.put("/api/lectures/약리학/missing/my-review", json=review).status_code == 404
    assert client.put(f"{base}/my-review", json=review | {"conversationUrl": ""}).status_code == 200
    detail = client.get(base).json()
    assert detail["myReview"] is None and detail["myPreview"] == preview
    app.dependency_overrides.clear()
    assert client.put(f"{base}/my-review", json=review).status_code == 401
    print("PASS: URL 검증 · 삭제 독립성 · 강의 및 로그인 검증")


if __name__ == "__main__":
    main()
