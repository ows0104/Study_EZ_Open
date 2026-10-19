"""Overview states are disjoint, read-only, and follow the actual daily queue."""
import copy

from app.study_engine import empty_state, record_review
from app.study_engine.card_progress import card_progress
from app.study_engine.daily_queue import lecture_goal
from app.study_engine.memory import DAY_MS
from app.study_engine.progress import mark_seen
from tests.bank_fixtures import example_bank


def main():
    bank = example_bank()
    base = bank["questions"][0]
    bank["questions"] = [{**base, "question_id": f"Q{i}", "concept_id": f"C{i}"} for i in range(7)]
    bank["questions"][-1]["tier"] = "Optional"
    now = 1_790_000_000_000
    yesterday = now - DAY_MS
    state = empty_state()
    mark_seen(state, "Q1")
    state = record_review(bank, state, "Q2", "Hard", yesterday)
    state = record_review(bank, state, "Q3", "Good", yesterday)
    for qid in ("Q4", "Q5"):
        for i in range(20):
            state = record_review(bank, state, qid, "Easy", yesterday + i)
    state = record_review(bank, state, "Q4", "Easy", now)
    state["suspended_question_ids"] = ["Q6"]
    original = copy.deepcopy(state)
    p = card_progress(bank, state, now)
    assert p["total"] == 6 and p["suspended"] == 1
    assert (p["unseen"], p["recognized"], p["retrieving"], p["retained"]) == (1, 2, 2, 1), p
    assert p["seen"] == 5 and p["newRemaining"] == 2
    assert sum(p[k] for k in ("unseen", "recognized", "retrieving", "retained")) == p["total"]
    assert p["reviewDue"] == lecture_goal(bank, state, "test", now)["reviewRemaining"]
    assert state == original
    # Same-day repeats alone do not establish spaced memory. An ungraded view remains new.
    assert card_progress(bank, {**state, "suspended_question_ids": []}, now)["total"] == 7
    assert card_progress(bank, empty_state(), now)["unseen"] == 7  # Optional included
    state = record_review(bank, state, "Q4", "Again", now + 100)
    assert card_progress(bank, state, now + 100)["retained"] == 0
    assert card_progress(bank, original, now + 1000 * DAY_MS)["retained"] == 0
    # Shared concept recall does not imply an unviewed sibling card has been learned.
    sibling = {**bank, "questions": bank["questions"] + [{**bank["questions"][4], "question_id": "sibling"}]}
    assert card_progress(sibling, original, now)["unseen"] == 2
    assert card_progress({**bank, "questions": []}, empty_state(), now)["total"] == 0
    print("PASS: overview card stages, spaced recall, decay, Optional, exclusions, daily queue, read-only")


if __name__ == "__main__":
    main()
