"""강의별 첫 학습 흐름을 유지하고, 강의 전체 후보에 공통 출제 정책을 적용한다."""
from .daily_queue import daily_candidates, daily_selection
from .ordering import choose_candidate, study_history
from .policy import DEFAULT


def select_batch_question(entries: list[dict], now: int, policy: dict = DEFAULT,
                          *, seed: str | None = None, prepared: tuple | None = None) -> tuple[dict | None, dict | None]:
    candidates, history = [], []
    for index, entry in enumerate(entries):
        history.extend(study_history(entry["bank"], entry["state"], now, entry["key"]))
        if not entry["goal"]["remaining"]:
            continue
        pool, ranked = daily_candidates(entry["bank"], entry["state"], entry["exam"], now, policy,
                                        scope=entry["key"], lecture_order=index, pages=entry["row"].pages)
        candidates.extend({**candidate, "entry": entry, "ranked": ranked} for candidate in pool)
    chosen = choose_candidate(candidates, history, now, policy, seed=seed, prepared=prepared)
    if chosen is None:
        return None, None
    entry = chosen["entry"]
    return entry, daily_selection(chosen, chosen["ranked"], entry["exam"], now)


def aggregate_goal(entries: list[dict], day_start: int) -> dict:
    fields = ("total", "completed", "remaining", "newRemaining", "reviewRemaining", "unlearnedRemaining",
              "relearningRemaining", "waiting", "reviewedToday", "firstPassSeen", "firstPassTotal")
    goal = {field: sum(entry["goal"].get(field, 0) for entry in entries) for field in fields}
    goal.update(title=f"선택한 {len(entries)}강의", dayStart=day_start, scope="all", retryAt=None,
                met=goal["remaining"] == 0, progressPercent=goal["completed"] * 100 // goal["total"] if goal["total"] else 100,
                lectureCount=len(entries), completedLectures=sum(entry["goal"]["met"] for entry in entries))
    return goal
