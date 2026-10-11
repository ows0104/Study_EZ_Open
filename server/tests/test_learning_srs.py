"""Observed recall, optional confidence and persistent FSRS review state."""
from app.study_engine.learning import apply_attempt, progress
from app.study_engine.learning_srs import delayed_recall, recall_rating, schedule_review
from app.study_engine.memory import DAY_MS

NOW = 1791676800000


def main():
    attempt = {"objectiveKey": "unit", "at": NOW, "kind": "question", "correct": True,
               "confidence": None, "assisted": False, "seconds": 30}
    assert recall_rating(attempt) == "Good"
    assert recall_rating({**attempt, "confidence": "unsure"}) == "Hard"
    assert recall_rating({**attempt, "confidence": "unsure", "reviewRating": "Good"}) == "Good"
    for change in ({"correct": False}, {"assisted": True}, {"confidence": "guess"}):
        assert recall_rating({**attempt, **change, "reviewRating": "Easy"}) == "Again"
    assert recall_rating({**attempt, "kind": "explanation"}) is None
    assert recall_rating({**attempt, "correct": None, "selfCorrect": True, "reviewRating": "Hard"}) == "Hard"
    assert recall_rating({**attempt, "correct": None, "selfCorrect": False, "reviewRating": "Easy"}) == "Again"

    initial = apply_attempt({}, {**attempt, "reviewRating": "Good"})
    old = initial["objectives"]["unit"]
    assert old["fsrs"] and old["scheduler"] == "fsrs-6.3.2"
    reviewed = {**attempt, "at": old["dueAt"], "confidence": "unsure", "reviewRating": "Hard"}
    repeated = apply_attempt(initial, reviewed)
    current = repeated["objectives"]["unit"]
    assert initial["objectives"]["unit"] == old  # no mutation during preview or application
    assert current["reviewRating"] == "Hard" and current["delayedSuccesses"] == 1
    assert current["dueAt"] > reviewed["at"] and current["fsrs"] != old["fsrs"]
    preview = schedule_review(old, reviewed, "Hard")
    assert preview["dueAt"] == current["dueAt"]
    assert not delayed_recall(old, {**reviewed, "at": NOW + 1000})
    assert not delayed_recall(old, {**reviewed, "correct": None, "selfCorrect": True})
    assert not delayed_recall(old, {**reviewed, "assisted": True})
    next_attempt = {**reviewed, "at": current["dueAt"], "reviewRating": "Good"}
    stable = apply_attempt(repeated, next_attempt)
    assert progress([{"key": "unit", "questions": [], "objective": {}}], stable)["delayedRecall"] == 1
    failed = apply_attempt(stable, {**attempt, "at": next_attempt["at"] + DAY_MS,
                                   "correct": False, "reviewRating": "Again"})
    assert failed["objectives"]["unit"]["delayedSuccesses"] == 0
    explanation = apply_attempt(initial, {**attempt, "kind": "explanation", "at": NOW + DAY_MS})
    assert explanation["objectives"]["unit"]["fsrs"] == old["fsrs"]
    fresh_explanation = apply_attempt({}, {**attempt, "kind": "explanation", "correct": None})
    assert "fsrs" not in fresh_explanation["objectives"]["unit"]
    legacy = {"intervalDays": 90, "dueAt": NOW + 90 * DAY_MS}
    assert schedule_review(legacy, attempt, "Good")["fsrs"] == schedule_review({}, attempt, "Good")["fsrs"]
    print("PASS uncertain success, failed/assisted recall, optional confidence, FSRS persistence and exposure-only history")


if __name__ == "__main__":
    main()
