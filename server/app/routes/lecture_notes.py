"""강의별 개인 기록: 강의록 회독(+/최근 것 지우기)과 짧은 메모. 본인 것만 읽고 쓴다."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models.lecture_notes import LectureMemo, NoteRead
from app.routes.common import LectureKey, lecture_or_404

router = APIRouter()

MAX_READS = 30
MAX_MEMO = 300


def note_read_counts(db: Session, user_id: str, keys: list[LectureKey]) -> dict[LectureKey, int]:
    """강의마다 이 사람의 강의록 회독 수. 없는 강의는 빠진다."""
    if not keys:
        return {}
    subjects = {subject for subject, _ in keys}
    run_ids = {run_id for _, run_id in keys}
    wanted = set(keys)
    rows = db.execute(
        select(NoteRead.subject, NoteRead.run_id, func.count())
        .where(NoteRead.user_id == user_id, NoteRead.subject.in_(subjects), NoteRead.run_id.in_(run_ids))
        .group_by(NoteRead.subject, NoteRead.run_id)
    ).all()
    return {(s, r): n for s, r, n in rows if (s, r) in wanted}


def _count(db: Session, user_id: str, subject: str, run_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(NoteRead)
        .where(NoteRead.user_id == user_id, NoteRead.subject == subject, NoteRead.run_id == run_id)
    ) or 0


def my_memo(db: Session, user_id: str, subject: str, run_id: str) -> str:
    memo = db.get(LectureMemo, (user_id, subject, run_id))
    return memo.body if memo else ""


@router.post("/lectures/{subject}/{run_id}/note-reads")
def add_note_read(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    lecture = lecture_or_404(db, subject, run_id)
    count = _count(db, user.id, lecture.subject, lecture.run_id)
    if count >= MAX_READS:
        raise HTTPException(status_code=409, detail=f"회독은 {MAX_READS}번까지 기록합니다.")
    db.add(NoteRead(id=uuid.uuid4().hex, user_id=user.id, subject=lecture.subject, run_id=lecture.run_id))
    db.commit()
    return {"noteReads": count + 1}


@router.delete("/lectures/{subject}/{run_id}/note-reads/last")
def remove_last_note_read(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """가장 최근 회독 한 줄을 지운다. 되돌리기는 웹이 다시 POST한다."""
    lecture = lecture_or_404(db, subject, run_id)
    last = db.scalars(
        select(NoteRead)
        .where(NoteRead.user_id == user.id, NoteRead.subject == lecture.subject, NoteRead.run_id == lecture.run_id)
        .order_by(NoteRead.created_at.desc(), NoteRead.id.desc())
        .limit(1)
    ).first()
    if last is not None:
        db.delete(last)
        db.commit()
    return {"noteReads": _count(db, user.id, lecture.subject, lecture.run_id)}


class MemoIn(BaseModel):
    memo: str = Field(default="", max_length=MAX_MEMO)


@router.put("/lectures/{subject}/{run_id}/my-memo")
def put_my_memo(
    subject: str,
    run_id: str,
    payload: MemoIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """비우면 줄을 지운다."""
    lecture = lecture_or_404(db, subject, run_id)
    body = payload.memo.rstrip()
    memo = db.get(LectureMemo, (user.id, lecture.subject, lecture.run_id))
    if not body:
        if memo is not None:
            db.delete(memo)
            db.commit()
        return {"memo": ""}
    if memo is None:
        memo = LectureMemo(user_id=user.id, subject=lecture.subject, run_id=lecture.run_id)
        db.add(memo)
    memo.body = body
    db.commit()
    return {"memo": memo.body}
