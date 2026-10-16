"""Private priorities affect study, survive refresh/undo, and never alter shared questions."""
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
from app.study_engine import rank_questions, concept_map, empty_state
from app.study_engine.daily_queue import select_daily_question
from app.study_engine.mastery import mastery_concepts
from app.study_engine.planning import state_before

NOW = 1791824400000
BASE = "/api/lectures/priority/demo/bank"


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    bank["retrieval_plan"][0]["target_mastery"] = .4
    bank["questions"] = bank["questions"][:2]
    bank["questions"][0].update(format="mcq", mcq_mode="recall_first", advanced=True,
        options=[{"id": "A", "text": "first"}, {"id": "B", "text": "second"}], correct_option_ids=["A"])
    bank["questions"][1].update(tier="Important", importance=4, prerequisites=[], retrieval_direction="reverse")
    original = copy.deepcopy(bank)
    with SessionLocal() as db:
        db.add(Lecture(subject="priority", run_id="demo", uid="priority-demo", date=datetime.date(2026, 10, 12),
                       slot=1, slot_end=1, start_time="09:00", title="Priority test"))
        db.flush()
        db.add(QuizBank(subject="priority", run_id="demo", build_id="v1", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)

    def put(qid, token, tier, status=200):
        response = client.put(f"{BASE}/questions/{qid}/priority", json={"tier": tier, "reviewToken": token})
        assert response.status_code == status, response.text
        return response.json()

    with patch("app.routes.bank.engine.now_ms", return_value=NOW):
        first = client.post(BASE + "/next?choiceProtocol=true").json()
        token = first["reviewToken"]
        assert first["question"]["question_id"] == "Q1"
        assert first["question"]["targetMastery"] == .4
        put("Q1", token, "Advanced", 422)
        put("missing", token, "Core", 404)
        put("Q2", token, "Optional", 409)
        put("Q1", "stale", "Optional", 409)
        changed = put("Q1", token, "Optional")["question"]
        assert changed["tier"] == "Optional" and changed["importance"] == 2
        assert changed["targetMastery"] == .55
        assert changed["personalTier"] and changed["originalTier"] == "Core" and changed["advanced"]
        assert changed["options"] == [] and "answer" not in changed and "correct_option_ids" not in changed
        refreshed = client.post(BASE + "/next?choiceProtocol=true").json()
        assert refreshed["reviewToken"] == token and refreshed["question"]["tier"] == "Optional"
        assert refreshed["answer"] is None
        with SessionLocal() as db:
            state = db.get(BankState, (STUDENT.id, "priority", "demo")).state
            assert state["history"] == [] and state["items"] == {} and state["dimensions"] == {}
            assert db.get(QuizBank, ("priority", "demo")).bank == original
            ranked = rank_questions(bank, state, "2026-11-12", NOW)
            row = next(r for r in ranked if r["question_id"] == "Q1")
            assert row["tier"] == "Optional" and row["target"]["effective"] == .55
            assert row["components"]["importance"] == .85
            assert select_daily_question(bank, {**state, "served": None}, "2026-11-12", NOW)["question"]["question_id"] == "Q1", "private tier changes keep first-learning slide order"
            assert concept_map(bank, state)[0]["directions"][0]["target"] == .55
            assert mastery_concepts(bank, state)[0] == "all", "private Core scope is used by lecture mastery"
        assert client.get(BASE).json()["summary"]["studyQuestionCount"] == 1
        for tier, target in (("Essential", .9), ("Core", .85), ("Important", .78), ("Optional", .55)):
            assert put("Q1", token, tier)["question"]["targetMastery"] == target
            assert client.get(BASE).json()["conceptMap"][0]["directions"][0]["target"] == target
        app.dependency_overrides[get_current_user] = lambda: replace(STUDENT, id="another-priority-student")
        other = client.post(BASE + "/next?choiceProtocol=true").json()
        assert other["question"]["tier"] == "Core" and not other["question"].get("personalTier")
        assert other["question"]["targetMastery"] == .4
        put("Q1", token, "Optional", 409)
        app.dependency_overrides[get_current_user] = lambda: STUDENT
        shown = client.post(BASE + "/options", json={"reviewToken": token}).json()
        assert len(shown["question"]["options"]) == 2 and shown["question"]["tier"] == "Optional"
        draft = client.get(BASE + "/questions/Q1/personal").json()
        saved = client.put(BASE + "/questions/Q1/personal", json={"revision": draft["revision"],
            "question": "My wording", "answer": draft["draft"]["answer"]}).json()
        assert saved["question"]["tier"] == "Optional" and saved["question"]["personalEdited"]
        assert saved["question"]["targetMastery"] == .55
        corrected = client.post(BASE + "/next?choiceProtocol=true").json()
        assert corrected["question"]["question"] == "My wording" and corrected["question"]["tier"] == "Optional"
        assert client.post(BASE + "/reveal", json={"reviewToken": token}).status_code == 200
        assert client.post(BASE + "/rate", json={"reviewToken": token, "rating": "Good"}).status_code == 200
        undo = client.post(BASE + "/undo", json={"reviewToken": token}).json()
        assert undo["question"]["tier"] == "Optional" and undo["answer"]
        reset = put("Q1", undo["reviewToken"], None)["question"]
        assert reset["tier"] == "Core" and reset["importance"] == 5 and not reset.get("personalTier")
        assert reset["targetMastery"] == .4
        assert reset["options"] == undo["question"]["options"], "tier reset preserves the current personal question options"
        put("Q1", undo["reviewToken"], "Important")
        batch = client.post("/api/bank/batch/next", json={"lectures": [{"subject": "priority", "runId": "demo"}]}).json()
        assert batch["question"]["tier"] == "Important" and batch["reviewToken"] == undo["reviewToken"]
        assert batch["question"]["targetMastery"] == .78
        with SessionLocal() as db:
            row = db.get(QuizBank, ("priority", "demo"))
            row.build_id = "v2"
            db.commit()
        put("Q1", undo["reviewToken"], "Core", 409)
        rebuilt = client.post(BASE + "/next?choiceProtocol=true").json()
        assert rebuilt["question"]["tier"] == "Core" and not rebuilt["question"].get("personalTier")
    assert bank == original, "pure study reads never mutate shared data"
    state = empty_state()
    state["dimensions"] = {"C1:direct": {"mastery": .6, "reviews": 2}}
    state["question_tiers"] = {"Q1": "Optional"}
    one = {**bank, "questions": bank["questions"][:1]}
    before = copy.deepcopy(state)
    assert concept_map(one, state)[0]["progress"] == 1
    state["question_tiers"] = {"Q1": "Core"}
    assert abs(concept_map(one, state)[0]["progress"] - .6 / .85) < 1e-9
    assert state["dimensions"] == before["dimensions"] and state["history"] == before["history"]
    assert state_before(one, state, NOW)["question_tiers"] == state["question_tiers"]
    print("PASS: personal priority validation, isolation, hidden answers, selection, targets, refresh, undo, reset, batch, and rebuild")


if __name__ == "__main__":
    main()
