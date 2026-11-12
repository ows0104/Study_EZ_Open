"""시험별 오늘 학습 목표. 시간표의 같은 과목 첫 시험에 범위를 자동 연결한다."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.lecture_mastery import main_quiz_inputs
from app.models import Lecture, TimetableEvent
from app.naming import normalize_stem
from app.root_learning.policy import configured_policy, instant
from app.root_learning.content import optional_excluded
from app.root_learning.score import lecture_score
from app.root_learning.state import optional_tasks
from app.study_engine import now_ms
from app.study_engine.planning import KOREA, daily_plan, day_start

router = APIRouter()


def _moment(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, UTC)


def main_quiz_unit(source, policy, day_begin: int, now: int, skip_optional: bool = False) -> dict:
    """계획 한 칸. Main-Quiz가 없으면 progress=None(0으로 가정, 미준비로 센다).
    `skip_optional`: Optional 계산 제외(2026-11-13) — 진척과 오늘 복습 수에서 Optional 문항을 뺀다."""
    if source is None:
        return {"progress": None, "reviewsToday": 0}
    doc, events = source

    def progress(until: int, at: int) -> float:
        score = lecture_score(doc, events, policy, _moment(at), until=_moment(until), skip_optional=skip_optional)
        return score.get("value") or 0.0

    begin, end = _moment(day_begin), _moment(now)
    skipped = optional_tasks(doc, events, end) if skip_optional else frozenset()
    return {"progress": progress,
            "reviewsToday": sum(e["kind"] == "rate" and begin <= instant(e["at"]) <= end
                                and e["payload"].get("task_id") not in skipped for e in events)}


def exam_time(event: TimetableEvent) -> int:
    return int(datetime.fromisoformat(f"{event.date.isoformat()}T{event.start_time or '09:00'}").replace(tzinfo=KOREA).timestamp() * 1000)


@router.get("/study-plan")
def read_study_plan(target: int = Query(90, ge=50, le=100),
                    subject: str | None = None, run_id: str | None = Query(None, alias="runId"),
                    user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    return build_study_plan(target, subject, run_id, user, db, now_ms())


def build_study_plan(target: int, subject: str | None, run_id: str | None,
                     user: CurrentUser, db: Session, now: int) -> dict:
    # 「오늘」은 학습일(한국 새벽 4시 경계)이다(2026-11-11 사용자 지시).
    today = datetime.fromtimestamp(day_start(now) / 1000, KOREA).date()
    events = db.scalars(select(TimetableEvent).order_by(TimetableEvent.date, TimetableEvent.start_time, TimetableEvent.id)).all()
    exams = [e for e in events if e.category == "exam" and "실습" not in e.title]
    upcoming = [e for e in exams if exam_time(e) > now]
    # 시험명이 단순히 '시험'인 경우는 다른 과목 시험으로 임의 연결하지 않는다.
    groups = {e.id: [] for e in upcoming}
    unassigned = 0
    for event in events:
        if event.category != "lecture":
            continue
        course = normalize_stem(event.course)
        chosen = next((exam for exam in exams if course and normalize_stem(exam.title).startswith(course)
                       and exam_time(exam) >= exam_time(event)), None)
        if chosen and chosen.id in groups:
            groups[chosen.id].append(event)
        elif chosen is None and event.date >= today:
            unassigned += 1
    # 시험 대비 계획은 시험 단위로, 풀이 완료는 해당 강의의 실제 학습 단위로 집계한다.
    if subject is not None or run_id is not None:
        lecture = db.get(Lecture, (subject, run_id)) if subject and run_id else None
        groups = {eid: group for eid, group in groups.items()
                  if lecture and any(event.id == lecture.timetable_event_id for event in group)}
        upcoming = [exam for exam in upcoming if exam.id in groups]
    ids = [e.id for group in groups.values() for e in group]
    lectures = db.scalars(select(Lecture).where(Lecture.timetable_event_id.in_(ids)).order_by(
        Lecture.date, Lecture.start_time, Lecture.subject, Lecture.run_id)).all() if ids else []
    by_event = {}
    for lecture in lectures:
        by_event.setdefault(lecture.timetable_event_id, []).append(lecture)
    keys = [(l.subject, l.run_id) for l in lectures]
    # 2026-11-11부터 계획의 강의 학습률은 Main-Quiz 하나다. Quiz Bank(legacy)는 세지 않는다.
    policy = configured_policy()
    inputs = main_quiz_inputs(db, keys, user) if keys and policy else {}
    skip = optional_excluded(db, user.id) if inputs else False
    day_begin = day_start(now)
    plans = []
    focused_goal = None  # Quiz Bank 강의별 오늘 목표(legacy). Main-Quiz의 오늘 할 일은 RootToday가 보인다.
    for exam in upcoming:
        group = groups[exam.id]
        if not group:
            continue
        units = []
        for event in group:
            attached = by_event.get(event.id) or [None]
            for lecture in attached:
                key = (lecture.subject, lecture.run_id) if lecture else None
                units.append({"date": event.date, **main_quiz_unit(inputs.get(key), policy, day_begin, now, skip)})
        plans.append({"examId": exam.id, "title": exam.title, "examDate": exam.date.isoformat(),
                      "examTime": exam.start_time or "09:00", "lectureCount": len(units),
                      "newToday": sum(u["date"] == today for u in units),
                      "upcomingLectures": sum(u["date"] > today for u in units),
                      "unassessedLectures": sum(u["progress"] is None for u in units),
                      **daily_plan(units, target, now, exam_time(exam))})
    return {"asOf": now, "plans": plans, "lectureGoal": focused_goal,
            "unmatchedExams": [e.title for e in upcoming if not groups[e.id]],
            "unassignedLectures": unassigned}
