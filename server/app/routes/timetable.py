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
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.lecture_mastery import lecture_overviews
from app.root_learning import content as root_content
from app.models import Lecture, TimetableEvent
from app.preview_sources import public_source
from app.routes.common import asset_grabs, bank_timelines, grab_tracks, material_marks, prequiz_progress

router = APIRouter()


@router.get("/timetable")
def read_timetable(
    start: Date | None = Query(None, description="이 날짜부터 (없으면 전체)"),
    end: Date | None = Query(None, description="이 날짜까지"),
    include_study: bool = Query(True, description="학습 집계 포함. false이면 목록만 먼저 읽는다"),
    include_cards: bool = Query(True, description="카드 단계 집계 포함. 시간표 학습률 조회에는 불필요"),
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
    marks = (material_marks(db, keys, is_admin=user.is_admin, include_banks=False) if include_study
             else {key: dict.fromkeys(("notesPrev", "preview", "prequiz", "notesCurrent", "quiz"), False) for key in keys})
    timelines = bank_timelines(db, keys, is_admin=user.is_admin, include_ready=not include_study)
    if not include_study:
        for key, timeline in timelines.items():
            marks[key]["quiz"] = timeline.pop("ready")
    progress = prequiz_progress(db, user.id, keys) if include_study else {}
    grabs = asset_grabs(db, user.id, keys) if include_study else {}
    overviews = lecture_overviews(db, user.id, keys, is_admin=user.is_admin, include_cards=include_cards) if include_study else {}
    for key, overview in overviews.items():
        marks[key]["quiz"] = overview["ready"]
    # 검토·공개된 Main-Quiz(뿌리 학습). `quiz`(Quiz Bank)와 따로 둔다 — 모아풀기는 은행만 섞는다.
    published = root_content.published_for(db, keys, user)
    for key in keys:
        marks.setdefault(key, {})["mainQuiz"] = key in published

    by_event: dict[str, list[dict[str, Any]]] = {}
    event_map = {event.id: event for event in events}
    for lecture in lectures:
        key = (lecture.subject, lecture.run_id)
        by_event.setdefault(lecture.timetable_event_id, []).append(
            {
                "subject": lecture.subject,
                "runId": lecture.run_id,
                "title": lecture.title,
                "professors": lecture.professors,
                "previewSource": public_source(lecture, event_map.get(lecture.timetable_event_id)),
                "marks": marks.get(key, {}),
                "bankTimeline": timelines.get(key),
                "mastery": overviews.get(key, {}).get("mastery"),
                "cardProgress": overviews.get(key, {}).get("cardProgress"),
                "studyLoaded": include_study,
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


class StudyLectureIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    runId: str = Field(min_length=1, max_length=32)


class StudyProgressIn(BaseModel):
    lectures: list[StudyLectureIn] = Field(min_length=1, max_length=8)


@router.post("/timetable/study-progress")
def read_study_progress(
    payload: StudyProgressIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict:
    keys = list(dict.fromkeys((l.subject, l.runId) for l in payload.lectures))
    overviews = lecture_overviews(db, user.id, keys, is_admin=user.is_admin)
    return {"lectures": [
        {"subject": subject, "runId": run_id, "ready": overviews.get((subject, run_id), {}).get("ready", False),
         "mastery": overviews.get((subject, run_id), {}).get("mastery"),
         "cardProgress": overviews.get((subject, run_id), {}).get("cardProgress")}
        for subject, run_id in keys
    ]}
