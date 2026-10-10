"""개인 예습·복습 프롬프트의 저장, 초기화와 계정 격리를 검사한다."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-prompts-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'prompts.db').as_posix()}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text, inspect  # noqa: E402
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user  # noqa: E402
from app.cli import ensure_columns  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Profile  # noqa: E402


def main() -> None:
    # 운영의 기존 profile에 새 칼럼을 붙여도 기존 프롬프트는 보존한다.
    with engine.begin() as db:
        db.execute(text("CREATE TABLE profile (id VARCHAR(64) PRIMARY KEY, preview_prompt TEXT NOT NULL DEFAULT '')"))
        db.execute(text("INSERT INTO profile (id, preview_prompt) VALUES ('legacy', 'keep')"))
    ensure_columns()
    ensure_columns()
    with engine.begin() as db:
        assert db.execute(text("SELECT preview_prompt, review_prompt FROM profile")).one() == ("keep", "")
        db.execute(text("DROP TABLE profile"))
    assert "profile" not in inspect(engine).get_table_names()
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user = CurrentUser(id="student-a", email="a@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    app.dependency_overrides[get_current_user] = lambda: user
    preview, review = "/api/me/preview-prompt", "/api/me/review-prompt"
    for path in (preview, review):
        assert client.get(path).json() == {"prompt": ""}
    assert client.put(preview, json={"prompt": "예습 문구"}).status_code == 200
    assert client.put(review, json={"prompt": "  {파일명}\n복습 문구  "}).json() == {"prompt": "{파일명}\n복습 문구"}
    assert client.get(preview).json() == {"prompt": "예습 문구"}
    assert client.get(review).json() == {"prompt": "{파일명}\n복습 문구"}
    with SessionLocal() as db:
        assert db.get(Profile, "student-a").review_prompt == "{파일명}\n복습 문구"
    user = CurrentUser(id="student-b", email="b@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    assert client.get(review).json() == {"prompt": ""}
    assert client.put(review, json={"prompt": "다른 계정"}).status_code == 200
    user = CurrentUser(id="student-a", email="a@example.com", is_admin=False,
                       apps={APP_STUDYEZ: ROLE_MEMBER})
    assert client.get(review).json() == {"prompt": "{파일명}\n복습 문구"}
    assert client.put(review, json={"prompt": "  "}).json() == {"prompt": ""}
    assert client.get(preview).json() == {"prompt": "예습 문구"}
    user = CurrentUser(id="pending", email="pending@example.com", is_admin=False, apps={})
    assert client.get(review).status_code == 403
    assert client.put(review, json={"prompt": "denied"}).status_code == 403
    app.dependency_overrides.clear()
    assert client.get(review).status_code == 401
    assert client.put(review, json={"prompt": "denied"}).status_code == 401
    print("PASS: 기존 칼럼 호환 · 예습/복습 저장 격리 · 계정 격리 · 초기화 · 승인/로그인 검사")


if __name__ == "__main__":
    main()
