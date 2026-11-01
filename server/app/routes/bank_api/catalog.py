"""Student bank summary, catalogue, excluded questions, and Anki download."""
from __future__ import annotations

import copy
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_excluded, bank_personal, study_engine as engine
from app.auth import CurrentUser, require_approved_user
from app.bank_catalog import ordered_questions
from app.bank_validation.publication import usable as bank_usable
from app.database import get_db
from app.lecture_mastery import for_bank
from app.models import Asset, BankPersonalEdit, BankState, SLIDE_KINDS
from app.routes.common import lecture_or_404, record_grabs, storage_or_503
from app.storage import ObjectStorage, StorageNotConfigured
from app.study_engine.daily_queue import lecture_goal
from app.study_engine.personal_priority import question_priority
from app.study_engine.review_undo import undo_token

from .common import _bank_or_404, _usable, exam_date_for, summary
from .presentation import _answer, _public
from .state import _save, _study_bank


router = APIRouter()


@router.get("/lectures/{subject}/{run_id}/bank/anki")
def download_bank_anki(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db)) -> dict[str, Any]:
    """Explicit offline export; use the same publication gate as web study."""
    from app.bank_anki import ensure_export

    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    _usable(row)
    export = ensure_export(db, lecture, row)
    url = storage_or_503().presign_download(export.key, filename=export.filename)
    record_grabs(db, user.id, [(lecture.subject, lecture.run_id, export.grab_kind)], purpose="download")
    return {"url": url, "filename": export.filename}


@router.get("/lectures/{subject}/{run_id}/bank")
def read_bank(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
              db: Session = Depends(get_db), target: int = Query(90, ge=50, le=100)) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    out = {"summary": summary(db, lecture, row, is_admin=user.is_admin, user_id=user.id), "examDate": exam_date_for(db, lecture),
           "sizes": engine.DEFAULT["session"]["sizes"], "defaultSize": engine.DEFAULT["session"]["defaultSize"],
           "session": None, "previousSessions": [], "conceptMap": [], "mastery": None, "undoToken": None}
    if bank_usable(row.bank, row.validation):
        bank = _study_bank(db, row, user)
        now = engine.now_ms()
        state = db.get(BankState, (user.id, row.subject, row.run_id))
        current = state.state if state and state.build_id == row.build_id else engine.empty_state()
        out["personalQuestions"] = [{"questionId": q["question_id"],
                                      "question": bank_personal.apply(db, row, user.id, q)["question"],
                                      "tier": question_priority(q, current)["tier"]}
                                     for q in bank["questions"] if q.get("personalAdded")]
        out["suspendedQuestions"] = [{"questionId": q["question_id"], "question": q["question"]}
                                     for q in bank["questions"]
                                     if q["question_id"] in current.get("suspended_question_ids", [])]
        if state and state.build_id == row.build_id:
            out["session"] = engine.session_summary(bank, state.state, now=now)
            out["previousSessions"] = state.state.get("sessions", [])[-5:]
            out["undoToken"] = undo_token(state.state)
        # 개념 지도는 첫 회차 전에도 그린다 — 숙련도가 다 0인 지도가 「무엇을 공부할지」의 답이다.
        out["conceptMap"] = engine.concept_map(bank, current, now=now)
        out["mastery"] = for_bank(row, state, is_admin=user.is_admin, now=now, bank=bank)
        out["lectureGoal"] = lecture_goal(bank, current, lecture.title, now)
    return out


@router.get("/lectures/{subject}/{run_id}/bank/catalog")
def read_bank_catalog(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                      db: Session = Depends(get_db)) -> dict[str, Any]:
    """All cards in PDF order. Browsing never creates or changes learning state."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    _usable(row)
    edits = list(db.scalars(select(BankPersonalEdit).where(
        BankPersonalEdit.user_id == user.id, BankPersonalEdit.subject == subject,
        BankPersonalEdit.run_id == run_id)))
    by_id = {edit.question_id: edit for edit in edits}
    bank = bank_personal.augment(db, row, user.id, edits=edits)
    state = db.get(BankState, (user.id, subject, run_id))
    current = state.state if state and state.build_id == row.build_id else {}
    suspended = set(current.get("suspended_question_ids", []))
    excluded = bank_excluded.records(row)
    decisions = current.get('excluded_question_decisions', {})
    active_ids = {q['question_id'] for q in bank['questions']}
    catalog_bank = {**bank, 'questions': [*bank['questions'],
        *(r['question'] for qid, r in excluded.items() if qid not in active_ids)]}
    questions = []
    for original, pages in ordered_questions(catalog_bank, row.pages or {}):
        q = question_priority(bank_personal.apply_edit(original, by_id.get(original["question_id"])), current)
        questions.append({"question": _public(q, bank=bank), "pages": pages,
                          "suspended": q["question_id"] in suspended,
                          "excludedStatus": decisions.get(q['question_id'], 'excluded') if q['question_id'] in excluded else None,
                          "excludedReason": excluded.get(q['question_id'], {}).get('reason', '')})
    # One asset query and one signed URL per slide, rather than per question.
    first_pages = {item["pages"][0] for item in questions if item["pages"]}
    slides = []
    assets = db.scalars(select(Asset).where(Asset.subject == subject, Asset.run_id == run_id,
        Asset.kind == SLIDE_KINDS["bank"], Asset.slide_no.in_(first_pages)).order_by(Asset.slide_no))
    try:
        storage = ObjectStorage()
        for asset in assets:
            slides.append({"page": asset.slide_no, "url": storage.presign_download(asset.object_key)})
    except StorageNotConfigured:
        pass
    return {"buildId": row.build_id, "title": lecture.title, "subject": subject, "runId": run_id,
            "questions": questions, "slides": slides}


@router.get("/lectures/{subject}/{run_id}/bank/catalog/{question_id}")
def read_catalog_answer(subject: str, run_id: str, question_id: str,
                        build_id: str = Query(..., alias="buildId"),
                        user: CurrentUser = Depends(require_approved_user),
                        db: Session = Depends(get_db)) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    if build_id != row.build_id:
        raise HTTPException(409, "문제은행이 갱신되었습니다. 목록을 새로고침해 주세요.")
    original = next((q for q in bank["questions"] if q["question_id"] == question_id), None)
    if original is None:
        original = bank_excluded.records(row).get(question_id, {}).get('question')
    if original is None:
        raise HTTPException(404, "이 문제를 찾을 수 없습니다. 목록을 새로고침해 주세요.")
    q = bank_personal.apply(db, row, user.id, original)
    state = db.get(BankState, (user.id, subject, run_id))
    current = state.state if state and state.build_id == row.build_id else {}
    q = question_priority(q, current)
    return {"question": _public(q, bank=bank), "answer": _answer(db, row, q)}


class ExcludedDecisionIn(BaseModel):
    build_id: str = Field(alias='buildId')
    decision: Literal['excluded', 'restored', 'deleted']


@router.put('/lectures/{subject}/{run_id}/bank/excluded/{question_id}')
def decide_excluded(subject: str, run_id: str, question_id: str, payload: ExcludedDecisionIn,
                    user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    _usable(row)
    if row.build_id != payload.build_id:
        raise HTTPException(409, '문제은행이 갱신되었습니다. 목록을 새로고침해 주세요.')
    if question_id not in bank_excluded.records(row):
        raise HTTPException(404, '보관된 제외 문항을 찾을 수 없습니다.')
    state = db.scalar(select(BankState).where(BankState.user_id == user.id,
        BankState.subject == subject, BankState.run_id == run_id).with_for_update())
    if state is None:
        state = BankState(user_id=user.id, subject=subject, run_id=run_id,
            build_id=row.build_id, state=engine.empty_state())
        db.add(state)
    elif state.build_id != row.build_id:
        raise HTTPException(409, '먼저 현재 문제은행의 학습 화면을 열어 주세요. 이전 학습 기록은 보존됩니다.')
    current = copy.deepcopy(state.state)
    previous = current.setdefault('excluded_question_decisions', {}).get(question_id, 'excluded')
    current['excluded_question_decisions'][question_id] = payload.decision
    if previous != payload.decision:
        current.setdefault('excluded_question_history', []).append({
            'question_id': question_id, 'from': previous, 'to': payload.decision, 'at': engine.now_ms()})
    if payload.decision != 'restored' and (current.get('served') or {}).get('question_id') == question_id:
        current['served'] = None
    # Preserve ratings, due dates, private edits and the archived original.
    _save(state, current)
    db.commit()
    return {'questionId': question_id, 'decision': payload.decision}
