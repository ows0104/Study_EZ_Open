"""Target-based intervals and private rescheduling use review facts, not the edit time."""
import copy
import datetime
import math
from dataclasses import replace
from unittest.mock import patch

from tests.test_bank import STUDENT, example_bank
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine as db_engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine import empty_state, record_review, start_session
from app.study_engine.engine import review_schedule, reschedule_bank, rank_questions
from app.study_engine.daily_queue import daily_units, lecture_goal, daily_candidates
from app.study_engine.memory import DAY_MS, memory_snapshot
from app.study_engine.personal_priority import personal_bank
from app.study_engine.planning import day_start
from app.study_engine.review_undo import remember_review, undo_review

NOW = 1791824400000
BASE = "/api/lectures/interval/demo/bank"


def main():
    bank = example_bank()
    bank["questions"] = bank["questions"][:1]
    at = NOW - 6 * DAY_MS
    snapshot = {"reviewed_at": at, "mastery_after": .95, "stability_days": 4}
    due = {}
    for tier, target in (("Core", .85), ("Important", .78), ("Optional", .55)):
        q = personal_bank(bank, {"question_tiers": {"Q1": tier}})["questions"][0]
        scheduled = review_schedule(bank, q, snapshot)
        due[tier] = scheduled["due_at"]
        assert scheduled["interval"] == scheduled["due_at"] - at
        measured = .95 / (1 + (scheduled["interval"] / DAY_MS) / 36)
        assert math.isclose(measured, target, abs_tol=1e-9)
    assert due["Core"] < due["Important"] < due["Optional"]
    assert due["Core"] < NOW < due["Optional"]
    # Identical grades and memory histories produce identical memory updates but different due dates.
    graded = {}
    seed = empty_state()
    seed["dimensions"]["C1:direct"] = {"mastery": .95, "reviews": 8, "updated_at": NOW - DAY_MS, "stability_days": 4}
    for tier in due:
        state = {**seed, "question_tiers": {"Q1": tier}}
        graded[tier] = record_review(bank, state, "Q1", "Good", NOW)
        assert graded[tier]["history"][-1]["next_due_at"] == graded[tier]["items"]["Q1"]["due_at"]
        assert graded[tier]["items"]["Q1"]["target_schedule"]["target"] == {"Core": .85, "Important": .78, "Optional": .55}[tier]
    assert graded["Core"]["dimensions"] == graded["Optional"]["dimensions"]
    assert graded["Core"]["items"]["Q1"]["due_at"] < graded["Important"]["items"]["Q1"]["due_at"] < graded["Optional"]["items"]["Q1"]["due_at"]
    low = record_review(bank, empty_state(), "Q1", "Again", NOW)
    assert low["items"]["Q1"]["due_at"] == day_start(NOW) + DAY_MS
    assert lecture_goal(bank, low, "test", NOW)["met"]
    assert lecture_goal(bank, low, "test", day_start(NOW) + DAY_MS)["reviewRemaining"] == 1
    # The old S-day cap must not make the lower-target schedule due early.
    optional = graded["Optional"]
    item = optional["items"]["Q1"]
    check_at = NOW + 2 * optional["dimensions"]["C1:direct"]["stability_days"] * DAY_MS
    assert check_at < item["due_at"]
    assert rank_questions(bank, optional, "2026-12-01", int(check_at))[0]["components"]["novelty"] == .25
    # Legacy schedules are recalculated on a priority change without touching their historical record.
    legacy = record_review(bank, empty_state(), "Q1", "Easy", at)
    legacy["dimensions"]["C1:direct"].update(mastery=.95, stability_days=4)
    legacy["history"][-1].update(mastery_after=.95, stability_after=4, next_due_at=at + 200 * DAY_MS)
    legacy["history"][-1].pop("target_schedule")
    legacy["items"]["Q1"] = {"reviews": 1, "interval": 200 * DAY_MS, "due_at": at + 200 * DAY_MS}
    legacy = start_session(bank, legacy, None, NOW)
    legacy["served"] = {"question_id": "Q1", "token": "current", "revealed": True, "presented_at": NOW - 1000}
    preserved = copy.deepcopy(legacy)
    assert reschedule_bank(bank, legacy) == legacy, "untouched legacy schedules retain their next date until grading or a tier change"
    pre_saved = {**legacy, "question_tiers": {"Q1": "Core"}}
    recalculated = reschedule_bank(bank, pre_saved)
    assert recalculated["items"]["Q1"]["due_at"] == due["Core"]
    assert recalculated["history"] == legacy["history"] and recalculated["dimensions"] == legacy["dimensions"]
    assert reschedule_bank(bank, recalculated) == recalculated
    assert daily_units(bank, pre_saved, NOW)[0]["scheduled_due"] == due["Core"]
    assert pre_saved["items"] == legacy["items"], "queue reads never mutate persistent state"
    history_only = {**pre_saved, "items": {}}
    assert reschedule_bank(bank, history_only)["items"]["Q1"]["due_at"] == due["Core"]
    ungraded = {**empty_state(), "question_tiers": {"Q1": "Core"}}
    assert reschedule_bank(bank, ungraded) == ungraded
    graded_once = record_review(bank, recalculated, "Q1", "Good", NOW)
    remember_review(recalculated, graded_once)
    graded_once["question_tiers"] = {"Q1": "Optional"}
    restored = reschedule_bank(bank, undo_review(graded_once, "current"))
    assert restored["items"]["Q1"]["due_at"] == due["Optional"], "undo restores memory but respects the CURRENT tier"
    assert restored["history"] == legacy["history"]
    Base.metadata.create_all(db_engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="interval", run_id="demo", uid="interval-demo", date=datetime.date(2026, 10, 12),
                       slot=1, slot_end=1, start_time="09:00", title="Interval test"))
        db.flush()
        db.add(QuizBank(subject="interval", run_id="demo", build_id="v1", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.add(BankState(user_id=STUDENT.id, subject="interval", run_id="demo", build_id="v1", state=legacy))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)
    def stored():
        with SessionLocal() as db:
            return copy.deepcopy(db.get(BankState, (STUDENT.id, "interval", "demo")).state)
    def put(tier, token="current", status=200):
        response = client.put(BASE + "/questions/Q1/priority", json={"tier": tier, "reviewToken": token})
        assert response.status_code == status, response.text
        return response.json()
    with patch("app.routes.bank.engine.now_ms", return_value=NOW):
        for tier in ("Optional", "Core", "Important", "Optional", "Core"):
            before_change = stored()
            result = put(tier)
            state = stored()
            assert result["rescheduled"] and state["items"]["Q1"]["due_at"] == due[tier]
            assert state["history"] == preserved["history"] and state["dimensions"] == preserved["dimensions"]
            assert state["served"] == before_change["served"] and state["session"] == before_change["session"]
            expected = 1 if due[tier] < day_start(NOW) + DAY_MS else 0
            assert result["lectureGoal"]["reviewRemaining"] == expected
            assert client.get(BASE).json()["lectureGoal"]["reviewRemaining"] == expected
            if tier == "Optional":
                payload = {"lectures": [{"subject": "interval", "runId": "demo"}],
                           "resumeLecture": {"subject": "interval", "runId": "demo"}}
                batch = client.post("/api/bank/batch/next", json=payload).json()
                assert batch["reviewToken"] == "current" and batch["question"]["tier"] == "Optional"
        put("Optional", "stale", 409)
        assert stored()["items"]["Q1"]["due_at"] == due["Core"]
        assert put(None)["question"]["targetMastery"] == .85
        assert stored()["items"]["Q1"]["due_at"] == due["Core"]
        # Extra review grading, tier change, then undo keep the CURRENT tier and recompute the restored old schedule.
        assert client.post(BASE + "/rate", json={"reviewToken": "current", "rating": "Good"}).status_code == 200
        assert client.post(BASE + "/next").status_code == 200
        # A completed daily task can be resumed through undo; restore the previous review first.
        undo = client.post(BASE + "/undo", json={"reviewToken": "current"}).json()
        assert undo["reviewToken"] != "current"
        put("Optional", undo["reviewToken"])
        assert stored()["items"]["Q1"]["due_at"] == due["Optional"]
        assert stored()["history"] == preserved["history"]
        pools, _ = daily_candidates(bank, stored(), "2026-12-01", NOW, extra=True)
        assert pools[0]["unit"]["scheduled_due"] == due["Optional"]
        app.dependency_overrides[get_current_user] = lambda: replace(STUDENT, id="another-interval-student")
        put("Core", undo["reviewToken"], 409)
        with SessionLocal() as db:
            assert db.get(QuizBank, ("interval", "demo")).bank == bank
    print("PASS: curve thresholds, tier/grade schedules, next-day floor, legacy rescheduling, anchored edits, read purity, daily/extra queues, reset, undo and user isolation")


if __name__ == "__main__":
    main()
