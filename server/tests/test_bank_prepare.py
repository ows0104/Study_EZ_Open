"""Answer warmup must not alter reveal timing, grading, or another user's state."""
from __future__ import annotations

import copy
import datetime
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-prepare-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver")

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BankState, Lecture, QuizBank  # noqa: E402
from tests.bank_fixtures import example_bank  # noqa: E402


def main():
    Base.metadata.create_all(engine)
    user = CurrentUser(id="student", email="s@example.com", is_admin=False,
                       apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    app.dependency_overrides[get_current_user] = lambda: user
    initial = {"served": {"question_id": "Q1", "token": "current", "revealed": False, "presented_at": 100}}
    with SessionLocal() as db:
        db.add(Lecture(subject="test", run_id="run", uid="test#run", date=datetime.date(2026, 10, 7),
                       slot=1, slot_end=1, start_time="09:00", title="Test", professors=[], author="", version=1))
        db.flush()
        db.add(QuizBank(subject="test", run_id="run", build_id="v1", status="ready", open_to_students=True,
                        bank=example_bank(), validation={"pass": True}, pages={}))
        db.add(BankState(user_id=user.id, subject="test", run_id="run", build_id="v1", state=initial))
        db.commit()
    client = TestClient(app)
    base = "/api/lectures/test/run/bank"
    body = {"reviewToken": "current"}
    with SessionLocal() as db:
        before = copy.deepcopy(db.get(BankState, (user.id, "test", "run")).state)
    for _ in range(2):
        prepared = client.post(base + "/prepare", json=body)
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["answer"] == "예시 정답"
    with SessionLocal() as db:
        assert db.get(BankState, (user.id, "test", "run")).state == before
    assert client.post(base + "/rate", json={**body, "rating": "Good"}).status_code == 409
    assert client.post(base + "/prepare", json={"reviewToken": "old"}).status_code == 409
    other = CurrentUser(id="other", email="other@example.com", is_admin=False, apps=user.apps)
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.post(base + "/prepare", json=body).status_code == 409
    app.dependency_overrides[get_current_user] = lambda: user
    revealed = client.post(base + "/reveal", json=body)
    assert revealed.status_code == 200, revealed.text
    assert revealed.json() == prepared.json()
    with SessionLocal() as db:
        served = db.get(BankState, (user.id, "test", "run")).state["served"]
        assert served["revealed"] and served["revealed_at"] > 100
        row = db.get(QuizBank, ("test", "run"))
        row.build_id = "v2"
        db.commit()
    assert client.post(base + "/prepare", json=body).status_code == 409
    with SessionLocal() as db:
        db.get(QuizBank, ("test", "run")).open_to_students = False
        db.commit()
    assert client.post(base + "/prepare", json=body).status_code == 404
    print("PASS: warmup is read-only, grading stays gated, and user/token/build/publication checks hold")


if __name__ == "__main__":
    main()
