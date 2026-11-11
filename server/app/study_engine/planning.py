"""하루 목표는 학습일 시작(한국 새벽 4시)의 기록으로 고정하고 현재 기록으로 남은 분량만 갱신한다."""

import math
from datetime import datetime

from .engine import dimension_key, empty_state
from .mastery import coverage, mastery_concepts
from .memory import DAY_MS, next_stability
from .study_day import KOREA, day_start


def state_before(bank: dict, state: dict, cutoff: int) -> dict:
    """현재 빌드의 평가 이력을 재생한다. 현재 숙련도를 과거로 되감아 감쇠하지 않는다."""
    past = empty_state()
    # Compare morning and current mastery against the same personal targets.
    past["question_tiers"] = dict(state.get("question_tiers", {}))
    by_id = {q["question_id"]: q for q in bank["questions"]}
    for review in state.get("history", []):
        if review["timestamp"] >= cutoff or "mastery_after" not in review:
            continue
        q = by_id.get(review["question_id"])
        if q is None:
            continue
        key = review.get("dimension") or dimension_key(q)
        previous = past["dimensions"].get(key) or {}
        stability = review.get("stability_after")
        if stability is None:
            stability = next_stability(previous, review["rating"], review["timestamp"])
        past["dimensions"][key] = {"mastery": review["mastery_after"], "reviews": previous.get("reviews", 0) + 1,
                                   "updated_at": review["timestamp"], "stability_days": stability}
    for key, dim in state["dimensions"].items():
        updated = dim.get("updated_at")
        if updated is not None and updated < cutoff:
            past["dimensions"][key] = dict(dim)
        elif updated is None and key not in past["dimensions"]:
            past["dimensions"][key] = dict(dim)
    restored = set()
    for review in state.get("history", []):
        if review["timestamp"] < cutoff:
            continue
        q = by_id.get(review["question_id"])
        if q is None:
            continue
        key = review.get("dimension") or dimension_key(q)
        if key in restored:
            continue
        restored.add(key)
        if "dimension_before" not in review:
            continue  # 첫 당일 평가가 옛 형식이면 위의 과거 이력 재생 결과를 쓴다.
        before = review["dimension_before"]
        # 첫 당일 평가 전 상태를 그대로 복원해, 옛 기록의 안정성 가정도 유지한다.
        if before:
            past["dimensions"][key] = dict(before)
        else:
            past["dimensions"].pop(key, None)
    return past


def total_score(values: list[float]) -> float:
    # 강의마다 같은 비중. 강의 내부의 개념 수 차이로 큰 강의가 전체를 독점하지 않는다.
    return 100 * (1 - math.sqrt(sum((1 - p) ** 2 for p in values) / len(values))) if values else 0


def balanced_daily_gain(baseline: float, target: float, retention: float, durations: list[float]) -> float:
    """B_next = r**dt * B + g*dt 를 목표일까지 전개해 일정한 하루 확보량 g를 구한다.

    현재 관측한 전체 학습률 유지 비율을 사용하는 계획 근사이며, 미래 개인 기억률은 아니다.
    """
    carried, weight = baseline, 0.0
    for duration in durations:
        factor = retention ** duration
        carried *= factor
        weight = weight * factor + duration
    return max(0.0, (target - carried) / weight) if weight else 0.0


def daily_plan(units: list[dict], target: int, now: int, deadline: int) -> dict:
    """unit: {bank,state,date}. 문제 미준비 강의는 bank=None, 계획상 학습도 0으로 가정한다."""
    start = day_start(now)
    study_deadline = deadline - 3 * DAY_MS
    # 목표일이 오늘 중간이면 그 시각까지 확보하고, 이후에는 시험일까지 유지·보충한다.
    buffer_phase = now >= study_deadline
    planning_deadline = deadline if buffer_phase else study_deadline
    horizon = min(start + DAY_MS, planning_deadline)
    days = max(1, math.ceil((deadline - start) / DAY_MS))
    morning, morning_end, current, projected, available = [], [], [], [], []
    for unit in units:
        bank, state = unit["bank"], unit["state"]
        if not bank:
            for values in (morning, morning_end, current, projected, available):
                values.append(0)
            continue
        past = state_before(bank, state, start)

        def progress(snapshot, at):
            return coverage(mastery_concepts(bank, snapshot, now=at)[1])

        morning.append(progress(past, start))
        morning_end.append(progress(past, horizon))
        current.append(progress(state, now))
        projected.append(progress(state, horizon))
        available.append(1)
    baseline = total_score(morning)
    baseline_end = total_score(morning_end)
    current_score = total_score(current)
    projected_end = total_score(projected)
    duration = (horizon - start) / DAY_MS
    # 아직 학습 기록이 없으면 안정성 1일의 초기 가정(하루 90% 유지)을 쓴다.
    retention = (min(1.0, baseline_end / baseline) ** (1 / duration)) if baseline > 0 else .9
    learning_days = max(0, math.ceil((study_deadline - start) / DAY_MS)) if not buffer_phase else 0
    durations = [min(1.0, (planning_deadline - at) / DAY_MS)
                 for at in range(start, planning_deadline, DAY_MS)]
    daily_gain = balanced_daily_gain(baseline, max(target, baseline), retention, durations)
    end_target = min(100.0, max(baseline, baseline_end + daily_gain * duration))
    net_gain = max(0, end_target - baseline)
    # 목표를 이미 넘겼어도 그날 시작 수준을 유지하도록 망각분 보충을 제시한다.
    gross = max(0, end_target - baseline_end)
    remaining = max(0, end_target - projected_end)
    capacity = total_score(available)
    met = remaining < 1e-9
    progress = 100 if met else min(99, max(0, math.floor((gross - remaining) / gross * 100))) if gross > 0 else 0
    reviewed_today = sum(1 for unit in units if unit["bank"] for review in unit["state"].get("history", [])
                         if start <= review["timestamp"] <= now)
    return {
        "daysLeft": days, "dayStart": start, "horizon": horizon,
        "studyDeadline": study_deadline, "learningDaysLeft": learning_days,
        "bufferDays": 3, "bufferPhase": buffer_phase,
        "assumedDailyRetention": round(retention, 4),
        "lateLectures": sum(u["date"] >= datetime.fromtimestamp(study_deadline / 1000, KOREA).date()
                            for u in units),
        "target": target, "morningScore": round(baseline, 1), "currentScore": round(current_score, 1),
        "projectedScore": round(projected_end, 1), "endTarget": round(end_target, 1),
        "netGain": round(net_gain, 1), "forgettingLoss": round(max(0, baseline - baseline_end), 1),
        "requiredGain": round(gross, 1), "earnedGain": round(projected_end - baseline_end, 1),
        # 아주 조금 남은 상태는 완료와 구분한다.
        "remainingGain": math.ceil(remaining * 10 - 1e-9) / 10,
        "met": met, "progressPercent": progress, "reviewedToday": reviewed_today,
        "availableCeiling": round(capacity, 1),
        "limitedByMaterials": capacity + 1e-9 < end_target,
    }
