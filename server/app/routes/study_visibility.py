"""Account-scoped visibility for the study overview, including pending events."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import Lecture, TimetableEvent
from app.models.study_visibility import StudyHiddenLecture

router = APIRouter()


class VisibilityIn(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=1000)
    hidden: bool


@router.get("/me/study-hidden")
def read_hidden(
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"keys": list(db.scalars(select(StudyHiddenLecture.lecture_key).where(
        StudyHiddenLecture.user_id == user.id)).all())}


@router.patch("/me/study-hidden")
def write_hidden(
    payload: VisibilityIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict:
    keys = set(payload.keys)
    if payload.hidden:
        valid = {f"{subject}/{run_id}" for subject, run_id in db.execute(select(Lecture.subject, Lecture.run_id))}
        valid.update(f"event:{event_id}" for event_id in db.scalars(select(TimetableEvent.id)))
        if not keys <= valid:
            raise HTTPException(404, "강의를 찾을 수 없습니다.")
        existing = set(db.scalars(select(StudyHiddenLecture.lecture_key).where(
            StudyHiddenLecture.user_id == user.id, StudyHiddenLecture.lecture_key.in_(keys))))
        db.add_all(StudyHiddenLecture(user_id=user.id, lecture_key=key) for key in keys - existing)
    else:
        db.execute(delete(StudyHiddenLecture).where(
            StudyHiddenLecture.user_id == user.id, StudyHiddenLecture.lecture_key.in_(keys)))
    db.commit()
    return read_hidden(user, db)
