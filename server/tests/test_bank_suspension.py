"""Personal suspension excludes new/review/extra/batch questions without grading them."""
import copy
import datetime
from dataclasses import replace
from unittest.mock import patch

from tests.test_bank import STUDENT, example_bank
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine import empty_state, select_question, record_review
from app.study_engine.daily_queue import daily_units, lecture_goal
from app.study_engine.progress import panel_progress

NOW = 1791824400000
BASE = "/api/lectures/suspend/demo/bank"


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    bank["questions"] = bank["questions"][:2]
    for q in bank["questions"]:
        q.update(retrieval_direction="direct", prerequisites=[], tier="Core")
    bank["questions"][1]["prerequisites"] = ["Q1"]
    original = copy.deepcopy(bank)
    with SessionLocal() as db:
        db.add(Lecture(subject="suspend", run_id="demo", uid="suspend-demo", date=datetime.date(2026, 10, 12),
                       slot=1, slot_end=1, start_time="09:00", title="비활성 테스트"))
        db.flush()
        db.add(QuizBank(subject="suspend", run_id="demo", build_id="v1", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)
    def put(qid, data, status=200):
        response = client.put(f"{BASE}/questions/{qid}/suspension", json=data)
        assert response.status_code == status, response.text
        return response.json()
    def next_question():
        response = client.post(BASE + "/next?choiceProtocol=true")
        assert response.status_code == 200, response.text
        return response.json()
    with patch("app.routes.bank.engine.now_ms", return_value=NOW):
        first = next_question()
        assert first["question"]["question_id"] == "Q1"
        token = {"reviewToken": first["reviewToken"], "suspended": True}
        put("Q2", token, 409)
        put("Q1", {**token, "reviewToken": "stale"}, 409)
        put("Q1", token)
        # An expired action cannot suspend the next question or grade the old one.
        put("Q1", token, 409)
        assert client.post(BASE + "/rate", json={"reviewToken": first["reviewToken"], "rating": "Easy"}).status_code == 409
        with SessionLocal() as db:
            stored = db.get(BankState, (STUDENT.id, "suspend", "demo"))
            assert stored.state["history"] == [] and stored.state["dimensions"] == {} and stored.state["items"] == {}
            assert db.get(QuizBank, ("suspend", "demo")).bank == original
        second = next_question()
        assert second["question"]["question_id"] == "Q2", "a suspended prerequisite cannot block a new question"
        assert second["lectureGoal"]["total"] == 1 and second["lectureGoal"]["completed"] == 0
        assert next_question()["reviewToken"] == second["reviewToken"], "refresh preserves active question"
        reading = client.get(BASE).json()
        assert [q["questionId"] for q in reading["suspendedQuestions"]] == ["Q1"]
        assert reading["summary"]["studyQuestionCount"] == 1
        app.dependency_overrides[get_current_user] = lambda: replace(STUDENT, id="another-student")
        assert client.get(BASE).json()["suspendedQuestions"] == []
        assert next_question()["question"]["question_id"] == "Q1"
        app.dependency_overrides[get_current_user] = lambda: STUDENT
        put("Q2", {"reviewToken": second["reviewToken"], "suspended": True})
        complete = next_question()
        assert complete["question"] is None and complete["lectureGoal"]["met"]
        assert complete["summary"]["reviewed"] == 0, "suspensions never count as reviews"
        batch = client.post("/api/bank/batch/next", json={"lectures": [{"subject": "suspend", "runId": "demo"}]}).json()
        assert batch["question"] is None and batch["batchGoal"]["total"] == 0
        put("Q1", {"suspended": False, "buildId": "old-build"}, 409)
        put("Q1", {"suspended": False, "buildId": "v1"})
        assert client.get(BASE).json()["lectureGoal"]["remaining"] == 1
        assert client.post(BASE + "/session/start", json={"size": None}).status_code == 200
        assert next_question()["question"]["question_id"] == "Q1"
        # A reviewed question retains its original history and due date when restored.
        state = record_review(bank, empty_state(), "Q1", "Again", NOW - 86400000)
        saved = copy.deepcopy(state)
        state["suspended_question_ids"] = ["Q1"]
        assert [u["key"] for u in daily_units(bank, state, NOW)] == ["Q2"]
        assert select_question(bank, state, "2026-11-12", NOW, prefer_unseen=True)["question"]["question_id"] == "Q2"
        assert panel_progress(bank, state)["studyQuestionCount"] == 1
        state["suspended_question_ids"] = []
        assert state["items"] == saved["items"] and state["history"] == saved["history"]
        assert any(u["key"] == "Q1" for u in daily_units(bank, state, NOW))
        assert lecture_goal(bank, {**state, "suspended_question_ids": ["Q1", "Q2"]}, "test", NOW)["met"]
    print("PASS: suspension persists per user, preserves records, handles empty goals, batch, prerequisites, and restoration")


if __name__ == "__main__":
    main()
