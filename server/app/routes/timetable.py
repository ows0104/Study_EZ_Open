"""캘린더가 읽는 것.

시간표만으로 그려진다. 파이프라인 산출물이 하나도 없어도 화면은 완성된 모습이고,
자료가 올라오면 칸에 점이 붙는다.

**이 응답은 사람마다 다르다.** `prequizProgress`와 `grabbed`가 그 사람이 푼 수와
받아 간 것을 싣기 때문이다. 캐시를 붙이려거든 사용자별로 갈라야 한다.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.lecture_mastery import lecture_masteries
from app.models import Lecture, TimetableEvent
from app.routes.common import asset_grabs, grab_tracks, material_marks, prequiz_progress

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
    keys = [(lecture.subject, lecture.run_id) for lecture in lectures]
    marks = material_marks(db, keys, is_admin=user.is_admin)
    progress = prequiz_progress(db, user.id, keys)
    grabs = asset_grabs(db, user.id, keys)
    mastery = lecture_masteries(db, user.id, keys, is_admin=user.is_admin)

    by_event: dict[str, list[dict[str, Any]]] = {}
    for lecture in lectures:
        key = (lecture.subject, lecture.run_id)
        by_event.setdefault(lecture.timetable_event_id, []).append(
            {
                "subject": lecture.subject,
                "runId": lecture.run_id,
                "title": lecture.title,
                "professors": lecture.professors,
                "marks": marks.get(key, {}),
                "mastery": mastery.get(key),
                # 웹에서 풀 문항이 없는 강의는 null이다. "안 풀었다"와 "잴 것이
                # 없다"는 화면에서 다르게 그려야 한다.
                "prequizProgress": progress.get(key),
                # 덱을 받아 갔는가. 자리 둘(예습·복습)로 묶어서 내려보낸다 —
                # 화면이 아는 것은 "이 자리를 손댔다"까지이고, Anki 안에서
                # 얼마나 풀었는지는 여기서도 저기서도 볼 수 없다.
                "grabbed": grab_tracks(grabs.get(key, set())),
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
