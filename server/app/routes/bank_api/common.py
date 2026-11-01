"""Bank lookup, summary, source list, and exam date. No HTTP route registration."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_personal
from app.auth import CurrentUser
from app.bank_validation.coverage import coverage_summary
from app.bank_validation.publication import usable as bank_usable, warning as publication_warning
from app.models import Asset, BankState, Lecture, QuizBank, TimetableEvent
from app.study_engine.progress import panel_progress


SOURCE_KINDS = (("notes_current", "S1"), ("jokbo", "S2"))


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _save_share_link(row: QuizBank, value: str | None) -> None:
    if value is not None:
        value = value.strip()
        if value != (row.share_url or ""):
            row.share_url = value
            row.linked_at = datetime.now(UTC) if value else None


def bank_sources(db: Session, lecture: Lecture) -> list[dict[str, Any]]:
    """ChatGPT 에 붙일 자료와 그 ID. 올해 필기(S1) · 족보 조각(S2, 있으면)."""
    out = []
    for kind, sid in SOURCE_KINDS:
        asset = db.scalars(select(Asset).where(Asset.subject == lecture.subject, Asset.run_id == lecture.run_id,
                                               Asset.kind == kind)).first()
        if asset:
            out.append({"id": sid, "kind": kind, "assetId": asset.id, "filename": asset.filename,
                        "contentType": asset.content_type})
    return out


def exam_date_for(db: Session, lecture: Lecture) -> str:
    """시험일. 강의 칸의 과목 이름으로 시작하는 첫 시험, 없으면 강의 뒤 첫 시험, 그것도 없으면 30일 뒤.

    Study_EZ 는 강의마다 시험일을 따로 적지 않는다. 시간표에 「약물의 이해 시험」 같은 칸이 있다.
    """
    exams = db.scalars(select(TimetableEvent).where(TimetableEvent.category == "exam",
                                                    TimetableEvent.date >= lecture.date)
                       .order_by(TimetableEvent.date)).all()
    event = db.get(TimetableEvent, lecture.timetable_event_id) if lecture.timetable_event_id else None
    course = (event.course if event else "").strip()
    same = next((e for e in exams if course and e.title.startswith(course)), None)
    chosen = same or (exams[0] if exams else None)
    if chosen:
        return chosen.date.isoformat()
    return (lecture.date + timedelta(days=30)).isoformat()


def _bank_or_404(db: Session, lecture: Lecture, user: CurrentUser) -> QuizBank:
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None or (not user.is_admin and not row.open_to_students):
        raise HTTPException(404, "이 강의에는 아직 Quiz Bank 가 없습니다.")
    return row


def _usable(row: QuizBank) -> dict:
    """학습에 쓸 수 있는 은행. 검증을 통과한 것만."""
    if not bank_usable(row.bank, row.validation):
        raise HTTPException(409, "검증을 통과한 문제은행이 아직 없습니다.")
    return row.bank


def summary(db: Session, lecture: Lecture, row: QuizBank | None, *, is_admin: bool,
            user_id: str | None = None) -> dict[str, Any] | None:
    """문제은행 링크는 관리자 전용이며 학생 문항은 공개된 은행만 싣는다."""
    if row is None or (not is_admin and not row.open_to_students):
        return None
    bank = bank_personal.augment(db, row, user_id) if user_id else row.bank or {}
    state = db.get(BankState, (user_id, row.subject, row.run_id)) if user_id else None
    current = state.state if state and state.build_id == row.build_id else {}
    out: dict[str, Any] = {
        "status": row.status, "open": row.open_to_students, "buildId": row.build_id,
        "linkedAt": _iso(row.linked_at),
        "questionCount": len(bank.get("questions", [])), "conceptCount": len(bank.get("concepts", [])),
        "builtAt": _iso(row.built_at), "usable": bank_usable(row.bank, row.validation),
        'publicationWarning': publication_warning(row.bank, row.validation),
        **panel_progress(bank, current),
        "coverage": coverage_summary(bank, row.validation or {}),
    }
    if out["coverage"]:
        source = db.scalars(select(Asset).where(Asset.subject == lecture.subject, Asset.run_id == lecture.run_id,
                                              Asset.kind == "notes_current")).first()
        if source is None or source.filename != out["coverage"].get("sourceFilename"):
            out["coverage"]["status"] = "stale"
    if is_admin:
        review = row.review or {}
        out.update(shareUrl=row.share_url, respondedAt=_iso(row.responded_at), promptVersion=row.prompt_version, message=row.message,
                   conversationUrl=row.conversation_url, revision=(row.validation or {}).get("revision"),
                   reviewCounts=review.get("counts"), errorCount=len((row.validation or {}).get("errors", [])),
                   # 검증에 걸려 뺀 문항(`quizbank.validate.validate_dropping`). 원문은 `GET …/bank` 의 validation 에 있다.
                   dropped=[{"questionId": d["question_id"], "errors": d["errors"]}
                            for d in (row.validation or {}).get("dropped", [])])
    return out
