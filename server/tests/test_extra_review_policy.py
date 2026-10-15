"""Extra study shares weighted reviews, includes future/done cards, spaces directions and avoids immediate repeats."""
import copy
from unittest.mock import patch

from app.study_engine import empty_state, record_review, select_question
from app.study_engine.daily_queue import daily_candidates, lecture_goal, select_daily_question, select_extra_question
from app.study_engine.memory import DAY_MS
from app.study_engine.ordering import review_weight
from app.study_engine.planning import day_start
from tests.test_question_order import make_bank, NOW, EXAM


def learned(bank, *, at=NOW - DAY_MS, due=NOW - 1):
    state = empty_state()
    for q in bank["questions"]:
        state = record_review(bank, state, q["question_id"], "Good", at)
        state["items"][q["question_id"]]["due_at"] = due
        state["history"][-1]["next_due_at"] = due
    return state


def main():
    bank = make_bank([(f"Q{i}", f"C{i}", "direct", i + 1, []) for i in range(4)])
    for q, tier in zip(bank["questions"], ("Core", "Advanced", "Optional", "Core")):
        q["tier"] = tier
    # Same targets isolate the multiplier from any separately authored mastery targets.
    for plan in bank["retrieval_plan"]:
        plan["target_mastery"] = 0.4
    state = learned(bank)
    before = copy.deepcopy(state)
    daily, _ = daily_candidates(bank, state, EXAM, NOW)
    extra, _ = daily_candidates(bank, state, EXAM, NOW, extra=True)
    assert {c["question"]["question_id"] for c in daily} == {c["question"]["question_id"] for c in extra}
    assert len(set(review_weight(c, NOW) for c in daily)) == 1  # No tier multiplier.
    assert [review_weight(c, NOW) for c in daily] == [review_weight(c, NOW) for c in extra]
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[-1]]) as draw:
        normal = select_daily_question(bank, state, EXAM, NOW)
        added = select_question(bank, state, EXAM, NOW, prefer_unseen=True)
        assert normal["question"] == added["question"]
        assert draw.call_args_list[0].kwargs["weights"] == draw.call_args_list[1].kwargs["weights"]
    assert state == before
    future = learned(bank, due=NOW + 7 * DAY_MS)
    assert select_daily_question(bank, future, EXAM, NOW)["question"] is None
    assert len(daily_candidates(bank, future, EXAM, NOW, extra=True)[0]) == 4
    nearer = copy.deepcopy(future)
    nearer["items"]["Q1"]["due_at"] = NOW + DAY_MS
    candidates, _ = daily_candidates(bank, nearer, EXAM, NOW, extra=True)
    upcoming = {c["question"]["question_id"]: review_weight(c, NOW) for c in candidates}
    assert upcoming["Q1"] > upcoming["Q2"]  # Earlier future dates matter, too.
    # Latest scheduled date is used after extra grading, rather than yesterday's baseline.
    future = record_review(bank, future, "Q0", "Good", NOW)
    units, _ = daily_candidates(bank, future, EXAM, NOW, extra=True)
    q0 = next(c for c in units if c["question"]["question_id"] == "Q0")
    assert q0["unit"]["scheduled_due"] == future["items"]["Q0"]["due_at"]
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[0]]) as draw:
        got = select_extra_question(bank, future, EXAM, NOW + 1)
        assert got["question"]["question_id"] != "Q0"
        assert all(c["question"]["question_id"] != "Q0" for c in draw.call_args.args[0])
    # All cards first graded today are reviews in extra study, not a deterministic new-card pool.
    today = learned(bank, at=NOW, due=NOW + DAY_MS)
    assert all(c["unit"]["kind"] == "review" for c in daily_candidates(bank, today, EXAM, NOW, extra=True)[0])
    assert lecture_goal(bank, today, "test", NOW)["met"]
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[0]]) as draw:
        assert select_extra_question(bank, today, EXAM, NOW)["question"]
        assert draw.call_count == 1
    # Overdue and weakness/importance still change weights in both modes.
    weighted = learned(bank, at=NOW - 5 * DAY_MS, due=NOW - 1)
    weighted["items"]["Q0"]["due_at"] = NOW - 3 * DAY_MS
    weighted["history"][0]["next_due_at"] = NOW - 3 * DAY_MS
    weighted["dimensions"]["C2:direct"]["mastery"] = 0.01
    bank["questions"][1]["importance"] = 1
    candidates, _ = daily_candidates(bank, weighted, EXAM, NOW, extra=True)
    weights = {c["question"]["question_id"]: review_weight(c, NOW) for c in candidates}
    assert weights["Q0"] > weights["Q3"] and weights["Q2"] > weights["Q3"] > weights["Q1"]
    # Four other questions separate same-concept recall directions in extra study, too.
    spaced = make_bank([("A", "CA", "direct", 1, []), ("reverse", "CA", "reverse", 1, [])] +
                       [(f"B{i}", f"CB{i}", "direct", i + 2, []) for i in range(5)])
    state = learned(spaced, due=NOW + DAY_MS)
    state = record_review(spaced, state, "A", "Good", NOW)
    for i in range(4):
        got = select_extra_question(spaced, state, EXAM, NOW + i + 1)
        assert got["question"]["question_id"] != "reverse"
        state = record_review(spaced, state, f"B{i}", "Good", NOW + i + 1)
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [next(c for c in pool if c["question"]["question_id"] == "reverse")]):
        assert select_extra_question(spaced, state, EXAM, NOW + 5)["question"]["question_id"] == "reverse"
    # One available question can be repeated immediately, including across the Korean day boundary.
    single = copy.deepcopy(bank)
    single["questions"] = single["questions"][:1]
    for at in (NOW, day_start(NOW) - 10_000):
        solo = learned(single, at=at, due=at + 7 * DAY_MS)
        ready = select_extra_question(single, solo, EXAM, at + 1)
        assert ready["question"]["question_id"] == "Q0" and ready["retry_at"] is None
        assert select_extra_question(single, solo, EXAM, at + 10_000)["question"]["question_id"] == "Q0"
    excluded = {**today, "suspended_question_ids": [q["question_id"] for q in bank["questions"]]}
    assert select_extra_question(bank, excluded, EXAM, NOW)["question"] is None
    assert select_extra_question(bank, excluded, EXAM, NOW)["retry_at"] is None
    print("PASS: shared weights without tier multipliers, future/done cards, due/weakness/importance, spacing, last-card exclusion, single-card immediate retry, KST and suspensions")


if __name__ == "__main__":
    main()
