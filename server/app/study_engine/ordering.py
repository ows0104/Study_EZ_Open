"""일반·모아풀기 공통 순서: 선행관계, 슬라이드 흐름, 간격, 예정일·약점 가중 섞기."""

import random

from app.bank_validation.pages import pages_of
from .memory import DAY_MS
from .planning import day_start
from .policy import DEFAULT


def question_slide(question: dict, pages: dict | None = None) -> float:
    # 강의자료(S1)의 위치만 사용한다. 족보의 페이지 번호와 섞지 않는다.
    found = (pages or {}).get(question["question_id"], [])
    if not found:
        found = [page for ref in question.get("source_refs", []) if ref["source_id"] == "S1"
                 for page in pages_of(ref["locator"])]
    return min(found) if found else float("inf")


def study_history(bank: dict, state: dict, now: int, scope: tuple = ()) -> list[dict]:
    by_id = {q["question_id"]: q for q in bank["questions"]}
    return [{"scope": scope, "question": by_id.get(h["question_id"]), "timestamp": h["timestamp"]}
            for h in state.get("history", []) if day_start(now) <= h["timestamp"] <= now]


def direction_gap(candidate: dict, history: list[dict]) -> int | None:
    q = candidate["question"]
    for gap, event in enumerate(reversed(history)):
        previous = event["question"]
        if (previous and event["scope"] == candidate["scope"] and previous["concept_id"] == q["concept_id"]
                and previous["retrieval_direction"] != q["retrieval_direction"]):
            return gap
    return None


def review_weight(candidate: dict, now: int) -> float:
    row = candidate["rank"]
    overdue = max(0, (day_start(now) - candidate["unit"]["scheduled_due"]) / DAY_MS)
    future_days = max(0, (day_start(candidate["unit"]["scheduled_due"]) - day_start(now)) / DAY_MS)
    components = row["components"]
    # 당일 시각을 기다리게 하지는 않지만 원래 예정일은 가중치에 남긴다.
    return ((1 + min(overdue, 30)) / (1 + future_days) * components["weakness"] * components["importance"]
            * components["examUrgency"] * components["examDirection"])


def choose_candidate(candidates: list[dict], history: list[dict], now: int, policy: dict = DEFAULT) -> dict | None:
    if not candidates:
        return None
    pool = [c for c in candidates if c["unit"]["kind"] == "new"] or candidates
    if pool[0]["unit"]["kind"] == "new":
        # Spacing can reorder peers, but cannot promote a lower priority or depth.
        priority = min(c["order"][:2] for c in pool)
        pool = [c for c in pool if c["order"][:2] == priority]
    history = sorted(history, key=lambda event: event["timestamp"])
    spacing = policy["ordering"]
    gaps = {id(c): direction_gap(c, history) for c in pool}
    # 목표 4문항, 최소 3문항. 후보가 부족하면 가능한 한 떨어뜨리고 기다리게 하지 않는다.
    for minimum in (spacing["targetIntervening"], spacing["minIntervening"]):
        spaced = [c for c in pool if gaps[id(c)] is None or gaps[id(c)] >= minimum]
        if spaced:
            pool = spaced
            break
    else:
        longest = max(gaps[id(c)] for c in pool)
        pool = [c for c in pool if gaps[id(c)] == longest]
    # 미룬 방향은 5문항을 지나면 우선 돌아온다. 선행관계는 후보 생성 시 충족한다.
    deferred = [c for c in pool if gaps[id(c)] is not None and gaps[id(c)] >= spacing["maxIntervening"]]
    if deferred:
        pool = deferred
    if pool[0]["unit"]["kind"] == "new":
        return min(pool, key=lambda c: c["order"])
    return random.choices(pool, weights=[review_weight(c, now) for c in pool], k=1)[0]
