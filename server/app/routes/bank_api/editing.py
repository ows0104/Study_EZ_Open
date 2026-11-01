"""Shared question review and admin edits; retention rules remain in bank_retention."""
from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_edits, bank_retention
from app.auth import CurrentUser, require_admin
from app.bank_validation.pages import cited_pages
from app.bank_validation.priorities import priority_fields
from app.bank_validation.publication import usable as bank_usable
from app.bank_validation.schema import QUESTION, schema_errors, without_retired
from app.database import get_db
from app.models import BANK_BUILDING, BANK_READY, BANK_RESPONDED, BankState, Lecture, QuizBank
from app.routes.common import lecture_or_404

from .common import bank_sources, summary


admin_router = APIRouter()


@admin_router.get("/bank-review")
def bank_review(subject: str | None = None, run_id: str | None = Query(None, alias="runId"),
                all_questions: bool = Query(False, alias="all"),
                question_id: str | None = Query(None, alias="questionId"),
                user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if question_id is not None and (subject is None or run_id is None):
        raise HTTPException(422, "문항을 고르려면 과목과 강의를 지정하세요.")
    query = select(QuizBank).join(Lecture)
    if subject is not None:
        query = query.where(QuizBank.subject == subject)
    if run_id is not None:
        query = query.where(QuizBank.run_id == run_id)
    groups = []
    for row in db.scalars(query.order_by(Lecture.date.desc(), Lecture.slot)).all():
        if not row.bank:
            continue
        lecture = db.get(Lecture, (row.subject, row.run_id))
        validation = row.validation or {}
        dropped = {d["question_id"]: d["errors"] for d in validation.get("dropped", [])}
        reviews = {r["question_id"]: r for r in (row.review or {}).get("reviews", [])}
        edits = validation.get("edits", {})
        questions = bank_edits.candidates(row.bank, validation)
        cards = []
        for qid, q in questions.items():
            if question_id is not None and qid != question_id:
                continue
            review = reviews.get(qid)
            if question_id is None and not all_questions and qid not in dropped and qid not in edits and (
                not review or review["verdict"] == "ok"
            ):
                continue
            cards.append({"question": priority_fields(q, question=True), "errors": dropped.get(qid, []),
                          "medicalReview": review, "edit": edits.get(qid)})
        if cards:
            groups.append({"subject": row.subject, "runId": row.run_id, "title": lecture.title,
                           "date": lecture.date.isoformat(), "buildId": row.build_id, "cards": cards,
                           "sources": bank_sources(db, lecture),
                           "conflicts": [{"id": c["conflict_id"], "description": c["description"]}
                                         for c in row.bank.get("source_conflicts", [])],
                           "concepts": [{"id": c["concept_id"], "title": c["title"]}
                                        for c in row.bank.get("concepts", [])],
                           "questions": [{"id": qid, "question": q.get("question", ""),
                                          "available": any(x["question_id"] == qid for x in row.bank["questions"])}
                                         for qid, q in questions.items()]})
    cards = [c for g in groups for c in g["cards"]]
    done = sum(bool(c["edit"]) for c in cards)
    return {"banks": groups, "open": len(cards) - done, "done": done}


class BankCardIn(BaseModel):
    build_id: str = Field(alias="buildId", max_length=64)
    expected_question: dict = Field(alias="expectedQuestion")
    action: Literal["edit", "accept", "delete", "reset", "split"]
    question: dict | None = None
    questions: list[dict] | None = None
    reason: str = Field(default="", max_length=4000)


@admin_router.put("/lectures/{subject}/{run_id}/bank/cards/{question_id}")
def edit_bank_card(subject: str, run_id: str, question_id: str, payload: BankCardIn,
                   user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    import copy

    lecture = lecture_or_404(db, subject, run_id)
    row = db.scalars(select(QuizBank).where(QuizBank.subject == subject, QuizBank.run_id == run_id)
                     .with_for_update()).first()
    if row is None or not row.bank:
        raise HTTPException(404, "문제은행이 없습니다.")
    if row.status in (BANK_RESPONDED, BANK_BUILDING) or (row.validation or {}).get("maintenance"):
        raise HTTPException(409, "정리가 끝난 뒤 수정하세요.")
    validation = row.validation or {}
    current = bank_edits.candidates(row.bank, validation).get(question_id)
    if current is None:
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    if row.build_id != payload.build_id or priority_fields(current, question=True) != payload.expected_question:
        raise HTTPException(409, "문항이 바뀌었습니다. 새로 불러온 뒤 수정하세요.")
    edits = copy.deepcopy(validation.get("edits", {}))
    original = edits.get(question_id, {}).get("original") or without_retired({"questions": [current]})["questions"][0]
    source_ids = [s["id"] for s in bank_sources(db, lecture)]
    candidate_bank = copy.deepcopy(row.bank)
    candidate_validation = copy.deepcopy(validation)
    if payload.action == "reset":
        previous_edit = edits.get(question_id, {})
        child_ids = {q['question_id'] for q in previous_edit.get('children', [])}
        for child_id in child_ids:
            edits.pop(child_id, None)
        for plan in candidate_bank.get('retrieval_plan', []):
            if plan['concept_id'] == original['concept_id'] and 'originalDirections' in previous_edit:
                plan['directions'] = previous_edit['originalDirections']
        edits.pop(question_id, None)
        # Restore the original before applying all remaining decisions.
        candidate_bank["questions"] = [q for q in candidate_bank["questions"] if q["question_id"] not in child_ids | {question_id}]
        candidate_validation["dropped"] = [d for d in validation.get("dropped", []) if d["question_id"] not in child_ids | {question_id}]
        candidate_validation["edits"] = edits
        candidate_bank["questions"].append(original)
    elif payload.action == 'split':
        if not payload.reason.strip() or not payload.questions or len(payload.questions) < 2:
            raise HTTPException(422, '분할한 문항과 근거가 필요합니다.')
        if edits.get(question_id, {}).get('children') or any(
            question_id in {q['question_id'] for q in e.get('children', [])} for e in edits.values()):
            raise HTTPException(422, '이미 분할된 문항은 먼저 기존 분할을 검토하세요.')
        replacements = without_retired({'questions': payload.questions})['questions']
        errors = [error for q in replacements for error in schema_errors(q, QUESTION)]
        if errors:
            raise HTTPException(422, '\n'.join(errors))
        ids = [q['question_id'] for q in replacements]
        if ids.count(question_id) != 1 or len(ids) != len(set(ids)):
            raise HTTPException(422, '기존 ID 한 개와 중복 없는 새 문항 ID가 필요합니다.')
        known_ids = set(bank_edits.candidates(row.bank, validation))
        for q in replacements:
            qid = q['question_id']
            if q['concept_id'] != current['concept_id']:
                raise HTTPException(422, '분할은 기존 개념 안에서 수행하세요.')
            if qid != question_id and (qid in known_ids or not qid.startswith(question_id + '-')):
                raise HTTPException(422, '기존 문항과 충돌하지 않는 하위 ID가 필요합니다.')
        anchor = next(q for q in replacements if q['question_id'] == question_id)
        children = [q for q in replacements if q['question_id'] != question_id]
        directions = next(p['directions'] for p in row.bank['retrieval_plan']
                          if p['concept_id'] == current['concept_id'])
        edits[question_id] = {'action': 'edit', 'original': original, 'question': anchor,
            'children': children, 'originalDirections': copy.deepcopy(directions), 'splitReason': payload.reason,
            'by': user.email or user.id, 'at': datetime.now(UTC).isoformat()}
        for qid in ids:
            errors = bank_edits.question_errors(candidate_bank, candidate_validation, edits, qid, source_ids)
            if errors:
                raise HTTPException(422, '\n'.join(errors))
    else:
        question = without_retired({"questions": [current]})["questions"][0]
        if payload.action == "edit":
            if payload.question is None:
                raise HTTPException(422, "수정한 문항이 필요합니다.")
            question = without_retired({"questions": [payload.question]})["questions"][0]
            errors = schema_errors(question, QUESTION)
            if errors:
                raise HTTPException(422, "\n".join(errors))
            if question["question_id"] != question_id:
                raise HTTPException(422, "문항 ID는 바꿀 수 없습니다.")
            if question == without_retired({"questions": [current]})["questions"][0]:
                raise HTTPException(422, "수정한 내용이 없습니다.")
        split_fields = {k: copy.deepcopy(edits[question_id][k]) for k in ('children', 'originalDirections', 'splitReason')
                        if k in edits.get(question_id, {})}
        edits[question_id] = {**split_fields, "action": payload.action, "original": original, "question": question,
                              "by": user.email or user.id, "at": datetime.now(UTC).isoformat()}
        if payload.action in ("edit", "accept"):
            errors = bank_edits.question_errors(candidate_bank, candidate_validation, edits, question_id, source_ids)
            if errors:
                raise HTTPException(422, "\n".join(errors))
    clean, checked = bank_edits.with_edits(candidate_bank, candidate_validation, edits, source_ids)
    if not bank_usable(clean, checked):
        raise HTTPException(422, "\n".join(checked["errors"]))
    before_questions = {q["question_id"]: q for q in without_retired(row.bank)["questions"]}
    after_questions = {q["question_id"]: q for q in clean["questions"]}
    affected = {qid for qid in before_questions.keys() | after_questions.keys()
                if before_questions.get(qid) != after_questions.get(qid)}
    bank_retention.replace_bank(db, row, clean, row.build_id)
    row.validation = checked
    row.pages = cited_pages(clean, "S1")
    row.status = BANK_READY
    # Preserve unrelated mastery; invalidate in-flight questions and undo snapshots.
    for state in db.scalars(select(BankState).where(BankState.subject == subject, BankState.run_id == run_id,
                                                   BankState.build_id == row.build_id)).all():
        value = copy.deepcopy(state.state)
        if (value.get("served") or {}).get("question_id") in affected:
            value["served"] = None
        if affected:
            for entry in value.get("history", []):
                entry.pop("undo", None)
        state.state = value
    db.commit()
    return {"summary": summary(db, lecture, row, is_admin=True, user_id=user.id), "action": payload.action}
