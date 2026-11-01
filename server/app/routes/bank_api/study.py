"""Single/batch study sessions, selection, rating, undo, and prepared responses."""
from __future__ import annotations

import copy
import hashlib
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, tuple_
from sqlalchemy.orm import Session

from app import bank_edits, bank_personal, study_engine as engine
from app.auth import CurrentUser, require_approved_user
from app.bank_validation.choice_mode import choice_mode
from app.config import get_settings
from app.database import get_db
from app.models import Asset, BankPersonalEdit, BankState, Lecture, QuizBank, SLIDE_KINDS
from app.routes.common import lecture_or_404
from app.study_engine import prepared_selection
from app.study_engine.batch import aggregate_goal, select_batch_question
from app.study_engine.choices import realize_choices
from app.study_engine.daily_queue import (
    daily_units, lecture_goal, select_daily_question, select_extra_question,
)
from app.study_engine.engine import reschedule_bank
from app.study_engine.planning import day_start
from app.study_engine.progress import mark_seen
from app.study_engine.review_undo import (
    last_undo, remember_review, remember_suspension, undo_review, undo_token,
)

from .common import _bank_or_404, exam_date_for, summary
from .presentation import _answer, _public, _served_question, _slides
from .state import _load_state, _save, _study_bank


router = APIRouter()


class StartIn(BaseModel):
    size: int | None = None
    continue_after_goal: bool = Field(False, alias="continueAfterGoal")
    daily_only: bool = Field(False, alias="dailyOnly")


@router.post("/lectures/{subject}/{run_id}/bank/session/start")
def start_bank_session(subject: str, run_id: str, payload: StartIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state = _load_state(db, user, row)
    try:
        started = engine.start_session(bank, state.state, payload.size, engine.now_ms())
        # 재개 요청으로 진행 중 회차의 종료 방식을 덮어쓰지 않는다.
        if (state.state.get("session") or {}).get("status") != "active":
            started["session"]["continue_after_goal"] = payload.continue_after_goal
        if payload.daily_only:
            # 모아 풀기는 열린 회차도 문항 수 제한 없이 오늘 분량까지만 이어간다.
            started["session"].update(size=None, continue_after_goal=False)
        _save(state, started)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return engine.session_summary(bank, state.state, now=engine.now_ms())


class EndIn(BaseModel):
    session_id: str = Field(alias="sessionId")

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/session/end")
def end_bank_session(subject: str, run_id: str, payload: EndIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state = _load_state(db, user, row)
    session = state.state.get("session") or {}
    if session.get("id") != payload.session_id:
        raise HTTPException(409, "현재 학습 회차가 아닙니다.")
    _save(state, engine.end_session(bank, state.state, "user_finished", engine.now_ms()))
    db.commit()
    return engine.session_summary(bank, state.state, now=engine.now_ms())


@router.post("/lectures/{subject}/{run_id}/bank/next")
def next_bank_question(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db), target: int = Query(90, ge=50, le=100),
                       shuffle: bool = False, choice_protocol: bool = Query(False, alias="choiceProtocol")) -> dict[str, Any]:
    return _next_bank_question(subject, run_id, user, db, choice_protocol=choice_protocol)


def _next_bank_question(subject: str, run_id: str, user: CurrentUser, db: Session,
                        *, choice_protocol: bool = False, selection: dict | None = None,
                        preview_state: dict | None = None, served_token: str | None = None,
                        preview_states_out: dict | None = None, prepared: tuple | None = None,
                        preview_entry: dict | None = None) -> dict[str, Any]:
    """다음 문항. **이미 내준 문항이 있으면 그것을 다시 준다** — 새로고침이 문항을 넘기지 않는다."""
    if preview_entry is not None:
        assert preview_state is not None
        lecture, row, bank = preview_entry["lecture"], preview_entry["row"], preview_entry["bank"]
    else:
        lecture = lecture_or_404(db, subject, run_id)
        row = _bank_or_404(db, lecture, user)
        bank = _study_bank(db, row, user)
    state_row = _load_state(db, user, row) if preview_state is None else None
    now = engine.now_ms()
    state = engine.upgrade_state(bank, state_row.state if state_row else preview_state, engine.DEFAULT, now)

    def save():
        if preview_states_out is not None:
            preview_states_out[(subject, run_id)] = copy.deepcopy(state)
        if state_row is not None:
            _save(state_row, state)
            db.commit()

    if not state.get("session"):
        state = engine.start_session(bank, state, None, now)
    if state["session"]["status"] == "complete":
        save()
        return {"question": None, "summary": engine.session_summary(bank, state, now=now), "undoToken": undo_token(state)}
    exam = preview_entry.get("exam") if preview_entry is not None else None
    if exam is None:
        exam = exam_date_for(db, lecture)
    by_id = {q["question_id"]: q for q in bank["questions"]}
    served = state.get("served")
    goal = lecture_goal(bank, state, lecture.title, now)
    if served and served["question_id"] in by_id and served["question_id"] not in state.get("suspended_question_ids", []):
        question = by_id[served["question_id"]]
        days = engine.days_until(exam, now)
    else:
        extra_today = state["session"].get("continue_after_goal") and day_start(
            state["session"]["started_at"]) == day_start(now)
        if goal and goal["met"] and not extra_today:
            state = engine.end_session(bank, state, "lecture_goal_met", now)
            save()
            return {"question": None, "summary": engine.session_summary(bank, state, now=now),
                    "lectureGoal": goal, "reason": "lecture_goal_met", "undoToken": undo_token(state)}
        reserved = ((), prepared[1]) if prepared and prepared[0] == (subject, run_id) else None
        picked = (select_extra_question(bank, state, exam, now, pages=row.pages, seed=served_token, prepared=reserved) if goal["met"] and extra_today
                  else selection if selection is not None
                  else select_daily_question(bank, state, exam, now, pages=row.pages, seed=served_token, prepared=reserved))
        question, days = picked["question"], picked["days"]
        if question is None:
            if not goal["met"]:
                save()
                return {"question": None, "waiting": True, "lectureGoal": goal,
                        "session": engine.session_summary(bank, state, now=now),
                        "reason": picked["reason"], "retryAt": picked["retry_at"], "undoToken": undo_token(state)}
            state = engine.end_session(bank, state, "no_eligible_question", now)
            save()
            return {"question": None, "summary": engine.session_summary(bank, state, now=now),
                    "reason": picked["reason"], "retryAt": picked["retry_at"], "undoToken": undo_token(state)}
        score = next((r for r in picked["ranked"] if r["question_id"] == question["question_id"]), None)
        served = {"question_id": question["question_id"], "token": served_token or uuid.uuid4().hex, "revealed": False,
                  "choice_protocol": bool(choice_protocol),
                  "presented_at": now, "policy_version": engine.DEFAULT["version"],
                  "policy_hash": engine.policy_hash(engine.DEFAULT), "score": score}
        state["served"] = served
    if choice_protocol and not served.get("choice_protocol"):
        # 구 화면에서 이미 보던 선지는 숨기지 않는다. 새 문항부터 인출 단계를 적용한다.
        served.update(choice_protocol=True, choices_shown=True)
    if "question_snapshot" not in served:
        question = (bank_personal.apply_edit(by_id[question["question_id"]], preview_entry["personal_edits"].get(question["question_id"]))
                    if preview_entry is not None and "personal_edits" in preview_entry
                    else bank_personal.apply(db, row, user.id, by_id[question["question_id"]]))
        review = next((r for r in bank_edits.current_review(row.review, row.validation)["reviews"]
                       if r["question_id"] == question["question_id"]), None)
        previous = state.setdefault("choice_variants", {}).get(question["question_id"])
        question = realize_choices({**question, "medicalReview": review}, served["token"], previous)
        question.pop("medicalReview", None)
        question["presentationSeed"] = hashlib.sha256(f"layout:{served['token']}".encode()).hexdigest()
        served["question_snapshot"] = question
        if question.get("choice_variant"):
            state["choice_variants"][question["question_id"]] = question["choice_variant"]
    question = _served_question(db, row, user.id, bank, served, prepared_entry=preview_entry)
    mark_seen(state, question["question_id"])
    save()
    choices_shown = not served.get("choice_protocol") or choice_mode(question) != "recall_first" or served.get("choices_shown", False) or served.get("revealed", False)
    return {"question": _public(question, bank=bank, show_choices=choices_shown), "choicesShown": choices_shown,
            "reviewToken": served["token"], "days": days, "examDate": exam,
            "lectureGoal": goal, "undoToken": undo_token(state),
            "preloadSlides": _slides(db, row, question["question_id"], question, prepared_entry=preview_entry),
            "session": engine.session_summary(bank, state, now=now),
            "answer": _answer(db, row, question, prepared_entry=preview_entry) if served.get("revealed") else None}


class TokenIn(BaseModel):
    review_token: str = Field(alias="reviewToken")

    model_config = {"populate_by_name": True}


class PriorityIn(TokenIn):
    tier: Literal["Essential", "Core", "Important", "Optional"] | None


@router.put("/lectures/{subject}/{run_id}/bank/questions/{question_id}/priority")
def set_bank_priority(subject: str, run_id: str, question_id: str, payload: PriorityIn,
                      user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    if not any(q["question_id"] == question_id for q in bank["questions"]):
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = state.get("served") or {}
    if served.get("token") != payload.review_token or served.get("question_id") != question_id:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    tiers = dict(state.get("question_tiers", {}))
    if payload.tier is None:
        tiers.pop(question_id, None)
    else:
        tiers[question_id] = payload.tier
    state["question_tiers"] = tiers
    state = reschedule_bank(bank, state, question_ids={question_id})
    _save(state_row, state)
    db.commit()
    question = _served_question(db, row, user.id, bank, served)
    choices_shown = not served.get("choice_protocol") or choice_mode(question) != "recall_first" or served.get("choices_shown", False) or served.get("revealed", False)
    return {"question": _public(question, bank=bank, show_choices=choices_shown),
            "rescheduled": bool((state.get("items", {}).get(question_id) or {}).get("target_schedule")),
            "lectureGoal": lecture_goal(bank, state, lecture.title, engine.now_ms())}


class SuspensionIn(BaseModel):
    suspended: bool
    review_token: str | None = Field(default=None, alias="reviewToken")
    build_id: str | None = Field(default=None, alias="buildId")


@router.put("/lectures/{subject}/{run_id}/bank/questions/{question_id}/suspension")
def set_bank_suspension(subject: str, run_id: str, question_id: str, payload: SuspensionIn,
                        user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _study_bank(db, row, user)
    if not any(q["question_id"] == question_id for q in bank["questions"]):
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = state.get("served") or {}
    if payload.suspended:
        if not payload.review_token or served.get("token") != payload.review_token or served.get("question_id") != question_id:
            raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    elif payload.build_id != row.build_id:
        raise HTTPException(409, "문제은행이 변경됐습니다. 목록을 새로고침하세요.")
    suspended = set(state.get("suspended_question_ids", []))
    if payload.suspended:
        remember_suspension(state, engine.now_ms())
        suspended.add(question_id)
        state["served"] = None
    else:
        suspended.discard(question_id)
        state["suspension_undo"] = [entry for entry in state.get("suspension_undo", [])
                                    if entry["question_id"] != question_id]
    state["suspended_question_ids"] = sorted(suspended)
    _save(state_row, state)
    db.commit()
    return {"questionId": question_id, "suspended": payload.suspended, "buildId": row.build_id}


@router.post("/lectures/{subject}/{run_id}/bank/options")
def show_bank_options(subject: str, run_id: str, payload: TokenIn,
                      user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _study_bank(db, row, user)
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = dict(state.get("served") or {})
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    question = _served_question(db, row, user.id, bank, served)
    served["choices_shown"] = True
    served.setdefault("choices_shown_at", engine.now_ms())
    state["served"] = served
    _save(state_row, state)
    db.commit()
    return {"question": _public(question, bank=bank), "choicesShown": True}


@router.post("/lectures/{subject}/{run_id}/bank/prepare")
def prepare_bank_answer(subject: str, run_id: str, payload: TokenIn,
                        user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """Read-only warmup for the served question; /reveal still records the actual click."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state_row = db.get(BankState, (user.id, row.subject, row.run_id))
    if state_row is None or state_row.build_id != row.build_id:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    served = state_row.state.get("served") or {}
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    question = _served_question(db, row, user.id, bank, served)
    return _answer(db, row, question)


class RevealIn(TokenIn):
    response_time_ms: int | None = Field(default=None, alias="responseTimeMs", ge=0, le=86_400_000)


@router.post("/lectures/{subject}/{run_id}/bank/reveal")
def reveal_bank_answer(subject: str, run_id: str, payload: RevealIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = dict(state.get("served") or {})
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    question = _served_question(db, row, user.id, bank, served)
    if served.get("choice_protocol") and choice_mode(question) == "recall_first" and not served.get("choices_shown") and not served.get("revealed"):
        raise HTTPException(409, "먼저 답을 떠올린 뒤 선지를 공개하세요.")
    served["revealed"] = True
    served.setdefault("revealed_at", engine.now_ms())
    if payload.response_time_ms is not None:
        # Cached cards can be read before the previous save reaches the server.
        served.setdefault("client_response_time_ms", payload.response_time_ms)
    state["served"] = served
    _save(state_row, state)
    db.commit()
    question = _served_question(db, row, user.id, bank, served)
    return _answer(db, row, question)


class BatchLectureIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    run_id: str = Field(alias="runId", min_length=1, max_length=32)


class RateIn(BaseModel):
    review_token: str = Field(alias="reviewToken")
    rating: Literal["Again", "Hard", "Good", "Easy"]
    advance: bool = False
    retry_safe: bool = Field(default=False, alias="retrySafe")
    selection_ticket: str | None = Field(default=None, alias="selectionTicket", max_length=2048)
    lectures: list[BatchLectureIn] | None = Field(default=None, min_length=1, max_length=100)

    model_config = {"populate_by_name": True}


def _advance_token(token: str, rating: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"studyez:{token}:{rating}").hex


def _draw_entries(subject, run_id, lectures, user, db):
    if lectures:
        entries = _batch_entries(BatchIn(lectures=lectures), user, db)
    else:
        lecture = lecture_or_404(db, subject, run_id)
        row = _bank_or_404(db, lecture, user)
        saved = db.get(BankState, (user.id, subject, run_id))
        entries = [{"key": (subject, run_id), "lecture": lecture, "row": row,
                    "bank": _study_bank(db, row, user), "state": saved.state if saved else engine.empty_state()}]
    for entry in entries:
        entry["exam"] = exam_date_for(db, entry["lecture"])
    return entries


def _draw_context(subject, run_id, lectures, user, db, states=None, entries=None):
    entries = [dict(entry) for entry in (entries if entries is not None else _draw_entries(subject, run_id, lectures, user, db))]
    for entry in entries:
        entry["state"] = (states or {}).get(entry["key"], entry["state"])
    return prepared_selection.context(entries, engine.now_ms())


def _seal_draw(got, parent, rating, fingerprint, subject, run_id, user):
    secret = get_settings().runner_token
    if got.get("question") and secret:
        ref = got.get("lecture") or {"subject": subject, "runId": run_id}
        got["selectionTicket"] = prepared_selection.seal(secret, user.id, parent, rating, fingerprint,
            (ref["subject"], ref["runId"]), got["question"]["question_id"])


def _reviewed_state(bank: dict, state: dict, rating: str, now: int) -> dict:
    served = state["served"]
    nxt = engine.record_review(bank, state, served["question_id"], rating, now)
    remember_review(state, nxt)
    last = nxt["history"][-1]
    from app.study_retention import fingerprint as study_fingerprint
    authored = next(q for q in bank['questions'] if q['question_id'] == served['question_id'])
    snapshot = served.get('question_snapshot') or {}
    last['question_fingerprint'] = study_fingerprint(snapshot if snapshot.get('personalEdited') else authored)
    last["score_breakdown"] = served.get("score")
    last["selection_policy_version"] = served.get("policy_version")
    presented = served.get("presented_at")
    last["response_time_sec"] = max(0, (served.get("revealed_at", now) - presented) / 1000) if presented else None
    if "client_response_time_ms" in served:
        last["response_time_sec"] = served["client_response_time_ms"] / 1000
    summary = engine.session_summary(bank, nxt, now=now)
    limit = nxt["session"]["size"]
    if summary and limit is not None and summary["reviewed"] >= limit:
        nxt = engine.end_session(bank, nxt, "size_reached", now)
    return nxt


@router.post("/lectures/{subject}/{run_id}/bank/rate")
def rate_bank_answer(subject: str, run_id: str, payload: RateIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """답을 본 뒤에 한 번만. 회차가 다 차면 여기서 닫는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state_row = _load_state(db, user, row)
    state = state_row.state
    served = state.get("served") or {}
    last = (state.get("history") or [{}])[-1]
    replay = payload.retry_safe and (last.get("undo", {}).get("served") or {}).get("token") == payload.review_token and last.get("rating") == payload.rating
    if not replay and (not served.get("revealed") or served.get("token") != payload.review_token):
        raise HTTPException(409, "정답 공개 후 한 번만 평가할 수 있습니다.")
    now = engine.now_ms()
    nxt = state if replay else _reviewed_state(bank, state, payload.rating, now)
    if not replay:
        _save(state_row, nxt)
        db.commit()
    result = {"reviews": len(nxt["history"]), "session": engine.session_summary(bank, nxt, now=now)}
    if payload.advance:
        # The review is committed even if selecting the next question fails.
        # Report that separately so clients never submit the same rating twice.
        try:
            token = _advance_token(payload.review_token, payload.rating)
            prepared = (prepared_selection.open_draw(payload.selection_ticket, get_settings().runner_token,
                user.id, payload.review_token, payload.rating,
                _draw_context(subject, run_id, payload.lectures, user, db)) if payload.selection_ticket and not replay else None)
            resume = None
            if replay and payload.lectures:
                resume = next(({"subject": entry["key"][0], "runId": entry["key"][1]}
                               for entry in _batch_entries(BatchIn(lectures=payload.lectures), user, db)
                               if (entry["state"].get("served") or {}).get("token") == token), None)
            result["next"] = (_next_batch_question(BatchIn(lectures=payload.lectures, resumeLecture=resume), user, db, served_token=token, prepared=prepared)
                              if payload.lectures else _next_bank_question(subject, run_id, user, db, choice_protocol=True,
                                                                         served_token=token, prepared=prepared))
        except Exception:
            db.rollback()
            result["advanceFailed"] = True
    return result


@router.post("/lectures/{subject}/{run_id}/bank/undo")
def undo_bank_answer(subject: str, run_id: str, payload: TokenIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    state_row = _load_state(db, user, row)
    try:
        state = reschedule_bank(bank, undo_review(state_row.state, payload.review_token))
    except ValueError as cause:
        raise HTTPException(409, str(cause)) from cause
    served = state["served"]
    served["token"] = uuid.uuid4().hex  # Discard any tokens held by other tabs before undo.
    question = _served_question(db, row, user.id, bank, served)
    now = engine.now_ms()
    _save(state_row, state)
    db.commit()
    exam = exam_date_for(db, lecture)
    choices_shown = not served.get("choice_protocol") or choice_mode(question) != "recall_first" or served.get("choices_shown", False) or served.get("revealed", False)
    return {"question": _public(question, bank=bank, show_choices=choices_shown), "reviewToken": served["token"], "undoToken": undo_token(state),
            "days": engine.days_until(exam, now), "examDate": exam,
            "lectureGoal": lecture_goal(bank, state, lecture.title, now),
            "session": engine.session_summary(bank, state, now=now),
            "answer": _answer(db, row, question) if served.get("revealed") else None,
            "choicesShown": choices_shown,
            "preloadSlides": _slides(db, row, question["question_id"], question)}


class BatchIn(BaseModel):
    lectures: list[BatchLectureIn] = Field(min_length=1, max_length=100)
    resume_lecture: BatchLectureIn | None = Field(None, alias="resumeLecture")


class BatchUndoIn(BatchIn):
    review_token: str = Field(alias="reviewToken")


class NextPreviewIn(TokenIn):
    lectures: list[BatchLectureIn] | None = Field(default=None, min_length=1, max_length=100)


@router.post("/lectures/{subject}/{run_id}/bank/prepare-next")
def prepare_next_bank_question(subject: str, run_id: str, payload: NextPreviewIn,
                               user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """Predict each rating on copied states; never serve, mark seen, or record a review."""
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _study_bank(db, row, user)
    state_row = db.get(BankState, (user.id, subject, run_id))
    if state_row is None or state_row.build_id != row.build_id:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    served = state_row.state.get("served") or {}
    if served.get("token") != payload.review_token or not served.get("revealed"):
        raise HTTPException(409, "정답 공개 후 다음 문항을 준비할 수 있습니다.")
    previews = {}
    draw_entries = _draw_entries(subject, run_id, payload.lectures, user, db)
    for rating in ("Again", "Hard", "Good", "Easy"):
        state = _reviewed_state(bank, copy.deepcopy(state_row.state), rating, engine.now_ms())
        token = _advance_token(payload.review_token, rating)
        fingerprint = _draw_context(subject, run_id, payload.lectures, user, db, {(subject, run_id): state}, draw_entries)
        got = (_next_batch_question(BatchIn(lectures=payload.lectures), user, db,
                                    served_token=token, preview_states={(subject, run_id): state})
               if payload.lectures else _next_bank_question(subject, run_id, user, db, choice_protocol=True,
                                                            preview_state=state, served_token=token))
        _seal_draw(got, payload.review_token, rating, fingerprint, subject, run_id, user)
        # These are display previews, not usable review tokens or exposed answers.
        got.pop("reviewToken", None)
        got.pop("undoToken", None)
        got["answer"] = None
        previews[rating] = got
    return previews


class BufferPreviewIn(NextPreviewIn):
    ratings: list[Literal["Again", "Hard", "Good", "Easy"]] = Field(default_factory=list, max_length=12)
    lookahead: Literal["near", "full"] = "full"


@router.post("/lectures/{subject}/{run_id}/bank/prepare-buffer")
def prepare_bank_buffer(subject: str, run_id: str, payload: BufferPreviewIn,
                        user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """Prepare two steps for every rating, six for Easy and three for Good.

    Static lecture data is loaded once per request. All projected study states
    remain private copies; signed draws are confirmed only by a real rating.
    """
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    state_row = db.get(BankState, (user.id, subject, run_id))
    if state_row is None or state_row.build_id != row.build_id or (
        state_row.state.get("served") or {}).get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    draw_entries = _draw_entries(subject, run_id, payload.lectures, user, db)
    by_key = {entry["key"]: entry for entry in draw_entries}
    states = {key: copy.deepcopy(entry["state"]) for key, entry in by_key.items()}
    if (subject, run_id) not in states:
        raise HTTPException(409, "현재 강의가 선택한 학습 목록에 없습니다.")
    frames = {}
    edits = list(db.scalars(select(BankPersonalEdit).where(BankPersonalEdit.user_id == user.id,
        tuple_(BankPersonalEdit.subject, BankPersonalEdit.run_id).in_(list(by_key)))))
    assets = list(db.scalars(select(Asset).where(Asset.kind == SLIDE_KINDS["bank"],
        tuple_(Asset.subject, Asset.run_id).in_(list(by_key)))))
    resources = {}
    for key, entry in by_key.items():
        entry["personal_edits"] = {edit.question_id: edit for edit in edits if (edit.subject, edit.run_id) == key}
        entry["assets"] = [asset for asset in assets if (asset.subject, asset.run_id) == key]
        entry["assets_by_id"] = {asset.id: asset for asset in entry["assets"]}
        entry["resources"] = resources

    def frame(got, snapshots, ratings):
        if not got.get("question"):
            return None
        ref = got.get("lecture") or {"subject": subject, "runId": run_id}
        key = (ref["subject"], ref["runId"])
        entry = by_key[key]
        bank_row, bank = entry["row"], entry["bank"]
        if got["reviewToken"] in frames:
            return key, bank, frames[got["reviewToken"]]
        served = snapshots[key]["served"]
        question = _served_question(db, bank_row, user.id, bank, served, prepared_entry={**entry, "state": snapshots[key]})
        result = {"next": got, "answer": _answer(db, bank_row, question, prepared_entry=entry),
                  "options": _public(question, bank=bank), "previews": {},
                  "origin": {"subject": subject, "runId": run_id,
                             "reviewToken": payload.review_token, "ratings": ratings}}
        frames[got["reviewToken"]] = result
        return key, bank, result

    if payload.lectures:
        current = _next_batch_question(BatchIn(lectures=payload.lectures,
            resumeLecture={"subject": subject, "runId": run_id}), user, db,
            preview_states=states, preview_states_out=states, preview_entries=draw_entries)
    else:
        current = _next_bank_question(subject, run_id, user, db, choice_protocol=True,
                                      preview_state=states[(subject, run_id)], preview_states_out=states,
                                      preview_entry=by_key[(subject, run_id)])
    def advance(current, snapshots, path, rating):
        parent = frame(current, snapshots, path)
        if parent is None:
            return None
        key, bank, prepared = parent
        branch = copy.deepcopy(snapshots)
        branch[key]["served"].update(revealed=True, choices_shown=True)
        branch[key] = _reviewed_state(bank, branch[key], rating, engine.now_ms())
        token = _advance_token(current["reviewToken"], rating)
        fingerprint = _draw_context(subject, run_id, payload.lectures, user, db, branch, draw_entries)
        got = (_next_batch_question(BatchIn(lectures=payload.lectures), user, db,
                served_token=token, preview_states=branch, preview_states_out=branch, preview_entries=draw_entries)
               if payload.lectures else _next_bank_question(*key, user, db, choice_protocol=True,
                preview_state=branch[key], served_token=token, preview_states_out=branch,
                preview_entry={**by_key[key], "state": branch[key]}))
        _seal_draw(got, current["reviewToken"], rating, fingerprint, subject, run_id, user)
        prepared["previews"][rating] = got
        frame(got, branch, [*path, rating])
        return got, branch

    def expand(current, snapshots, path, all_steps, easy_steps, good_steps):
        if frame(current, snapshots, path) is None:
            return
        for rating in ("Easy", "Good", "Hard", "Again"):
            got, branch = advance(current, snapshots, path, rating)
            remaining_all = max(0, all_steps - 1)
            remaining_easy = max(0, easy_steps - 1) if rating == "Easy" else 0
            remaining_good = max(0, good_steps - 1) if rating == "Good" else 0
            if remaining_all or remaining_easy or remaining_good:
                expand(got, branch, [*path, rating], remaining_all, remaining_easy, remaining_good)

    path = []
    for rating in payload.ratings:
        projected = advance(current, states, path, rating)
        if projected is None:
            break
        current, states = projected
        path = [*path, rating]
    if payload.lookahead == "near":
        expand(current, states, path, 1, 1, 1)
    else:
        expand(current, states, path, 2, 6, 3)
    return {"frames": frames, "lookahead": payload.lookahead}


def _batch_entries(payload: BatchIn, user: CurrentUser, db: Session) -> list[dict]:
    now, entries = engine.now_ms(), []
    keys = list(dict.fromkeys((ref.subject, ref.run_id) for ref in payload.lectures))
    rows = db.execute(select(Lecture, QuizBank, BankState).outerjoin(QuizBank, and_(
        QuizBank.subject == Lecture.subject, QuizBank.run_id == Lecture.run_id)).outerjoin(BankState, and_(
        BankState.subject == Lecture.subject, BankState.run_id == Lecture.run_id, BankState.user_id == user.id))
        .where(tuple_(Lecture.subject, Lecture.run_id).in_(keys))).all()
    by_key = {(lecture.subject, lecture.run_id): (lecture, row, state_row) for lecture, row, state_row in rows}
    for key in keys:
        if key not in by_key:
            raise HTTPException(404, "선택한 강의를 찾을 수 없습니다.")
        lecture, row, state_row = by_key[key]
        if row is None or not user.is_admin and not row.open_to_students:
            raise HTTPException(404, "선택한 강의에 공개된 문제은행이 없습니다.")
        bank = _study_bank(db, row, user)
        state = state_row.state if state_row and state_row.build_id == row.build_id else engine.empty_state()
        entries.append({"key": key, "lecture": lecture, "row": row, "bank": bank, "state": state,
                        "goal": lecture_goal(bank, state, lecture.title, now)})
    return entries


def _refresh_batch_entry(entry: dict, user: CurrentUser, db: Session) -> None:
    state_row = db.get(BankState, (user.id, *entry["key"]))
    entry["state"] = state_row.state if state_row else engine.empty_state()
    entry["goal"] = lecture_goal(entry["bank"], entry["state"], entry["lecture"].title, engine.now_ms())


def _batch_undo(entries: list[dict]) -> tuple[dict | None, str | None]:
    available = [(entry, undo_token(entry["state"])) for entry in entries]
    available = [(entry, token) for entry, token in available if token]
    if not available:
        return None, None
    return max(available, key=lambda pair: last_undo(pair[0]["state"])["timestamp"])


def _batch_reply(next_question: dict, entries: list[dict], chosen: dict | None) -> dict:
    previous, token = _batch_undo(entries)
    lecture = chosen["lecture"] if chosen else None
    return {**next_question, "undoToken": token,
            "lecture": {"subject": lecture.subject, "runId": lecture.run_id, "title": lecture.title} if lecture else None,
            "batchGoal": aggregate_goal(entries, day_start(engine.now_ms())),
            "undoLecture": {"subject": previous["key"][0], "runId": previous["key"][1]} if previous else None}


@router.post("/bank/batch/next")
def next_batch_question(payload: BatchIn, user: CurrentUser = Depends(require_approved_user),
                         db: Session = Depends(get_db)) -> dict:
    return _next_batch_question(payload, user, db)


def _next_batch_question(payload: BatchIn, user: CurrentUser, db: Session, *, served_token: str | None = None,
                         preview_states: dict | None = None, preview_states_out: dict | None = None,
                         prepared: tuple | None = None, preview_entries: list[dict] | None = None) -> dict:
    if preview_entries is not None:
        assert preview_states is not None
        entries = [dict(entry) for entry in preview_entries]
    else:
        entries = _batch_entries(payload, user, db)
    if preview_states is not None:
        for entry in entries:
            entry["state"] = copy.deepcopy(preview_states.get(entry["key"], entry["state"]))
            entry["goal"] = lecture_goal(entry["bank"], entry["state"], entry["lecture"].title, engine.now_ms())
    goal = aggregate_goal(entries, day_start(engine.now_ms()))
    resume = (payload.resume_lecture.subject, payload.resume_lecture.run_id) if payload.resume_lecture else None
    # Lowering the target may move this exposure out of today's queue. Keep the
    # current ungraded question on refresh, just as ordinary study does.
    chosen = next((entry for entry in entries if entry["key"] == resume
                   and (entry["state"].get("served") or {}).get("question_id") in {
                       q["question_id"] for q in entry["bank"]["questions"]
                       if q["question_id"] not in entry["state"].get("suspended_question_ids", [])}), None)
    if goal["met"] and chosen is None:
        if preview_states is not None:
            return _batch_reply({"question": None, "summary": None, "reason": "lecture_goal_met"}, entries, None)
        for entry in entries:
            state_row = db.get(BankState, (user.id, *entry["key"]))
            if state_row and state_row.build_id == entry["row"].build_id:
                _save(state_row, engine.end_session(entry["bank"], state_row.state, "lecture_goal_met", engine.now_ms()))
        db.commit()
        for entry in entries:
            _refresh_batch_entry(entry, user, db)
        return _batch_reply({"question": None, "summary": None, "reason": "lecture_goal_met"}, entries, None)
    resuming = chosen is not None
    selection = None
    if chosen is None:
        for entry in entries:
            if "exam" not in entry:
                entry["exam"] = exam_date_for(db, entry["lecture"])
        chosen, selection = select_batch_question(entries, engine.now_ms(), seed=served_token, prepared=prepared)
    if chosen is None:
        raise HTTPException(409, "남은 문항을 선택할 수 없습니다. 강의 목록을 다시 확인하세요.")
    state_row = _load_state(db, user, chosen["row"]) if preview_states is None else None
    state = engine.start_session(chosen["bank"], state_row.state if state_row else chosen["state"], None, engine.now_ms())
    state["session"].update(size=None, continue_after_goal=False)
    pending = {u["key"] for u in daily_units(chosen["bank"], state, engine.now_ms()) if u["status"] == "pending"}
    if not resuming and state.get("served") and state["served"]["question_id"] not in pending:
        state["served"] = None
    if state_row is not None:
        _save(state_row, state)
        db.commit()
    got = _next_bank_question(*chosen["key"], user=user, db=db, choice_protocol=True, selection=selection,
                             preview_state=state if preview_states is not None else None, served_token=served_token,
                             preview_states_out=preview_states_out, preview_entry=chosen if preview_states is not None else None)
    if preview_states is not None:
        return _batch_reply(got, entries, chosen)
    _refresh_batch_entry(chosen, user, db)
    return _batch_reply(got, entries, chosen)


@router.post("/bank/batch/undo")
def undo_batch_question(payload: BatchUndoIn, user: CurrentUser = Depends(require_approved_user),
                         db: Session = Depends(get_db)) -> dict:
    entries = _batch_entries(payload, user, db)
    chosen, token = _batch_undo(entries)
    if chosen is None or token != payload.review_token:
        raise HTTPException(409, "모아 풀기의 마지막 평가가 아닙니다.")
    got = undo_bank_answer(*chosen["key"], TokenIn(reviewToken=token), user=user, db=db)
    _refresh_batch_entry(chosen, user, db)
    return _batch_reply(got, entries, chosen)


@router.post("/bank/batch/session/end")
def end_batch_session(payload: BatchIn, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db)) -> dict:
    entries = _batch_entries(payload, user, db)
    for entry in entries:
        state_row = db.get(BankState, (user.id, *entry["key"]))
        if state_row and state_row.build_id == entry["row"].build_id:
            _save(state_row, engine.end_session(entry["bank"], state_row.state, "user_finished", engine.now_ms()))
    db.commit()
    return {"batchGoal": aggregate_goal(entries, day_start(engine.now_ms()))}
