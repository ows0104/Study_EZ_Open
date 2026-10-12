"""강의를 섞어 고르되 새 카드가 남으면 복습보다 먼저 배치한다."""
import random


def choose_lecture(entries: list[dict], previous: tuple[str, str] | None = None) -> dict | None:
    pending = [entry for entry in entries if entry["goal"]["remaining"] > 0]
    pool = [entry for entry in pending if entry["goal"]["newRemaining"] > 0] or pending
    others = [entry for entry in pool if entry["key"] != previous]
    if others:
        pool = others
    if not pool:
        return None
    weights = [entry["goal"]["newRemaining"] or entry["goal"]["reviewRemaining"] for entry in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def aggregate_goal(entries: list[dict], day_start: int) -> dict:
    fields = ("total", "completed", "remaining", "newRemaining", "reviewRemaining", "unlearnedRemaining",
              "relearningRemaining", "waiting", "reviewedToday", "firstPassSeen", "firstPassTotal")
    goal = {field: sum(entry["goal"].get(field, 0) for entry in entries) for field in fields}
    goal.update(title=f"선택한 {len(entries)}강의", dayStart=day_start, scope="all", retryAt=None,
                met=goal["remaining"] == 0, progressPercent=goal["completed"] * 100 // goal["total"] if goal["total"] else 100,
                lectureCount=len(entries), completedLectures=sum(entry["goal"]["met"] for entry in entries))
    return goal
