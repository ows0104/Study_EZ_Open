"""Legacy counts stay unknown; new automatic attachment intents never become downloads."""
from __future__ import annotations

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException

_TMP = Path(tempfile.mkdtemp(prefix="studyez-file-request-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
                  RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from app.auth import LOCAL_TEST_USER_ID
from app.cli import ensure_columns
from app.database import Base, SessionLocal, engine
from app.file_requests import request_stats
from app.main import app
from app.models import Asset, AssetGrab, Lecture, Profile
from app.routes.common import record_grabs

USER = {"Authorization": "Bearer local-test-token"}
SUBJECT, RUN = "요청 검증", "261101_01"
FILE = f"/api/lectures/{SUBJECT}/{RUN}/files/notes"
OLD = datetime(2026, 9, 1, 3, tzinfo=UTC)
checks = 0


def check(label, condition):
    global checks
    assert condition, label
    checks += 1
    print("PASS", label)


def detail(client):
    return client.get(f"/api/admin/usage/{LOCAL_TEST_USER_ID}", headers=USER).json()["lectures"][0]


def main():
    # Start from the exact old table shape, including populated historical data.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE asset_grab (user_id VARCHAR(64), subject TEXT, run_id VARCHAR(32), "
                          "kind VARCHAR(24), count INTEGER NOT NULL, first_at TIMESTAMP, last_at TIMESTAMP, "
                          "PRIMARY KEY (user_id, subject, run_id, kind))"))
        conn.execute(text("INSERT INTO asset_grab VALUES (:uid, :subject, :run, 'notes_prev', 2, :at, :at)"),
                     {"uid": LOCAL_TEST_USER_ID, "subject": SUBJECT, "run": RUN, "at": OLD})
    ensure_columns()
    ensure_columns()
    check("existing schema receives one idempotent JSON column",
          sum(c["name"] == "request_stats" for c in inspect(engine).get_columns("asset_grab")) == 1)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Profile(id=LOCAL_TEST_USER_ID, email="local-test@studyez.local", is_admin=True))
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid="test", date=date(2026, 11, 1), slot=1,
                       slot_end=1, start_time="09:00", title="파일 목적 검증", professors=[], author="", version=1))
        db.add(Asset(id="notes", subject=SUBJECT, run_id=RUN, kind="notes_prev", filename="notes.pdf",
                     object_key="test/notes.pdf", content_type="application/pdf"))
        db.add(Asset(id="slide", subject=SUBJECT, run_id=RUN, kind="media", filename="slide.png",
                     object_key="test/slide.png", content_type="image/png"))
        db.commit()
    client = TestClient(app)
    before = detail(client)
    legacy = before["fileRequests"][0]
    check("historical requests remain unknown", legacy["purpose"] == "unknown" and legacy["count"] == 2)

    for purpose in ("preview_attach", "review_attach", "quiz_attach", "download", "view"):
        response = client.get(FILE, params={"purpose": purpose}, headers=USER)
        check(f"{purpose} keeps the signed-file contract", response.status_code == 200 and "url" in response.json())
    row = detail(client)
    by_purpose = {r["purpose"]: r for r in row["fileRequests"]}
    check("five new intents are separate from two old requests", len(by_purpose) == 6
          and all(by_purpose[p]["count"] == 1 for p in ("preview_attach", "review_attach", "quiz_attach", "download", "view")))
    overview = next(r for r in client.get("/api/admin/usage?window=week", headers=USER).json()["users"]
                    if r["id"] == LOCAL_TEST_USER_ID)
    check("recent classified requests do not move historical unknown activity into this window",
          overview["fileRequests"]["unknown"] == 0 and overview["fileRequests"]["preview_attach"] == 1
          and overview["fileRequests"]["download"] == 1)
    check("new requests preserve the legacy timestamp", by_purpose["unknown"] == legacy)
    check("requesting files does not imply quiz or preview completion", not row["preview"]
          and row["pre"]["cards"] == row["main"]["cards"] == row["bank"]["cards"] == 0)

    response = client.get(FILE, headers=USER)  # Old clients omit the new optional field.
    check("old clients still work and remain unknown", response.status_code == 200
          and next(r for r in detail(client)["fileRequests"] if r["purpose"] == "unknown")["count"] == 3)
    client.get(FILE, params={"inline": 1}, headers=USER)
    check("old inline callers are explicitly browser opens",
          next(r for r in detail(client)["fileRequests"] if r["purpose"] == "view")["count"] == 2)
    snapshot = detail(client)["fileRequests"]
    check("invalid purposes are rejected", client.get(FILE, params={"purpose": "pretend"}, headers=USER).status_code == 422)
    check("anonymous file requests are denied", client.get(FILE).status_code == 401)
    check("missing assets do not count", client.get(FILE.replace("/notes", "/missing"), headers=USER).status_code == 404)
    with patch("app.routes.lectures.storage_or_503", side_effect=HTTPException(503, "not ready")):
        check("storage failure does not count", client.get(FILE, headers=USER).status_code == 503)
    client.get(FILE.replace("/notes", "/slide"), headers=USER)
    check("failed requests and automatic slide loading leave no file activity", detail(client)["fileRequests"] == snapshot)

    def concurrent_request(_):
        with SessionLocal() as db:
            return record_grabs(db, LOCAL_TEST_USER_ID, [(SUBJECT, RUN, "notes_prev")], purpose="preview_attach")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(concurrent_request, range(8)))
    check("concurrent attachments all record successfully", results == [1] * 8)
    with SessionLocal() as db:
        grab = db.get(AssetGrab, (LOCAL_TEST_USER_ID, SUBJECT, RUN, "notes_prev"))
        stats = request_stats(grab)
        check("concurrent requests do not overwrite counts", stats["preview_attach"]["count"] == 9
              and grab.count == sum(v["count"] for v in stats.values()) == 17)
        record_grabs(db, "another-user", [(SUBJECT, RUN, "notes_prev")], purpose="download")
    check("another user's download cannot change this user's totals", next(r for r in detail(client)["fileRequests"]
          if r["purpose"] == "download")["count"] == 1)
    check("file activity never exposes a signed URL", "http" not in str(detail(client)["fileRequests"]))
    print(f"All {checks} file purpose checks passed")


if __name__ == "__main__":
    main()
