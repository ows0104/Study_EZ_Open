"""학습 회차 — 기본은 개수 제한 없음. 선택한 상한이 있으면 적용한다.

AdaptiveStudy3/study_engine/session.mjs 를 옮겼다(2026-10-04).
"""

from __future__ import annotations

import copy
import uuid

from .engine import core_mastery, dimension_key, target_for
from .memory import memory_snapshot
from .policy import DEFAULT, policy_hash
from .personal_priority import personal_bank

RATINGS = ("Again", "Hard", "Good", "Easy")


def start_session(bank: dict, previous: dict, size: int | None, now: int, policy: dict = DEFAULT) -> dict:
    if size is not None and size not in policy["session"]["sizes"]:
        raise ValueError("지원하지 않는 학습 회차 크기입니다.")
    state = copy.deepcopy(previous)
    if (state.get("session") or {}).get("status") == "active":
        return state
    current = memory_snapshot(state, now, policy)
    state["session"] = {"id": str(uuid.uuid4()), "size": size, "status": "active",
                        "start_index": len(state["history"]), "started_at": now,
                        "dimensions_before": copy.deepcopy(current["dimensions"]),
                        "core_before": core_mastery(bank, current),
                        "policy_version": policy["version"], "policy_hash": policy_hash(policy)}
    return state


def session_summary(bank: dict, state: dict, policy: dict = DEFAULT, *, now: int | None = None) -> dict | None:
    bank = personal_bank(bank, state)
    session = state.get("session")
    if not session:
        return None
    # 완료된 회차는 당시 결과다. 오늘의 망각 때문에 과거 성과까지 내려가지 않는다.
    if session["status"] == "complete":
        saved = next((s for s in state.get("sessions", []) if s["session_id"] == session["id"]), None)
        if saved:
            return copy.deepcopy(saved)
    reviews = [r for r in state["history"][session["start_index"]:] if r.get("session_id") == session["id"]]
    ratings = {r: 0 for r in RATINGS}
    for r in reviews:
        ratings[r["rating"]] += 1
    at = session.get("ended_at") if session["status"] == "complete" else now
    if at is None:
        at = reviews[-1]["timestamp"] if reviews else session["started_at"]
    state = memory_snapshot(state, at, policy)
    titles = {c["concept_id"]: c["title"] for c in bank["concepts"]}
    by_dim = {dimension_key(q): q for q in bank["questions"]}
    dims = [{"concept_id": q["concept_id"], "title": titles.get(q["concept_id"], q["concept_id"]),
             "direction": q["retrieval_direction"],
             "before": (session["dimensions_before"].get(key) or {}).get("mastery", 0),
             "after": (state["dimensions"].get(key) or {}).get("mastery", 0),
             "target": target_for(bank, q, policy)["effective"]} for key, q in by_dim.items()]
    improved = sorted((d for d in dims if d["after"] > d["before"]), key=lambda d: d["after"] - d["before"], reverse=True)
    weaknesses = sorted((d for d in dims if d["after"] < d["target"]), key=lambda d: d["target"] - d["after"], reverse=True)[:5]
    return {"session_id": session["id"], "status": session["status"], "reason": session.get("reason"),
            "size": session["size"], "reviewed": len(reviews), "ratings": ratings,
            "core_before": session["core_before"], "core_after": core_mastery(bank, state),
            "improved": improved, "weaknesses": weaknesses,
            "remediation_events": [e for r in reviews for e in r.get("remediation_events") or []],
            "started_at": session["started_at"], "ended_at": session.get("ended_at"),
            "policy_version": session["policy_version"], "policy_hash": session["policy_hash"]}


def end_session(bank: dict, previous: dict, reason: str, now: int, policy: dict = DEFAULT) -> dict:
    state = copy.deepcopy(previous)
    if not state.get("session") or state["session"]["status"] != "active":
        return state
    state["session"].update(status="complete", reason=reason, ended_at=now)
    state["served"] = None
    state["sessions"].append(session_summary(bank, state, policy))
    return state
