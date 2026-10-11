"""Per-question coverage, new/review mixing, prerequisites and day boundaries."""
import copy
from datetime import datetime
from app.study_engine import empty_state, record_review
from app.study_engine.daily_queue import lecture_goal, select_daily_question
from app.study_engine.planning import KOREA, day_start
from app.study_engine.memory import DAY_MS
from app.study_engine.progress import mark_seen
from tests.bank_fixtures import example_bank

NOW = int(datetime(2026, 10, 6, 10, tzinfo=KOREA).timestamp() * 1000)
EXAM = "2026-10-20"


def main():
    bank = example_bank()
    bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "variant"})
    bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "optional", "tier": "Optional"})
    original = empty_state()
    assert lecture_goal(bank, original, "test", NOW)["newRemaining"] == 5
    # Two due reviews coexist with three unseen questions: both kinds must actually appear.
    state = record_review(bank, original, "Q1", "Again", NOW - DAY_MS)
    state = record_review(bank, state, "Q2", "Again", NOW - DAY_MS)
    goal = lecture_goal(bank, state, "test", NOW)
    assert goal["total"] == 5 and goal["reviewRemaining"] == 2 and goal["newRemaining"] == 3
    selected = []
    for i in range(5):
        before = copy.deepcopy(state)
        got = select_daily_question(bank, state, EXAM, NOW + i)
        qid = got["question"]["question_id"]
        assert state == before and qid not in selected
        selected.append(qid)
        row = next(r for r in got["ranked"] if r["question_id"] == qid)
        assert row["eligible"] and not row["reasons"]
        state = record_review(bank, state, qid, "Again", NOW + i)
        goal = lecture_goal(bank, state, "test", NOW + i)
        assert goal["completed"] == i + 1 and goal["total"] == 5
        assert goal["met"] == (i == 4)
    assert selected[0] == "variant" and selected[2] == "Q3" and selected[4] == "optional"
    assert set(selected[1::2]) == {"Q1", "Q2"}
    assert select_daily_question(bank, state, EXAM, NOW + 61_000)["question"] is None
    repeated = record_review(bank, state, "Q1", "Again", NOW + 61_000)
    assert lecture_goal(bank, repeated, "test", NOW + 61_000)["met"]
    assert lecture_goal(bank, repeated, "test", NOW + 61_000)["reviewedToday"] == 6
    tomorrow = day_start(NOW) + DAY_MS
    assert lecture_goal(bank, repeated, "test", tomorrow)["reviewRemaining"] == 5
    # A same-concept repeat and viewing without grading cannot complete other questions.
    partial = record_review(bank, original, "Q1", "Good", NOW)
    partial = record_review(bank, partial, "Q1", "Good", NOW + 1)
    for q in bank["questions"]:
        mark_seen(partial, q["question_id"])
    assert lecture_goal(bank, partial, "test", NOW + 1)["remaining"] == 4
    assert select_daily_question(bank, partial, EXAM, NOW + 1)["question"]["question_id"] == "variant"
    # Scheduled future reviews are excluded; unseen advanced questions stay in the daily task.
    easy = record_review(bank, original, "Q1", "Easy", NOW - DAY_MS)
    assert lecture_goal(bank, easy, "test", NOW)["total"] == 4
    assert lecture_goal(bank, easy, "test", NOW)["newRemaining"] == 4
    legacy = copy.deepcopy(easy)
    legacy["history"] = []
    before = copy.deepcopy(legacy)
    assert lecture_goal(bank, legacy, "test", NOW)["total"] == 4
    assert legacy == before and original == empty_state()
    # First-pass prerequisites use individual evaluated questions, not shared mastery gates.
    prereq = example_bank()
    prereq["questions"][0]["tier"] = "Advanced"
    prereq["questions"][2]["tier"] = "Core"
    assert lecture_goal(prereq, original, "test", NOW)["total"] == 3
    picked = select_daily_question(prereq, original, EXAM, NOW)["question"]
    assert picked["question_id"] == "Q1"
    unlocked = record_review(prereq, original, "Q1", "Again", NOW)
    assert select_daily_question(prereq, unlocked, EXAM, NOW)["question"]["question_id"] == "Q3"
    # Every grade counts once today, and a late difficult review returns the following day.
    single = example_bank()
    single["questions"] = single["questions"][:1]
    for rating in ("Again", "Hard", "Good", "Easy"):
        rated = record_review(single, original, "Q1", rating, NOW)
        assert lecture_goal(single, rated, "test", NOW)["met"]
        assert select_daily_question(single, rated, EXAM, NOW)["question"] is None
    late = record_review(single, original, "Q1", "Again", tomorrow - 10_000)
    assert lecture_goal(single, late, "test", tomorrow)["reviewRemaining"] == 1
    print("PASS: individual question coverage, alternating new/review, no duplicate completion, prerequisites, all tiers, future reviews, legacy, KST")


if __name__ == "__main__":
    main()
