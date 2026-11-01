"""Read-only card overview. Viewing, successful recall, and spaced recall stay distinct."""

from .daily_queue import daily_units
from .engine import dimension_key, mastery, target_for
from .memory import memory_snapshot
from .planning import day_start
from .policy import DEFAULT
from .progress import seen_ids
from .suspension import active_bank


def card_progress(bank: dict, state: dict, now: int, policy: dict = DEFAULT) -> dict:
    active = active_bank(bank, state)
    questions = active["questions"]
    seen = seen_ids(state)
    snapshot = memory_snapshot(state, now, policy)
    histories: dict[str, list[dict]] = {}
    for review in state.get("history", []):
        if review["timestamp"] <= now:
            histories.setdefault(review["question_id"], []).append(review)
    counts = dict(unseen=0, recognized=0, retrieving=0, retained=0)
    for q in questions:
        qid = q["question_id"]
        if qid not in seen:
            counts["unseen"] += 1
            continue
        history = histories.get(qid, [])
        last = max(history, key=lambda h: h["timestamp"], default={})
        if last.get("rating") not in ("Good", "Easy"):
            counts["recognized"] += 1
            continue
        days = {day_start(h["timestamp"]) for h in history if h["rating"] in ("Good", "Easy")}
        dim = snapshot["dimensions"].get(dimension_key(q), {})
        if len(days) >= 2 and dim.get("reviews", 0) and mastery(snapshot, q) >= target_for(active, q, policy)["effective"]:
            counts["retained"] += 1
        else:
            counts["retrieving"] += 1
    units = daily_units(bank, state, now, policy)
    return {
        "total": len(questions), "seen": len(questions) - counts["unseen"], **counts,
        "newRemaining": sum(u["kind"] == "new" and u["status"] == "pending" for u in units),
        "reviewDue": sum(u["kind"] == "review" and u["status"] == "pending" for u in units),
        "suspended": len(bank["questions"]) - len(questions),
    }
