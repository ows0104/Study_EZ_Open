"""Distinct questions viewed, excluding Optional from the panel denominator."""


def seen_ids(state: dict) -> set[str]:
    ids = set(state.get("seen_question_ids", []))
    ids.update(qid for qid, item in state.get("items", {}).items() if item.get("reviews", 0) > 0)
    ids.update(r["question_id"] for r in state.get("history", []) if r.get("question_id"))
    served = state.get("served") or {}
    if served.get("question_id"):
        ids.add(served["question_id"])
    return ids


def mark_seen(state: dict, question_id: str) -> None:
    state["seen_question_ids"] = sorted(seen_ids(state) | {question_id})


def panel_progress(bank: dict, state: dict) -> dict[str, int]:
    required = {q["question_id"] for q in bank.get("questions", [])
                if q["tier"] != "Optional" and q.get("role") != "exam"}
    return {"studyQuestionCount": len(required), "seenQuestionCount": len(required & seen_ids(state))}
