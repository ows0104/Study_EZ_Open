"""피드백 접수·첨부 보존·권한·검증·실패 시 정리. 임시 로컬 DB에서만 검사한다."""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-feedback-"))
os.environ.update(
    ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'feedback.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import CurrentUser, get_current_user  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.storage import ObjectStorage  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZfoAAAAASUVORK5CYII=")
SHOT = {"name": "화면.png", "data": base64.b64encode(PNG).decode()}


def main() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    assert client.post("/api/feedback", json={"message": "x"}).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("student", "student@example.com", False, {"studyez": "member"})
    result = client.post("/api/feedback", json={"message": "  화면이 이상해요\n확인 부탁해요.  ", "page": "/prequiz/test/run", "screenshots": [SHOT]})
    assert result.status_code == 201, result.text
    feedback_id = result.json()["id"]
    assert client.get("/api/admin/feedback").status_code == 403
    path = f"/api/admin/feedback/{feedback_id}/screenshots/0"
    assert client.get(path).status_code == 403
    assert client.patch(f"/api/admin/feedback/{feedback_id}", json={"status": "resolved"}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("pending", "pending@example.com", False)
    assert client.post("/api/feedback", json={"message": "x"}).status_code == 403
    app.dependency_overrides.clear()
    assert client.get(path).status_code == 401
    board = client.get("/api/admin/feedback", headers=USER).json()
    assert len(board) == 1 and board[0]["message"] == "화면이 이상해요\n확인 부탁해요."
    assert board[0]["email"] == "student@example.com" and board[0]["page"] == "/prequiz/test/run"
    assert board[0]["screenshots"] == [{"name": "화면.png"}]
    image = client.get(path, headers=USER)
    assert image.content == PNG and image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, no-store"
    assert client.get(path[:-1] + "5", headers=USER).status_code == 404
    stored = list((_TMP / "storage").rglob("*.png"))
    assert len(stored) == 1
    key = stored[0].relative_to(_TMP / "storage").as_posix()
    assert client.get(f"/api/local-storage/{key}").status_code == 404
    assert client.patch(f"/api/admin/feedback/{feedback_id}", headers=USER, json={"status": "resolved"}).json()["status"] == "resolved"
    assert client.patch(f"/api/admin/feedback/{feedback_id}", headers=USER, json={"status": "open"}).json()["status"] == "open"
    assert client.patch(f"/api/admin/feedback/{feedback_id}", headers=USER, json={"status": "bad"}).status_code == 422
    assert client.patch("/api/admin/feedback/999", headers=USER, json={"status": "open"}).status_code == 404
    assert client.post("/api/feedback", headers=USER, json={"message": "  "}).status_code == 422
    assert client.post("/api/feedback", headers=USER, json={"message": "x" * 4001}).status_code == 422
    invalid = [
        [{"name": "a.png", "data": "invalid-base64"}],
        [{"name": "a.png", "data": base64.b64encode(b"<svg></svg>").decode()}],
        [{"name": "a.png", "data": base64.b64encode(PNG + b"x" * (3 * 1024 * 1024)).decode()}],
        [SHOT] * 4,
    ]
    for shots in invalid:
        assert client.post("/api/feedback", headers=USER, json={"message": "x", "screenshots": shots}).status_code == 422
    assert len(list((_TMP / "storage").rglob("*.png"))) == 1
    actual_upload = ObjectStorage.upload_fileobj
    def fail_after_upload(storage, fileobj, key, *, content_type):
        actual_upload(storage, fileobj, key, content_type=content_type)
        raise RuntimeError("storage failure")
    with patch.object(ObjectStorage, "upload_fileobj", fail_after_upload):
        assert client.post("/api/feedback", headers=USER, json={"message": "x", "screenshots": [SHOT]}).status_code == 503
    assert len(list((_TMP / "storage").rglob("*.png"))) == 1
    assert len(client.get("/api/admin/feedback", headers=USER).json()) == 1
    assert client.post("/api/feedback", headers=USER, json={"message": "첨부 없이도 보내요"}).status_code == 201
    assert client.get("/api/admin/feedback", headers=USER).json()[0]["message"] == "첨부 없이도 보내요"
    print("피드백: 접수·캡처·관리자 권한·입력 제한·실패 정리 모두 통과")


if __name__ == "__main__":
    main()
