"""캘린더가 읽는 것.

시간표만으로 그려진다. 파이프라인 산출물이 하나도 없어도 화면은 완성된 모습이고,
자료가 올라오면 칸에 점이 붙는다.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import Lecture, TimetableEvent
from app.routes.common import material_marks

router = APIRouter()


@router.get("/timetable")
def read_timetable(
    start: Date | None = Query(None, description="이 날짜부터 (없으면 전체)"),
    end: Date | None = Query(None, description="이 날짜까지"),
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(TimetableEvent)
    if start is not None:
        query = query.where(TimetableEvent.date >= start)
    if end is not None:
        query = query.where(TimetableEvent.date <= end)
    events = db.scalars(query.order_by(TimetableEvent.date, TimetableEvent.start_time)).all()

    event_ids = [event.id for event in events]
    lectures = (
        db.scalars(select(Lecture).where(Lecture.timetable_event_id.in_(event_ids))).all()
        if event_ids
        else []
    )
    marks = material_marks(db, [(lecture.subject, lecture.run_id) for lecture in lectures])

    by_event: dict[str, list[dict[str, Any]]] = {}
    for lecture in lectures:
        by_event.setdefault(lecture.timetable_event_id, []).append(
            {
                "subject": lecture.subject,
                "runId": lecture.run_id,
                "title": lecture.title,
                "professors": lecture.professors,
                "marks": marks.get((lecture.subject, lecture.run_id), {}),
            }
        )

    return {
        "events": [
            {
                "id": event.id,
                "date": event.date.isoformat(),
                "startTime": event.start_time,
                "endTime": event.end_time,
                "title": event.title,
                "details": event.details,
                "professor": event.professor,
                "category": event.category,
                "course": event.course,
                "slot": event.slot,
                # 한 칸에 여러 강의가 붙을 수 있다. 선택형 과목이 그렇다.
                "lectures": by_event.get(event.id, []),
            }
            for event in events
        ]
    }
