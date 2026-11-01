"""공통 예습 프롬프트의 권한·영속 저장·개인 설정 분리."""

import os
import tempfile
from pathlib import Path

_LOCAL = Path(__file__).resolve().parent.parent / "local_test_data"
_LOCAL.mkdir(exist_ok=True)
_TMP = Path(tempfile.mkdtemp(prefix="shared-prompt-", dir=_LOCAL))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import SitePrompt

PATH = "/api/admin/preview-prompt"


def main():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    def login(who="admin", admin=True):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=who, email=f"{who}@example.com", is_admin=admin, apps={APP_STUDYEZ: ROLE_MEMBER})

    login()
    assert client.get(PATH).json() == {"prompt": ""}
    original = "{파일명}\n{강의}의 흐름과 핵심 용어를 알려줘."
    response = client.put(PATH, json={"prompt": f"  {original}\n"})
    assert response.status_code == 200, response.text
    assert response.json() == {"prompt": original}
    with SessionLocal() as db:
        assert db.get(SitePrompt, "shared-preview").prompt == original
    login("second-admin")
    assert TestClient(app).get(PATH).json() == {"prompt": original}
    changed = "{파일명}\n{과목}의 {교수} 강의를 간단히 설명해줘."
    assert client.put(PATH, json={"prompt": changed}).status_code == 200
    assert client.get(PATH).json() == {"prompt": changed}
    assert client.put(PATH, json={"prompt": "a" * 20001}).status_code == 422
    assert client.get(PATH).json() == {"prompt": changed}
    assert client.put(PATH, json={}).status_code == 422

    login("student", admin=False)
    assert client.get(PATH).status_code == 403
    assert client.put(PATH, json={"prompt": "forbidden"}).status_code == 403
    assert client.put("/api/me/preview-prompt", json={"prompt": "내 개인 문구"}).status_code == 200
    login("second-admin")
    assert client.get(PATH).json() == {"prompt": changed}
    assert client.put(PATH, json={"prompt": " \n "}).json() == {"prompt": ""}
    assert client.get(PATH).json() == {"prompt": ""}
    login("student", admin=False)
    assert client.get("/api/me/preview-prompt").json() == {"prompt": "내 개인 문구"}
    app.dependency_overrides.clear()
    assert client.get(PATH).status_code == 401
    assert client.put(PATH, json={"prompt": "forbidden"}).status_code == 401
    print("PASS: admin-only access, shared persistence, updates, reset, validation, personal isolation")


if __name__ == "__main__":
    main()
