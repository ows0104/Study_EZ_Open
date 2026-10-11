"""Explicit extra study covers unseen variants and advanced questions before repeats."""
import copy
from datetime import datetime

from app.study_engine import empty_state, record_review, select_question
from app.study_engine.daily_queue import lecture_goal
from app.study_engine.planning import KOREA
from app.study_engine.progress import mark_seen, seen_ids
from tests.bank_fixtures import example_bank

NOW = int(datetime(2026, 10, 11, 14, tzinfo=KOREA).timestamp() * 1000)
EXAM = "2026-10-20"


def main():
    bank = example_bank()
    bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "variant"})
    bank["questions"][2]["prerequisites"] = ["Q1", "Q2"]
    bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "optional", "tier": "Optional"})
    state = record_review(bank, empty_state(), "Q1", "Again", NOW)
    assert lecture_goal(bank, state, "test", NOW)["met"]  # Same-direction variants do not add daily units.
    assert select_question(example_bank(), state, EXAM, NOW + 61_000)["question"]["question_id"] == "Q1"
    for qid in ("variant", "Q2", "Q3", "optional"):
        before = copy.deepcopy(state)
        got = select_question(bank, state, EXAM, NOW + 61_000, prefer_unseen=True)
        assert got["question"]["question_id"] == qid, got
        assert qid not in seen_ids(state)
        assert state == before  # Selection never mutates stored learning records.
        row = next(r for r in got["ranked"] if r["question_id"] == qid)
        assert row["eligible"] and not row["reasons"] and row["score"] > 0
        if qid == "Q2":
            blocked = next(r for r in got["ranked"] if r["question_id"] == "Q3")
            assert not blocked["eligible"]  # Unseen prerequisites come first.
        mark_seen(state, qid)  # A viewed but ungraded question also counts as seen.
    assert select_question(bank, state, EXAM, NOW + 61_000, prefer_unseen=True) == select_question(bank, state, EXAM, NOW + 61_000)
    assert lecture_goal(bank, state, "test", NOW + 61_000)["met"]
    # Old review records and an already served question must also prevent duplicate first views.
    legacy = record_review(bank, empty_state(), "Q1", "Good", NOW)
    legacy["served"] = {"question_id": "variant"}
    assert select_question(bank, legacy, EXAM, NOW + 61_000, prefer_unseen=True)["question"]["question_id"] == "Q2"
    print("PASS: unseen variants, advanced/optional unlock, prerequisite order, ungraded and legacy views, repeat fallback, stable daily goal")


if __name__ == "__main__":
    main()
