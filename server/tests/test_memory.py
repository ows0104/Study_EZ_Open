"""시간·간격·평가에 따른 망각, 조회 무변경, 회차 결과 보존."""

import copy
import math
import os

os.environ.update(ENVIRONMENT="local-test", DATABASE_URL="sqlite://")

from app.study_engine import empty_state, record_review, start_session, end_session, session_summary
from app.study_engine.engine import concept_map, rank_questions
from app.study_engine.mastery import lecture_mastery
from app.study_engine.memory import DAY_MS, memory_snapshot, next_stability, retention
from app.study_engine.policy import DEFAULT, validate_policy
from tests.bank_fixtures import example_bank


def main():
    now = 1_791_003_600_000
    bank = example_bank()
    bank["questions"][1]["advanced"] = True
    dim = {"mastery": 0.95, "reviews": 10, "updated_at": now, "stability_days": 1}
    assert retention(dim, now) == retention(dim, now - DAY_MS) == 1
    assert math.isclose(retention(dim, now + DAY_MS), 0.9)
    assert math.isclose(retention(dim, now + 9 * DAY_MS), 0.5)
    assert retention({**dim, "stability_days": 5}, now + 9 * DAY_MS) > retention(dim, now + 9 * DAY_MS)
    legacy = {k: v for k, v in dim.items() if k != "stability_days"}
    assert retention(legacy, now + DAY_MS) == retention(dim, now + DAY_MS)
    assert retention({"mastery": 0.8, "reviews": 3}, now) == 1  # 학습 시각을 추측하지 않는다.

    state = empty_state()
    state["dimensions"]["C1:direct"] = dim
    # 옛 간격이 아주 길어도 망각된 문항을 복습 대상으로 다시 고른다.
    state["items"]["Q1"] = {"reviews": 10, "interval": 365 * DAY_MS, "due_at": now + 365 * DAY_MS}
    untouched = copy.deepcopy(state)
    later = now + 9 * DAY_MS
    recent_score = lecture_mastery(bank, state, now=now)
    forgotten = lecture_mastery(bank, state, now=later)
    assert recent_score["status"] == "mastered" and forgotten["status"] == "needs_review"
    assert recent_score["score"] > forgotten["score"] > 0
    assert forgotten == lecture_mastery(bank, state, now=later) and state == untouched
    expected = memory_snapshot(state, later)["dimensions"]["C1:direct"]["mastery"]
    cmap = concept_map(bank, state, now=later)
    assert cmap[0]["directions"][0]["mastery"] == expected
    ranked = rank_questions(bank, state, "2026-12-01", later)
    first = next(r for r in ranked if r["question_id"] == "Q1")
    assert first["mastery"] == expected and first["components"]["novelty"] == DEFAULT["weights"]["due"]
    assert not next(r for r in ranked if r["question_id"] == "Q2")["eligible"]  # 기초가 약해진 심화 진입

    reviewed = record_review(bank, state, "Q1", "Good", later)
    restored = reviewed["dimensions"]["C1:direct"]
    assert restored["mastery"] > expected and restored["stability_days"] > dim["stability_days"]
    assert reviewed["history"][-1]["mastery_before"] == expected
    due = reviewed["items"]["Q1"]["due_at"]
    assert math.isclose(memory_snapshot(reviewed, due)["dimensions"]["C1:direct"]["mastery"], .85, abs_tol=1e-8)
    assert state == untouched
    failed = record_review(bank, state, "Q1", "Again", later)["dimensions"]["C1:direct"]
    assert failed["mastery"] < expected and failed["stability_days"] < dim["stability_days"]
    assert next_stability(dim, "Easy", now + DAY_MS) > next_stability(dim, "Good", now + DAY_MS)
    assert next_stability(dim, "Good", now + DAY_MS) > next_stability(dim, "Hard", now + DAY_MS)

    cram = empty_state()
    for i in range(20):
        cram = record_review(bank, cram, "Q1", "Good", now + i * 60_000)
    assert cram["dimensions"]["C1:direct"]["stability_days"] == DEFAULT["forgetting"]["initialDays"]["Good"]
    assert cram["items"]["Q1"]["interval"] < 2 * DAY_MS
    assert math.isclose(retention(cram["dimensions"]["C1:direct"], now + 19 * 60_000 + DAY_MS), 0.9)
    spaced, at = empty_state(), now
    for _ in range(12):
        spaced = record_review(bank, spaced, "Q1", "Good", at)
        at += round(spaced["dimensions"]["C1:direct"]["stability_days"] * DAY_MS)
    assert lecture_mastery(bank, spaced)["status"] == "mastered"
    assert spaced["dimensions"]["C1:direct"]["stability_days"] <= DEFAULT["forgetting"]["maxDays"]

    session = start_session(bank, state, 10, later)
    assert session["session"]["core_before"] == expected
    assert session_summary(bank, session, now=later)["core_after"] == expected
    assert session_summary(bank, session, now=later + DAY_MS)["core_after"] < expected
    session = record_review(bank, session, "Q1", "Good", later + 1000)
    session = end_session(bank, session, "user_finished", later + 2000)
    assert session_summary(bank, session, now=later + 50 * DAY_MS) == session["sessions"][-1]

    for key, value in [("minDays", 0), ("legacyDays", 0), ("maxDays", float("inf")), ("lapseMultiplier", 1)]:
        policy = copy.deepcopy(DEFAULT)
        policy["forgetting"][key] = value
        try:
            validate_policy(policy)
        except ValueError:
            pass
        else:
            raise AssertionError(f"잘못된 망각 정책 허용: {key}")
    print("PASS: 망각곡선, 간격 반복, 즉시 반복 제한, 목표 도달, 출제·표시 일치, 기록·회차 보존")


if __name__ == "__main__":
    main()
