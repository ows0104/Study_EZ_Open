"""Private question additions, edits, and source slides."""
from __future__ import annotations

import copy
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_personal
from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import Asset, BankFeedback, BankPersonalEdit, BankState
from app.personal_question_input import PersonalQuestionSettings
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage
from app.study_engine.personal_priority import question_priority

from .common import _bank_or_404, _usable
from .feedback import FEEDBACK_CATEGORIES
from .presentation import _answer, _public, _slides
from .state import _save, _study_bank


router = APIRouter()


def _personal_source(db: Session, subject: str, run_id: str, question_id: str, user: CurrentUser):
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _study_bank(db, row, user)
    question = next((q for q in bank["questions"] if q["question_id"] == question_id), None)
    if question is None:
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    return row, question


@router.get("/lectures/{subject}/{run_id}/bank/questions/{question_id}/personal")
def read_personal_question(subject: str, run_id: str, question_id: str,
                          user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row, original = _personal_source(db, subject, run_id, question_id, user)
    current = bank_personal.apply(db, row, user.id, original)
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id))
    valid = edit is not None and bank_personal.same_source(edit.original, original)
    return {"original": {"question": original["question"], "answer": original["answer"], "explanation": original.get("explanation", "")},
            "draft": {"question": current["question"], "answer": current["answer"], "explanation": current.get("explanation", "")},
            "edited": valid, "comment": edit.comment if valid else "", "revision": bank_personal.revision(original),
            "personalAdded": bool(original.get("personalAdded"))}


class PersonalEditIn(BaseModel):
    action: Literal["save", "reset"] = "save"
    revision: str = Field(min_length=64, max_length=64)
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    report: bool = False
    category: Literal[FEEDBACK_CATEGORIES] = "content"  # type: ignore[valid-type]
    comment: str = Field(default="", max_length=2000)
    explanation: str | None = Field(default=None, max_length=12000)


class PersonalQuestionIn(PersonalQuestionSettings):
    client_id: uuid.UUID = Field(alias="clientId")
    source_question_id: str | None = Field(default=None, alias="sourceQuestionId", min_length=1, max_length=128)
    slide_asset_ids: list[str] | None = Field(default=None, alias="slideAssetIds", max_length=100)
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    explanation: str = Field(default="", max_length=12000)
    tier: Literal["Essential", "Core", "Important", "Optional"] = "Core"


@router.post("/lectures/{subject}/{run_id}/bank/personal-questions", status_code=201)
def add_personal_question(subject: str, run_id: str, payload: PersonalQuestionIn,
                          user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    _usable(row)
    question, answer = payload.question.strip(), payload.answer.strip()
    if not question or not answer:
        raise HTTPException(422, "발문과 정답을 비워 둘 수 없습니다.")
    qid = f"PQ_{payload.client_id.hex}"
    if payload.format == "cloze":
        blanks = re.findall(r"\{\{c\d+\}\}", question)
        if not blanks or len(blanks) != len(payload.answer_units):
            raise HTTPException(422, "발문의 빈칸 수와 빈칸별 정답 수를 맞춰 주세요.")
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, qid))
    if edit is None:
        settings = payload.model_dump(include=set(PersonalQuestionSettings.model_fields))
        original = bank_personal.added_question(qid, question, answer, payload.tier, payload.explanation.strip(), settings=settings)
        inherited = []
        if payload.source_question_id:
            bank = _study_bank(db, row, user)
            source = next((q for q in bank["questions"] if q["question_id"] == payload.source_question_id), None)
            if source is None:
                raise HTTPException(404, "참고할 문항을 찾을 수 없습니다.")
            original["source_refs"] = copy.deepcopy(source.get("source_refs", []))
            inherited = _slides(db, row, source["question_id"], source, references_only=True)
        original["personalSlideReferences"] = inherited
        if payload.slide_asset_ids is not None:
            from app.personal_question_slides import choices
            available = choices(db, row, inherited)
            ids = list(dict.fromkeys(payload.slide_asset_ids))
            if any(asset_id not in available for asset_id in ids):
                raise HTTPException(422, "선택한 슬라이드를 사용할 수 없습니다. 슬라이드 목록을 다시 불러오세요.")
            original["personalSlideReferences"] = [available[asset_id] for asset_id in ids]
            original["source_refs"] = [{"source_id": "S1", "locator": f"p{ref['page']}"}
                                       for ref in original["personalSlideReferences"] if ref.get("sourceId") == "self"]
        db.add(BankPersonalEdit(user_id=user.id, subject=subject, run_id=run_id, question_id=qid,
                               original=original, question=question, answer=answer, comment=""))
        db.commit()
    return {"questionId": qid}


@router.get("/lectures/{subject}/{run_id}/bank/personal-question-slides")
def personal_question_slides(subject: str, run_id: str,
                             source_question_id: str | None = Query(None, alias="sourceQuestionId", max_length=128),
                             user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    from app.personal_question_slides import choices
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    _usable(row)
    inherited = []
    if source_question_id:
        bank = _study_bank(db, row, user)
        source = next((q for q in bank["questions"] if q["question_id"] == source_question_id), None)
        if source is None:
            raise HTTPException(404, "참고할 문항을 찾을 수 없습니다.")
        inherited = _slides(db, row, source["question_id"], source, references_only=True)
    available = choices(db, row, inherited)
    assets = {asset.id: asset for asset in db.scalars(select(Asset).where(Asset.id.in_(available)))}
    slides = []
    for ref in available.values():
        asset = assets.get(ref["assetId"])
        if asset is None:
            continue
        slides.append({**ref, "url": ObjectStorage().presign_download(asset.object_key)})
    return {"slides": slides, "selectedAssetIds": [ref["assetId"] for ref in inherited]}


@router.delete("/lectures/{subject}/{run_id}/bank/personal-questions/{question_id}")
def delete_personal_question(subject: str, run_id: str, question_id: str,
                             user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    _usable(row)
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id))
    if not edit or not edit.original.get("personalAdded"):
        raise HTTPException(404, "내가 추가한 문제를 찾을 수 없습니다.")
    state_row = db.get(BankState, (user.id, subject, run_id))
    if state_row and state_row.build_id == row.build_id:
        state = copy.deepcopy(state_row.state)
        if (state.get("served") or {}).get("question_id") == question_id:
            state["served"] = None
        for event in state.get("history", []):
            if event["question_id"] == question_id:
                event.pop("undo", None)
        state["suspension_undo"] = [entry for entry in state.get("suspension_undo", [])
                                    if entry["question_id"] != question_id]
        state["suspended_question_ids"] = [qid for qid in state.get("suspended_question_ids", []) if qid != question_id]
        state.get("question_tiers", {}).pop(question_id, None)
        _save(state_row, state)
    db.delete(edit)
    db.commit()
    return {"questionId": question_id, "deleted": True}


@router.put("/lectures/{subject}/{run_id}/bank/questions/{question_id}/personal")
def save_personal_question(subject: str, run_id: str, question_id: str, payload: PersonalEditIn,
                          user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row, original = _personal_source(db, subject, run_id, question_id, user)
    if payload.revision != bank_personal.revision(original):
        raise HTTPException(409, "공용 문항이 바뀌었습니다. 수정창을 다시 열어 주세요.")
    question, answer = payload.question.strip(), payload.answer.strip()
    if not question or not answer:
        raise HTTPException(422, "발문과 정답을 비워 둘 수 없습니다.")
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id))
    changed = question != original["question"] or answer != original["answer"]
    if not original.get("personalAdded") and (payload.action == "reset" or (not changed and not payload.comment.strip())):
        if edit:
            db.delete(edit)
    else:
        if edit is None:
            edit = BankPersonalEdit(user_id=user.id, subject=subject, run_id=run_id, question_id=question_id)
            db.add(edit)
        edit.original, edit.question, edit.answer = original, question, answer
        edit.comment = payload.comment.strip()
        if original.get("personalAdded"):
            edit.original = {**original, "question": question, "answer": answer,
                             "explanation": payload.explanation.strip() if payload.explanation is not None else original.get("explanation", "")}
            if answer != original["answer"]:
                edit.original = {**edit.original, "personalAnswerOverride": True,
                                 "answer_units": [], "correct_option_ids": [], "answer_pairs": [], "correct_order": []}
    if payload.action == "save" and not original.get("personalAdded"):
        comment = payload.comment.strip()
        correction = None
        if changed:
            comment += f"\n\n[개인 수정 제안]\n발문: {question}\n정답: {answer}"
            correction = {"original": original, "proposed": {"question": question, "answer": answer},
                          "changedFields": [key for key, value in (("question", question), ("answer", answer))
                                            if value != original[key]]}
        db.add(BankFeedback(user_id=user.id, subject=subject, run_id=run_id, build_id=row.build_id,
                            question_id=question_id, category=payload.category, comment=comment.strip(),
                            highlighted=payload.report, correction=correction))
    db.commit()
    current = bank_personal.apply(db, row, user.id, edit.original if original.get("personalAdded") else original)
    state = db.get(BankState, (user.id, row.subject, row.run_id))
    if state and state.build_id == row.build_id:
        current = question_priority(current, state.state)
    return {"question": _public(current, bank=row.bank), "answer": _answer(db, row, current),
            "reported": payload.action == "save" and not original.get("personalAdded"),
            "highlighted": payload.report and payload.action == "save" and not original.get("personalAdded")}
