"""Focused shared editing returns one card and retains the admin access gate."""
import datetime
from unittest.mock import patch
from tests.test_bank import example_bank, STUDENT
from fastapi.testclient import TestClient
from app.auth import CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, QuizBank


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for run in ("A", "B"):
            db.add(Lecture(subject="focus", run_id=run, uid=f"focus-{run}", date=datetime.date(2026, 10, 16),
                           slot=1, slot_end=1, start_time="09:00", title=run))
            db.flush()
            db.add(QuizBank(subject="focus", run_id=run, build_id="v1", status="ready", open_to_students=True,
                            bank=example_bank(), validation={"pass": True}, pages={}))
        db.commit()
    client = TestClient(app)
    admin = CurrentUser(id="admin", email="admin@example.com", is_admin=True, apps=STUDENT.apps)
    app.dependency_overrides[get_current_user] = lambda: admin
    with patch("app.routes.bank.bank_sources", return_value=[]):
        url = "/api/admin/bank-review?subject=focus&runId=A&questionId=Q2"
        response = client.get(url)
        assert response.status_code == 200, response.text
        result = response.json()
        assert len(result["banks"]) == 1 and result["banks"][0]["runId"] == "A"
        group = result["banks"][0]
        assert [card["question"]["question_id"] for card in group["cards"]] == ["Q2"]
        assert len(group["questions"]) == 3  # Prerequisite labels only, no other answer bodies.
        assert all("answer" not in item for item in group["questions"])
        assert client.get("/api/admin/bank-review?questionId=Q2").status_code == 422
        assert not client.get(url.replace("Q2", "missing")).json()["banks"]
        app.dependency_overrides[get_current_user] = lambda: STUDENT
        assert client.get(url).status_code == 403
    print("PASS: focused editing returns one card with prerequisite labels; unrelated banks and students are excluded")


if __name__ == "__main__":
    main()
