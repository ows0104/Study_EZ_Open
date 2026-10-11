"""FSRS for objective reviews, with observed recall preceding confidence.

Default model parameters are not a personalized calibration. Different item
formats/variants can change difficulty: retain the actual question and outcome
in attempts, and do not describe model predictions as exam scores.
Daily planning visits an objective once, so minute-scale learning steps are
disabled. FSRS schedules day-scale reviews; extra practice remains available.
"""
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

SCHEDULER = Scheduler(desired_retention=.9, learning_steps=(),
                      relearning_steps=(), enable_fuzzing=False)
RATINGS = ("Again", "Hard", "Good", "Easy")


def recall_rating(attempt: dict) -> str | None:
    """Again means no independent recall, even if a guessed choice was correct.

Old clients can omit the post-answer rating. Uncertain-but-correct responses
then map to Hard, not failure. Explanation-only exposure is not an FSRS review.
"""
    if attempt.get("kind") == "explanation": return None
    correct = attempt.get("correct")
    if correct is None: correct = attempt.get("selfCorrect")
    if correct is not True or attempt.get("assisted") or attempt.get("confidence") == "guess":
        return "Again"
    if attempt.get("reviewRating") in RATINGS: return attempt["reviewRating"]
    return "Hard" if attempt.get("confidence") == "unsure" else "Good"


def schedule_review(old: dict, attempt: dict, rating: str) -> dict:
    at = datetime.fromtimestamp(attempt["at"] / 1000, timezone.utc)
    # A legacy doubling interval is not evidence of FSRS stability. Keep its
    # old due date until an actual new review initializes the standard model.
    card = Card.from_dict(old["fsrs"]) if old.get("fsrs") else Card(card_id=0, due=at)
    card, log = SCHEDULER.review_card(card, Rating[rating], review_datetime=at,
                                    review_duration=attempt.get("seconds", 0) * 1000)
    due = round(card.due.timestamp() * 1000)
    return {"fsrs": card.to_dict(), "fsrsReview": log.to_dict(),
            "dueAt": due, "intervalDays": (due - attempt["at"]) / 86_400_000,
            "reviewRating": rating, "scheduler": "fsrs-6.3.2", "desiredRetention": .9}


def delayed_recall(old: dict, attempt: dict) -> bool:
    # Reporting threshold only; it does not control FSRS intervals. Self-rated
    # answers remain distinct from automatically graded evidence.
    return bool(old.get("lastAt") and attempt["at"] - old["lastAt"] >= 20 * 3_600_000
                and attempt.get("correct") is True
                and recall_rating(attempt) in ("Hard", "Good", "Easy"))
