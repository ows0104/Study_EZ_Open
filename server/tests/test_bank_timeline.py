"""Link timestamps survive retries; list timestamps use upload completion, not later edits."""
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-timeline-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
                  PUBLIC_API_BASE_URL="http://testserver", RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank, TimetableEvent
from tests.bank_fixtures import example_bank

ADMIN = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
KEY = ("test", "261015_01")
BASE = "/api/admin/lectures/test/261015_01"
SHARE = "https://chatgpt.com/share/timeline"
FIRST = datetime(2026, 10, 15, 4, 0, tzinfo=UTC)
SECOND = datetime(2026, 10, 15, 5, 0, tzinfo=UTC)


def timeline(client, headers=ADMIN):
    lectures = client.get("/api/timetable", headers=headers).json()["events"][0]["lectures"]
    return next(l["bankTimeline"] for l in lectures if (l["subject"], l["runId"]) == KEY)


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="timeline", date=date(2026, 10, 15), start_time="10:00",
                              end_time="11:00", title="시각 검사", category="lecture"))
        db.add(Lecture(subject=KEY[0], run_id=KEY[1], uid="timeline", date=date(2026, 10, 15),
                       slot=1, slot_end=1, start_time="10:00", title="시각 검사", professors=[],
                       timetable_event_id="timeline"))
        # Migration leaves existing links without a guessed creation date.
        db.add(QuizBank(subject=KEY[0], run_id=KEY[1], status="linked", share_url=SHARE))
        db.add(Asset(id="notes", subject=KEY[0], run_id=KEY[1], kind="notes_current",
                     filename="notes.pdf", object_key="notes.pdf", content_type="application/pdf"))
        db.commit()
    client = TestClient(app)
    assert timeline(client)["linkedAt"] is None
    assert client.put(BASE + "/bank/links", headers=ADMIN, json={"shareUrl": SHARE}).status_code == 200
    assert timeline(client)["linkedAt"] is None
    with patch("app.routes.bank.datetime") as clock:
        clock.now.return_value = FIRST
        assert client.put(BASE + "/bank/links", headers=ADMIN, json={"shareUrl": SHARE + "-new"}).status_code == 200
    assert timeline(client)["linkedAt"] == FIRST.isoformat()
    # Repeated saves and personal-link arrival cannot move the shared-link clock.
    assert client.put(BASE + "/bank/links", headers=ADMIN, json={
        "shareUrl": SHARE + "-new", "conversationUrl": "https://chatgpt.com/c/private"}).status_code == 200
    assert timeline(client)["linkedAt"] == FIRST.isoformat()
    raw = "Web response " * 30 + "STUDYEZ_BANK_COMPLETE"
    response = client.put(BASE + "/bank-response", headers=ADMIN, json={"raw": raw, "shareUrl": SHARE + "-new"})
    assert response.status_code == 200
    responded = response.json()["respondedAt"]
    assert timeline(client)["linkedAt"] == FIRST.isoformat()
    assert client.put(BASE + "/bank", headers=RUNNER, json={"respondedAt": responded, "message": "failed"}).status_code == 200
    assert timeline(client)["builtAt"] is None
    bank = example_bank()
    for q in bank["questions"]:
        q.update(hint="회상 단서", explanation="정답 부연")
    with patch("app.routes.bank.datetime") as clock:
        clock.now.return_value = SECOND
        uploaded = client.put(BASE + "/bank", headers=RUNNER, json={"respondedAt": responded,
            "bank": bank, "validation": {"pass": True, "errors": [], "warnings": []}})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "ready", uploaded.text
    expected = {"shareUrl": SHARE + "-new", "linkedAt": FIRST.isoformat(), "builtAt": SECOND.isoformat()}
    assert timeline(client) == expected
    # Student list has public timestamps but never the administrator's personal URL.
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student", email="s@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    assert timeline(client, {}) == expected
    app.dependency_overrides.clear()
    # Closing the bank hides its upload metadata from students; share metadata remains public.
    with SessionLocal() as db:
        db.get(QuizBank, KEY).open_to_students = False
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="student", email="s@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    assert timeline(client, {}) == {**expected, "builtAt": None}
    app.dependency_overrides.clear()
    assert client.put(BASE + "/bank/links", headers=ADMIN, json={"shareUrl": ""}).status_code == 200
    assert timeline(client)["linkedAt"] is None
    assert timeline(client)["builtAt"] == SECOND.isoformat()
    print("Bank link and final upload timestamps passed")


if __name__ == "__main__":
    main()
