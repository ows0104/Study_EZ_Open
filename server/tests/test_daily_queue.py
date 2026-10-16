"""Per-question coverage, all-new-before-review order, prerequisites and day boundaries."""
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
    # All unseen questions, including advanced/optional, precede even overdue core reviews.
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
    assert selected[:3] == ["Q3", "variant", "optional"]
    assert set(selected[3:]) == {"Q1", "Q2"}
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
    established = empty_state()
    established["dimensions"]["C1:direct"] = {"mastery": .95, "reviews": 5, "updated_at": NOW - 2 * DAY_MS, "stability_days": 5}
    easy = record_review(bank, established, "Q1", "Easy", NOW - DAY_MS)
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
    # 선행문항이 뒤쪽 슬라이드라도 먼저 풀고, 이후에는 슬라이드 흐름으로 돌아간다.
    for q, page in zip(prereq["questions"], (30, 40, 1)):
        q["source_refs"] = [{"source_id": "S1", "locator": f"p.{page}"}]
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
    # All unseen questions and due reviews stay in today's target, including after ten new answers.
    large = example_bank()
    large["questions"] += [{**copy.deepcopy(large["questions"][0]), "question_id": f"N{i:02d}"}
                           for i in range(24)]
    state = record_review(large, original, "Q1", "Again", NOW - DAY_MS)
    state = record_review(large, state, "Q2", "Again", NOW - DAY_MS)
    target = lecture_goal(large, state, "test", NOW)
    assert target["total"] == 27 and target["newRemaining"] == 25 and target["reviewRemaining"] == 2
    assert target["unlearnedRemaining"] == 25
    kinds, first_pass = [], set()
    for i in range(27):
        q = select_daily_question(large, state, EXAM, NOW + i)["question"]
        qid = q["question_id"]
        kinds.append("review" if qid in ("Q1", "Q2") else "new")
        if kinds[-1] == "new":
            assert qid not in first_pass
            first_pass.add(qid)
        state = record_review(large, state, qid, "Again", NOW + i)
        goal = lecture_goal(large, state, "test", NOW + i)
        assert goal["total"] == 27 and goal["completed"] == i + 1
        assert goal["met"] == (i == 26)
    assert kinds == ["new"] * 25 + ["review"] * 2
    assert len(first_pass) == 25 and goal["unlearnedRemaining"] == 0
    assert select_daily_question(large, state, EXAM, NOW + 27)["question"] is None
    from app.study_engine import select_question
    extra = select_question(large, state, EXAM, NOW + 61_000, prefer_unseen=True)["question"]
    assert extra["question_id"] in first_pass | {"Q1", "Q2"}
    state = record_review(large, state, extra["question_id"], "Again", NOW + 61_000)
    extra_goal = lecture_goal(large, state, "test", NOW + 61_000)
    assert extra_goal["met"] and extra_goal["total"] == extra_goal["completed"] == 27
    assert extra_goal["reviewedToday"] == 28 and extra_goal["unlearnedRemaining"] == 0
    next_goal = lecture_goal(large, state, "test", tomorrow)
    assert next_goal["newRemaining"] == 0 and next_goal["reviewRemaining"] == 27
    assert select_daily_question(large, state, EXAM, tomorrow)["question"] is not None
    # Repeating a question cannot complete other unseen questions; old capped study carries over.
    repeated = original
    for i in range(15):
        repeated = record_review(large, repeated, "Q1", "Again", NOW + i)
    assert lecture_goal(large, repeated, "test", NOW + 15)["newRemaining"] == 26
    for i, q in enumerate(large["questions"][1:16]):
        repeated = record_review(large, repeated, q["question_id"], "Again", NOW + 20 + i)
    carried = lecture_goal(large, repeated, "test", NOW + 40)
    assert not carried["met"] and carried["total"] == 27 and carried["remaining"] == 11
    assert select_daily_question(large, repeated, EXAM, NOW + 40)["question"] is not None
    # Extra review before its due date cannot expand the daily goal.
    future = record_review(single, established, "Q1", "Easy", NOW - DAY_MS)
    before_goal = lecture_goal(single, future, "test", NOW)
    future = record_review(single, future, "Q1", "Again", NOW)
    after_goal = lecture_goal(single, future, "test", NOW)
    assert before_goal["total"] == after_goal["total"] == 0 and after_goal["met"]
    assert after_goal["reviewedToday"] == 1
    # A known review follows the remaining new prerequisite and keeps its place in the goal.
    guarded = example_bank()
    guarded["questions"][2]["prerequisites"] = ["Q2"]
    guarded["questions"].append({**copy.deepcopy(guarded["questions"][0]), "question_id": "variant"})
    guarded_state = record_review(guarded, original, "Q3", "Again", NOW - DAY_MS)
    guarded_state = record_review(guarded, guarded_state, "Q1", "Again", NOW)
    guarded_state = record_review(guarded, guarded_state, "variant", "Again", NOW)
    assert select_daily_question(guarded, guarded_state, EXAM, NOW)["question"]["question_id"] == "Q2"
    guarded_state = record_review(guarded, guarded_state, "Q2", "Again", NOW)
    assert select_daily_question(guarded, guarded_state, EXAM, NOW)["question"]["question_id"] == "Q3"
    print("PASS: unlimited new questions before reviews, due reviews, distinct completion, carryover, stable extras, prerequisites, legacy, KST")


if __name__ == "__main__":
    main()
