"""시험별 오늘 학습 목표. 시간표의 같은 과목 첫 시험에 범위를 자동 연결한다."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, load_only

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import BankState, Lecture, QuizBank, TimetableEvent
from app.naming import normalize_stem
from app.study_engine import empty_state, now_ms
from app.study_engine.planning import KOREA, daily_plan
from app.study_engine.daily_queue import lecture_goal

router = APIRouter()


def exam_time(event: TimetableEvent) -> int:
    return int(datetime.fromisoformat(f"{event.date.isoformat()}T{event.start_time or '09:00'}").replace(tzinfo=KOREA).timestamp() * 1000)


@router.get("/study-plan")
def read_study_plan(target: int = Query(90, ge=50, le=100),
                    subject: str | None = None, run_id: str | None = Query(None, alias="runId"),
                    user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    return build_study_plan(target, subject, run_id, user, db, now_ms())


def build_study_plan(target: int, subject: str | None, run_id: str | None,
                     user: CurrentUser, db: Session, now: int) -> dict:
    today = datetime.fromtimestamp(now / 1000, KOREA).date()
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
    banks, states = {}, {}
    if keys:
        query = select(QuizBank).options(load_only(QuizBank.subject, QuizBank.run_id, QuizBank.build_id,
            QuizBank.bank, QuizBank.validation, QuizBank.open_to_students)).where(tuple_(QuizBank.subject, QuizBank.run_id).in_(keys))
        if not user.is_admin:
            query = query.where(QuizBank.open_to_students.is_(True))
        banks = {(b.subject, b.run_id): b for b in db.scalars(query)
                 if b.bank and b.bank.get("questions") and (b.validation or {}).get("pass")}
        states = {(s.subject, s.run_id): s for s in db.scalars(select(BankState).options(load_only(
            BankState.subject, BankState.run_id, BankState.user_id, BankState.build_id, BankState.state,
        )).where(BankState.user_id == user.id, tuple_(BankState.subject, BankState.run_id).in_(keys)))}
    plans = []
    focused_goal = None
    for exam in upcoming:
        group = groups[exam.id]
        if not group:
            continue
        units = []
        for event in group:
            attached = by_event.get(event.id) or [None]
            for lecture in attached:
                key = (lecture.subject, lecture.run_id) if lecture else None
                bank, state = banks.get(key), states.get(key)
                unit = {"date": event.date, "bank": bank.bank if bank else None,
                        "state": state.state if bank and state and state.build_id == bank.build_id else empty_state()}
                units.append(unit)
                if lecture and bank and (lecture.subject, lecture.run_id) == (subject, run_id):
                    focused_goal = lecture_goal(bank.bank, unit["state"], lecture.title, now)
        plans.append({"examId": exam.id, "title": exam.title, "examDate": exam.date.isoformat(),
                      "examTime": exam.start_time or "09:00", "lectureCount": len(units),
                      "newToday": sum(u["date"] == today for u in units),
                      "upcomingLectures": sum(u["date"] > today for u in units),
                      "unassessedLectures": sum(u["bank"] is None for u in units),
                      **daily_plan(units, target, now, exam_time(exam))})
    return {"asOf": now, "plans": plans, "lectureGoal": focused_goal,
            "unmatchedExams": [e.title for e in upcoming if not groups[e.id]],
            "unassignedLectures": unassigned}
