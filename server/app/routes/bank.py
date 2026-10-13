"""Quiz Bank — 관리자가 ChatGPT 응답을 넣고, 러너가 정리해 올리고, 학생이 Study Engine 으로 푼다.

    관리자   PUT  /api/admin/lectures/{s}/{r}/bank-response   확장이 받아 온 응답 원문 → 일감(kind=bank)
             PUT  /api/admin/lectures/{s}/{r}/bank/open       학생에게 열기·닫기
             GET|PUT /api/admin/bank-feedback                 학생 신고 — 편을 가로질러 문항별로 · 상태
    러너     GET  /api/admin/lectures/{s}/{r}/bank-response   원문 + 자료 목록
             PUT  /api/admin/lectures/{s}/{r}/bank            정리·검증·검토 결과
    학생     GET  /api/lectures/{s}/{r}/bank                  요약 · 현재 회차 · 개념 지도
             POST /api/lectures/{s}/{r}/bank/session/start|end · next · reveal · rate · feedback

답·채점 단위는 문항 목록에 넣지 않는다. prepare는 현재 문항의 답을 미리 읽고,
reveal은 실제 클릭 시각을 기록한다. 다음 문항은 서버가 고른다(`app/study_engine/`) —
Main-Quiz 처럼 목록을 통째로 보내고 화면이 고르는 방식이 아니다. 고르는 데 숙련도·선행 문항·
시험까지 남은 날이 다 필요하고, 그 계산이 두 곳에 살면 갈라진다.

검증을 통과한 업로드는 학생에게 자동 공개한다(`open_to_students`). 관리자는 다시 닫을 수 있다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, tuple_
from sqlalchemy.orm import Session

from app import study_engine as engine
from app import bank_edits
from app import bank_personal
from app.bank_validation.pages import cited_pages
from app.bank_validation.schema import QUESTION, schema_errors, without_retired
from app.bank_validation.coverage import coverage_summary
from app.bank_validation.validate import validate_bank
from app.bank_validation.choice_mode import choice_mode
from app.preview_links import conversation_url as valid_conversation_url, share_url as valid_share_url
from app.auth import CurrentUser, require_admin, require_approved_user, require_runner
from app.database import get_db
from app.lecture_mastery import for_bank
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
    BankPersonalEdit,
    Lecture,
    PrequizJob,
    Profile,
    QuizBank,
    TimetableEvent,
)
from app.routes.common import lecture_or_404, record_grabs, storage_or_503
from app.study_engine.daily_queue import daily_units, lecture_goal, select_daily_question
from app.study_engine.progress import mark_seen, panel_progress
from app.study_engine.choices import realize_choices
from app.study_engine.planning import day_start
from app.study_engine.review_undo import remember_review, undo_review, undo_token
from app.study_engine.batch import aggregate_goal, choose_lecture
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter()
admin_router = APIRouter()

COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE"
# 첨부 순서가 곧 자료 ID 다 — 웹이 프롬프트에 이 순서로 적고 확장이 이 순서로 붙인다.
SOURCE_KINDS = (("notes_current", "S1"), ("jokbo", "S2"))
ANSWER_FIELDS = ("answer", "answer_units", "correct_option_ids", "answer_pairs", "correct_order", "option_explanations", "option_pools", "choice_variant")
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


def summary(db: Session, lecture: Lecture, row: QuizBank | None, *, is_admin: bool,
            user_id: str | None = None) -> dict[str, Any] | None:
    """강의 상세에 싣는 요약. 학생에게는 열린 은행만."""
    if row is None or (not is_admin and not row.open_to_students):
        return None
    bank = row.bank or {}
    state = db.get(BankState, (user_id, row.subject, row.run_id)) if user_id else None
    current = state.state if state and state.build_id == row.build_id else {}
    out: dict[str, Any] = {
        "status": row.status, "open": row.open_to_students, "buildId": row.build_id,
        "shareUrl": row.share_url,
        "questionCount": len(bank.get("questions", [])), "conceptCount": len(bank.get("concepts", [])),
        "builtAt": _iso(row.built_at), "usable": bool(row.bank and (row.validation or {}).get("pass")),
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
        out.update(respondedAt=_iso(row.responded_at), promptVersion=row.prompt_version, message=row.message,
                   conversationUrl=row.conversation_url, revision=(row.validation or {}).get("revision"),
                   reviewCounts=review.get("counts"), errorCount=len((row.validation or {}).get("errors", [])),
                   # 검증에 걸려 뺀 문항(`quizbank.validate.validate_dropping`). 원문은 `GET …/bank` 의 validation 에 있다.
                   dropped=[{"questionId": d["question_id"], "errors": d["errors"]}
                            for d in (row.validation or {}).get("dropped", [])])
    return out


# ---------------------------------------------------------------- 관리자 · 러너


class ResponseIn(BaseModel):
    raw: str = Field(min_length=200, max_length=2_000_000)
    conversation_url: str = Field(default="", alias="conversationUrl", max_length=500)
    share_url: str | None = Field(default=None, alias="shareUrl", max_length=500)
    prompt_version: str = Field(default="", alias="promptVersion", max_length=16)

    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank-response")
def put_bank_response(subject: str, run_id: str, payload: ResponseIn,
                      user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """확장이 ChatGPT 탭에서 받아 온 응답 원문. 저장하면 러너가 정리할 일감이 선다."""
    lecture = lecture_or_404(db, subject, run_id)
    if COMPLETE_MARK not in payload.raw:
        raise HTTPException(422, "완료 표시가 없는 응답입니다. 답이 끝난 뒤 다시 저장하세요.")
    if not valid_conversation_url(payload.conversation_url, "chatgpt") or (
            payload.share_url is not None and not valid_share_url(payload.share_url, "chatgpt")):
        raise HTTPException(422, "ChatGPT 공유 링크와 개인 대화 주소를 확인하세요.")
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        row = QuizBank(subject=lecture.subject, run_id=lecture.run_id)
        db.add(row)
    row.raw_response = payload.raw
    if (row.validation or {}).get("revision"):
        row.validation = {k: v for k, v in row.validation.items() if k != "revision"}
    # 새 원문에는 이전 보강 요청을 이어 붙이지 않는다.
    if (row.validation or {}).get("maintenance"):
        row.validation = {k: v for k, v in row.validation.items() if k != "maintenance"}
    if payload.share_url is not None:
        row.share_url = payload.share_url.strip()
    elif row.conversation_url != payload.conversation_url:
        row.share_url = ""
    row.conversation_url = payload.conversation_url.strip()
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
    if row is None:
        raise HTTPException(404, "저장된 ChatGPT 응답이 없습니다.")
    row.status = BANK_BUILDING
    row.message = "러너가 정리하는 중"
    db.commit()
    maintenance = (row.validation or {}).get("maintenance")
    return {"raw": row.raw_response, "respondedAt": _iso(row.responded_at), "promptVersion": row.prompt_version,
            **({"existingBank": row.bank, "baseBuildId": row.build_id} if maintenance else {}),
            "examDate": exam_date_for(db, lecture),
            "title": lecture.title, "sources": [{k: s[k] for k in ("id", "kind", "filename")}
                                                for s in bank_sources(db, lecture)]}


class BankLinksIn(BaseModel):
    share_url: str = Field(alias="shareUrl", max_length=500)
    conversation_url: str = Field(alias="conversationUrl", max_length=500)
    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank/links")
def put_bank_links(subject: str, run_id: str, payload: BankLinksIn,
                   user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        raise HTTPException(404, "먼저 문제은행 대화를 생성하세요.")
    if not valid_share_url(payload.share_url, "chatgpt") or not valid_conversation_url(payload.conversation_url, "chatgpt"):
        raise HTTPException(422, "ChatGPT 공유 링크와 개인 대화 주소를 확인하세요.")
    row.share_url = payload.share_url.strip()
    row.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"shareUrl": row.share_url, "conversationUrl": row.conversation_url}


class GeneratedResponseIn(ResponseIn):
    responded_at: str = Field(alias="respondedAt")


@admin_router.put("/lectures/{subject}/{run_id}/bank-generated-response")
def put_generated_response(subject: str, run_id: str, payload: GeneratedResponseIn,
                           user: CurrentUser = Depends(require_runner),
                           db: Session = Depends(get_db)) -> dict[str, Any]:
    """자동 출제의 원문을 저장한다. 그 사이 저장된 관리자 응답은 덮지 않는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = db.scalars(select(QuizBank).where(QuizBank.subject == lecture.subject,
                                          QuizBank.run_id == lecture.run_id).with_for_update()).first()
    if row is None or _iso(row.responded_at) != payload.responded_at or row.raw_response:
        raise HTTPException(409, "그 사이 새 응답이 저장됐습니다. 새 응답으로 다시 정리하세요.")
    if COMPLETE_MARK not in payload.raw:
        raise HTTPException(422, "완료 표시가 없는 응답입니다.")
    row.raw_response = payload.raw
    row.prompt_version = payload.prompt_version
    row.responded_by = "runner:auto"
    row.message = "자동 출제 완료 — 정리·검증 중"
    db.commit()
    return {"respondedAt": _iso(row.responded_at)}


class BankIn(BaseModel):
    responded_at: str = Field(alias="respondedAt")
    bank: dict | None = None
    validation: dict | None = None
    review: dict | None = None
    pages: dict[str, list[int]] | None = None
    usage: list[dict] | None = None
    message: str = Field(default="", max_length=2000)
    base_build_id: str | None = Field(None, alias="baseBuildId")
    revision: dict | None = None

    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank")
def put_bank(subject: str, run_id: str, payload: BankIn, user: CurrentUser = Depends(require_runner),
             db: Session = Depends(get_db)) -> dict[str, Any]:
    """러너의 결과. **그 사이 관리자가 응답을 다시 저장했으면 거절한다** — 옛 응답의 정리가
    새 응답을 덮으면, 다시 만들라고 누른 사람에게 다시 만들었는데 그대로인 것을 돌려준다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = db.scalars(select(QuizBank).where(QuizBank.subject == subject, QuizBank.run_id == run_id)
                     .with_for_update()).first()
    if row is None or _iso(row.responded_at) != payload.responded_at:
        raise HTTPException(409, "그 사이 새 응답이 저장됐습니다. 새 응답으로 다시 정리하세요.")
    maintenance = payload.base_build_id is not None
    if (row.validation or {}).get("maintenance") and not maintenance:
        raise HTTPException(409, "보강 요청에는 현재 은행을 유지하는 새 러너의 결과가 필요합니다.")
    if maintenance and (row.build_id != payload.base_build_id or not (row.validation or {}).get("maintenance")):
        raise HTTPException(409, "보강 대상이 바뀌었습니다. 현재 은행으로 다시 요청하세요.")
    if payload.bank is None or payload.validation is None:
        if payload.revision is not None:
            row.validation = {**(row.validation or {}), "revision": payload.revision}
        row.status = BANK_READY if maintenance else BANK_FAILED
        if maintenance:
            row.validation = {k: v for k, v in (row.validation or {}).items() if k != "maintenance"}
        row.message = payload.message or "정리에 실패했다"
        db.commit()
        return {"status": row.status}
    source_ids = [s["id"] for s in bank_sources(db, lecture)]
    incoming, checked = bank_edits.reapply(
        payload.bank, payload.validation, row.validation or {}, source_ids)
    if maintenance:
        old_questions = without_retired(row.bank)["questions"]
        incoming_questions = {q["question_id"]: q for q in without_retired(incoming)["questions"]}
        def content(question):
            return {k: v for k, v in question.items() if k != "mcq_mode"} if question is not None else None
        if any(content(incoming_questions.get(q["question_id"])) != content(q) for q in old_questions):
            raise HTTPException(422, "보강은 기존 질문과 정답을 그대로 유지해야 합니다.")
        if not validate_bank(incoming, source_ids)["pass"] or not checked.get("pass"):
            raise HTTPException(422, "보강본의 문항 검증을 통과해야 합니다.")
    row.bank, row.validation = incoming, checked
    row.review = payload.review
    row.pages, row.usage = payload.pages or {}, payload.usage or []
    if (row.validation or {}).get("edits"):
        row.pages = cited_pages(row.bank, "S1")
    if not maintenance:
        row.build_id = uuid.uuid4().hex[:16]
    row.built_at = datetime.now(UTC)
    row.status = BANK_READY if row.validation.get("pass") else BANK_INVALID
    if not maintenance:
        row.open_to_students = row.status == BANK_READY
    row.message = payload.message or (
        "" if row.status == BANK_READY else f"검증 오류 {len(payload.validation.get('errors', []))}건")
    db.commit()
    return {"status": row.status, "buildId": row.build_id}


@admin_router.post("/lectures/{subject}/{run_id}/bank/audit")
def request_bank_audit(subject: str, run_id: str, user: CurrentUser = Depends(require_admin),
                       db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = db.scalars(select(QuizBank).where(QuizBank.subject == subject, QuizBank.run_id == run_id)
                     .with_for_update()).first()
    if row is None:
        raise HTTPException(404, "먼저 문제은행을 준비하세요.")
    _usable(row)
    job = open_job_of(db, subject, run_id, JOB_BANK)
    if job:
        if (row.validation or {}).get("maintenance"):
            return {"jobId": job.id, "created": False}
        raise HTTPException(409, "진행 중인 생성 작업이 끝난 뒤 검증하세요.")
    if not any(s["kind"] == "notes_current" for s in bank_sources(db, lecture)):
        raise HTTPException(400, "원본 올해 필기 PDF가 필요합니다.")
    row.validation = {**(row.validation or {}), "maintenance": {"buildId": row.build_id}}
    job = PrequizJob(subject=subject, run_id=run_id, kind=JOB_BANK, state=JOB_QUEUED, force=True,
                     stage="원본 누락 검증·객관식 보강 대기", requested_by=user.email or user.id, origin=JOB_BUTTON)
    db.add(job)
    db.commit()
    return {"jobId": job.id, "created": True}


@admin_router.post("/lectures/{subject}/{run_id}/bank/runner-audit")
def request_runner_bank_audit(subject: str, run_id: str, user: CurrentUser = Depends(require_runner),
                              db: Session = Depends(get_db)) -> dict:
    """같은 보강 일감을 로컬 러너의 운영 작업에서도 요청한다."""
    return request_bank_audit(subject, run_id, user, db)


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
    return {"summary": summary(db, lecture, row, is_admin=True, user_id=user.id), "bank": row.bank, "validation": row.validation,
            "review": row.review, "pages": row.pages, "usage": row.usage,
            "feedback": [{"id": f.id, "questionId": f.question_id, "category": f.category, "comment": f.comment,
                          "status": f.status, "buildId": f.build_id, "createdAt": _iso(f.created_at)}
                         for f in feedback]}


FEEDBACK_STATUSES = ("open", "resolved", "wontfix")


@admin_router.get("/bank-review")
def bank_review(subject: str | None = None, run_id: str | None = Query(None, alias="runId"),
                all_questions: bool = Query(False, alias="all"),
                user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
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
            review = reviews.get(qid)
            if not all_questions and qid not in dropped and qid not in edits and (
                not review or review["verdict"] == "ok"
            ):
                continue
            cards.append({"question": q, "errors": dropped.get(qid, []),
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
    action: Literal["edit", "accept", "delete", "reset"]
    question: dict | None = None


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
    if row.build_id != payload.build_id or current != payload.expected_question:
        raise HTTPException(409, "문항이 바뀌었습니다. 새로 불러온 뒤 수정하세요.")
    edits = copy.deepcopy(validation.get("edits", {}))
    original = edits.get(question_id, {}).get("original") or without_retired({"questions": [current]})["questions"][0]
    source_ids = [s["id"] for s in bank_sources(db, lecture)]
    candidate_bank = copy.deepcopy(row.bank)
    candidate_validation = copy.deepcopy(validation)
    if payload.action == "reset":
        edits.pop(question_id, None)
        # Restore the original before applying all remaining decisions.
        candidate_bank["questions"] = [q for q in candidate_bank["questions"] if q["question_id"] != question_id]
        candidate_validation["dropped"] = [d for d in validation.get("dropped", []) if d["question_id"] != question_id]
        candidate_validation["edits"] = edits
        candidate_bank["questions"].append(original)
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
        edits[question_id] = {"action": payload.action, "original": original, "question": question,
                              "by": user.email or user.id, "at": datetime.now(UTC).isoformat()}
        if payload.action in ("edit", "accept"):
            errors = bank_edits.question_errors(candidate_bank, candidate_validation, edits, question_id, source_ids)
            if errors:
                raise HTTPException(422, "\n".join(errors))
    clean, checked = bank_edits.with_edits(candidate_bank, candidate_validation, edits, source_ids)
    if not checked["pass"]:
        raise HTTPException(422, "\n".join(checked["errors"]))
    before_questions = {q["question_id"]: q for q in without_retired(row.bank)["questions"]}
    after_questions = {q["question_id"]: q for q in clean["questions"]}
    affected = {qid for qid in before_questions.keys() | after_questions.keys()
                if before_questions.get(qid) != after_questions.get(qid)}
    row.bank, row.validation = clean, checked
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
            "highlighted": f.highlighted,
            "email": emails.get(f.user_id, ""), "createdAt": _iso(f.created_at),
            "stale": bank is None or f.build_id != bank.build_id,
        })
    out = list(groups.values())
    out.sort(key=lambda g: any(r["highlighted"] and r["status"] == "open" for r in g["reports"]), reverse=True)
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


@router.get("/lectures/{subject}/{run_id}/bank/anki")
def download_bank_anki(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db)) -> dict[str, Any]:
    """Explicit offline export; use the same publication gate as web study."""
    from app.bank_anki import ensure_export

    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    _usable(row)
    export = ensure_export(db, lecture, row)
    url = storage_or_503().presign_download(export.key, filename=export.filename)
    record_grabs(db, user.id, [(lecture.subject, lecture.run_id, export.grab_kind)])
    return {"url": url, "filename": export.filename}


def _load_state(db: Session, user: CurrentUser, row: QuizBank) -> BankState:
    """이 사람의 상태. 은행이 새로 만들어졌으면 옛 상태를 밀어 두고 새로 시작한다."""
    state = db.scalars(select(BankState).where(
        BankState.user_id == user.id, BankState.subject == row.subject, BankState.run_id == row.run_id
    ).with_for_update()).first()
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


def _public(q: dict, *, show_choices: bool = True) -> dict:
    out = {**{k: v for k, v in q.items() if k not in ANSWER_FIELDS}, "mcq_mode": choice_mode(q)}
    if not show_choices and out["mcq_mode"] == "recall_first":
        out["options"] = []
    return out


def _served_question(db: Session, row: QuizBank, user_id: str, bank: dict, served: dict) -> dict:
    original = next(q for q in bank["questions"] if q["question_id"] == served["question_id"])
    personal = bank_personal.apply(db, row, user_id, original)
    snapshot = served.get("question_snapshot") or {}
    # Explicit private corrections take effect immediately and disable pools.
    # A reset during the same exposure restores the original authored options.
    if personal.get("personalEdited") or snapshot.get("personalEdited"):
        return personal
    return snapshot or personal


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
    review = next((r for r in bank_edits.current_review(row.review, row.validation)["reviews"]
                   if r["question_id"] == q["question_id"]), None)
    if q.get("personalAnswer"):
        review = None
    # 프롬프트 v1.2(2026-10-05): 충돌은 한 문항으로 합치고 외부 의학지식으로 답을 정한다. 학생은 답을 본 뒤
    # 각 출처가 무엇이라고 하는지와 고른 근거(충돌 기록의 설명)를 읽는다. 자료 밖 내용은 출처 `EXT` 로 표시된다.
    conflict = next((c for c in (row.bank or {}).get("source_conflicts", [])
                     if q["conflict_id"] and c["conflict_id"] == q["conflict_id"]), None)
    return {"answer": q["answer"], "answerUnits": q["answer_units"], "correctOptionIds": q["correct_option_ids"],
            "personalEdited": q.get("personalEdited", False), "personalAnswer": q.get("personalAnswer", False),
            "answerPairs": q["answer_pairs"], "correctOrder": q["correct_order"],
            "slides": _slides(db, row, q["question_id"]), "medicalReview": review,
            "conflict": conflict["description"] if conflict else "",
            "external": any(r["source_id"] == "EXT" for r in q["source_refs"])}


@router.get("/lectures/{subject}/{run_id}/bank")
def read_bank(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
              db: Session = Depends(get_db), target: int = Query(90, ge=50, le=100)) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    out = {"summary": summary(db, lecture, row, is_admin=user.is_admin, user_id=user.id), "examDate": exam_date_for(db, lecture),
           "sizes": engine.DEFAULT["session"]["sizes"], "defaultSize": engine.DEFAULT["session"]["defaultSize"],
           "session": None, "previousSessions": [], "conceptMap": [], "mastery": None, "undoToken": None}
    if row.bank and (row.validation or {}).get("pass"):
        now = engine.now_ms()
        state = db.get(BankState, (user.id, row.subject, row.run_id))
        current = state.state if state and state.build_id == row.build_id else engine.empty_state()
        if state and state.build_id == row.build_id:
            out["session"] = engine.session_summary(row.bank, state.state, now=now)
            out["previousSessions"] = state.state.get("sessions", [])[-5:]
            out["undoToken"] = undo_token(state.state)
        # 개념 지도는 첫 회차 전에도 그린다 — 숙련도가 다 0인 지도가 「무엇을 공부할지」의 답이다.
        out["conceptMap"] = engine.concept_map(row.bank, current, now=now)
        out["mastery"] = for_bank(row, state, is_admin=user.is_admin, now=now)
        out["lectureGoal"] = lecture_goal(row.bank, current, lecture.title, now)
    return out


class StartIn(BaseModel):
    size: int | None = None
    continue_after_goal: bool = Field(False, alias="continueAfterGoal")
    daily_only: bool = Field(False, alias="dailyOnly")


@router.post("/lectures/{subject}/{run_id}/bank/session/start")
def start_bank_session(subject: str, run_id: str, payload: StartIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state = _load_state(db, user, row)
    try:
        started = engine.start_session(bank, state.state, payload.size, engine.now_ms())
        # 재개 요청으로 진행 중 회차의 종료 방식을 덮어쓰지 않는다.
        if (state.state.get("session") or {}).get("status") != "active":
            started["session"]["continue_after_goal"] = payload.continue_after_goal
        if payload.daily_only:
            # 모아 풀기는 열린 회차도 문항 수 제한 없이 오늘 분량까지만 이어간다.
            started["session"].update(size=None, continue_after_goal=False)
        _save(state, started)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return engine.session_summary(bank, state.state, now=engine.now_ms())


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
    return engine.session_summary(bank, state.state, now=engine.now_ms())


@router.post("/lectures/{subject}/{run_id}/bank/next")
def next_bank_question(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db), target: int = Query(90, ge=50, le=100),
                       shuffle: bool = False, choice_protocol: bool = Query(False, alias="choiceProtocol")) -> dict[str, Any]:
    """다음 문항. **이미 내준 문항이 있으면 그것을 다시 준다** — 새로고침이 문항을 넘기지 않는다."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    now = engine.now_ms()
    state = engine.upgrade_state(bank, state_row.state, engine.DEFAULT, now)
    if not state.get("session"):
        state = engine.start_session(bank, state, None, now)
    if state["session"]["status"] == "complete":
        _save(state_row, state)
        db.commit()
        return {"question": None, "summary": engine.session_summary(bank, state, now=now), "undoToken": undo_token(state)}
    exam = exam_date_for(db, lecture)
    by_id = {q["question_id"]: q for q in bank["questions"]}
    served = state.get("served")
    goal = lecture_goal(bank, state, lecture.title, now)
    if served and served["question_id"] in by_id:
        question = by_id[served["question_id"]]
        days = engine.days_until(exam, now)
    else:
        extra_today = state["session"].get("continue_after_goal") and day_start(
            state["session"]["started_at"]) == day_start(now)
        if goal and goal["met"] and not extra_today:
            state = engine.end_session(bank, state, "lecture_goal_met", now)
            _save(state_row, state)
            db.commit()
            return {"question": None, "summary": engine.session_summary(bank, state, now=now),
                    "lectureGoal": goal, "reason": "lecture_goal_met", "undoToken": undo_token(state)}
        picked = (engine.select_question(bank, state, exam, now, prefer_unseen=True) if goal["met"] and extra_today
                  else select_daily_question(bank, state, exam, now, shuffle=shuffle))
        question, days = picked["question"], picked["days"]
        if question is None:
            if not goal["met"]:
                _save(state_row, state)
                db.commit()
                return {"question": None, "waiting": True, "lectureGoal": goal,
                        "session": engine.session_summary(bank, state, now=now),
                        "reason": picked["reason"], "retryAt": picked["retry_at"], "undoToken": undo_token(state)}
            state = engine.end_session(bank, state, "no_eligible_question", now)
            _save(state_row, state)
            db.commit()
            return {"question": None, "summary": engine.session_summary(bank, state, now=now),
                    "reason": picked["reason"], "retryAt": picked["retry_at"], "undoToken": undo_token(state)}
        score = next((r for r in picked["ranked"] if r["question_id"] == question["question_id"]), None)
        served = {"question_id": question["question_id"], "token": uuid.uuid4().hex, "revealed": False,
                  "choice_protocol": bool(choice_protocol),
                  "presented_at": now, "policy_version": engine.DEFAULT["version"],
                  "policy_hash": engine.policy_hash(engine.DEFAULT), "score": score}
        state["served"] = served
    if choice_protocol and not served.get("choice_protocol"):
        # 구 화면에서 이미 보던 선지는 숨기지 않는다. 새 문항부터 인출 단계를 적용한다.
        served.update(choice_protocol=True, choices_shown=True)
    if "question_snapshot" not in served:
        question = bank_personal.apply(db, row, user.id, question)
        review = next((r for r in bank_edits.current_review(row.review, row.validation)["reviews"]
                       if r["question_id"] == question["question_id"]), None)
        previous = state.setdefault("choice_variants", {}).get(question["question_id"])
        question = realize_choices({**question, "medicalReview": review}, served["token"], previous)
        question.pop("medicalReview", None)
        served["question_snapshot"] = question
        if question.get("choice_variant"):
            state["choice_variants"][question["question_id"]] = question["choice_variant"]
    question = _served_question(db, row, user.id, bank, served)
    mark_seen(state, question["question_id"])
    _save(state_row, state)
    db.commit()
    choices_shown = not served.get("choice_protocol") or choice_mode(question) != "recall_first" or served.get("choices_shown", False) or served.get("revealed", False)
    return {"question": _public(question, show_choices=choices_shown), "choicesShown": choices_shown,
            "reviewToken": served["token"], "days": days, "examDate": exam,
            "lectureGoal": goal, "undoToken": undo_token(state),
            "preloadSlides": _slides(db, row, question["question_id"]),
            "session": engine.session_summary(bank, state, now=now),
            "answer": _answer(db, row, question) if served.get("revealed") else None}


class TokenIn(BaseModel):
    review_token: str = Field(alias="reviewToken")

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/options")
def show_bank_options(subject: str, run_id: str, payload: TokenIn,
                      user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    state = dict(state_row.state)
    served = dict(state.get("served") or {})
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    question = _served_question(db, row, user.id, bank, served)
    served["choices_shown"] = True
    served.setdefault("choices_shown_at", engine.now_ms())
    state["served"] = served
    _save(state_row, state)
    db.commit()
    return {"question": _public(question), "choicesShown": True}


@router.post("/lectures/{subject}/{run_id}/bank/prepare")
def prepare_bank_answer(subject: str, run_id: str, payload: TokenIn,
                        user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    """Read-only warmup for the served question; /reveal still records the actual click."""
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = db.get(BankState, (user.id, row.subject, row.run_id))
    if state_row is None or state_row.build_id != row.build_id:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    served = state_row.state.get("served") or {}
    if served.get("token") != payload.review_token:
        raise HTTPException(409, "현재 학습 문항이 아닙니다.")
    question = _served_question(db, row, user.id, bank, served)
    return _answer(db, row, question)


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
    question = _served_question(db, row, user.id, bank, served)
    if served.get("choice_protocol") and choice_mode(question) == "recall_first" and not served.get("choices_shown") and not served.get("revealed"):
        raise HTTPException(409, "먼저 답을 떠올린 뒤 선지를 공개하세요.")
    served["revealed"] = True
    served.setdefault("revealed_at", engine.now_ms())
    state["served"] = served
    _save(state_row, state)
    db.commit()
    question = _served_question(db, row, user.id, bank, served)
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
    remember_review(state, nxt)
    last = nxt["history"][-1]
    last["score_breakdown"] = served.get("score")
    last["selection_policy_version"] = served.get("policy_version")
    presented = served.get("presented_at")
    last["response_time_sec"] = max(0, (served.get("revealed_at", now) - presented) / 1000) if presented else None
    summary_now = engine.session_summary(bank, nxt, now=now)
    limit = nxt["session"]["size"]
    if summary_now and limit is not None and summary_now["reviewed"] >= limit:
        nxt = engine.end_session(bank, nxt, "size_reached", now)
    _save(state_row, nxt)
    db.commit()
    return {"reviews": len(nxt["history"]), "session": engine.session_summary(bank, nxt, now=now)}


@router.post("/lectures/{subject}/{run_id}/bank/undo")
def undo_bank_answer(subject: str, run_id: str, payload: TokenIn,
                     user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _usable(row)
    state_row = _load_state(db, user, row)
    try:
        state = undo_review(state_row.state, payload.review_token)
    except ValueError as cause:
        raise HTTPException(409, str(cause)) from cause
    served = state["served"]
    served["token"] = uuid.uuid4().hex  # Discard any tokens held by other tabs before undo.
    question = _served_question(db, row, user.id, bank, served)
    now = engine.now_ms()
    _save(state_row, state)
    db.commit()
    exam = exam_date_for(db, lecture)
    return {"question": _public(question), "reviewToken": served["token"], "undoToken": undo_token(state),
            "days": engine.days_until(exam, now), "examDate": exam,
            "lectureGoal": lecture_goal(bank, state, lecture.title, now),
            "session": engine.session_summary(bank, state, now=now), "answer": _answer(db, row, question),
            "preloadSlides": _slides(db, row, question["question_id"])}


class FeedbackIn(BaseModel):
    question_id: str = Field(alias="questionId", max_length=64)
    category: Literal[FEEDBACK_CATEGORIES]  # type: ignore[valid-type]
    comment: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


def _personal_source(db: Session, subject: str, run_id: str, question_id: str, user: CurrentUser):
    row = _bank_or_404(db, lecture_or_404(db, subject, run_id), user)
    bank = _usable(row)
    question = next((q for q in bank["questions"] if q["question_id"] == question_id), None)
    if question is None:
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    return row, question


@router.get("/lectures/{subject}/{run_id}/bank/questions/{question_id}/personal")
def read_personal_question(subject: str, run_id: str, question_id: str,
                          user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row, original = _personal_source(db, subject, run_id, question_id, user)
    current = bank_personal.apply(db, row, user.id, original)
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id))
    valid = edit is not None and bank_personal.same_source(edit.original, original)
    return {"original": {"question": original["question"], "answer": original["answer"]},
            "draft": {"question": current["question"], "answer": current["answer"]},
            "edited": valid, "comment": edit.comment if valid else "", "revision": bank_personal.revision(original)}


class PersonalEditIn(BaseModel):
    action: Literal["save", "reset"] = "save"
    revision: str = Field(min_length=64, max_length=64)
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    report: bool = False
    category: Literal[FEEDBACK_CATEGORIES] = "content"  # type: ignore[valid-type]
    comment: str = Field(default="", max_length=2000)


@router.put("/lectures/{subject}/{run_id}/bank/questions/{question_id}/personal")
def save_personal_question(subject: str, run_id: str, question_id: str, payload: PersonalEditIn,
                          user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    row, original = _personal_source(db, subject, run_id, question_id, user)
    if payload.revision != bank_personal.revision(original):
        raise HTTPException(409, "공용 문항이 바뀌었습니다. 수정창을 다시 열어 주세요.")
    question, answer = payload.question.strip(), payload.answer.strip()
    if not question or not answer:
        raise HTTPException(422, "발문과 정답을 비워 둘 수 없습니다.")
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id))
    changed = question != original["question"] or answer != original["answer"]
    if payload.action == "reset" or (not changed and not payload.comment.strip()):
        if edit:
            db.delete(edit)
    else:
        if edit is None:
            edit = BankPersonalEdit(user_id=user.id, subject=subject, run_id=run_id, question_id=question_id)
            db.add(edit)
        edit.original, edit.question, edit.answer = original, question, answer
        edit.comment = payload.comment.strip()
    if payload.action == "save":
        comment = payload.comment.strip()
        correction = None
        if changed:
            comment += f"\n\n[개인 수정 제안]\n발문: {question}\n정답: {answer}"
            correction = {"original": original, "proposed": {"question": question, "answer": answer},
                          "changedFields": [key for key, value in (("question", question), ("answer", answer))
                                            if value != original[key]]}
        db.add(BankFeedback(user_id=user.id, subject=subject, run_id=run_id, build_id=row.build_id,
                            question_id=question_id, category=payload.category, comment=comment.strip(),
                            highlighted=payload.report, correction=correction))
    db.commit()
    current = bank_personal.apply(db, row, user.id, original)
    return {"question": _public(current), "answer": _answer(db, row, current),
            "reported": payload.action == "save", "highlighted": payload.report and payload.action == "save"}


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


class BatchLectureIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    run_id: str = Field(alias="runId", min_length=1, max_length=32)


class BatchIn(BaseModel):
    lectures: list[BatchLectureIn] = Field(min_length=1, max_length=100)
    resume_lecture: BatchLectureIn | None = Field(None, alias="resumeLecture")


class BatchUndoIn(BatchIn):
    review_token: str = Field(alias="reviewToken")


def _batch_entries(payload: BatchIn, user: CurrentUser, db: Session) -> list[dict]:
    now, entries = engine.now_ms(), []
    keys = list(dict.fromkeys((ref.subject, ref.run_id) for ref in payload.lectures))
    rows = db.execute(select(Lecture, QuizBank, BankState).outerjoin(QuizBank, and_(
        QuizBank.subject == Lecture.subject, QuizBank.run_id == Lecture.run_id)).outerjoin(BankState, and_(
        BankState.subject == Lecture.subject, BankState.run_id == Lecture.run_id, BankState.user_id == user.id))
        .where(tuple_(Lecture.subject, Lecture.run_id).in_(keys))).all()
    by_key = {(lecture.subject, lecture.run_id): (lecture, row, state_row) for lecture, row, state_row in rows}
    for key in keys:
        if key not in by_key:
            raise HTTPException(404, "선택한 강의를 찾을 수 없습니다.")
        lecture, row, state_row = by_key[key]
        if row is None or not user.is_admin and not row.open_to_students:
            raise HTTPException(404, "선택한 강의에 공개된 문제은행이 없습니다.")
        bank = _usable(row)
        state = state_row.state if state_row and state_row.build_id == row.build_id else engine.empty_state()
        entries.append({"key": key, "lecture": lecture, "row": row, "bank": bank, "state": state,
                        "goal": lecture_goal(bank, state, lecture.title, now)})
    return entries


def _refresh_batch_entry(entry: dict, user: CurrentUser, db: Session) -> None:
    state_row = db.get(BankState, (user.id, *entry["key"]))
    entry["state"] = state_row.state if state_row else engine.empty_state()
    entry["goal"] = lecture_goal(entry["bank"], entry["state"], entry["lecture"].title, engine.now_ms())


def _batch_undo(entries: list[dict]) -> tuple[dict | None, str | None]:
    available = [(entry, undo_token(entry["state"])) for entry in entries]
    available = [(entry, token) for entry, token in available if token]
    if not available:
        return None, None
    return max(available, key=lambda pair: pair[0]["state"]["history"][-1]["timestamp"])


def _batch_reply(next_question: dict, entries: list[dict], chosen: dict | None) -> dict:
    previous, token = _batch_undo(entries)
    lecture = chosen["lecture"] if chosen else None
    return {**next_question, "undoToken": token,
            "lecture": {"subject": lecture.subject, "runId": lecture.run_id, "title": lecture.title} if lecture else None,
            "batchGoal": aggregate_goal(entries, day_start(engine.now_ms())),
            "undoLecture": {"subject": previous["key"][0], "runId": previous["key"][1]} if previous else None}


@router.post("/bank/batch/next")
def next_batch_question(payload: BatchIn, user: CurrentUser = Depends(require_approved_user),
                         db: Session = Depends(get_db)) -> dict:
    entries = _batch_entries(payload, user, db)
    goal = aggregate_goal(entries, day_start(engine.now_ms()))
    if goal["met"]:
        for entry in entries:
            state_row = db.get(BankState, (user.id, *entry["key"]))
            if state_row and state_row.build_id == entry["row"].build_id:
                _save(state_row, engine.end_session(entry["bank"], state_row.state, "lecture_goal_met", engine.now_ms()))
        db.commit()
        for entry in entries:
            _refresh_batch_entry(entry, user, db)
        return _batch_reply({"question": None, "summary": None, "reason": "lecture_goal_met"}, entries, None)
    resume = (payload.resume_lecture.subject, payload.resume_lecture.run_id) if payload.resume_lecture else None
    chosen = next((entry for entry in entries if entry["key"] == resume and entry["goal"]["remaining"]
                   and (entry["state"].get("served") or {}).get("question_id") in {
                       u["key"] for u in daily_units(entry["bank"], entry["state"], engine.now_ms()) if u["status"] == "pending"}), None)
    chosen = chosen or choose_lecture(entries, resume)
    if chosen is None:
        raise HTTPException(409, "남은 문항을 선택할 수 없습니다. 강의 목록을 다시 확인하세요.")
    state_row = _load_state(db, user, chosen["row"])
    state = engine.start_session(chosen["bank"], state_row.state, None, engine.now_ms())
    state["session"].update(size=None, continue_after_goal=False)
    pending = {u["key"] for u in daily_units(chosen["bank"], state, engine.now_ms()) if u["status"] == "pending"}
    if state.get("served") and state["served"]["question_id"] not in pending:
        state["served"] = None
    _save(state_row, state)
    db.commit()
    got = next_bank_question(*chosen["key"], user=user, db=db, target=90, shuffle=True, choice_protocol=True)
    _refresh_batch_entry(chosen, user, db)
    return _batch_reply(got, entries, chosen)


@router.post("/bank/batch/undo")
def undo_batch_question(payload: BatchUndoIn, user: CurrentUser = Depends(require_approved_user),
                         db: Session = Depends(get_db)) -> dict:
    entries = _batch_entries(payload, user, db)
    chosen, token = _batch_undo(entries)
    if chosen is None or token != payload.review_token:
        raise HTTPException(409, "모아 풀기의 마지막 평가가 아닙니다.")
    got = undo_bank_answer(*chosen["key"], TokenIn(reviewToken=token), user=user, db=db)
    _refresh_batch_entry(chosen, user, db)
    return _batch_reply(got, entries, chosen)


@router.post("/bank/batch/session/end")
def end_batch_session(payload: BatchIn, user: CurrentUser = Depends(require_approved_user),
                       db: Session = Depends(get_db)) -> dict:
    entries = _batch_entries(payload, user, db)
    for entry in entries:
        state_row = db.get(BankState, (user.id, *entry["key"]))
        if state_row and state_row.build_id == entry["row"].build_id:
            _save(state_row, engine.end_session(entry["bank"], state_row.state, "user_finished", engine.now_ms()))
    db.commit()
    return {"batchGoal": aggregate_goal(entries, day_start(engine.now_ms()))}
