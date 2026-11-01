"""Personal hiding and admin-only quiz removal preserve sources and history."""

import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-study-management-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, BankPersonalEdit, BankState, Lecture, PrequizJob, QuizBank, QuizBankArchive, TimetableEvent
from tests.bank_fixtures import example_bank
from app.study_engine import empty_state

SUBJECT, RUN = "약리학", "261002_02"
KEY = f"{SUBJECT}/{RUN}"
BASE = f"/api/admin/lectures/{SUBJECT}/{RUN}/bank"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="pending", date=date(2026, 10, 2), start_time="09:00", end_time="10:00",
                              title="예정 강의", category="lecture", course=SUBJECT))
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid="test", date=date(2026, 10, 2), slot=1,
                       slot_end=1, start_time="09:00", title="예시", timetable_event_id="pending"))
        db.commit()
        db.add(QuizBank(subject=SUBJECT, run_id=RUN, build_id="v1", status="ready", bank=example_bank(),
                        raw_response="original response", validation={"pass": True}, open_to_students=True))
        db.add(BankState(user_id="student", subject=SUBJECT, run_id=RUN, build_id="v1", state={**empty_state(), "kept": True}))
        db.add(Asset(id="notes", subject=SUBJECT, run_id=RUN, kind="notes_current", filename="notes.pdf", object_key="notes.pdf"))
        db.add(BankPersonalEdit(user_id="student", subject=SUBJECT, run_id=RUN, question_id="Q1",
                                original={}, question="personal", answer="answer"))
        db.commit()
    client = TestClient(app)

    def login(who="student", admin=False, approved=True):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=who, email=f"{who}@example.com", is_admin=admin,
            apps={APP_STUDYEZ: ROLE_MEMBER} if approved else {})

    login()
    assert client.get("/api/me/study-hidden").json() == {"keys": []}
    payload = {"keys": [KEY, "event:pending", KEY], "hidden": True}
    assert client.patch("/api/me/study-hidden", json=payload).status_code == 200
    assert len(client.patch("/api/me/study-hidden", json=payload).json()["keys"]) == 2
    # Hiding has no effect on the public timetable or somebody else's preferences.
    events = client.get("/api/timetable").json()["events"]
    assert events[0]["lectures"][0]["marks"]["quiz"]
    assert "deleteVersion" not in events[0]["lectures"][0]["bankTimeline"]
    login("other")
    assert client.get("/api/me/study-hidden").json() == {"keys": []}
    client.patch("/api/me/study-hidden", json={"keys": [KEY], "hidden": False})
    login()
    assert len(client.get("/api/me/study-hidden").json()["keys"]) == 2
    assert client.patch("/api/me/study-hidden", json={"keys": [KEY, "missing/key"], "hidden": True}).status_code == 404
    assert client.patch("/api/me/study-hidden", json={"keys": [], "hidden": True}).status_code == 422
    assert client.delete(BASE, params={"version": "any"}).status_code == 403
    login("pending-user", approved=False)
    assert client.get("/api/me/study-hidden").status_code == 403
    login()
    assert client.patch("/api/me/study-hidden", json={"keys": [KEY, "event:pending"], "hidden": False}).json() == {"keys": []}

    login("admin", admin=True)
    version = client.get("/api/timetable").json()["events"][0]["lectures"][0]["bankTimeline"]["deleteVersion"]
    assert client.delete(BASE, params={"version": "stale"}).status_code == 409
    with SessionLocal() as db:
        db.add(PrequizJob(subject=SUBJECT, run_id=RUN, kind="bank", state="queued", requested_by="test"))
        db.commit()
    assert client.delete(BASE, params={"version": version}).status_code == 409
    with SessionLocal() as db:
        job = db.scalars(select(PrequizJob)).one()
        job.state = "canceled"
        db.commit()
    response = client.delete(BASE, params={"version": version})
    assert response.status_code == 200, response.text
    assert response.json()["deleted"]
    assert client.delete(BASE, params={"version": version}).status_code == 404
    with SessionLocal() as db:
        assert db.get(QuizBank, (SUBJECT, RUN)) is None
        archive = db.scalars(select(QuizBankArchive)).one()
        assert archive.snapshot["raw_response"] == "original response"
        assert archive.snapshot["bank"] == example_bank()
        assert archive.deleted_by == "admin"
        assert db.get(BankState, ("student", SUBJECT, RUN)).state["kept"]
        assert db.get(BankPersonalEdit, ("student", SUBJECT, RUN, "Q1")).question == "personal"
        assert db.get(Asset, "notes") is not None
        assert db.get(Lecture, (SUBJECT, RUN)) is not None
    login()
    lecture = client.get("/api/timetable").json()["events"][0]["lectures"][0]
    assert not lecture["marks"]["quiz"] and lecture["cardProgress"] is None
    assert client.get(f"/api/lectures/{SUBJECT}/{RUN}/bank").status_code == 404
    app.dependency_overrides.clear()
    assert client.get("/api/me/study-hidden").status_code == 401
    assert client.delete(BASE, params={"version": version}).status_code == 401
    print("PASS: hiding isolation, restore, permissions, stale/active-job protection, archived deletion, preserved history")


if __name__ == "__main__":
    main()
