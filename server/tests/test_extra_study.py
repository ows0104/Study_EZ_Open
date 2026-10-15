"""Explicit extra study covers unseen variants and advanced questions before repeats."""
import copy
from datetime import datetime
from unittest.mock import patch

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
    assert lecture_goal(bank, state, "test", NOW)["remaining"] == 4
    assert select_question(example_bank(), state, EXAM, NOW + 61_000)["question"]["question_id"] == "Q2"  # Important is independent of depth gating.
    selected = set()
    for _ in range(4):
        before = copy.deepcopy(state)
        got = select_question(bank, state, EXAM, NOW + 61_000, prefer_unseen=True)
        qid = got["question"]["question_id"]
        assert qid in {"variant", "Q2", "Q3", "optional"} - selected, got
        if qid == "Q3":
            assert "Q2" in seen_ids(state)
        selected.add(qid)
        assert qid not in seen_ids(state)
        assert state == before  # Selection never mutates stored learning records.
        row = next(r for r in got["ranked"] if r["question_id"] == qid)
        assert row["eligible"] and not row["reasons"] and row["score"] > 0
        if qid == "Q2":
            blocked = next(r for r in got["ranked"] if r["question_id"] == "Q3")
            assert not blocked["eligible"]  # Unseen prerequisites come first.
        mark_seen(state, qid)  # A viewed but ungraded question also counts as seen.
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[-1]]) as draw:
        got = select_question(bank, state, EXAM, NOW + 61_000, prefer_unseen=True)
        assert got["question"] is not None and draw.call_count == 1
        assert all(c["question"]["question_id"] != "Q1" for c in draw.call_args.args[0])
    assert not lecture_goal(bank, state, "test", NOW + 61_000)["met"]
    for qid in ("variant", "Q2", "Q3", "optional"):
        state = record_review(bank, state, qid, "Again", NOW + 61_000)
    assert lecture_goal(bank, state, "test", NOW + 61_000)["met"]
    # Old review records and an already served question must also prevent duplicate first views.
    legacy = record_review(bank, empty_state(), "Q1", "Good", NOW)
    legacy["served"] = {"question_id": "variant"}
    assert select_question(bank, legacy, EXAM, NOW + 61_000, prefer_unseen=True)["question"]["question_id"] in {"Q2", "optional"}
    print("PASS: unseen variants and prerequisites, shared weighted repeats, ungraded and legacy views, stable daily goal")


if __name__ == "__main__":
    main()
