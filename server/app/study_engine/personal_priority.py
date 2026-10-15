"""Per-user question priorities live with the current bank's learning state."""

from app.bank_validation.priorities import IMPORTANCE, priority_tier


def question_priority(question: dict, state: dict) -> dict:
    tier = state.get("question_tiers", {}).get(question["question_id"])
    if tier not in IMPORTANCE:
        return question
    return {**question, "tier": tier, "importance": IMPORTANCE[tier],
            "personalTier": True, "originalTier": question.get("originalTier", priority_tier(question))}


def personal_bank(bank: dict, state: dict) -> dict:
    if not state.get("question_tiers"):
        return bank
    return {**bank, "questions": [question_priority(q, state) for q in bank["questions"]]}
