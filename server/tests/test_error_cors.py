"""처리되지 않은 예외의 500에도 허용 출처의 CORS 헤더가 붙는다(브라우저 「Failed to fetch」 방지)."""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-error-cors-"))
ALLOWED = "https://studyez.kr"
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  CORS_ALLOWED_ORIGINS=ALLOWED)

from fastapi.testclient import TestClient
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.database import Base, engine
from app.main import app


def main():
    Base.metadata.create_all(engine)
    # 2026-11-10 운영과 같은 상태: 라우트는 있는데 표가 없다.
    Base.metadata.tables["user_note"].drop(engine)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student", email="student@example.com", is_admin=False, apps={APP_STUDYEZ: ROLE_MEMBER})
    client = TestClient(app, raise_server_exceptions=False)

    broken = client.get("/api/me/notes", headers={"Origin": ALLOWED})
    assert broken.status_code == 500, broken.text
    assert broken.json() == {"detail": "Internal Server Error"}
    assert broken.headers.get("access-control-allow-origin") == ALLOWED
    assert "origin" in broken.headers.get("vary", "").lower()
    assert "user_note" not in broken.text  # 예외 내용은 응답에 싣지 않는다

    other = client.get("/api/me/notes", headers={"Origin": "https://evil.example"})
    assert other.status_code == 500 and "access-control-allow-origin" not in other.headers
    bare = client.get("/api/me/notes")
    assert bare.status_code == 500 and "access-control-allow-origin" not in bare.headers

    # 정상·4xx 응답은 그대로
    ok = client.get("/api/health", headers={"Origin": ALLOWED})
    assert ok.status_code == 200 and ok.headers.get("access-control-allow-origin") == ALLOWED
    missing = client.get("/api/me/notes/none", headers={"Origin": ALLOWED})
    assert missing.status_code == 500  # 표가 없으니 이것도 500 — 헤더는 붙는다
    assert missing.headers.get("access-control-allow-origin") == ALLOWED
    app.dependency_overrides.clear()
    unauth = client.get("/api/me/notes", headers={"Origin": ALLOWED})
    assert unauth.status_code == 401 and unauth.headers.get("access-control-allow-origin") == ALLOWED

    # 예외는 다시 던져져 서버 로그에 남는다
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student", email="student@example.com", is_admin=False, apps={APP_STUDYEZ: ROLE_MEMBER})
    strict = TestClient(app, raise_server_exceptions=True)
    try:
        strict.get("/api/me/notes", headers={"Origin": ALLOWED})
    except Exception:
        pass
    else:
        raise AssertionError("예외가 다시 던져지지 않았다")
    app.dependency_overrides.clear()
    print("error_cors ok")


if __name__ == "__main__":
    main()
