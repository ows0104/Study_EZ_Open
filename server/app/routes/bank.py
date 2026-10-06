"""Quiz Bank — 관리자가 ChatGPT 응답을 넣고, 러너가 정리해 올리고, 학생이 Study Engine 으로 푼다.

    관리자   PUT  /api/admin/lectures/{s}/{r}/bank-response   확장이 받아 온 응답 원문 → 일감(kind=bank)
             PUT  /api/admin/lectures/{s}/{r}/bank/open       학생에게 열기·닫기
             GET|PUT /api/admin/bank-feedback                 학생 신고 — 편을 가로질러 문항별로 · 상태
    러너     GET  /api/admin/lectures/{s}/{r}/bank-response   원문 + 자료 목록
             PUT  /api/admin/lectures/{s}/{r}/bank            정리·검증·검토 결과
    학생     GET  /api/lectures/{s}/{r}/bank                  요약 · 현재 회차 · 개념 지도
             POST /api/lectures/{s}/{r}/bank/session/start|end · next · reveal · rate · feedback

답·채점 단위는 reveal 전에 안 나간다. 다음 문항은 서버가 고른다(`app/study_engine/`) —
Main-Quiz 처럼 목록을 통째로 보내고 화면이 고르는 방식이 아니다. 고르는 데 숙련도·선행 문항·
시험까지 남은 날이 다 필요하고, 그 계산이 두 곳에 살면 갈라진다.

**처음엔 관리자에게만 보인다**(`open_to_students`). 새 파이프라인의 첫 은행들이다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import study_engine as engine
from app.auth import CurrentUser, require_admin, require_approved_user, require_runner
from app.database import get_db
from app.jobs.queue import open_job_of
from app.models import (
    BANK_BUILDING,
    BANK_FAILED,
    BANK_INVALID,
    BANK_READY,
    BANK_RESPONDED,
    JOB_BANK,
    JOB_BUTTON,
    JOB_QUEUED,
    SLIDE_KINDS,
    Asset,
    BankFeedback,
    BankState,
    Lecture,
    PrequizJob,
    Profile,
    QuizBank,
    TimetableEvent,
)
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter()
admin_router = APIRouter()

COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE"
# 첨부 순서가 곧 자료 ID 다 — 웹이 프롬프트에 이 순서로 적고 확장이 이 순서로 붙인다.
SOURCE_KINDS = (("notes_current", "S1"), ("jokbo", "S2"))
ANSWER_FIELDS = ("answer", "answer_units", "correct_option_ids", "answer_pairs", "correct_order")
FEEDBACK_CATEGORIES = ("good", "wording", "easy", "hard", "leak", "format", "burden", "importance",
                       "content", "duplicate", "sequencing", "other")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


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
    if not row.bank or not (row.validation or {}).get("pass"):
        raise HTTPException(409, "검증을 통과한 문제은행이 아직 없습니다.")
    return row.bank


def summary(db: Session, lecture: Lecture, row: QuizBank | None, *, is_admin: bool) -> dict[str, Any] | None:
    """강의 상세에 싣는 요약. 학생에게는 열린 은행만."""
    if row is None or (not is_admin and not row.open_to_students):
        return None
    bank = row.bank or {}
    out: dict[str, Any] = {
        "status": row.status, "open": row.open_to_students, "buildId": row.build_id,
        "questionCount": len(bank.get("questions", [])), "conceptCount": len(bank.get("concepts", [])),
        "builtAt": _iso(row.built_at), "usable": bool(row.bank and (row.validation or {}).get("pass")),
    }
    if is_admin:
        review = row.review or {}
        out.update(respondedAt=_iso(row.responded_at), promptVersion=row.prompt_version, message=row.message,
                   reviewCounts=review.get("counts"), errorCount=len((row.validation or {}).get("errors", [])),
                   # 검증에 걸려 뺀 문항(`quizbank.validate.validate_dropping`). 원문은 `GET …/bank` 의 validation 에 있다.
                   dropped=[{"questionId": d["question_id"], "errors": d["errors"]}
                            for d in (row.validation or {}).get("dropped", [])])
    return out


# ---------------------------------------------------------------- 관리자 · 러너


class ResponseIn(BaseModel):
    raw: str = Field(min_length=200, max_length=2_000_000)
    conversation_url: str = Field(default="", alias="conversationUrl", max_length=500)
    prompt_version: str = Field(default="", alias="promptVersion", max_length=16)

    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank-response")
def put_bank_response(subject: str, run_id: str, payload: ResponseIn,
                      user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """확장이 ChatGPT 탭에서 받아 온 응답 원문. 저장하면 러너가 정리할 일감이 선다."""
    lecture = lecture_or_404(db, subject, run_id)
    if COMPLETE_MARK not in payload.raw:
        raise HTTPException(422, "완료 표시가 없는 응답입니다. 답이 끝난 뒤 다시 저장하세요.")
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        row = QuizBank(subject=lecture.subject, run_id=lecture.run_id)
        db.add(row)
    row.raw_response = payload.raw
    row.conversation_url = payload.conversation_url
    row.prompt_version = payload.prompt_version
    row.responded_by = user.email or user.id
    row.responded_at = datetime.now(UTC)
    row.status = BANK_RESPONDED
    row.message = "응답을 받았다 — 러너가 정리한다"
    job = open_job_of(db, lecture.subject, lecture.run_id, JOB_BANK)
    if job is None:
        job = PrequizJob(subject=lecture.subject, run_id=lecture.run_id, kind=JOB_BANK, state=JOB_QUEUED,
                         stage="응답을 받았다 — 러너를 기다리는 중", requested_by=user.email or user.id,
                         origin=JOB_BUTTON)
        db.add(job)
    db.commit()
    return {"status": row.status, "respondedAt": _iso(row.responded_at), "jobId": job.id}


@admin_router.get("/lectures/{subject}/{run_id}/bank-response")
def get_bank_response(subject: str, run_id: str, user: CurrentUser = Depends(require_runner),
                      db: Session = Depends(get_db)) -> dict[str, Any]:
    """러너가 정리할 재료. 집어 가면 `building` 으로 적는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None or not row.raw_response:
        raise HTTPException(404, "저장된 ChatGPT 응답이 없습니다.")
    row.status = BANK_BUILDING
    row.message = "러너가 정리하는 중"
    db.commit()
    return {"raw": row.raw_response, "respondedAt": _iso(row.responded_at), "promptVersion": row.prompt_version,
            "title": lecture.title, "sources": [{k: s[k] for k in ("id", "kind", "filename")}
                                                for s in bank_sources(db, lecture)]}


class BankIn(BaseModel):
    responded_at: str = Field(alias="respondedAt")
    bank: dict | None = None
    validation: dict | None = None
    review: dict | None = None
    pages: dict[str, list[int]] | None = None
    usage: list[dict] | None = None
    message: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank")
def put_bank(subject: str, run_id: str, payload: BankIn, user: CurrentUser = Depends(require_runner),
             db: Session = Depends(get_db)) -> dict[str, Any]:
    """러너의 결과. **그 사이 관리자가 응답을 다시 저장했으면 거절한다** — 옛 응답의 정리가
    새 응답을 덮으면, 다시 만들라고 누른 사람에게 다시 만들었는데 그대로인 것을 돌려준다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None or _iso(row.responded_at) != payload.responded_at:
        raise HTTPException(409, "그 사이 새 응답이 저장됐습니다. 새 응답으로 다시 정리하세요.")
    if payload.bank is None or payload.validation is None:
        row.status = BANK_FAILED
        row.message = payload.message or "정리에 실패했다"
        db.commit()
        return {"status": row.status}
    row.bank, row.validation, row.review = payload.bank, payload.validation, payload.review
    row.pages, row.usage = payload.pages or {}, payload.usage or []
    row.build_id = uuid.uuid4().hex[:16]
    row.built_at = datetime.now(UTC)
    row.status = BANK_READY if payload.validation.get("pass") else BANK_INVALID
    row.message = payload.message or (
        "" if row.status == BANK_READY else f"검증 오류 {len(payload.validation.get('errors', []))}건")
    db.commit()
    return {"status": row.status, "buildId": row.build_id}


class OpenIn(BaseModel):
    open: bool


@admin_router.put("/lectures/{subject}/{run_id}/bank/open")
def put_bank_open(subject: str, run_id: str, payload: OpenIn, user: CurrentUser = Depends(require_admin),
                  db: Session = Depends(get_db)) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        raise HTTPException(404, "Quiz Bank 가 없습니다.")
    if payload.open:
        _usable(row)
    row.open_to_students = payload.open
    db.commit()
    return {"open": row.open_to_students}


@admin_router.get("/lectures/{subject}/{run_id}/bank")
def get_bank_admin(subject: str, run_id: str, user: CurrentUser = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict[str, Any]:
    """관리자가 은행 전체를 본다 — 문항·답·검증·검토·피드백."""
    lecture = lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        raise HTTPException(404, "Quiz Bank 가 없습니다.")
    feedback = db.scalars(select(BankFeedback).where(BankFeedback.subject == lecture.subject,
                                                     BankFeedback.run_id == lecture.run_id)
                          .order_by(BankFeedback.created_at.desc())).all()
    return {"summary": summary(db, lecture, row, is_admin=True), "bank": row.bank, "validation": row.validation,
            "review": row.review, "pages": row.pages, "usage": row.usage,
            "feedback": [{"id": f.id, "questionId": f.question_id, "category": f.category, "comment": f.comment,
                          "status": f.status, "buildId": f.build_id, "createdAt": _iso(f.created_at)}
                         for f in feedback]}


FEEDBACK_STATUSES = ("open", "resolved", "wontfix")


@admin_router.get("/bank-feedback")
def bank_feedback(user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """학생의 「문제 있음」을 편을 가로질러 **문항별로** 묶는다 — 관리 화면 「Quiz Bank 신고」 탭.

    여럿이 같은 문항을 신고하면 한 묶음이다. 문항은 **지금 은행의 것**을 싣는다 — 신고 줄에는
    문면이 없다. 그래서 신고가 옛 빌드에서 왔으면 `stale` 로 갈라 둔다: 다시 만들면 ChatGPT 가
    같은 ID(Q7)에 다른 문항을 낼 수 있어서, 지금 문항을 두고 옛 신고를 읽으면 엉뚱한 판정이 된다.

    `good`(좋은 문제)은 신고가 아니라서 뺀다. 화면의 폼에는 없고 서버만 받는 값이다.
    """
    rows = db.scalars(select(BankFeedback).where(BankFeedback.category != "good")
                      .order_by(BankFeedback.created_at.desc())).all()
    banks: dict[tuple[str, str], QuizBank | None] = {}
    lectures: dict[tuple[str, str], Lecture | None] = {}
    emails = {p.id: p.email for p in db.scalars(select(Profile).where(
        Profile.id.in_({f.user_id for f in rows})))} if rows else {}
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for f in rows:
        key = (f.subject, f.run_id)
        if key not in banks:
            banks[key] = db.get(QuizBank, key)
            lectures[key] = db.get(Lecture, key)
        bank, lecture = banks[key], lectures[key]
        group = groups.get((*key, f.question_id))
        if group is None:
            questions = (bank.bank or {}).get("questions", []) if bank else []
            q = next((q for q in questions if q["question_id"] == f.question_id), None)
            review = next((r for r in ((bank.review or {}).get("reviews", []) if bank else [])
                           if r["question_id"] == f.question_id), None)
            group = groups[(*key, f.question_id)] = {
                "subject": f.subject, "runId": f.run_id, "questionId": f.question_id,
                "title": lecture.title if lecture else "", "date": lecture.date.isoformat() if lecture else "",
                "question": q, "medicalReview": review, "reports": [],
            }
        group["reports"].append({
            "id": f.id, "category": f.category, "comment": f.comment, "status": f.status,
            "email": emails.get(f.user_id, ""), "createdAt": _iso(f.created_at),
            "stale": bank is None or f.build_id != bank.build_id,
        })
    out = list(groups.values())
    open_count = sum(1 for g in out if any(r["status"] == "open" for r in g["reports"]))
    return {"questions": out, "open": open_count, "done": len(out) - open_count}


class FeedbackStatusIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    status: Literal[FEEDBACK_STATUSES]  # type: ignore[valid-type]


@admin_router.put("/bank-feedback")
def set_bank_feedback_status(payload: FeedbackStatusIn, user: CurrentUser = Depends(require_admin),
                             db: Session = Depends(get_db)) -> dict[str, Any]:
    """신고 여럿의 상태를 한 번에 — 반영했다(resolved) · 그대로 둔다(wontfix) · 되돌린다(open)."""
    rows = db.scalars(select(BankFeedback).where(BankFeedback.id.in_(payload.ids))).all()
    if len(rows) != len(set(payload.ids)):
        raise HTTPException(404, "없는 신고가 섞여 있습니다.")
    for row in rows:
        row.status = payload.status
    db.commit()
    return {"updated": len(rows)}


# ---------------------------------------------------------------- 학생


def _load_state(db: Session, user: CurrentUser, row: QuizBank) -> BankState:
    """이 사람의 상태. 은행이 새로 만들어졌으면 옛 상태를 밀어 두고 새로 시작한다."""
    state = db.get(BankState, (user.id, row.subject, row.run_id))
    if state is None:
        state = BankState(user_id=user.id, subject=row.subject, run_id=row.run_id, build_id=row.build_id,
                          state=engine.empty_state())
        db.add(state)
    elif state.build_id != row.build_id:
        state.previous = {"build_id": state.build_id, "state": state.state}
        state.build_id = row.build_id
        state.state = engine.empty_state()
    return state


def _save(state: BankState, value: dict) -> None:
    # JSON 칼럼은 새 객체를 넣어야 바뀐 줄 안다.
    state.state = value


def _public(q: dict) -> dict:
    return {k: v for k, v in q.items() if k not in ANSWER_FIELDS}


def _slides(db: Session, row: QuizBank, question_id: str) -> list[dict[str, Any]]:
    pages = (row.pages or {}).get(question_id) or []
    if not pages:
        return []
    assets = {a.slide_no: a for a in db.scalars(select(Asset).where(
        Asset.subject == row.subject, Asset.run_id == row.run_id, Asset.kind == SLIDE_KINDS["bank"],
        Asset.slide_no.in_(pages)))}
    out = []
    for page in pages:
        asset = assets.get(page)
        if asset is None:
            continue
        try:
            out.append({"page": page, "url": ObjectStorage().presign_download(asset.object_key)})
        except StorageNotConfigured:
            break
    return out


def _answer(db: Session, row: QuizBank, q: dict) -> dict[str, Any]:
    review = next((r for r in (row.review or {}).get("reviews", []) if r["question_id"] == q["question_id"]), None)
    # 프롬프트 v1.2(2026-10-05): 충돌은 한 문항으로 합치고 외부 의학지식으로 답을 정한다. 학생은 답을 본 뒤
    # 각 출처가 무엇이라고 하는지와 고른 근거(충돌 기록의 설명)를 읽는다. 자료 밖 내용은 출처 `EXT` 로 표시된다.
    conflict = next((c for c in (row.bank or {}).get("source_conflicts", [])
                     if q["conflict_id"] and c["conflict_id"] == q["conflict_id"]), None)
    return {"answer": q["answer"], "answerUnits": q["answer_units"], "correctOptionIds": q["correct_option_ids"],
            "answerPairs": q["answer_pairs"], "correctOrder": q["correct_order"],
            "slides": _slides(db, row, q["question_id"]), "medicalReview": review,
            "conflict": conflict["description"] if conflict else "",
            "external": any(r["source_id"] == "EXT" for r in q["source_refs"])}


@router.get("/lectures/{subject}/{run_id}/bank")
def read_bank(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
              db: Session = Depends(get_db)) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    out = {"summary": summary(db, lecture, row, is_admin=user.is_admin), "examDate": exam_date_for(db, lecture),
           "sizes": engine.DEFAULT["session"]["sizes"], "defaultSize": engine.DEFAULT["session"]["defaultSize"],
           "session": None, "previousSessions": [], "conceptMap": []}
    if row.bank and (row.validation or {}).get("pass"):
        state = db.get(BankState, (user.id, row.subject, row.run_id))
        current = state.state if state and state.build_id == row.build_id else engine.empty_state()
        if state and state.build_id == row.build_id:
            out["session"] = engine.session_summary(row.bank, state.state)
            out["previousSessions"] = state.state.get("sessions", [])[-5:]
        # 개념 지도는 첫 회차 전에도 그린다 — 숙련도가 다 0인 지도가 「무엇을 공부할지」의 답이다.
        out["conceptMap"] = engine.concept_map(row.bank, current)
    return out


class StartIn(BaseModel):
    size: int


@router.post("/lectures/{subject}/{run_id}/bank/session/start")
def start_bank_session(subject: str, run_id: str, payload: StartIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state = _load_state(db, user, row)
    try:
        _save(state, engine.start_session(bank, state.state, payload.size, engine.now_ms()))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return engine.session_summary(bank, state.state)


class EndIn(BaseModel):
    session_id: str = Field(alias="sessionId")

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/session/end")
def end_bank_session(subject: str, run_id: str, payload: EndIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state = _load_state(db, user, row)
    session = state.state.get("session") or {}
    if session.get("id") != payload.session_id:
        raise HTTPException(409, "현재 학습 회차가 아닙니다.")
    _save(state, engine.end_session(bank, state.state, "user_finished", engine.now_ms()))
    db.commit()
    return engine.session_summary(bank, state.state)


@router.post("/lectures/{subject}/{run_id}/bank/next")
def next_bank_question(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db)) -> dict[str, Any]:
    """다음 문항. **이미 내준 문항이 있으면 그것을 다시 준다** — 새로고침이 문항을 넘기지 않는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    now = engine.now_ms()
    state = engine.upgrade_state(bank, state_row.state, engine.DEFAULT, now)
    if not state.get("session"):
        state = engine.start_session(bank, state, engine.DEFAULT["session"]["defaultSize"], now)
    if state["session"]["status"] == "complete":
        _save(state_row, state)
        db.commit()
        return {"question": None, "summary": engine.session_summary(bank, state)}
    exam = exam_date_for(db, lecture)
    by_id = {q["question_id"]: q for q in bank["questions"]}
    served = state.get("served")
    if served and served["question_id"] in by_id:
        question = by_id[served["question_id"]]
        days = engine.days_until(exam, now)
    else:
        picked = engine.select_question(bank, state, exam, now)
        question, days = picked["question"], picked["days"]
        if question is None:
            state = engine.end_session(bank, state, "no_eligible_question", now)
            _save(state_row, state)
            db.commit()
            return {"question": None, "summary": engine.session_summary(bank, state),
                    "reason": picked["reason"], "retryAt": picked["retry_at"]}
        score = next((r for r in picked["ranked"] if r["question_id"] == question["question_id"]), None)
        served = {"question_id": question["question_id"], "token": uuid.uuid4().hex, "revealed": False,
                  "presented_at": now, "policy_version": engine.DEFAULT["version"],
                  "policy_hash": engine.policy_hash(engine.DEFAULT), "score": score}
        state["served"] = served
    _save(state_row, state)
    db.commit()
    return {"question": _public(question), "reviewToken": served["token"], "days": days, "examDate": exam,
            "preloadSlides": _slides(db, row, question["question_id"]),
            "session": engine.session_summary(bank, state),
            "answer": _answer(db, row, question) if served.get("revealed") else None}


class TokenIn(BaseModel):
    review_token: str = Field(alias="reviewToken")

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/reveal")
def reveal_bank_answer(subject: str, run_id: str, payload: TokenIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = dict(state.get("served") or {})
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    served["revealed"] = True
    served.setdefault("revealed_at", engine.now_ms())
    state["served"] = served
    _save(state_row, state)
    db.commit()
    question = next(q for q in bank["questions"] if q["question_id"] == served["question_id"])
    return _answer(db, row, question)


class RateIn(BaseModel):
    review_token: str = Field(alias="reviewToken")
    rating: Literal["Again", "Hard", "Good", "Easy"]

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/rate")
def rate_bank_answer(subject: str, run_id: str, payload: RateIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """답을 본 뒤에 한 번만. 회차가 다 차면 여기서 닫는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    state = state_row.state
    served = state.get("served") or {}
    if not served.get("revealed") or served.get("token") != payload.review_token:
        raise HTTPException(409, "정답 공개 후 한 번만 평가할 수 있습니다.")
    now = engine.now_ms()
    nxt = engine.record_review(bank, state, served["question_id"], payload.rating, now)
    last = nxt["history"][-1]
    last["score_breakdown"] = served.get("score")
    last["selection_policy_version"] = served.get("policy_version")
    presented = served.get("presented_at")
    last["response_time_sec"] = max(0, (served.get("revealed_at", now) - presented) / 1000) if presented else None
    summary_now = engine.session_summary(bank, nxt)
    if summary_now and summary_now["reviewed"] >= nxt["session"]["size"]:
        nxt = engine.end_session(bank, nxt, "size_reached", now)
    _save(state_row, nxt)
    db.commit()
    return {"reviews": len(nxt["history"]), "session": engine.session_summary(bank, nxt)}


class FeedbackIn(BaseModel):
    question_id: str = Field(alias="questionId", max_length=64)
    category: Literal[FEEDBACK_CATEGORIES]  # type: ignore[valid-type]
    comment: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/feedback", status_code=201)
def post_bank_feedback(subject: str, run_id: str, payload: FeedbackIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    if not any(q["question_id"] == payload.question_id for q in bank["questions"]):
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    entry = BankFeedback(user_id=user.id, subject=row.subject, run_id=row.run_id, build_id=row.build_id,
                         question_id=payload.question_id, category=payload.category, comment=payload.comment)
    db.add(entry)
    db.commit()
    return {"id": entry.id}
