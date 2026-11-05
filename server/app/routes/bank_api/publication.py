"""Admin/runner response ingestion, publication, audit, and visibility."""
from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_edits, bank_retention, bank_shared_response
from app.auth import CurrentUser, require_admin, require_runner
from studyez_contracts.bank.response_file import (
    required as markdown_file_required, validate as validate_markdown_file,
    is_json,
)
from app.bank_validation.pages import cited_pages
from app.bank_validation.publication import stamp as publication_stamp, usable as bank_usable
from app.bank_validation.schema import without_retired
from app.database import get_db
from app.jobs.queue import open_job_of
from app.models import (
    BANK_BUILDING, BANK_FAILED, BANK_INVALID, BANK_READY, BANK_RESPONDED, BankFeedback, JOB_BANK,
    JOB_BUTTON, JOB_QUEUED, PrequizJob, QuizBank, QuizBankArchive,
)
from app.preview_links import conversation_url as valid_conversation_url, share_url as valid_share_url
from app.routes.common import lecture_or_404

from .common import _iso, _save_share_link, _usable, bank_sources, exam_date_for, summary


admin_router = APIRouter()


COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE"


class ResponseFileIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    byte_length: int = Field(ge=200, le=8_000_000, alias='byteLength')
    model_config = {"populate_by_name": True}


class ResponseIn(BaseModel):
    raw: str = Field(min_length=200, max_length=2_000_000)
    source: Literal['extension', 'manual'] = 'extension'
    conversation_url: str = Field(default="", alias="conversationUrl", max_length=500)
    share_url: str | None = Field(default=None, alias="shareUrl", max_length=500)
    prompt_version: str = Field(default="", alias="promptVersion", max_length=16)
    response_file: ResponseFileIn | None = Field(default=None, alias='responseFile')

    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank-response")
def put_bank_response(subject: str, run_id: str, payload: ResponseIn,
                      user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """확장이 ChatGPT 탭에서 받아 온 응답 원문. 저장하면 러너가 정리할 일감이 선다."""
    lecture = lecture_or_404(db, subject, run_id)
    db.refresh(lecture, with_for_update=True)
    from app.routes.root_generation import pending_for_lecture
    if pending_for_lecture(db, subject, run_id):
        raise HTTPException(409, 'Concept map 자동출제 작업이 있습니다. 완료하거나 취소한 뒤 웹 응답을 저장하세요.')
    file_info = None
    file_required = markdown_file_required(subject, run_id, payload.prompt_version)
    if payload.response_file is not None or is_json(payload.raw) or 'STUDYEZ_BANK_FILE' in payload.raw or file_required:
        if payload.response_file is None:
            raise HTTPException(422, '실제 문제은행 JSON 파일을 불러와 저장하세요. 기존 판의 MD도 읽을 수 있습니다.')
        try:
            file_info = validate_markdown_file(payload.raw, payload.response_file.filename, subject, run_id,
                                              payload.response_file.model_dump(by_alias=True))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if payload.prompt_version and payload.prompt_version != file_info['promptVersion']:
            raise HTTPException(422, '파일과 요청의 프롬프트 버전이 다릅니다.')
        payload.prompt_version = file_info['promptVersion']
    if file_info is None and not payload.raw.rstrip().endswith(COMPLETE_MARK):
        raise HTTPException(422, "완료 표시가 없는 응답입니다. 답이 끝난 뒤 다시 저장하세요.")
    if not valid_conversation_url(payload.conversation_url, "chatgpt") or (
            payload.share_url is not None and not valid_share_url(payload.share_url, "chatgpt")):
        raise HTTPException(422, "ChatGPT 공유 링크와 개인 대화 주소를 확인하세요.")
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    job = open_job_of(db, lecture.subject, lecture.run_id, JOB_BANK)
    if row is not None and bank_shared_response.manual(row) and payload.source != 'manual' and row.raw_response != payload.raw:
        raise HTTPException(409, '직접 저장한 답변을 우선합니다. 새 답변은 직접 붙여 넣어 저장하세요.')
    if row is not None and row.raw_response == payload.raw:
        # A legacy extension may deliver the same answer first without metadata.
        # Filling it in must not queue another job or invalidate a running build.
        if not row.prompt_version and payload.prompt_version.strip():
            if job is not None and job.state == "running":
                raise HTTPException(409, "검수 중에는 프롬프트 버전을 바꿀 수 없습니다. 완료 후 다시 전달하세요.")
            row.prompt_version = payload.prompt_version.strip()
        if payload.source == 'manual':
            row.responded_by = f'manual:{user.email or user.id}'
        if file_info:
            row.validation = {**(row.validation or {}), 'responseFile': file_info}
        _save_share_link(row, payload.share_url)
        if "conversation_url" in payload.model_fields_set:
            row.conversation_url = payload.conversation_url.strip()
        db.commit()
        return {"status": row.status, "respondedAt": _iso(row.responded_at),
                "jobId": job.id if job else None, "reused": True}
    if job is not None and job.state == "running":
        raise HTTPException(409, "이전 문항을 검수 중입니다. 완료 후 새 응답을 다시 전달합니다.")
    if row is None:
        row = QuizBank(subject=lecture.subject, run_id=lecture.run_id)
        db.add(row)
    row.raw_response = payload.raw
    row.validation = {k: v for k, v in (row.validation or {}).items() if k != 'responseFile'}
    if file_info:
        row.validation['responseFile'] = file_info
    if (row.validation or {}).get("revision"):
        row.validation = {k: v for k, v in row.validation.items() if k != "revision"}
    # 새 원문에는 이전 보강 요청을 이어 붙이지 않는다.
    if (row.validation or {}).get("maintenance"):
        row.validation = {k: v for k, v in row.validation.items() if k != "maintenance"}
    _save_share_link(row, payload.share_url)
    if "conversation_url" in payload.model_fields_set:
        row.conversation_url = payload.conversation_url.strip()
    row.prompt_version = payload.prompt_version
    row.responded_by = f'manual:{user.email or user.id}' if payload.source == 'manual' else user.email or user.id
    row.responded_at = datetime.now(UTC)
    row.status = BANK_RESPONDED
    row.message = "응답을 받았다 — 러너가 정리한다"
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
    from app.routes.root_generation import pending_for_lecture
    explicit_generation = pending_for_lecture(db, subject, run_id)
    if explicit_generation:
        return explicit_generation
    row = db.get(QuizBank, (lecture.subject, lecture.run_id))
    if row is None:
        raise HTTPException(404, "저장된 ChatGPT 응답이 없습니다.")
    if not bank_shared_response.pending(row):
        row.status = BANK_BUILDING
        row.message = "러너가 정리하는 중"
    db.commit()
    maintenance = (row.validation or {}).get("maintenance")
    return {"raw": row.raw_response, "respondedAt": _iso(row.responded_at), "promptVersion": row.prompt_version,
            "responseFile": (row.validation or {}).get('responseFile'),
            "shareUrl": row.share_url, "importShare": bank_shared_response.pending(row),
            "responseSource": "manual" if bank_shared_response.manual(row) else "link",
            "publishedCurrent": bool(row.bank and row.built_at and row.responded_at and row.built_at >= row.responded_at and row.open_to_students),
            **({"existingBank": row.bank, "baseBuildId": row.build_id} if maintenance else {}),
            "examDate": exam_date_for(db, lecture),
            "title": lecture.title, "sources": [{k: s[k] for k in ("id", "kind", "filename")}
                                                for s in bank_sources(db, lecture)]}


@admin_router.get("/lectures/{subject}/{run_id}/bank/source-context")
def get_bank_source_context(subject: str, run_id: str, user: CurrentUser = Depends(require_runner),
                            db: Session = Depends(get_db)) -> dict[str, Any]:
    """Independent point preparation receives original source metadata only."""
    lecture = lecture_or_404(db, subject, run_id)
    sources = [{k: s[k] for k in ("id", "kind", "filename")} for s in bank_sources(db, lecture)]
    if not any(s["kind"] == "notes_current" for s in sources):
        raise HTTPException(400, "올해 강의록이 아직 없습니다.")
    return {"title": lecture.title, "sources": sources}


class BankLinksIn(BaseModel):
    share_url: str | None = Field(default=None, alias="shareUrl", max_length=500)
    conversation_url: str | None = Field(default=None, alias="conversationUrl", max_length=500)
    model_config = {"populate_by_name": True}


@admin_router.put("/lectures/{subject}/{run_id}/bank/links")
def put_bank_links(subject: str, run_id: str, payload: BankLinksIn,
                   user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    if (payload.share_url is not None and not valid_share_url(payload.share_url, "chatgpt")) or (
            payload.conversation_url is not None and not valid_conversation_url(payload.conversation_url, "chatgpt")):
        raise HTTPException(422, "ChatGPT 공유 링크와 개인 대화 주소를 확인하세요.")
    # 첫 두 링크가 동시에 도착해도 같은 강의의 은행을 한 번만 만든다.
    db.refresh(lecture, with_for_update=True)
    from app.routes.root_generation import pending_for_lecture
    if pending_for_lecture(db,subject,run_id):
        return {'preserved':True,'message':'뿌리 자동출제 링크는 완성 파일과 함께 보존합니다.'}
    row = db.scalars(select(QuizBank).where(QuizBank.subject == subject, QuizBank.run_id == run_id)
                     .with_for_update()).first()
    if row is None:
        row = QuizBank(subject=lecture.subject, run_id=lecture.run_id, status="linked")
        db.add(row)
    # 독립적으로 도착하는 두 링크가 서로 덮어쓰지 않는다. 빈 문자열은 명시적 삭제다.
    changed_share = bool(not bank_shared_response.manual(row) and not bank_shared_response.file_source(row) and payload.share_url is not None and payload.share_url.strip() and (payload.share_url.strip() != row.share_url or bank_shared_response.pending(row)))
    job = open_job_of(db, lecture.subject, lecture.run_id, JOB_BANK) if changed_share else None
    if job is not None and job.state == 'running':
        raise HTTPException(409, '검수 중입니다. 완료 후 새 공유 링크를 다시 저장합니다.')
    _save_share_link(row, payload.share_url)
    if changed_share and job is None:
        db.add(PrequizJob(subject=lecture.subject, run_id=lecture.run_id, kind=JOB_BANK,
                         state=JOB_QUEUED, origin=JOB_BUTTON, requested_by=user.email or user.id,
                         stage='저장된 공유 링크에서 완성 응답 가져오기'))
    if payload.conversation_url is not None:
        row.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"shareUrl": row.share_url, "conversationUrl": row.conversation_url}


class SharedResponseIn(BaseModel):
    raw: str = Field(min_length=200, max_length=2_000_000)
    share_url: str = Field(alias='shareUrl', max_length=500)
    expected_responded_at: str | None = Field(alias='expectedRespondedAt')
    expected_raw_hash: str = Field(alias='expectedRawHash', pattern=r'^[a-f0-9]{64}$')
    extraction_strategy: str = Field(alias='extractionStrategy', max_length=100)


@admin_router.get('/lectures/{subject}/{run_id}/bank/shared-source')
def get_bank_shared_source(subject: str, run_id: str, user: CurrentUser = Depends(require_runner),
                           db: Session = Depends(get_db)):
    lecture_or_404(db, subject, run_id)
    row = db.get(QuizBank, (subject, run_id))
    if row is None:
        raise HTTPException(404, '저장된 공유 응답이 없습니다.')
    return {'raw': row.raw_response, 'respondedAt': _iso(row.responded_at),
            'responseFile': (row.validation or {}).get('responseFile'),
            'responseSource': 'manual' if bank_shared_response.manual(row) else 'link',
            'shareUrl': row.share_url, 'importShare': bank_shared_response.pending(row),
            'publishedCurrent': bool(row.bank and row.built_at and row.responded_at and row.built_at >= row.responded_at and row.open_to_students)}


@admin_router.put('/lectures/{subject}/{run_id}/bank-shared-response')
def put_bank_shared_response(subject: str, run_id: str, payload: SharedResponseIn,
                             user: CurrentUser = Depends(require_runner), db: Session = Depends(get_db)):
    lecture = lecture_or_404(db, subject, run_id)
    db.refresh(lecture, with_for_update=True)
    row = db.get(QuizBank, (subject, run_id))
    if row is None or not valid_share_url(payload.share_url, 'chatgpt') or (payload.raw != row.raw_response and not payload.raw.rstrip().endswith(COMPLETE_MARK)):
        raise HTTPException(422, '저장된 공유 링크와 완성 응답을 확인하세요.')
    return bank_shared_response.store(db, row, payload, user.email or user.id)


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
    allow_unresolved: bool = Field(False, alias='allowUnresolved')

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
        # 실패 뒤 러너가 같은 일감을 재시도해도 보강 의도를 유지한다.
        # 새 ChatGPT 원문을 저장하는 명시적인 재생성 경로에서만 이 표시를 지운다.
        row.message = payload.message or "정리에 실패했다"
        db.commit()
        return {"status": row.status}
    source_ids = [s["id"] for s in bank_sources(db, lecture)]
    incoming, checked = bank_edits.reapply(
        payload.bank, payload.validation, row.validation or {}, source_ids)
    if payload.revision is not None:
        checked = {**checked, 'revision': payload.revision}
    checked = publication_stamp(incoming, checked, source_ids, allow_unresolved=payload.allow_unresolved)
    if (row.validation or {}).get('responseFile'):
        checked = {**checked, 'responseFile': row.validation['responseFile']}
    if maintenance:
        old_questions = without_retired(row.bank)["questions"]
        incoming_questions = {q["question_id"]: q for q in without_retired(incoming)["questions"]}
        def content(question):
            return {k: v for k, v in question.items() if k != "mcq_mode"} if question is not None else None
        if any(content(incoming_questions.get(q["question_id"])) != content(q) for q in old_questions):
            raise HTTPException(422, "보강은 기존 질문과 정답을 그대로 유지해야 합니다.")
        if not bank_usable(incoming, checked):
            raise HTTPException(422, "보강본의 문항 검증을 통과해야 합니다.")
    if (row.validation or {}).get('excludedQuestions'):
        checked['excludedQuestions'] = copy.deepcopy(row.validation['excludedQuestions'])
    new_build = row.build_id if maintenance else uuid.uuid4().hex[:16]
    bank_retention.replace_bank(db, row, incoming, new_build)
    row.validation = checked
    row.review = payload.review
    row.pages, row.usage = payload.pages or {}, payload.usage or []
    if (row.validation or {}).get("edits"):
        row.pages = cited_pages(row.bank, "S1")
    row.built_at = datetime.now(UTC)
    row.status = BANK_READY if bank_usable(row.bank, row.validation) else BANK_INVALID
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


@admin_router.delete("/lectures/{subject}/{run_id}/bank")
def delete_bank(subject: str, run_id: str, version: str = Query(..., min_length=1),
                user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = db.scalars(select(QuizBank).where(QuizBank.subject == lecture.subject,
                     QuizBank.run_id == lecture.run_id).with_for_update()).first()
    if row is None:
        raise HTTPException(404, "삭제할 퀴즈가 없습니다.")
    if _iso(row.updated_at) != version:
        raise HTTPException(409, "퀴즈가 변경됐습니다. 목록을 새로고침한 뒤 다시 삭제하세요.")
    if open_job_of(db, lecture.subject, lecture.run_id, JOB_BANK):
        raise HTTPException(409, "생성·검증 작업이 진행 중입니다. 작업을 끝내거나 취소한 뒤 삭제하세요.")
    snapshot = {column.name: (_iso(value) if isinstance(value, datetime) else value)
                for column in QuizBank.__table__.columns
                for value in [getattr(row, column.name)]}
    archive = QuizBankArchive(subject=lecture.subject, run_id=lecture.run_id,
                              deleted_by=user.id, snapshot=snapshot)
    db.add(archive)
    db.delete(row)
    # Archive and removal are atomic. History, personal edits, and sources belong to the lecture.
    db.commit()
    return {"deleted": True, "archiveId": archive.id}


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
