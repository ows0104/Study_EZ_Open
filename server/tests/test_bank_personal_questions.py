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
from app.models import Asset, BankFeedback, BankState, Lecture, QuizBank, SLIDE_KINDS
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
                        pages={"Q1": [3]}, validation={"pass": True}, open_to_students=True))
        db.add(Asset(id="personal-reference", subject="private", run_id="demo", kind=SLIDE_KINDS["bank"],
                     slide_no=3, filename="3.png", object_key="slides/3.png"))
        db.add(Asset(id="replacement", subject="private", run_id="demo", kind=SLIDE_KINDS["bank"],
                     slide_no=7, filename="7.png", object_key="slides/7.png"))
        db.add(Asset(id="wrong-kind", subject="private", run_id="demo", kind="notes_current",
                     slide_no=9, filename="notes.pdf", object_key="notes.pdf"))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)

    def request(method, path, payload=None, status=200):
        response = client.request(method, path, **({"json": payload} if payload is not None else {}))
        assert response.status_code == status, response.text
        return response.json()

    with patch("app.routes.bank.engine.now_ms", return_value=NOW):
        draft = {"clientId": str(uuid.uuid4()), "question": "내가 외울 질문", "answer": "내 정답",
                 "explanation": "내 설명", "tier": "Essential", "sourceQuestionId": "Q1"}
        options = request("GET", BASE + "/personal-question-slides?sourceQuestionId=Q1")
        assert options["selectedAssetIds"] == ["personal-reference"]
        assert {s["assetId"] for s in options["slides"]} == {"personal-reference", "replacement"}
        assert request("GET", BASE + "/personal-question-slides")["selectedAssetIds"] == []
        request("GET", BASE + "/personal-question-slides?sourceQuestionId=missing", status=404)
        for ids in [["wrong-kind"], ["missing-asset"]]:
            request("POST", BASE + "/personal-questions", {**draft, "slideAssetIds": ids}, 422)
        for ids in [[], ["replacement", "replacement"]]:
            made = request("POST", BASE + "/personal-questions", {**draft, "clientId": str(uuid.uuid4()), "slideAssetIds": ids}, 201)
            from app.models import BankPersonalEdit
            from app.routes.bank import _slides
            with SessionLocal() as db:
                saved = db.get(BankPersonalEdit, (STUDENT.id, "private", "demo", made["questionId"]))
                expected = ["replacement"] if ids else []
                assert [r["assetId"] for r in saved.original["personalSlideReferences"]] == expected
                assert saved.original["source_refs"] == ([{"source_id": "S1", "locator": "p7"}] if ids else [])
                assert [s["page"] for s in _slides(db, db.get(QuizBank, ("private", "demo")), made["questionId"], saved.original)] == ([7] if ids else [])
            request("DELETE", f"{BASE}/personal-questions/{made['questionId']}")
        request("POST", BASE + "/personal-questions", {**draft, "sourceQuestionId": "missing"}, 404)
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
        assert "personalSlideReferences" not in current["question"]
        assert current["question"]["source_refs"] == bank["questions"][0]["source_refs"]
        assert [slide["page"] for slide in current["preloadSlides"]] == [3]
        assert all(not slide["primary"] for slide in current["preloadSlides"])
        # A second addition can inherit a private card's references without a reveal.
        inherited = request("POST", BASE + "/personal-questions", {**draft,
            "clientId": str(uuid.uuid4()), "sourceQuestionId": qid}, 201)
        with SessionLocal() as db:
            from app.models import BankPersonalEdit
            saved = db.get(BankPersonalEdit, (STUDENT.id, "private", "demo", inherited["questionId"]))
            assert saved.original["personalSlideReferences"][0]["assetId"] == "personal-reference"
            assert "url" not in saved.original["personalSlideReferences"][0]
        request("DELETE", f"{BASE}/personal-questions/{inherited['questionId']}")
        token = current["reviewToken"]
        snapshot = request("GET", f"{BASE}/questions/{qid}/personal")
        assert snapshot["personalAdded"] and snapshot["draft"]["explanation"] == "내 설명"
        edited = request("PUT", f"{BASE}/questions/{qid}/personal", {
            "revision": snapshot["revision"], "question": "바꾼 질문", "answer": "바꾼 답", "explanation": "바꾼 설명"})
        assert not edited["reported"] and edited["answer"]["answer"] == "바꾼 답"
        assert request("POST", BASE + "/next?choiceProtocol=true")["question"]["question"] == "바꾼 질문"
        revealed = request("POST", BASE + "/reveal", {"reviewToken": token})
        assert revealed["answer"] == "바꾼 답" and revealed["explanation"] == "바꾼 설명" and revealed["personalAnswer"]
        assert [slide["page"] for slide in revealed["slides"]] == [3]
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
        # Each private format must survive storage and the real serving contract.
        settings_cases = [
            {"format": "mcq", "mcq_mode": "recall_first", "retrieval_direction": "reverse",
             "options": [{"id": "1", "text": "맞는 보기"}, {"id": "2", "text": "다른 보기"}], "correct_option_ids": ["1"]},
            {"format": "multi_select", "mcq_mode": "comparison",
             "options": [{"id": "1", "text": "첫째"}, {"id": "2", "text": "둘째"}], "correct_option_ids": ["1", "2"]},
            {"format": "matching", "answer_pairs": [{"left": "a", "right": "A"}, {"left": "b", "right": "B"}]},
            {"format": "sequence", "correct_order": ["시작", "중간", "끝"]},
            {"format": "cloze", "question": "답은 {{c1}}", "answer_units": ["정답"]},
            {"format": "list", "answer_units": ["하나", "둘"]},
            {"format": "ox"},
        ]
        for settings in settings_cases:
            created = request("POST", BASE + "/personal-questions", {**draft, "clientId": str(uuid.uuid4()), **settings}, 201)
            with SessionLocal() as db:
                db.delete(db.get(BankState, (STUDENT.id, "private", "demo")))
                db.commit()
            shared = request("POST", BASE + "/next?choiceProtocol=true")
            assert shared["question"]["question_id"] == "Q1"
            request("POST", BASE + "/reveal", {"reviewToken": shared["reviewToken"]})
            request("POST", BASE + "/rate", {"reviewToken": shared["reviewToken"], "rating": "Good"})
            served = request("POST", BASE + "/next?choiceProtocol=true")
            q = served["question"]
            assert q["question_id"] == created["questionId"] and q["format"] == settings["format"]
            assert q["retrieval_direction"] == settings.get("retrieval_direction", "direct")
            assert "answer" not in q and "correct_option_ids" not in q
            if settings.get("mcq_mode") == "recall_first":
                assert not q["options"]
                request("POST", BASE + "/reveal", {"reviewToken": served["reviewToken"]}, 409)
                shown = request("POST", BASE + "/options", {"reviewToken": served["reviewToken"]})
                assert len(shown["question"]["options"]) == 2
            revealed = request("POST", BASE + "/reveal", {"reviewToken": served["reviewToken"]})
            assert revealed["correctOptionIds"] == settings.get("correct_option_ids", [])
            assert revealed["answerUnits"] == settings.get("answer_units", [])
            assert revealed["answerPairs"] == settings.get("answer_pairs", [])
            assert revealed["correctOrder"] == settings.get("correct_order", [])
            if settings["format"] in {"mcq", "multi_select", "matching", "sequence"}:
                assert not revealed["personalAnswer"], "structured private answers retain scoring"
            if settings["format"] == "mcq":
                snapshot = request("GET", f"{BASE}/questions/{created['questionId']}/personal")
                edited = request("PUT", f"{BASE}/questions/{created['questionId']}/personal", {
                    "revision": snapshot["revision"], "question": draft["question"], "answer": "새로 고친 답"})
                assert edited["answer"]["personalAnswer"] and edited["answer"]["correctOptionIds"] == []
            request("DELETE", f"{BASE}/personal-questions/{created['questionId']}")
        for invalid in [
            {"format": "unknown"}, {"retrieval_direction": "unknown"}, {"format": "mcq"},
            {"format": "mcq", "options": [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}], "correct_option_ids": ["3"]},
            {"format": "matching", "answer_pairs": [{"left": "a", "right": ""}]},
            {"format": "sequence", "correct_order": ["중복", "중복"]}, {"format": "cloze"},
        ]:
            request("POST", BASE + "/personal-questions", {**draft, "clientId": str(uuid.uuid4()), **invalid}, 422)
        plain = request("POST", BASE + "/personal-questions", {**draft, "clientId": str(uuid.uuid4()), "sourceQuestionId": None}, 201)
        snapshot = request("GET", f"{BASE}/questions/{plain['questionId']}/personal")
        assert snapshot["original"]["question"] == draft["question"]
    print("PASS: private add/edit/delete, idempotency, isolation, study/batch/undo/overview, Essential and bank rebuilds")


if __name__ == "__main__":
    main()
