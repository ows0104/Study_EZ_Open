"""강의 학습도. 현재 은행의 핵심 개념을 목표 대비로 집계한다."""

from math import sqrt

from .engine import concept_map
from .policy import DEFAULT
from .personal_priority import personal_bank


def mastery_concepts(bank: dict, state: dict, policy: dict = DEFAULT, *, now: int | None = None) -> tuple[str, list[dict]]:
    bank = personal_bank(bank, state)
    # 문항 수가 많은 개념이 점수를 독점하지 않도록 개념 단위로 집계한다.
    # 중요도 Core만 집계한다. 독립 심화 표시는 Core 여부를 바꾸지 않는다.
    core = [q for q in bank["questions"] if q["tier"] == "Core"]
    scope = "core" if core else "all"
    scoped = {**bank, "questions": core or bank["questions"]}
    concepts = [c for c in concept_map(scoped, state, policy, now=now) if c["directions"]]
    return scope, concepts


def coverage(concepts: list[dict]) -> float:
    return 1 - sqrt(sum((1 - c["progress"]) ** 2 for c in concepts) / len(concepts)) if concepts else 0


def lecture_mastery(bank: dict, state: dict, policy: dict = DEFAULT, *, now: int | None = None) -> dict | None:
    scope, concepts = mastery_concepts(bank, state, policy, now=now)
    if not concepts:
        return None
    directions = [d for c in concepts for d in c["directions"]]
    assessed = sum(d["reviews"] > 0 for d in directions)
    weak = [c for c in concepts if any(d["reviews"] == 0 or d["mastery"] < d["target"]
                                     for d in c["directions"])]
    weak.sort(key=lambda c: (c["progress"], -c["importance"], c["concept_id"]))
    status = "not_started" if not assessed else "needs_review" if weak else "mastered"
    # 학습이 덜 된 개념을 더 크게 반영한다: 1 - RMS(목표까지 남은 부족분).
    # [100%, 0%]는 29%, [50%, 50%]는 50%다. 같은 폭의 향상이라도
    # 약한 개념을 보완할 때 점수가 더 많이 오르며, 한 개념이 0이어도
    # 전체 점수가 0으로 고정되지는 않는다. 목표 초과분은 progress에서 잘린다.
    progress = coverage(concepts)
    return {
        "status": status,
        # 반올림으로 목표 미달 강의가 100%로 표시되지 않게 한다.
        "score": 100 if status == "mastered" else min(99, round(progress * 100)),
        "scope": scope,
        "conceptCount": len(concepts),
        "masteredConcepts": len(concepts) - len(weak),
        "weakConcepts": len(weak),
        "assessedDirections": assessed,
        "totalDirections": len(directions),
        "weakest": [{"conceptId": c["concept_id"], "title": c["title"]} for c in weak[:3]],
    }
