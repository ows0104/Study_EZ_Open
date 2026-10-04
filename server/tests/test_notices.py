"""공지사항(`routes/notices.py`). 쓰고 · 고치고 · 고정하고 · 지운다.

2026-10-04 운영을 시작하며 섰다.

    server/.venv/Scripts/python.exe -m tests.test_notices

로컬 검사 토큰은 관리자다(`auth.get_current_user`). 그래서 여기서 재는 것은
**문이 아니라 순서와 값이다** — 고정이 먼저 오는가, 빈 제목을 받지 않는가,
지운 것이 목록에서 사라지는가.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-notices-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'notices.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def main() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)

    r = client.get("/api/notices")
    check("토큰 없이는 못 읽는다", r.status_code == 401, r.status_code)

    r = client.get("/api/notices", headers=USER)
    check("처음에는 빈 목록이다", r.status_code == 200 and r.json() == [], r.text)

    first = client.post("/api/admin/notices", headers=USER, json={"title": "  첫 공지  ", "body": "본문\n둘째 줄"}).json()
    check("제목 앞뒤 빈칸을 깎는다", first["title"] == "첫 공지", first)
    check("본문 줄바꿈은 그대로다", first["body"] == "본문\n둘째 줄", first)
    second = client.post("/api/admin/notices", headers=USER, json={"title": "둘째 공지"}).json()

    ids = [row["id"] for row in client.get("/api/notices", headers=USER).json()]
    check("새 글이 먼저다", ids == [second["id"], first["id"]], ids)

    r = client.put(f"/api/admin/notices/{first['id']}", headers=USER,
                   json={"title": "첫 공지(고침)", "body": "본문", "pinned": True})
    check("고친다", r.status_code == 200 and r.json()["title"] == "첫 공지(고침)", r.text)
    ids = [row["id"] for row in client.get("/api/notices", headers=USER).json()]
    check("고정한 것이 새 글보다 먼저다", ids == [first["id"], second["id"]], ids)

    r = client.post("/api/admin/notices", headers=USER, json={"title": "   "})
    check("빈 제목은 받지 않는다", r.status_code == 422, r.status_code)

    r = client.delete(f"/api/admin/notices/{second['id']}", headers=USER)
    check("지운다", r.status_code == 204, r.status_code)
    ids = [row["id"] for row in client.get("/api/notices", headers=USER).json()]
    check("지운 것은 목록에서 사라진다", ids == [first["id"]], ids)

    r = client.put(f"/api/admin/notices/{second['id']}", headers=USER, json={"title": "x"})
    check("없는 공지를 고치면 404", r.status_code == 404, r.status_code)

    print(f"\n{'실패 ' + str(len(failures)) if failures else '모두 통과'}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
