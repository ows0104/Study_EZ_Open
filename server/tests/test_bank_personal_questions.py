"""Private additions share study, batch, undo and overview behavior without leaking."""
import copy
import datetime
import uuid
from dataclasses import replace
from unittest.mock import patch
from sqlalchemy import select
from fastapi.testclient import TestClient
from tests.test_bank import STUDENT, example_bank
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankFeedback, BankState, Lecture, QuizBank
from app.lecture_mastery import lecture_overviews

NOW = 1791824400000
BASE = "/api/lectures/private/demo/bank"


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    bank["questions"] = bank["questions"][:1]
    original = copy.deepcopy(bank)
    with SessionLocal() as db:
        db.add(Lecture(subject="private", run_id="demo", uid="private-demo", date=datetime.date(2026, 10, 12),
                       slot=1, slot_end=1, start_time="09:00", title="Private questions"))
        db.flush()
        db.add(QuizBank(subject="private", run_id="demo", build_id="v1", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)

    def request(method, path, payload=None, status=200):
        response = client.request(method, path, **({"json": payload} if payload is not None else {}))
        assert response.status_code == status, response.text
        return response.json()

    with patch("app.routes.bank.engine.now_ms", return_value=NOW):
        draft = {"clientId": str(uuid.uuid4()), "question": "내가 외울 질문", "answer": "내 정답",
                 "explanation": "내 설명", "tier": "Essential"}
        request("POST", BASE + "/personal-questions", {**draft, "question": "  "}, 422)
        request("POST", BASE + "/personal-questions", {**draft, "tier": "wrong"}, 422)
        added = request("POST", BASE + "/personal-questions", draft, 201)
        qid = added["questionId"]
        assert request("POST", BASE + "/personal-questions", draft, 201) == added, "retry must not duplicate"
        info = request("GET", BASE)
        assert len(info["personalQuestions"]) == 1 and info["lectureGoal"]["total"] == 2
        assert info["summary"]["questionCount"] == 2
        shared = request("POST", BASE + "/next?choiceProtocol=true")
        assert shared["question"]["question_id"] == "Q1", "new cards preserve slide order across tiers"
        request("POST", BASE + "/reveal", {"reviewToken": shared["reviewToken"]})
        request("POST", BASE + "/rate", {"reviewToken": shared["reviewToken"], "rating": "Good"})
        current = request("POST", BASE + "/next?choiceProtocol=true")
        assert current["question"]["question_id"] == qid
        assert current["question"]["targetMastery"] == .9 and current["answer"] is None
        assert "answer" not in current["question"]
        token = current["reviewToken"]
        snapshot = request("GET", f"{BASE}/questions/{qid}/personal")
        assert snapshot["personalAdded"] and snapshot["draft"]["explanation"] == "내 설명"
        edited = request("PUT", f"{BASE}/questions/{qid}/personal", {
            "revision": snapshot["revision"], "question": "바꾼 질문", "answer": "바꾼 답", "explanation": "바꾼 설명"})
        assert not edited["reported"] and edited["answer"]["answer"] == "바꾼 답"
        assert request("POST", BASE + "/next?choiceProtocol=true")["question"]["question"] == "바꾼 질문"
        revealed = request("POST", BASE + "/reveal", {"reviewToken": token})
        assert revealed["answer"] == "바꾼 답" and revealed["explanation"] == "바꾼 설명" and revealed["personalAnswer"]
        request("POST", BASE + "/rate", {"reviewToken": token, "rating": "Good"})
        request("POST", BASE + "/next?choiceProtocol=true")
        restored = request("POST", BASE + "/undo", {"reviewToken": token})
        assert restored["question"]["question_id"] == qid and restored["answer"]["answer"] == "바꾼 답"
        with SessionLocal() as db:
            overview = lecture_overviews(db, STUDENT.id, [("private", "demo")], is_admin=False)[("private", "demo")]
            assert overview["cardProgress"]["total"] == 2
            assert db.get(QuizBank, ("private", "demo")).bank == original
            assert not list(db.scalars(select(BankFeedback))), "private additions never become admin feedback"
        app.dependency_overrides[get_current_user] = lambda: replace(STUDENT, id="other-student")
        assert request("GET", BASE)["personalQuestions"] == []
        request("GET", f"{BASE}/questions/{qid}/personal", status=404)
        request("DELETE", f"{BASE}/personal-questions/{qid}", status=404)
        assert request("POST", BASE + "/next?choiceProtocol=true")["question"]["question_id"] == "Q1"
        app.dependency_overrides[get_current_user] = lambda: STUDENT
        with SessionLocal() as db:
            db.get(QuizBank, ("private", "demo")).build_id = "v2"
            db.commit()
        info = request("GET", BASE)
        assert info["personalQuestions"][0]["question"] == "바꾼 질문" and info["lectureGoal"]["total"] == 2
        batch = request("POST", "/api/bank/batch/next", {"lectures": [{"subject": "private", "runId": "demo"}]})
        assert batch["question"]["question_id"] == "Q1" and batch["batchGoal"]["total"] == 2
        request("POST", BASE + "/reveal", {"reviewToken": batch["reviewToken"]})
        request("POST", BASE + "/rate", {"reviewToken": batch["reviewToken"], "rating": "Good"})
        batch = request("POST", "/api/bank/batch/next", {"lectures": [{"subject": "private", "runId": "demo"}]})
        assert batch["question"]["question_id"] == qid
        request("PUT", f"{BASE}/questions/{qid}/suspension", {"reviewToken": batch["reviewToken"], "suspended": True})
        request("DELETE", f"{BASE}/personal-questions/Q1", status=404)
        request("DELETE", f"{BASE}/personal-questions/{qid}")
        info = request("GET", BASE)
        assert info["personalQuestions"] == [] and info["suspendedQuestions"] == []
        assert info["lectureGoal"]["total"] == 1 and info["undoToken"] is not None
        assert request("POST", BASE + "/next?choiceProtocol=true")["question"] is None
    print("PASS: private add/edit/delete, idempotency, isolation, study/batch/undo/overview, Essential and bank rebuilds")


if __name__ == "__main__":
    main()
