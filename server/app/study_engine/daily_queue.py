"""강의별 오늘 할 일. 핵심 개념×회상 방향과 필요한 선행 단위를 한 번씩 확인한다.

숙련도 점수와 독립적이다. 이력에서 재구성하므로 조회는 저장 상태를 바꾸지 않는다.
Good/Easy는 오늘 완료, Again/Hard는 재학습 대기다. 성공한 단위는 빨라도 다음 날 복습한다.
"""

from .engine import dimension_key, question_stage, rank_questions, days_until
from .planning import day_start
from .memory import DAY_MS
from .policy import DEFAULT


def learning_groups(bank: dict) -> dict[str, list[dict]]:
    by_id = {q["question_id"]: q for q in bank["questions"]}
    seeds = [q for q in bank["questions"] if q["tier"] == "Core"] or bank["questions"]
    selected = {q["question_id"]: q for q in seeds}
    pending = list(seeds)
    while pending:
        for qid in pending.pop()["prerequisites"]:
            if qid in by_id and qid not in selected:
                selected[qid] = by_id[qid]
                pending.append(by_id[qid])
    groups = {}
    for q in selected.values():
        groups.setdefault(dimension_key(q), []).append(q)
    return groups


def _due(review: dict, state: dict, *, latest: bool, policy: dict) -> int:
    rating, at = review["rating"], review["timestamp"]
    if rating in ("Again", "Hard"):
        # 재학습은 짧은 간격으로 확인한다. 과거에 길어진 Hard 간격은 사용하지 않는다.
        return at + policy["intervals"]["againMs" if rating == "Again" else "hardMs"]
    item = state.get("items", {}).get(review["question_id"], {}) if latest else {}
    scheduled = review.get("next_due_at", item.get("due_at", at + policy["intervals"]["goodMs" if rating == "Good" else "easyMs"]))
    return max(day_start(at) + DAY_MS, scheduled)


def daily_units(bank: dict, state: dict, now: int, policy: dict = DEFAULT) -> list[dict]:
    start, end = day_start(now), day_start(now) + DAY_MS
    groups = learning_groups(bank)
    keys = {q["question_id"]: key for key, qs in groups.items() for q in qs}
    reviews = {key: [] for key in groups}
    for h in state.get("history", []):
        key = keys.get(h["question_id"])
        if key is not None and h["timestamp"] <= now:
            reviews[key].append(h)
    units = []
    for key, questions in groups.items():
        history = sorted(reviews[key], key=lambda h: h["timestamp"])
        before = next((h for h in reversed(history) if h["timestamp"] < start), None)
        today = [h for h in history if h["timestamp"] >= start]
        last = today[-1] if today else None
        # 이력 없는 옛 상태도 저장된 문항 일정이 있으면 복습으로 이어간다.
        legacy = [state.get("items", {}).get(q["question_id"], {}) for q in questions]
        legacy = [item for item in legacy if item.get("reviews", 0) > 0]
        known = bool(history or legacy)
        kind = "review" if before or legacy and not history else "new"
        due = _due(before, state, latest=not today, policy=policy) if before else min(
            (item.get("due_at", start) for item in legacy), default=start)
        scheduled = bool(today) or not known or due < end
        if not scheduled:
            units.append({"key": key, "questions": questions, "status": "later", "due": due,
                          "kind": kind, "seen": known, "today": 0, "last": None})
            continue
        if not today and (not before or before["rating"] in ("Good", "Easy")):
            # 장기 복습은 예정된 날짜에 풀 수 있다. 분 단위 대기는 재학습에만 적용한다.
            due = start
        status = "relearning" if before and before["rating"] in ("Again", "Hard") else "pending"
        if last:
            status = "done" if last["rating"] in ("Good", "Easy") else "relearning"
            due = _due(last, state, latest=True, policy=policy)
        units.append({"key": key, "questions": questions, "status": status, "due": due,
                      "kind": kind, "seen": known, "today": len(today), "last": last or before})
    return units


def lecture_goal(bank: dict, state: dict, title: str, now: int, policy: dict = DEFAULT) -> dict:
    units = daily_units(bank, state, now, policy)
    today = [u for u in units if u["status"] != "later"]
    completed = sum(u["status"] == "done" for u in today)
    pending = [u for u in today if u["status"] != "done"]
    waiting = [u for u in pending if u["due"] > now]
    return {"title": title, "dayStart": day_start(now), "scope": "core" if any(
                q["tier"] == "Core" for q in bank["questions"]) else "all",
            "total": len(today), "completed": completed, "remaining": len(pending),
            "newRemaining": sum(u["status"] == "pending" and u["kind"] == "new" for u in pending),
            "reviewRemaining": sum(u["status"] == "pending" and u["kind"] == "review" for u in pending),
            "relearningRemaining": sum(u["status"] == "relearning" for u in pending),
            "waiting": len(waiting), "retryAt": min((u["due"] for u in waiting), default=None),
            "met": bool(units) and not pending,
            "progressPercent": completed * 100 // len(today) if today else 100 if units else 0,
            "reviewedToday": sum(u["today"] for u in today),
            "firstPassSeen": sum(u["seen"] for u in units), "firstPassTotal": len(units)}


def select_daily_question(bank: dict, state: dict, exam: str, now: int, policy: dict = DEFAULT) -> dict:
    units = daily_units(bank, state, now, policy)
    remaining = [u for u in units if u["status"] not in ("done", "later")]
    pending_keys = {u["key"] for u in remaining}
    by_id = {q["question_id"]: q for q in bank["questions"]}
    # 기존 적응형 점수는 순서를 정하는 데 쓴다. 숙련도 진입 장벽으로 오늘 할 일을 막지 않는다.
    ranked = rank_questions(bank, state, exam, now, policy)
    scores = {r["question_id"]: r["raw_score"] for r in ranked}
    candidates = []
    for unit in remaining:
        if unit["due"] > now:
            continue
        questions = unit["questions"]
        if unit["status"] == "relearning":
            questions = [q for q in questions if q["question_id"] == unit["last"]["question_id"]]
        for q in questions:
            dependencies = sum(dimension_key(by_id[qid]) in pending_keys for qid in q["prerequisites"] if qid in by_id)
            candidates.append((dependencies, question_stage(q), -scores[q["question_id"]], q["question_id"], q))
    candidates.sort(key=lambda row: row[:4])
    return {"question": candidates[0][-1] if candidates else None, "ranked": ranked,
            "days": days_until(exam, now), "reason": "learning_wait" if remaining and not candidates else None,
            "retry_at": min((u["due"] for u in remaining if u["due"] > now), default=None)}
