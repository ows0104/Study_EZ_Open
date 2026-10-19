"""Compare-and-swap storage for a runner-recovered public bank response."""
from datetime import UTC, datetime
import hashlib

from fastapi import HTTPException
from app.jobs.queue import open_job_of
from app.models import QuizBank, PrequizJob, JOB_BANK, JOB_BUTTON, JOB_QUEUED


def manual(row):
    return bool(row.raw_response and (row.responded_by or '').startswith('manual:'))


def file_source(row):
    info = (row.validation or {}).get('responseFile') or {}
    return bool(info.get('validated') is True and row.raw_response
                and info.get('sha256') == hashlib.sha256(row.raw_response.encode()).hexdigest())


def pending(row):
    if manual(row) or file_source(row):
        return False
    if not row.share_url:
        return False
    recovered = (row.validation or {}).get('sharedResponse', {})
    if recovered.get('shareUrl') == row.share_url and recovered.get('rawHash') == hashlib.sha256(row.raw_response.encode()).hexdigest():
        try:
            checked = datetime.fromisoformat(recovered['checkedAt'])
            linked = row.linked_at
            if not linked or checked >= (linked if linked.tzinfo else linked.replace(tzinfo=UTC)):
                return False
        except (KeyError, TypeError, ValueError):
            pass
    return not row.raw_response or bool(row.linked_at and (not row.responded_at or row.linked_at > row.responded_at))


def store(db, row, payload, actor):
    if file_source(row) and payload.raw != row.raw_response:
        raise HTTPException(409, '검증된 파일 원문을 공유 링크 응답으로 바꿀 수 없습니다.')
    if 'STUDYEZ_BANK_FILE' in payload.raw and payload.raw != row.raw_response:
        raise HTTPException(422, '파일 문제은행은 실제 .md 파일을 불러와 전달하세요. 공유 링크의 텍스트로 대신 저장하지 않습니다.')
    if manual(row):
        raise HTTPException(409, '직접 저장한 답변을 우선합니다. 공유 링크 응답으로 바꿀 수 없습니다.')
    current = (row.responded_at if row.responded_at.tzinfo else row.responded_at.replace(tzinfo=UTC)).isoformat() if row.responded_at else None
    if current != payload.expected_responded_at or row.share_url != payload.share_url or hashlib.sha256(row.raw_response.encode()).hexdigest() != payload.expected_raw_hash:
        raise HTTPException(409, '공유 링크 또는 응답이 바뀌었습니다. 현재 입력을 다시 확인하세요.')
    if row.raw_response == payload.raw:
        row.validation = {**(row.validation or {}), 'sharedResponse': {'shareUrl': row.share_url, 'rawHash': payload.expected_raw_hash, 'checkedAt': datetime.now(UTC).isoformat()}}
        db.commit()
        return {'reused': True}
    row.raw_response = payload.raw
    row.responded_at = datetime.now(UTC)
    row.responded_by = 'runner:shared-response'
    # A public share does not reliably expose its prompt version or original /c URL.
    row.prompt_version = ''
    row.conversation_url = ''
    row.validation = {k:v for k,v in (row.validation or {}).items() if k not in ('revision','maintenance')}
    row.validation['sharedResponse'] = {'shareUrl': row.share_url, 'rawHash': hashlib.sha256(payload.raw.encode()).hexdigest(), 'extractionStrategy': payload.extraction_strategy, 'checkedAt': row.responded_at.isoformat(), 'promptVersionKnown': False}
    job = open_job_of(db, row.subject, row.run_id, JOB_BANK)
    if job is None:
        job = PrequizJob(subject=row.subject, run_id=row.run_id, kind=JOB_BANK, state=JOB_QUEUED,
                         origin=JOB_BUTTON, requested_by=actor, stage='공유 응답 저장 완료 — 검수·업로드 대기')
        db.add(job)
    row.status = 'building' if job.state == 'running' else 'responded'
    row.message = '저장된 공유 응답을 가져왔다 — 러너가 검수·업로드한다'
    db.commit()
    return {'respondedAt': row.responded_at.isoformat(), 'jobId': job.id}
