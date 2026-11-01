"""Small live checklist: verified web completion and accepted quiz upload dates."""
from datetime import UTC, datetime, timedelta
from typing import Literal
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session
from app.auth import CurrentUser, require_approved_user, require_runner
from app.database import get_db
from app.models import Lecture, QuizBank, PrequizJob
from app.models.quiz_publication import QuizPublicationCheck
from app.routes.bank import valid_share_url
from app.bank_shared_response import file_source, manual as manual_source

router = APIRouter()
CUTOFF = datetime(2026, 10, 14, 15, tzinfo=UTC)  # 10/15 00:00 KST, inclusive


def utc(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


def rows(db: Session, is_admin: bool):
    # 직접 저장하거나 검증한 파일 응답은 링크 모니터의 실패 결과보다 우선한다.
    manual = {row.run_id: row for row in db.scalars(select(QuizBank).where(
        QuizBank.subject == '약리학', or_(QuizBank.responded_by.startswith('manual:'),
            QuizBank.validation['responseFile']['validated'].as_boolean() == True),
        QuizBank.raw_response != '')) if manual_source(row) or file_source(row)}
    records = db.execute(select(Lecture.run_id, Lecture.title, QuizBank.share_url,
        QuizBank.built_at, QuizBank.responded_at, QuizBank.open_to_students,
        func.json_array_length(QuizBank.bank['questions']), QuizPublicationCheck.share_url,
        QuizPublicationCheck.result, QuizPublicationCheck.checked_at).select_from(Lecture)
        .outerjoin(QuizBank, (QuizBank.subject == Lecture.subject) & (QuizBank.run_id == Lecture.run_id))
        .outerjoin(QuizPublicationCheck, (QuizPublicationCheck.subject == Lecture.subject) & (QuizPublicationCheck.run_id == Lecture.run_id))
        .where(Lecture.subject == '약리학').order_by(Lecture.date, Lecture.slot)).all()
    jobs = db.scalars(select(PrequizJob).where(PrequizJob.subject == '약리학', PrequizJob.kind == 'bank')
                      .order_by(PrequizJob.id.desc())).all()
    latest = {}
    for job in jobs:
        latest.setdefault(job.run_id, job)
    result = []
    for rid, title, url, built, responded, opened, count, checked_url, proof, checked in records:
        proof = proof if url and checked_url == url else None
        completed = datetime.fromisoformat(proof['completedAt']) if proof and proof.get('completedAt') else None
        link_state = proof['state'] if proof else ('unchecked' if url else 'missing')
        saved = manual.get(rid)
        if saved:
            completed = utc(saved.responded_at)
            link_state = 'complete' if saved.raw_response.rstrip().endswith('STUDYEZ_BANK_COMPLETE') else 'incomplete'
            ids = re.findall(r'(?m)^#{1,6}\s+(Q[\w-]+)\s*\|', saved.raw_response)
            proof = {'questionCount': len(set(ids))}
            checked = saved.responded_at
        recent = bool(completed and utc(completed) >= CUTOFF)
        uploaded = bool(built and utc(built) >= CUTOFF and count and (is_admin or opened))
        current = bool(uploaded and responded and utc(built) >= utc(responded))
        job = latest.get(rid)
        result.append({'subject': '약리학', 'runId': rid, 'title': title,
            **({'shareUrl': url or ''} if is_admin else {}),
            'responseSource': 'file' if saved and file_source(saved) else 'manual' if saved else 'link',
            'link': {'state': link_state, 'sinceCutoff': bool(link_state == 'complete' and recent),
                     'completedAt': completed.isoformat() if completed else None,
                     'questionCount': proof.get('questionCount', 0) if proof else 0,
                     'checkedAt': utc(checked).isoformat() if proof and checked else None},
            'upload': {'sinceCutoff': uploaded, 'current': current,
                       'builtAt': utc(built).isoformat() if built and (is_admin or opened) else None},
            'job': {'state': job.state, 'stage': job.stage if job.state in ('queued', 'running', 'held') else ''} if job else None})
    return {'cutoff': CUTOFF.isoformat(), 'lectures': result}


@router.get('/timetable/quiz-publication')
def read_publication(user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    return rows(db, user.is_admin)


@router.get('/admin/quiz-publication/sources')
def read_sources(user: CurrentUser = Depends(require_runner), db: Session = Depends(get_db)):
    return rows(db, True)


class CheckIn(BaseModel):
    run_id: str = Field(alias='runId', min_length=1, max_length=32)
    share_url: str = Field(alias='shareUrl', max_length=500)
    state: Literal['complete', 'incomplete', 'wrong_lecture', 'unavailable', 'unsupported']
    completed_at: datetime | None = Field(default=None, alias='completedAt')
    question_count: int = Field(default=0, alias='questionCount', ge=0, le=10000)
    raw_hash: str | None = Field(default=None, alias='rawHash', pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def completed_source(self):
        if self.state == 'complete' and (not self.completed_at or not self.completed_at.tzinfo or not self.question_count or not self.raw_hash):
            raise ValueError('완성 응답에는 작성 시각·문항 수·원문 지문이 필요합니다.')
        if self.completed_at and utc(self.completed_at) > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError('미래의 응답 작성 시각입니다.')
        return self


@router.put('/admin/quiz-publication/check')
def save_check(payload: CheckIn, user: CurrentUser = Depends(require_runner), db: Session = Depends(get_db)):
    lecture = db.get(Lecture, ('약리학', payload.run_id))
    if lecture is None:
        raise HTTPException(404, '강의를 찾을 수 없습니다.')
    db.refresh(lecture, with_for_update=True)
    bank = db.get(QuizBank, ('약리학', payload.run_id))
    if not bank or bank.share_url != payload.share_url or not valid_share_url(payload.share_url, 'chatgpt'):
        raise HTTPException(409, '공유 링크가 바뀌었습니다. 현재 링크를 확인하세요.')
    checked = db.get(QuizPublicationCheck, ('약리학', payload.run_id))
    if not checked:
        checked = QuizPublicationCheck(subject='약리학', run_id=payload.run_id, share_url=payload.share_url)
        db.add(checked)
    checked.share_url = payload.share_url
    checked.result = {'state': payload.state, 'completedAt': utc(payload.completed_at).isoformat() if payload.completed_at else None,
                      'questionCount': payload.question_count, 'rawHash': payload.raw_hash}
    checked.checked_at = datetime.now(UTC)
    db.commit()
    return {'checkedAt': checked.checked_at.isoformat()}
