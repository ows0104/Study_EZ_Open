"""HTTP extra-study future eligibility, no immediate repetition, reload/undo and cooldown continuation."""
import datetime
from unittest.mock import patch

from tests.test_bank import STUDENT as USER
from tests.test_extra_review_policy import learned
from tests.test_question_order import make_bank, NOW
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine import record_review
from app.study_engine.memory import DAY_MS


def main():
    Base.metadata.create_all(engine)
    banks = {name: make_bank([(f"Q{i}", f"C{i}", "direct", i + 1, []) for i in range(count)])
             for name, count in (("many", 4), ("single", 1))}
    with SessionLocal() as db:
        for name, bank in banks.items():
            state = learned(bank, due=NOW + 7 * DAY_MS)
            state = record_review(bank, state, "Q0", "Good", NOW)
            db.add(Lecture(subject="extra", run_id=name, uid=f"extra-{name}", date=datetime.date(2026, 10, 12),
                           slot=1, slot_end=1, start_time="09:00", title=name))
            db.flush()
            db.add(QuizBank(subject="extra", run_id=name, build_id=name, bank=bank,
                            validation={"pass": True}, open_to_students=True))
            db.add(BankState(user_id=USER.id, subject="extra", run_id=name, build_id=name, state=state))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)

    def post(base, suffix, payload=None):
        response = client.post(base + suffix, json=payload or {})
        assert response.status_code == 200, response.text
        return response.json()

    base = "/api/lectures/extra/many/bank"
    with patch("app.routes.bank.engine.now_ms", return_value=NOW + 1), \
         patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[-1]]):
        post(base, "/session/start", {"continueAfterGoal": True})
        got = post(base, "/next")
        assert got["question"]["question_id"] == "Q3" and got["lectureGoal"]["met"]
        assert post(base, "/next")["reviewToken"] == got["reviewToken"]
        token = {"reviewToken": got["reviewToken"]}
        post(base, "/reveal", token)
        post(base, "/rate", {**token, "rating": "Good"})
        next_got = post(base, "/next")
        assert next_got["question"]["question_id"] != "Q3" and next_got["lectureGoal"]["met"]
        restored = post(base, "/undo", token)
        assert restored["question"]["question_id"] == "Q3"
        assert post(base, "/next")["reviewToken"] == restored["reviewToken"]
    single = "/api/lectures/extra/single/bank"
    with patch("app.routes.bank.engine.now_ms", return_value=NOW + 1):
        post(single, "/session/start", {"continueAfterGoal": True})
        waiting = post(single, "/next")
        assert waiting["question"] is None and waiting["waiting"] and waiting["retryAt"] == NOW + 60_000
        assert waiting["lectureGoal"]["met"] and waiting["session"]["status"] == "active"
    with patch("app.routes.bank.engine.now_ms", return_value=NOW + 60_000):
        ready = post(single, "/next")
        assert ready["question"]["question_id"] == "Q0" and ready["lectureGoal"]["met"]
        assert ready["session"]["session_id"] == waiting["session"]["session_id"]
    print("PASS: future extra reviews, immediate-repeat exclusion, daily completion, reload/undo and same-session cooldown retry")


if __name__ == "__main__":
    main()
