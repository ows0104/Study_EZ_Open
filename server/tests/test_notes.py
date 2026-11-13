"""자유 노트: 본인 노트만, 태그 정리, 제한, 수정 순서, 삭제."""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-notes-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.database import Base, engine
from app.main import app
from app.routes import notes as notes_route


def main():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    def login(who="student", approved=True):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=who, email=f"{who}@example.com", is_admin=False,
            apps={APP_STUDYEZ: ROLE_MEMBER} if approved else {})

    login()
    assert client.get("/api/me/notes").json() == {"notes": []}

    blocks = [
        {"id": "a", "type": "h2", "html": "그람양성"},
        {"id": "b", "type": "todo", "html": "1회독", "checked": True, "rev": 3},
        {"id": "c", "type": "divider", "html": "ignored"},
        {"id": "d", "type": "text", "html": '<span style="color: #c13f37;">빨강</span>'},
    ]
    first = client.post("/api/me/notes", json={"title": "세균", "tags": [" 1차 시험 ", "세균", "세균", ""],
                                               "blocks": blocks})
    assert first.status_code == 200, first.text
    note = first.json()
    assert note["tags"] == ["1차 시험", "세균"]
    assert note["blocks"][1] == {"id": "b", "type": "todo", "html": "1회독", "checked": True}
    assert note["blocks"][2] == {"id": "c", "type": "divider", "html": ""}
    assert "checked" not in note["blocks"][0]

    second = client.post("/api/me/notes", json={}).json()
    assert second["title"] == "" and second["blocks"] == [] and second["tags"] == []
    assert [n["id"] for n in client.get("/api/me/notes").json()["notes"]] == [second["id"], note["id"]]

    put = client.put(f"/api/me/notes/{note['id']}", json={"title": "세균 정리", "tags": ["자유 태그"], "blocks": blocks[:1]})
    assert put.status_code == 200 and put.json()["title"] == "세균 정리"
    listed = client.get("/api/me/notes").json()["notes"]
    assert [n["id"] for n in listed] == [note["id"], second["id"]]
    assert listed[0] == {"id": note["id"], "title": "세균 정리", "tags": ["자유 태그"], "updatedAt": listed[0]["updatedAt"]}
    assert "blocks" not in listed[0]
    assert listed[0]["updatedAt"].endswith("+00:00")  # sqlite에서도 UTC 표시
    full = client.get(f"/api/me/notes/{note['id']}").json()
    assert full["blocks"] == [{"id": "a", "type": "h2", "html": "그람양성"}] and full["tags"] == ["자유 태그"]

    # 사진 블록: id만 저장하고 html(예: data URL)은 버린다. 다른 종류의 image 값도 버린다.
    pic = client.put(f"/api/me/notes/{note['id']}", json={"title": "세균 정리", "tags": ["자유 태그"], "blocks": [
        {"id": "p", "type": "image", "html": '<img src="data:image/png;base64,AAAA">', "image": "abc12345xyz"},
        {"id": "q", "type": "text", "html": "글", "image": "abc12345xyz"}]})
    assert pic.status_code == 200, pic.text
    assert pic.json()["blocks"] == [{"id": "p", "type": "image", "html": "", "image": "abc12345xyz"},
                                    {"id": "q", "type": "text", "html": "글"}]
    assert client.put(f"/api/me/notes/{note['id']}", json={"blocks": [{"id": "p", "type": "image"}]}).status_code == 422
    assert client.put(f"/api/me/notes/{note['id']}", json={"blocks": [
        {"id": "p", "type": "image", "image": "../etc/passwd"}]}).status_code == 422
    client.put(f"/api/me/notes/{note['id']}", json={"title": "세균 정리", "tags": ["자유 태그"], "blocks": blocks[:1]})

    # 형식·제한
    assert client.put(f"/api/me/notes/{note['id']}", json={"blocks": [{"id": "x", "type": "table", "html": ""}]}).status_code == 422
    assert client.put(f"/api/me/notes/{note['id']}", json={"tags": ["x" * 41]}).status_code == 422
    assert client.put(f"/api/me/notes/{note['id']}", json={"tags": [str(i) for i in range(31)]}).status_code == 422
    assert client.put(f"/api/me/notes/{note['id']}", json={"title": "t" * 201}).status_code == 422
    assert client.put(f"/api/me/notes/{note['id']}", json={"blocks": [{"id": "x", "type": "text", "html": "h" * 20_001}]}).status_code == 422
    assert client.get(f"/api/me/notes/{note['id']}").json()["title"] == "세균 정리"

    # 다른 계정은 보지도 고치지도 지우지도 못한다.
    login("other")
    assert client.get("/api/me/notes").json() == {"notes": []}
    assert client.get(f"/api/me/notes/{note['id']}").status_code == 404
    assert client.put(f"/api/me/notes/{note['id']}", json={"title": "탈취"}).status_code == 404
    assert client.delete(f"/api/me/notes/{note['id']}").status_code == 404

    # 개수 상한
    original = notes_route.MAX_NOTES
    notes_route.MAX_NOTES = 2
    try:
        assert client.post("/api/me/notes", json={}).status_code == 200
        assert client.post("/api/me/notes", json={}).status_code == 200
        assert client.post("/api/me/notes", json={}).status_code == 409
    finally:
        notes_route.MAX_NOTES = original

    login()
    assert client.get(f"/api/me/notes/{note['id']}").json()["title"] == "세균 정리"
    assert client.delete(f"/api/me/notes/{note['id']}").json() == {"ok": True}
    assert client.get(f"/api/me/notes/{note['id']}").status_code == 404
    assert [n["id"] for n in client.get("/api/me/notes").json()["notes"]] == [second["id"]]

    login(approved=False)
    assert client.get("/api/me/notes").status_code == 403
    app.dependency_overrides.clear()
    assert client.get("/api/me/notes").status_code == 401
    print("PASS: own notes only, tag cleanup, block shape, limits, recent-first order, delete, 403/401")


if __name__ == "__main__":
    main()
