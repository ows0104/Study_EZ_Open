"""문항별 오늘 할 일. 미학습 문항을 제한 없이 먼저 확인한 뒤 예정된 복습을 진행한다.

숙련도 점수와 독립적이다. 이력에서 재구성하므로 조회는 저장 상태를 바꾸지 않는다.
평가한 문항은 등급에 관계없이 오늘 완료다. 어려웠던 문항은 다음날부터 복습한다.
추가 학습의 평가는 숙련도에 반영하지만 오늘 달성한 분량을 되돌리지 않는다.
"""

from .engine import rank_questions, days_until
from .ordering import choose_candidate, question_slide, study_history
from .planning import day_start
from .memory import DAY_MS
from .policy import DEFAULT
from .progress import seen_ids
from .suspension import active_bank


def _due(review: dict, state: dict, *, latest: bool, policy: dict) -> int:
    rating, at = review["rating"], review["timestamp"]
    if rating in ("Again", "Hard"):
        return max(day_start(at) + DAY_MS,
                   at + policy["intervals"]["againMs" if rating == "Again" else "hardMs"])
    item = state.get("items", {}).get(review["question_id"], {}) if latest else {}
    scheduled = review.get("next_due_at", item.get("due_at", at + policy["intervals"]["goodMs" if rating == "Good" else "easyMs"]))
    return max(day_start(at) + DAY_MS, scheduled)


def daily_units(bank: dict, state: dict, now: int, policy: dict = DEFAULT) -> list[dict]:
    start, end = day_start(now), day_start(now) + DAY_MS
    groups = {q["question_id"]: [q] for q in active_bank(bank, state)["questions"]}
    reviews = {key: [] for key in groups}
    for h in state.get("history", []):
        key = h["question_id"]
        if key in reviews and h["timestamp"] <= now:
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
        scheduled_due = due
        scheduled = kind == "new" or due < end
        if not scheduled:
            units.append({"key": key, "questions": questions, "status": "later", "due": due,
                          "scheduled_due": scheduled_due,
                          "kind": kind, "seen": known, "today": len(today), "last": last or before})
            continue
        if not today:
            # 오늘 예정된 복습은 바로 풀 수 있다. 할당량 도중 분 단위 대기는 없다.
            due = start
        status = "pending"
        if last:
            status = "done"
            due = _due(last, state, latest=True, policy=policy)
        units.append({"key": key, "questions": questions, "status": status, "due": due,
                      "scheduled_due": scheduled_due,
                      "kind": kind, "seen": known, "today": len(today), "last": last or before})
    return units


def _new_progress(units: list[dict]) -> tuple[int, int]:
    # 오늘 처음 평가한 문항도 신규 풀에 남아 있어 목표가 풀이할 때마다 늘지 않는다.
    new = [u for u in units if u["kind"] == "new"]
    return len(new), sum(u["status"] == "done" for u in new)


def lecture_goal(bank: dict, state: dict, title: str, now: int, policy: dict = DEFAULT) -> dict:
    units = daily_units(bank, state, now, policy)
    reviews = [u for u in units if u["kind"] == "review" and u["status"] != "later"]
    new_total, new_completed = _new_progress(units)
    total = len(reviews) + new_total
    completed = sum(u["status"] == "done" for u in reviews) + new_completed
    pending = [u for u in reviews if u["status"] != "done"]
    waiting = [u for u in pending if u["due"] > now]
    return {"title": title, "dayStart": day_start(now), "scope": "all",
            "total": total, "completed": completed, "remaining": total - completed,
            "newRemaining": new_total - new_completed,
            "reviewRemaining": len(pending),
            "unlearnedRemaining": sum(not u["seen"] for u in units),
            "relearningRemaining": sum(u["status"] == "relearning" for u in pending),
            "waiting": len(waiting), "retryAt": min((u["due"] for u in waiting), default=None),
            "met": bool(bank["questions"]) and completed == total,
            "progressPercent": completed * 100 // total if total else 100 if bank["questions"] else 0,
            "reviewedToday": sum(u["today"] for u in units),
            "firstPassSeen": sum(u["seen"] for u in units), "firstPassTotal": len(units)}


def daily_candidates(bank: dict, state: dict, exam: str, now: int, policy: dict = DEFAULT,
                     *, scope: tuple = (), lecture_order: int = 0, pages: dict | None = None,
                     extra: bool = False) -> tuple[list[dict], list[dict]]:
    """선행관계를 만족하는 오늘의 후보. 일정은 원래 예정일과 오늘 풀이 가능 시각을 구분한다."""
    units = daily_units(bank, state, now, policy)
    seen = seen_ids(state) if extra else set()
    remaining = units if extra else [u for u in units if u["status"] not in ("done", "later")]
    unlearned = {u["key"] for u in units if (u["key"] not in seen if extra else not u["seen"])}
    # 미학습 문항을 모두 먼저 확인한다. 완료 문항은 다시 고르지 않는다.
    ranked = rank_questions(bank, state, exam, now, policy)
    rows = {r["question_id"]: r for r in ranked}
    positions = {q["question_id"]: i for i, q in enumerate(bank["questions"])}
    candidates = []
    for unit in remaining:
        if extra:
            # 완료·미도래 문항도 포함한다. 오늘 처음 평가한 문항도 추가 학습에서는 복습이다.
            item = state.get("items", {}).get(unit["key"], {})
            last = unit["last"] or {}
            unit = {**unit, "kind": "review" if unit["key"] in seen else "new", "due": now,
                    "scheduled_due": item.get("due_at", last.get("next_due_at", unit["scheduled_due"]))}
        if unit["due"] > now:
            continue
        q = unit["questions"][0]
        if unit["kind"] == "new" and any(qid in unlearned for qid in q["prerequisites"]):
            continue  # 아직 평가하지 않은 선행 문항부터 확인한다.
        slide = question_slide(q, pages)
        candidates.append({"unit": unit, "question": q, "rank": rows[unit["key"]], "scope": scope,
                           "order": (lecture_order, slide, rows[unit["key"]]["stage"] if slide != float("inf") else 0,
                                     positions[unit["key"]])})
    return candidates, ranked


def daily_selection(chosen: dict | None, ranked: list[dict], exam: str, now: int) -> dict:
    question = chosen["question"] if chosen else None
    if question:
        row = next(r for r in ranked if r["question_id"] == question["question_id"])
        row["notes"] += ["첫 학습은 선행관계·슬라이드 순서, 복습은 예정일·약점을 반영해 섞습니다.",
                         "가능하면 같은 개념의 다른 회상방향 사이에 다른 문제 3~5개를 둡니다."] + row["reasons"]
        row.update(eligible=True, score=row["raw_score"], reasons=[])
    return {"question": question, "ranked": ranked,
            "days": days_until(exam, now), "reason": None, "retry_at": None}


def select_daily_question(bank: dict, state: dict, exam: str, now: int, policy: dict = DEFAULT,
                          *, shuffle: bool = False, pages: dict | None = None) -> dict:
    # shuffle은 기존 호출 호환용이다. 두 화면 모두 동일한 정책으로 신규 정렬·복습 섞기를 한다.
    candidates, ranked = daily_candidates(bank, state, exam, now, policy, pages=pages)
    chosen = choose_candidate(candidates, study_history(bank, state, now), now, policy)
    return daily_selection(chosen, ranked, exam, now)


def select_extra_question(bank: dict, state: dict, exam: str, now: int, policy: dict = DEFAULT,
                          *, pages: dict | None = None) -> dict:
    """추가 학습도 공통 선택기를 사용하되 완료·미도래 문항까지 포함한다."""
    candidates, ranked = daily_candidates(bank, state, exam, now, policy, pages=pages, extra=True)
    history = [h for h in state.get("history", []) if h["timestamp"] <= now]
    last = max(history, key=lambda h: h["timestamp"], default=None)
    retry_at = None
    recent = last and (day_start(last["timestamp"]) == day_start(now)
                       or now < last["timestamp"] + policy["recency"]["minimumRepeatMs"])
    if recent and any(c["question"]["question_id"] == last["question_id"] for c in candidates):
        others = [c for c in candidates if c["question"]["question_id"] != last["question_id"]]
        if others:
            candidates = others
        elif now < last["timestamp"] + policy["recency"]["minimumRepeatMs"]:
            candidates = []
            retry_at = last["timestamp"] + policy["recency"]["minimumRepeatMs"]
    chosen = choose_candidate(candidates, study_history(bank, state, now), now, policy)
    result = daily_selection(chosen, ranked, exam, now)
    if chosen:
        chosen["rank"]["notes"].append("추가 학습은 완료·미도래 문항도 같은 복습 가중치로 고르고 직전 문항의 연속 반복을 피합니다.")
    else:
        result.update(reason="직전 문제의 즉시 반복을 잠시 쉬고 있습니다." if retry_at else "학습 가능한 문제가 없습니다.",
                      retry_at=retry_at)
    return result
