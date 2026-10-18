"""다음에 풀 문항을 고르고, 평가로 숙련도를 고친다. **DB 도 시계도 없다** — `now`(ms)를 받는다.

AdaptiveStudy3/study_engine/engine.mjs 를 줄 단위로 옮겼다(2026-10-04). SM-2(`app/srs.py`)와
다른 점: 카드 하나가 아니라 **개념 × 회상 방향** 마다 숙련도(0–1, EMA)를 두고, 중요도·약점·
시험까지 남은 날·단계·선행 문항을 곱해 다음 문항을 서버가 고른다.

시각은 시제품과 같이 **epoch 밀리초 정수**다. 학습 상태 JSON 이 시제품과 같은 꼴이어야
옮겨 온 검사가 같은 값을 낸다.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

from .policy import DEFAULT, policy_hash
from .memory import memory_snapshot, next_stability, stability_days
from .suspension import active_bank
from .personal_priority import personal_bank
from .study_day import day_start
from app.bank_validation.priorities import TIER_ORDER, is_advanced, priority_tier

DAY_MS = 86_400_000
KST = timedelta(hours=9)
_DIRECTION_STAGE = {"reverse": 2, "discrimination": 2, "trap": 2, "mechanism": 3, "sequence": 3, "integration": 4}


def empty_state() -> dict:
    return {"version": 2, "dimensions": {}, "items": {}, "history": [], "remediations": [],
            "remediation_events": [], "served": None, "session": None, "sessions": []}


def dimension_key(q: dict) -> str:
    return f"{q['concept_id']}:{q['retrieval_direction']}"


def mastery(state: dict, q: dict | None) -> float:
    if not q:
        return 0
    return (state["dimensions"].get(dimension_key(q)) or {}).get("mastery", 0)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _korea_midnight_ms(now: int) -> int:
    """`now` 가 속한 한국 날짜의 0시."""
    local = datetime.fromtimestamp(now / 1000, UTC) + KST
    return int((datetime(local.year, local.month, local.day, tzinfo=UTC) - KST).timestamp() * 1000)


def days_until(date: str, now: int) -> int:
    exam = int((datetime.fromisoformat(date).replace(tzinfo=UTC) - KST).timestamp() * 1000)
    return round((exam - _korea_midnight_ms(now)) / DAY_MS)


def _plan(bank: dict, concept_id: str) -> dict | None:
    return next((p for p in bank["retrieval_plan"] if p["concept_id"] == concept_id), None)


def target_for(bank: dict, q: dict, policy: dict = DEFAULT) -> dict:
    plan = _plan(bank, q["concept_id"])
    # An explicit private tier replaces the authored concept target in both directions.
    requested = (policy["mastery"]["tierTargets"][priority_tier(q)] if q.get("personalTier") or priority_tier(q) == "Essential"
                 else plan["target_mastery"] if plan else policy["mastery"]["targets"][str(q["importance"])])
    return {"requested": requested, "effective": min(requested, policy["mastery"]["maxTarget"],
            policy["mastery"]["tierTargets"][priority_tier(q)])}


def review_schedule(bank: dict, q: dict, snapshot: dict, policy: dict = DEFAULT) -> dict:
    """Invert the same forgetting curve used by memory_snapshot, from the actual review time."""
    at = snapshot["reviewed_at"]
    target = target_for(bank, q, policy)["effective"]
    stability = stability_days({"stability_days": snapshot["stability_days"]}, policy)
    # M(t) = M_after / (1 + t / (9*S)); a target already missed is due next KST day.
    days = min(policy["forgetting"]["maxDays"],
               max(0, 9 * stability * (snapshot["mastery_after"] / target - 1)))
    due = max(day_start(at) + DAY_MS, at + round(days * DAY_MS))
    return {"interval": due - at, "due_at": due,
            "target_schedule": {"reviewed_at": at, "mastery_after": snapshot["mastery_after"],
                                "stability_days": stability, "target": target}}


def reschedule_bank(bank: dict, state: dict, policy: dict = DEFAULT, *, question_ids: set[str] | None = None) -> dict:
    """Refresh schedules only; review facts, mastery, tokens, and completed sessions are preserved.

    Old untouched schedules remain until their next review. Previously saved private tiers
    and target-based schedules are recalculated on load, including before a read-only queue.
    """
    bank = personal_bank(bank, state)
    latest = {}
    for review in state.get("history", []):
        qid = review["question_id"]
        if qid not in latest or review["timestamp"] >= latest[qid]["timestamp"]:
            latest[qid] = review
    items = state.get("items", {})
    changed = None
    for q in bank["questions"]:
        qid = q["question_id"]
        item = items.get(qid) or {}
        review = latest.get(qid) or {}
        if not (item.get("reviews") or review) or not (item.get("target_schedule") or q.get("personalTier")
                                           or question_ids is not None and qid in question_ids):
            continue
        snapshot = item.get("target_schedule")
        if not snapshot and "mastery_after" in review:
            snapshot = {"reviewed_at": review["timestamp"], "mastery_after": review["mastery_after"],
                        "stability_days": review.get("stability_after", policy["forgetting"]["legacyDays"])}
        if not snapshot:
            # Legacy records without question history use their stored review anchor and known dimension.
            dim = state.get("dimensions", {}).get(dimension_key(q)) or {}
            at = item.get("due_at", 0) - item.get("interval", 0)
            if not at or "mastery" not in dim:
                continue
            snapshot = {"reviewed_at": at, "mastery_after": dim["mastery"],
                        "stability_days": stability_days(dim, policy)}
        count = item.get("reviews") or sum(h["question_id"] == qid for h in state.get("history", []))
        updated = {**item, "reviews": count, **review_schedule(bank, q, snapshot, policy)}
        if updated != item:
            if changed is None:
                changed = dict(items)
            changed[qid] = updated
    return {**state, "items": changed} if changed is not None else state


def question_stage(q: dict) -> int:
    if q["retrieval_direction"] == "direct" or (q["format"] == "ox" and q["item_difficulty"] <= 2):
        return 1
    return _DIRECTION_STAGE[q["retrieval_direction"]]


def concept_readiness(bank: dict, state: dict, concept_id: str, policy: dict = DEFAULT) -> int:
    questions = [q for q in bank["questions"] if q["concept_id"] == concept_id]
    stages = sorted({question_stage(q) for q in questions})
    ready = stages[0] if stages else 1
    for stage in stages:
        ready = stage
        dims = {dimension_key(q): q for q in questions if question_stage(q) == stage}.values()
        if stage == 4 or any(mastery(state, q) < policy["progression"]["thresholds"][str(stage)] for q in dims):
            break
    return ready


def core_mastery(bank: dict, state: dict, concept_id: str | None = None, *, foundations_only: bool = False) -> float:
    bank = personal_bank(bank, state)
    by_concept: dict[str, dict[str, float]] = {}
    for q in bank["questions"]:
        if (q["tier"] in ("Essential", "Core") and (not concept_id or q["concept_id"] == concept_id)
                and (not foundations_only or not is_advanced(q))):
            by_concept.setdefault(q["concept_id"], {})[q["retrieval_direction"]] = mastery(state, q)
    return _average([_average(list(ds.values())) for ds in by_concept.values()])


def weak_high_core(bank: dict, state: dict, policy: dict = DEFAULT) -> list[dict]:
    concepts = {c["concept_id"]: c for c in bank["concepts"]}
    high = policy["progression"]["highImportance"]
    return [q for q in bank["questions"]
            if q["tier"] in ("Essential", "Core")
            and max(q["importance"], (concepts.get(q["concept_id"]) or {}).get("importance", 0)) >= high
            and mastery(state, q) < target_for(bank, q, policy)["effective"]]


def _weakest(bank: dict, state: dict, ids: list[str]) -> dict | None:
    found = [q for qid in ids if (q := next((x for x in bank["questions"] if x["question_id"] == qid), None))]
    found.sort(key=lambda q: (mastery(state, q), q["question_id"]))
    return found[0] if found else None


def upgrade_state(bank: dict, previous: dict, policy: dict = DEFAULT, now: int = 0) -> dict:
    state = {**empty_state(), **copy.deepcopy(previous)}
    if previous.get("version") != 2 or "remediation" in state:
        target = (state.get("remediation") or {}).get("target")
        parent = next((q for q in bank["questions"] if q["question_id"] == target), None)
        prerequisite = _weakest(bank, memory_snapshot(state, now, policy), parent["prerequisites"]) if parent else None
        if prerequisite:
            state["remediations"] = [{"parent_id": parent["question_id"], "prerequisite_id": prerequisite["question_id"],
                                      "remaining": policy["remediation"]["maxReviews"], "started_at": now}]
        state.pop("remediation", None)
        state["version"] = 2
        state["served"] = None
        state["migrated_at"] = now
        state["migration_note"] = "기존 숙련도와 평가 기록은 유지하고 새 정책은 이후 평가부터 적용합니다."
    return state


def rank_questions(bank: dict, state: dict, exam_date: str, now: int, policy: dict = DEFAULT) -> list[dict]:
    state = reschedule_bank(bank, state, policy)
    bank = active_bank(bank, state)
    state = memory_snapshot(state, now, policy)
    days = days_until(exam_date, now)
    by_id = {q["question_id"]: q for q in bank["questions"]}
    start = day_start(now)
    rec, ex, prog, w = policy["recency"], policy["exam"], policy["progression"], policy["weights"]
    today = [h for h in state["history"] if start <= h["timestamp"] <= now]
    recent = today[-rec["window"]:]
    last = today[-1] if today else None
    weak_core = weak_high_core(bank, state, policy)
    core = core_mastery(bank, state)
    remediations = state.get("remediations") or []
    readiness = {c["concept_id"]: concept_readiness(bank, state, c["concept_id"], policy) for c in bank["concepts"]}
    any_core = any(o["tier"] in ("Essential", "Core") for o in bank["questions"])
    last_q = by_id.get(last["question_id"]) if last else None
    recent_directions = [(by_id.get(h["question_id"]) or {}).get("retrieval_direction")
                         for h in today[-rec["diversityWindow"]:]]

    rows = []
    for q in bank["questions"]:
        qid = q["question_id"]
        m = mastery(state, q)
        item = state["items"].get(qid)
        dim = state["dimensions"].get(dimension_key(q)) or {}
        due_at = (item or {}).get("due_at", now)
        if dim.get("updated_at") is not None and not (item or {}).get("target_schedule"):
            # 옛 일정도 현재 기억 유지 기간보다 멀리 밀린 경우 복습 대상으로 돌아온다.
            due_at = min(due_at, dim["updated_at"] + stability_days(dim, policy) * DAY_MS)
        target = target_for(bank, q, policy)
        stage = question_stage(q)
        ready = readiness.get(q["concept_id"], stage)
        prereq_ready = all(mastery(state, by_id.get(pid)) >= prog["prerequisiteMastery"] for pid in q["prerequisites"])
        has_core = any(o["concept_id"] == q["concept_id"] and o["tier"] in ("Essential", "Core") and not is_advanced(o)
                       for o in bank["questions"])
        remediation = any(r["prerequisite_id"] == qid for r in remediations)
        reasons: list[str] = []
        notes: list[str] = []
        if target["requested"] != target["effective"]:
            notes.append(f"요청 목표 {target['requested']}를 도달 가능한 정책 상한 {target['effective']}로 적용")
        if q["tier"] == "Optional" and weak_core:
            reasons.append("중요한 Core의 약점을 먼저 복습합니다.")
        elif q["tier"] == "Optional" and core < prog["optionalCore"] and days > ex["closeDays"] and any_core:
            reasons.append("Core 숙련도가 Optional 진입 기준보다 낮습니다.")
        if (is_advanced(q) and has_core and core_mastery(bank, state, q["concept_id"], foundations_only=True) < prog["advancedCore"]
                and not (q["prerequisites"] and prereq_ready)):
            reasons.append("기초 Core 또는 선행 문항의 숙련도를 더 쌓아야 합니다.")
        if stage > ready + prog["maxStageAhead"] and not remediation:
            reasons.append("현재 회상 단계보다 너무 앞선 문제입니다.")
        if q["prerequisites"] and not prereq_ready and not remediation:
            reasons.append("선행 문항을 먼저 복습해야 합니다.")
        if any(r["parent_id"] == qid for r in remediations):
            reasons.append("실패한 문제의 선행 문항을 보충 중입니다.")
        if last and last["question_id"] == qid and now - last["timestamp"] < rec["minimumRepeatMs"] and not remediation:
            reasons.append("직전 문제의 즉시 반복을 잠시 쉬고 있습니다.")

        high = q["importance"] >= prog["highImportance"]
        weak = m < target["effective"]
        urgency, direction = 1, 1
        if days > ex["farDays"]:
            direction = ex["earlyDirect"] if stage == 1 else ex["earlyHigher"] if stage >= 3 else 1
        elif days > ex["middleDays"]:
            direction = ex["middleReverseMechanism"] if q["retrieval_direction"] in ("reverse", "mechanism") else 1
        else:
            direction = ex["lateExamDirections"] if q["retrieval_direction"] in ("discrimination", "integration") else 1
            if days <= ex["closeDays"]:
                urgency = (ex["closeHigh"] if high and weak else ex["closeNewLow"] if not high and not item
                           else ex["closeLow"] if not high else 1)
            else:
                urgency = ex["nearHigh"] if high and weak else ex["nearLow"] if not high else 1

        plan = _plan(bank, q["concept_id"])
        components = {
            "importance": w["importance"][str(q["importance"])],
            "weakness": max(policy["mastery"]["weaknessFloor"], target["effective"] - m),
            "examUrgency": urgency, "examDirection": direction,
            "progression": prog["stageMatch"] if stage <= ready else prog["stageAhead"] if stage == ready + 1 else prog["stageFar"],
            "tier": w["tier"][priority_tier(q)],
            "novelty": w["novelty"] if not item else w["due"] if due_at <= now else w["notDue"],
            "budget": (w["budgetExceeded"] if (item or {}).get("reviews", 0) >= (plan["repetition_budget"] if plan else 1)
                       and m >= target["effective"] else 1),
            "remediation": policy["remediation"]["boost"] if remediation else 1,
            "diversity": ((rec["sameConceptPenalty"] if last_q and last_q["concept_id"] == q["concept_id"] else 1)
                          * (rec["newDirectionBonus"] if recent_directions and q["retrieval_direction"] not in recent_directions else 1)),
            "recent": rec["recentPenalty"] if any(h["question_id"] == qid for h in recent) and not remediation else 1,
        }
        raw_score = 1.0
        for value in components.values():
            raw_score *= value
        rows.append({"question_id": qid, "concept_id": q["concept_id"], "direction": q["retrieval_direction"],
                     "tier": priority_tier(q), "advanced": is_advanced(q), "eligible": not reasons, "reasons": reasons, "notes": notes,
                     "raw_score": raw_score, "score": 0 if reasons else raw_score, "components": components,
                     "mastery": m, "target": target, "stage": stage, "ready_stage": ready, "remediation": remediation})

    queued = [r for r in rows if r["eligible"] and r["remediation"]]
    if queued:
        for row in rows:
            if row["eligible"] and not row["remediation"]:
                row["eligible"], row["score"] = False, 0
                row["reasons"].append("지정된 선행 문항 보충이 우선입니다.")
    last_id = last["question_id"] if last else None
    alternative = any(r["eligible"] and r["question_id"] != last_id for r in rows)
    if not queued and alternative:
        for row in rows:
            if row["eligible"] and row["question_id"] == last_id:
                row["eligible"], row["score"] = False, 0
                row["reasons"].append("다른 문제를 먼저 풀어 연속 반복을 피합니다.")
    rows.sort(key=lambda r: r["question_id"])
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def select_question(bank: dict, state: dict, exam_date: str, now: int, policy: dict = DEFAULT,
                    *, prefer_unseen: bool = False, pages: dict | None = None) -> dict:
    if prefer_unseen:
        # 추가 학습의 기존 호출도 일반·모아풀기와 같은 선택 정책으로 연결한다.
        from .daily_queue import select_extra_question
        return select_extra_question(bank, state, exam_date, now, policy, pages=pages)
    bank = active_bank(bank, state)
    ranked = rank_questions(bank, state, exam_date, now, policy)
    chosen = next((r for r in ranked if r["eligible"] and r["score"] > 0), None)
    question = next((q for q in bank["questions"] if chosen and q["question_id"] == chosen["question_id"]), None)
    last = state["history"][-1]["timestamp"] if state["history"] else now
    return {"question": question, "ranked": ranked, "days": days_until(exam_date, now),
            "reason": None if chosen else "지금 풀 수 있는 문제가 없습니다. 기초 문제의 반복 대기나 진입 조건을 확인하세요.",
            "retry_at": None if chosen else last + policy["recency"]["minimumRepeatMs"]}


def record_review(bank: dict, previous: dict, question_id: str, rating: str, now: int, policy: dict = DEFAULT) -> dict:
    bank = personal_bank(bank, previous)
    if rating not in policy["mastery"]["ratings"]:
        raise ValueError("잘못된 평가입니다.")
    q = next((x for x in bank["questions"] if x["question_id"] == question_id), None)
    if not q:
        raise ValueError("문항을 찾을 수 없습니다.")
    state = upgrade_state(bank, previous, policy, now)
    dim = dimension_key(q)
    dimension_before = copy.deepcopy(state["dimensions"].get(dim))
    current = memory_snapshot(state, now, policy)
    before = mastery(current, q)
    stability = next_stability(state["dimensions"].get(dim) or {}, rating, now, policy)
    alpha = policy["mastery"]["alpha"]
    # 성공적으로 회상하면 이전에 쌓은 수준을 회복한다. 감쇠한 값에만 EMA를
    # 적용하면 일정대로 계속 Good이어도 목표에 도달하지 못하는 고정점이 생긴다.
    baseline = mastery(state, q) if rating in ("Good", "Easy") else before
    after = (1 - alpha) * baseline + alpha * policy["mastery"]["ratings"][rating]
    state["dimensions"][dim] = {"mastery": after, "reviews": (state["dimensions"].get(dim) or {}).get("reviews", 0) + 1,
                                "updated_at": now, "stability_days": stability}
    old = state["items"].get(question_id) or {"reviews": 0}
    schedule = review_schedule(bank, q, {"reviewed_at": now, "mastery_after": after, "stability_days": stability}, policy)
    state["items"][question_id] = {"reviews": old["reviews"] + 1, **schedule}

    events, remaining = [], []
    for r in state["remediations"]:
        success = r["prerequisite_id"] == question_id and rating in policy["remediation"]["successRatings"]
        if success or r["remaining"] <= 1:
            events.append({**r, "action": "recovered" if success else "expired", "timestamp": now})
        else:
            remaining.append({**r, "remaining": r["remaining"] - 1})
    state["remediations"] = remaining
    if rating == "Again" and q["prerequisites"] and (question_stage(q) >= 3 or is_advanced(q)):
        weakest = _weakest(bank, memory_snapshot(state, now, policy), q["prerequisites"])
        if weakest:
            entry = {"parent_id": question_id, "prerequisite_id": weakest["question_id"],
                     "remaining": policy["remediation"]["maxReviews"], "started_at": now}
            state["remediations"] = [r for r in state["remediations"] if r["parent_id"] != question_id] + [entry]
            events.append({**entry, "action": "queued", "timestamp": now})
    state["remediation_events"].extend(events)
    state["history"].append({
        "question_id": question_id, "rating": rating, "timestamp": now, "mastery_before": before,
        "mastery_after": after, "dimension": dim, "session_id": (state.get("session") or {}).get("id"),
        "stability_after": stability,
        "next_due_at": schedule["due_at"], "target_schedule": dict(schedule["target_schedule"]),
        "dimension_before": dimension_before,
        "policy_version": policy["version"], "policy_hash": policy_hash(policy), "remediation_events": events})
    state["served"] = None
    return state


_DIRECTION_ORDER = ("direct", "reverse", "discrimination", "trap", "mechanism", "sequence", "integration")


def concept_map(bank: dict, state: dict, policy: dict = DEFAULT, *, now: int | None = None) -> list[dict]:
    """개념 지도 — 개념마다 은행이 적은 것과, 이 사람의 방향별 숙련도를 목표와 나란히.

    **방향은 문항이 있는 것만 싣는다.** 회상 계획(`retrieval_plan`)에 적혔어도 문항이 없는 방향은
    엔진이 낼 수 없어 숙련도가 영영 0이다 — 그걸 그리면 학생이 못 채우는 칸을 본다.
    목표는 `target_for` 그대로다(정책 상한을 씌운 값). 화면이 다시 계산하면 갈라진다.

    `progress` 는 방향마다 목표 대비 비율(1에서 자른다)의 평균 — 그래프의 색 하나로 쓰는 값이다.
    """
    bank = personal_bank(bank, state)
    state = memory_snapshot(state, now, policy)
    ids = {c["concept_id"] for c in bank["concepts"]}
    out = []
    for concept in bank["concepts"]:
        cid = concept["concept_id"]
        by_direction: dict[str, list[dict]] = {}
        for q in bank["questions"]:
            if q["concept_id"] == cid:
                by_direction.setdefault(q["retrieval_direction"], []).append(q)
        directions = []
        for direction in sorted(by_direction, key=lambda d: _DIRECTION_ORDER.index(d)
                                if d in _DIRECTION_ORDER else len(_DIRECTION_ORDER)):
            questions = by_direction[direction]
            dim = state["dimensions"].get(dimension_key(questions[0])) or {}
            target = max(target_for(bank, q, policy)["effective"] for q in questions)
            directions.append({"direction": direction, "mastery": dim.get("mastery", 0), "target": target,
                               "reviews": dim.get("reviews", 0), "questions": len(questions)})
        progress = _average([min(d["mastery"] / d["target"], 1) if d["target"] else 1 for d in directions])
        out.append({
            "concept_id": cid, "title": concept["title"], "core_facts": concept.get("core_facts", []),
            "graph_title": concept.get("graph_title", ""),
            "importance": concept["importance"], "importance_rationale": concept.get("importance_rationale", ""),
            "concept_difficulty": concept["concept_difficulty"], "tier": priority_tier(concept),
            "exam_signal_strength": concept.get("exam_signal_strength", ""),
            "related_concepts": [r for r in concept.get("related_concepts", []) if r in ids and r != cid],
            "directions": directions, "progress": progress,
        })
    return out


def now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)
