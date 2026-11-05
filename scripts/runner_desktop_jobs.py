"""Local desktop adapter to the existing authenticated job policies, not a web endpoint."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_ROOT = Path.home() / 'SynologyDrive'
TIMETABLE = ROOT / 'server/local_test_data/studyez.db'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'server'))

from runner import desktop_control as control


def scope(root=ROOT):
    from runner import ahead
    from runner.blocks import DEFAULT_SOURCE
    today = date.today()
    subjects, note = ahead.subjects_in_block(Path.home() / 'SynologyDrive', str(today.year), root / 'runs', today, DEFAULT_SOURCE)
    if not subjects:
        raise ValueError(note)
    from runner import blocks
    block = blocks.find(today).block
    return subjects, note, (block.start, block.end)


def tasks(db, subjects, runs, window, *, notes_root=None, timetable=None):
    from sqlalchemy import select
    from app.models import Asset, Lecture, Preview, QuizBank, PrequizJob
    from app.jobs.queue import auto_review_excluded
    from runner import readiness, blocks
    notes_root = Path(notes_root) if notes_root is not None else NOTES_ROOT
    timetable = Path(timetable) if timetable is not None else TIMETABLE
    sources = {}
    for subject in subjects:
        try:
            sources[subject] = readiness.preview_sources(notes_root, subject, str(window[0].year),
                                                       str(window[0].year - 1), runs, timetable)
        except (OSError, ValueError):
            sources[subject] = {}
    state = control.read(runs)
    lectures = db.scalars(select(Lecture).where(Lecture.subject.in_(subjects), Lecture.date >= window[0], Lecture.date <= window[1])
                          .order_by(Lecture.date, Lecture.slot)).all()
    assets = {(s, r, k) for s, r, k in db.execute(select(Asset.subject, Asset.run_id, Asset.kind).where(Asset.subject.in_(subjects)))}
    links = {(s, r) for s, r in db.execute(select(Preview.subject, Preview.run_id).where(Preview.subject.in_(subjects), Preview.share_url != ''))}
    banks = {(b.subject, b.run_id): b for b in db.scalars(select(QuizBank).where(QuizBank.subject.in_(subjects)))}
    latest = {}
    for job in db.scalars(select(PrequizJob).where(PrequizJob.subject.in_(subjects)).order_by(PrequizJob.id.desc())):
        latest.setdefault((job.subject, job.run_id, job.kind), job)
    result = []
    for lecture in lectures:
        subject, run_id = lecture.subject, lecture.run_id
        bank = banks.get((subject, run_id))
        for kind, label in [('pre', '예습'), ('bank', '복습')]:
            job = latest.get((subject, run_id, kind))
            key = control.job_key(subject, run_id, kind)
            choice = state.get('jobs', {}).get(key, '')
            has_notes = (subject, run_id, 'notes_current') in assets
            local = sources[subject].get(run_id, dict(ready=False, reason='작년 필기·시간표 연결 확인 필요'))
            ready = ((subject, run_id) in links and local['ready']) if kind == 'pre' else has_notes and bool(bank and bank.raw_response.strip())
            reason = '' if ready else (('예습 링크 필요' if (subject, run_id) not in links else local['reason'])
                                      if kind == 'pre' else '올해 필기 필요' if not has_notes else '저장된 웹 응답 필요')
            completed = (subject, run_id, 'pre_apkg') in assets if kind == 'pre' else bool(bank and bank.built_at)
            job_state = job.state if job else ('done' if completed else 'ready' if ready else 'unavailable')
            excluded = kind == 'bank' and auto_review_excluded(db, subject, run_id)
            auto_ready = ready and not job and not completed and not choice and not excluded
            result.append(dict(subject=subject, runId=run_id, title=lecture.title, date=lecture.date.isoformat(),
                               kind=kind, label=label, ready=ready, reason=reason, state=job_state,
                               jobId=job.id if job else None, stage=job.stage if job else '',
                               message=job.message if job else '', cancelRequested=bool(job and job.cancel_requested),
                               choice=choice, autoReady=auto_ready, manualOnly=excluded))
    return result


def history_records(db, subjects, window):
    """Full job history, not the board's recent-50 slice. Never modify a row."""
    from sqlalchemy import and_, select
    from app.models import Lecture, PrequizJob
    from app.jobs.views import job_row
    records = []
    query = select(PrequizJob, Lecture).outerjoin(Lecture, and_(
        Lecture.subject == PrequizJob.subject, Lecture.run_id == PrequizJob.run_id)).order_by(PrequizJob.id.desc())
    for job, lecture in db.execute(query):
        if lecture and lecture.subject in subjects and window[0] <= lecture.date <= window[1]:
            continue
        row = job_row(job)
        # Keep task provenance without making a second copy of account identities.
        row.pop('requestedBy', None)
        row.pop('worker', None)
        for key in ('elapsedSeconds', 'stageSeconds', 'etaSeconds'):
            row.pop(key, None)
        row['title'] = lecture.title if lecture else job.run_id
        row['date'] = lecture.date.isoformat() if lecture else ''
        row['startedAt'] = job.started_at.isoformat() if job.started_at else ''
        row['finishedAt'] = job.finished_at.isoformat() if job.finished_at else ''
        records.append(row)
    return records


def operate(db, user, runs, subjects, request, window):
    from sqlalchemy import select
    from app.models import PrequizJob, JOB_HELD, JOB_QUEUED
    from app.jobs.queue import ensure_auto_job
    from app.routes.prequiz_jobs import request_prequiz, cancel_prequiz_job, JobRequest
    action = request['action']
    value = control.read(runs)
    if value.get('error'):
        raise ValueError(value['error'])
    value.setdefault('jobs', {})
    if action in ('pause', 'resume'):
        value['paused'] = action == 'pause'
        control.write(runs, value)
        if action == 'resume':
            for job in db.scalars(select(PrequizJob).where(PrequizJob.state == JOB_HELD, PrequizJob.stage == control.GLOBAL_STAGE)):
                if job.subject in subjects and not value['jobs'].get(control.job_key(job.subject, job.run_id, job.kind)):
                    job.state, job.stage = JOB_QUEUED, '프로그램에서 전체 재개'
            db.commit()
        return
    rows = tasks(db, subjects, runs, window)
    if action == 'auto':
        if value.get('paused'):
            return
        for row in rows:
            if row['autoReady']:
                ensure_auto_job(db, row['subject'], row['runId'], row['kind'], '프로그램 1분 자동 시작')
        db.commit()
        return
    if action not in ('start', 'stop', 'cancel'):
        raise ValueError('알 수 없는 작업입니다.')
    row = next((r for r in rows if all(r[k] == request.get(k) for k in ('subject', 'runId', 'kind'))), None)
    if not row:
        raise ValueError('이번 블럭의 강의·작업이 아닙니다.')
    key = control.job_key(row['subject'], row['runId'], row['kind'])
    if action == 'start':
        if value.get('paused'):
            raise ValueError('전체 일시정지를 먼저 해제해 주세요.')
        if not row['ready']:
            raise ValueError(row['reason'])
        if row['state'] == 'done':
            raise ValueError('이미 완료한 작업입니다. 재생성은 기존 강의 관리 화면에서 요청하세요.')
        if row['cancelRequested']:
            raise ValueError('러너가 중지·취소를 확인한 뒤 다시 시작해 주세요.')
        value['jobs'].pop(key, None)
        control.write(runs, value)
        previous = db.get(PrequizJob, row['jobId']) if row['jobId'] else None
        requested_by = previous.requested_by if previous else ''
        result = request_prequiz(row['subject'], row['runId'], kind=row['kind'], payload=JobRequest(force=False), user=user, db=db)
        if previous and requested_by and previous.id == result['job']['id']:
            previous.requested_by = requested_by
            db.commit()
        return
    value['jobs'][key] = 'stopped' if action == 'stop' else 'canceled'
    control.write(runs, value)
    job = db.get(PrequizJob, row['jobId']) if row['jobId'] else None
    if job is None or job.state in ('done', 'failed', 'canceled'):
        return
    if action == 'stop':
        if job.state in ('queued', 'held'):
            job.state, job.stage = 'held', control.JOB_STAGE
            db.commit()
        # A running worker acknowledges the local choice itself, preserving checkpoints.
    elif not job.cancel_requested:
        cancel_prequiz_job(job.id, user=user, db=db)


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'server/.env')
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    from sqlalchemy import text
    from app.auth import require_runner
    from app.config import get_settings
    from app.database import SessionLocal
    from app.jobs.views import board
    request = json.load(sys.stdin)
    runs = ROOT / 'runs'
    try:
        try:
            subjects, note, window = scope()
        except (OSError, ValueError):
            if request['action'] != 'pause':
                raise
            # Pausing must work even if a timetable disappears during an active job.
            subjects, note, window = [], '', (date.today(), date.today())
        with SessionLocal() as db:
            # Same runner credential validation as the existing API. Never print credentials.
            token = os.getenv('STUDYEZ_RUNNER_TOKEN') or get_settings().runner_token
            user = require_runner(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
            if request['action'] in ('read', 'history'):
                if db.bind.dialect.name == 'postgresql':
                    db.execute(text('SET TRANSACTION READ ONLY'))
                    db.execute(text("SET LOCAL statement_timeout = '10000'"))
                scope_info = dict(subjects=subjects, since=window[0].isoformat(), until=window[1].isoformat())
                if request['action'] == 'history':
                    value = dict(records=history_records(db, subjects, window))
                    from sqlalchemy import select
                    from app.models import Lecture
                    value['scopeKeys'] = [dict(subject=s, runId=r) for s, r in db.execute(
                        select(Lecture.subject, Lecture.run_id).where(Lecture.subject.in_(subjects),
                            Lecture.date >= window[0], Lecture.date <= window[1]))]
                else:
                    value = board(db)
                    value['tasks'] = tasks(db, subjects, runs, window)
                value['scopeInfo'] = scope_info
                value['scope'] = note
                value['control'] = control.read(runs)
                print(json.dumps({'ok': True, 'value': value}, ensure_ascii=True))
            else:
                with control.locked(runs):
                    operate(db, user, runs, subjects, request, window)
                print(json.dumps({'ok': True}))
    except HTTPException as error:
        print(json.dumps({'ok': False, 'error': str(error.detail)}, ensure_ascii=True))
    except (ValueError, TimeoutError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True))
    except Exception:
        print(json.dumps({'ok': False, 'error': '서버 작업 처리 실패 · 연결 상태와 설정을 확인해 주세요.'}, ensure_ascii=True))


if __name__ == '__main__':
    main()
