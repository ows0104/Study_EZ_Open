"""학습 회차 — 10/20/25/30문항. 중간에 나가도 이어지고, 끝나면 요약을 남긴다.

AdaptiveStudy3/study_engine/session.mjs 를 옮겼다(2026-10-04).
"""

from __future__ import annotations

import copy
import uuid

from .engine import core_mastery, dimension_key, target_for
from .policy import DEFAULT, policy_hash

RATINGS = ("Again", "Hard", "Good", "Easy")


def start_session(bank: dict, previous: dict, size: int, now: int, policy: dict = DEFAULT) -> dict:
    if size not in policy["session"]["sizes"]:
        raise ValueError("지원하지 않는 학습 회차 크기입니다.")
    state = copy.deepcopy(previous)
    if (state.get("session") or {}).get("status") == "active":
        return state
    state["session"] = {"id": str(uuid.uuid4()), "size": size, "status": "active",
                        "start_index": len(state["history"]), "started_at": now,
                        "dimensions_before": copy.deepcopy(state["dimensions"]),
                        "core_before": core_mastery(bank, state),
                        "policy_version": policy["version"], "policy_hash": policy_hash(policy)}
    return state


def session_summary(bank: dict, state: dict, policy: dict = DEFAULT) -> dict | None:
    session = state.get("session")
    if not session:
        return None
    reviews = [r for r in state["history"][session["start_index"]:] if r.get("session_id") == session["id"]]
    ratings = {r: 0 for r in RATINGS}
    for r in reviews:
        ratings[r["rating"]] += 1
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
