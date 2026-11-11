"""The first list never reads bank bodies; bounded summaries preserve access and state boundaries."""
import copy
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-study-loading-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.bank_validation.coverage import bank_hash
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank, TimetableEvent
from app.study_engine import empty_state
from tests.bank_fixtures import example_bank


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    validation = {"pass": False, "publication": {"allowed": True, "bankHash": bank_hash(bank),
                  "structuralValidation": {"pass": True}}}
    with SessionLocal() as db:
        db.add(TimetableEvent(id="event", date=date(2026, 10, 2), start_time="09:00", end_time="10:00",
                              title="Example", category="lecture", course="subject"))
        for run in ("public", "private", "invalid"):
            db.add(Lecture(subject="subject", run_id=run, uid=run, date=date(2026, 10, 2), slot=1,
                           slot_end=1, start_time="09:00", title=run, timetable_event_id="event"))
        db.commit()
        for run in ("public", "private", "invalid"):
            db.add(QuizBank(subject="subject", run_id=run, build_id="v2", bank=copy.deepcopy(bank),
                            validation=validation if run != "invalid" else {"pass": False},
                            status="invalid" if run == "invalid" else "ready",
                            raw_response="UNNEEDED_RAW" * 100_000, open_to_students=run != "private"))
        db.add(BankState(user_id="one", subject="subject", run_id="public", build_id="old",
                         state={**empty_state(), "seen": {"Q1": 1}}))
        db.commit()

    client = TestClient(app)
    def login(who="one", admin=False, approved=True):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=who, email=f"{who}@example.com", is_admin=admin,
            apps={APP_STUDYEZ: ROLE_MEMBER} if approved else {})
    login()
    captured = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        captured.append(statement.lower())
    event.listen(engine, "before_cursor_execute", observe)
    response = client.get("/api/timetable?include_study=false")
    assert response.status_code == 200, response.text
    assert all(l["studyLoaded"] is False for l in response.json()["events"][0]["lectures"])
    basic = {l["runId"]: l for l in response.json()["events"][0]["lectures"]}
    assert basic["public"]["marks"]["quiz"] and not basic["private"]["marks"]["quiz"]
    assert not basic["invalid"]["marks"]["quiz"]
    assert not any("quiz_bank.bank" in sql or "bank_state" in sql or "raw_response" in sql for sql in captured)
    assert not any("quiz_bank.validation" in sql for sql in captured)
    assert not any("quiz_attempt" in sql or "asset_grab" in sql or "pre_item" in sql for sql in captured)

    payload = {"lectures": [{"subject": "subject", "runId": run} for run in ("public", "private", "invalid", "missing")]}
    captured.clear()
    response = client.post("/api/timetable/study-progress", json=payload)
    assert response.status_code == 200, response.text
    values = {l["runId"]: l for l in response.json()["lectures"]}
    # 2026-11-11: study-progress의 학습률은 Main-Quiz 하나다. Quiz Bank만 있는 강의는 학습률이 없다.
    for run in ("public", "private", "invalid", "missing"):
        assert not values[run]["ready"] and values[run]["mastery"] is None and values[run]["cardProgress"] is None
    assert not any("raw_response" in sql or "quiz_bank.review" in sql or "bank_state.previous" in sql for sql in captured)
    full = {l["runId"]: l for l in client.get("/api/timetable").json()["events"][0]["lectures"]}
    for run in ("public", "private", "invalid"):
        assert full[run]["marks"]["quiz"] == basic[run]["marks"]["quiz"]  # legacy 입구 표시는 그대로
        assert full[run]["cardProgress"] == values[run]["cardProgress"]
    with patch("app.lecture_mastery.lecture_score", side_effect=AssertionError("no Main-Quiz here")):
        calendar = client.get("/api/timetable?start=2026-10-02&end=2026-10-02&include_cards=false")
        assert calendar.status_code == 200, calendar.text
        public = next(l for l in calendar.json()["events"][0]["lectures"] if l["runId"] == "public")
        assert public["mastery"] == values["public"]["mastery"] and public["cardProgress"] is None
        assert client.get("/api/timetable?start=2026-11-01&end=2026-11-05&include_cards=false").json() == {"events": []}
    captured.clear()
    decks = client.get("/api/bundles/decks?subject=subject&start=2026-10-01&end=2026-10-05")
    assert decks.status_code == 200, decks.text
    assert {l["runId"] for l in decks.json()["decks"]} == {"public"}
    assert not any("raw_response" in sql or "quiz_bank.usage" in sql for sql in captured)
    assert client.get("/api/bundles/decks?subject=other").json() == {"decks": []}
    assert client.post("/api/timetable/study-progress", json={"lectures": payload["lectures"] * 3}).status_code == 422
    assert client.post("/api/timetable/study-progress", json={"lectures": []}).status_code == 422
    login("two")
    assert client.post("/api/timetable/study-progress", json=payload).json()["lectures"][0]["cardProgress"] is None
    login("admin", admin=True)
    assert client.post("/api/timetable/study-progress", json=payload).json()["lectures"][1]["mastery"] is None
    login(approved=False)
    assert client.post("/api/timetable/study-progress", json=payload).status_code == 403
    app.dependency_overrides.clear()
    assert client.post("/api/timetable/study-progress", json=payload).status_code == 401
    event.remove(engine, "before_cursor_execute", observe)
    print("PASS: metadata without bank JSON, bounded progress, publication, permissions, rebuild and user isolation")


if __name__ == "__main__":
    main()
