"""Undo reviews and suspensions in order, preserving schedules and remediation."""

import copy


def last_undo(state: dict) -> dict:
    history = state.get("history") or []
    session = state.get("session") or {}
    suspensions = state.get("suspension_undo") or []
    if suspensions:
        last = suspensions[-1]
        if last["session_id"] == session.get("id") and last["history_count"] == len(history):
            return last
    last = history[-1] if history else {}
    saved = last.get("undo")
    if not saved or last.get("session_id") != session.get("id") or last.get("question_id") in state.get("suspended_question_ids", []):
        return {}
    return last


def undo_token(state: dict) -> str | None:
    last = last_undo(state)
    return last["undo"]["served"]["token"] if last else None


def remember_suspension(state: dict, now: int) -> None:
    state["suspension_undo"] = [*state.get("suspension_undo", []), {
        "session_id": state["session"]["id"], "timestamp": now,
        "history_count": len(state["history"]),
        "question_id": state["served"]["question_id"],
        "undo": {"served": copy.deepcopy(state["served"])},
    }]


def remember_review(previous: dict, reviewed: dict) -> None:
    last = reviewed["history"][-1]
    last["undo"] = copy.deepcopy({
        "served": previous["served"],
        "item": previous["items"].get(last["question_id"]),
        "remediations": previous["remediations"],
        "event_count": len(previous["remediation_events"]),
    })


def undo_review(previous: dict, token: str) -> dict:
    if not token or undo_token(previous) != token:
        raise ValueError("되돌릴 수 있는 마지막 학습 작업이 아닙니다.")
    state = copy.deepcopy(previous)
    last = last_undo(state)
    saved = last["undo"]
    if "history_count" in last:
        state["suspension_undo"].pop()
        state["suspended_question_ids"] = [qid for qid in state.get("suspended_question_ids", [])
                                           if qid != last["question_id"]]
    else:
        if last.get('origin_event_id') or state.get('_study_build_id'):
            from app.study_retention import event_identity
            origin = event_identity(state.get('_study_build_id', ''), last)
            state['review_tombstones'] = sorted({*state.get('review_tombstones', []), origin})
        state["history"].pop()
        for field, key, value in (("dimensions", last["dimension"], last["dimension_before"]),
                                  ("items", last["question_id"], saved["item"])):
            if value is None:
                state[field].pop(key, None)
            else:
                state[field][key] = value
        state["remediations"] = saved["remediations"]
        state["remediation_events"] = state["remediation_events"][:saved["event_count"]]
    state["served"] = saved["served"]
    session = state["session"]
    session["status"] = "active"
    session.pop("reason", None)
    session.pop("ended_at", None)
    state["sessions"] = [s for s in state["sessions"] if s["session_id"] != session["id"]]
    return state
