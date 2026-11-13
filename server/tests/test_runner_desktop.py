"""Desktop queue controls against isolated SQLite; never load server/.env."""
import os
import sys
import tempfile
from datetime import date, datetime, UTC
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix='studyez-desktop-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  RUNNER_TOKEN='runner-test', STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / 'storage'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from app.auth import require_runner
from app.database import Base, SessionLocal, engine
from app.models import JOB_AUTO_DAILY_CAP, Asset, Lecture, Preview, PrequizJob, QuizBank
from runner import desktop_control as control
from scripts.runner_desktop_jobs import tasks, operate
from scripts import runner_desktop_jobs as service
import json

WINDOW = (date(2026, 11, 2), date(2026, 11, 26))
SUBJECTS = ['과목']
RUNS = _TMP / 'runs'
NOTES = _TMP / 'notes'
TABLE = _TMP / 'table.json'
TABLE.write_text('[]', encoding='utf-8')
service.NOTES_ROOT, service.TIMETABLE = NOTES, TABLE


def command(db, user, action, n=None, kind='pre'):
    request = {'action': action}
    if n:
        request.update(subject='과목', runId=f'261102_{n:02}', kind=kind)
    with control.locked(RUNS):
        return operate(db, user, RUNS, SUBJECTS, request, WINDOW)


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = require_runner(HTTPAuthorizationCredentials(scheme='Bearer', credentials='runner-test'), db)
        for n in range(1, 12):
            run_id = f'261102_{n:02}'
            db.add(Lecture(subject='과목', run_id=run_id, uid=f'u{n}', date=WINDOW[0],
                           slot=n, slot_end=n, start_time='09:00', title=f'강의 {n}', professors=[]))
            db.add(Preview(subject='과목', run_id=run_id, share_url=f'https://chatgpt.com/share/example-{n}'))
            for year, subfolder in [('2026', ''), ('2025', '1차')]:
                folder = NOTES / '과목' / '필기' / year / subfolder
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'[{year[2:]}1102_{n:02}] 강의 {n}(가나다)_라마바v1.pdf').write_bytes(b'fixture')
        db.add(Lecture(subject='과목', run_id='260901_01', uid='old', date=date(2026, 9, 1), slot=1, slot_end=1,
                       start_time='09:00', title='지난 블럭', professors=[]))
        db.commit()
        for n in (1, 2):
            db.add(Asset(id=f'a{n}', subject='과목', run_id=f'261102_{n:02}', kind='notes_current',
                         filename='notes.pdf', object_key=f'n{n}.pdf', content_type='application/pdf'))
        db.add(QuizBank(subject='과목', run_id='261102_01', raw_response='saved response'))
        db.commit()
        rows = tasks(db, SUBJECTS, RUNS, WINDOW)
        assert len(rows) == 22 and all(r['runId'] != '260901_01' for r in rows)
        review = {r['runId']: r for r in rows if r['kind'] == 'bank'}
        assert review['261102_01']['ready']
        assert review['261102_02']['reason'] == '저장된 웹 응답 필요'
        assert review['261102_03']['reason'] == '올해 필기 필요'
        previous_pdf = next((NOTES / '과목/필기/2025/1차').glob('[[]251102_11]*'))
        previous_pdf.rename(previous_pdf.with_suffix('.removed'))
        missing = next(r for r in tasks(db, SUBJECTS, RUNS, WINDOW) if r['runId'] == '261102_11' and r['kind'] == 'pre')
        assert not missing['ready'] and not missing['autoReady'] and '작년' in missing['reason']
        previous_pdf.with_suffix('.removed').rename(previous_pdf)
        command(db, user, 'start', 1, 'pre')
        command(db, user, 'start', 1, 'bank')
        command(db, user, 'start', 1, 'pre')
        assert db.query(PrequizJob).count() == 2
        pre = db.scalars(select(PrequizJob).where(PrequizJob.kind == 'pre')).one()
        bank = db.scalars(select(PrequizJob).where(PrequizJob.kind == 'bank')).one()
        pre.requested_by = 'original-admin@example.test'
        db.commit()
        command(db, user, 'stop', 1, 'pre')
        assert pre.state == 'held' and bank.state == 'queued'
        command(db, user, 'pause')
        command(db, user, 'resume')
        assert pre.state == 'held'  # individual stop survives global resume
        command(db, user, 'start', 1, 'pre')
        assert pre.state == 'queued' and not pre.force
        assert pre.requested_by == 'original-admin@example.test'
        bank.state = 'running'
        db.commit()
        command(db, user, 'cancel', 1, 'bank')
        assert bank.cancel_requested and bank.state == 'running'
        command(db, user, 'cancel', 1, 'bank')
        assert bank.state == 'running'  # repeated cancel cannot force it off the board
        command(db, user, 'cancel', 3, 'pre')
        # Completed, failed, individually stopped/canceled tasks must never auto-repeat.
        db.add(PrequizJob(subject='과목', run_id='261102_04', kind='pre', state='done'))
        db.add(PrequizJob(subject='과목', run_id='261102_05', kind='pre', state='failed'))
        db.commit()
        command(db, user, 'auto')
        count = db.query(PrequizJob).count()
        command(db, user, 'auto')
        assert db.query(PrequizJob).count() == count
        assert not db.scalars(select(PrequizJob).where(PrequizJob.run_id == '261102_03')).first()
        assert db.query(PrequizJob).filter_by(run_id='261102_04').count() == 1
        assert db.query(PrequizJob).filter_by(run_id='261102_05').count() == 1
        auto = db.scalars(select(PrequizJob).where(PrequizJob.origin == 'auto')).all()
        assert len([j for j in auto if j.state == 'queued']) <= JOB_AUTO_DAILY_CAP
        command(db, user, 'pause')
        pre.state, pre.stage = 'held', control.GLOBAL_STAGE
        db.commit()
        command(db, user, 'resume')
        assert pre.state == 'queued'
        assert db.get(QuizBank, ('과목', '261102_01')).raw_response == 'saved response'
        # The archive reads every older task, including rows outside board()'s recent 50.
        older = []
        for n in range(60):
            job = PrequizJob(subject='과목', run_id='260901_01', kind='pre', state='failed' if n % 2 else 'done',
                            message=f'옛 기록 {n}', requested_by='private@example.test')
            db.add(job)
            older.append(job)
        db.add(Lecture(subject='다른 과목', run_id='261102_01', uid='other', date=WINDOW[0], slot=1, slot_end=1,
                       start_time='09:00', title='같은 날짜 다른 과목', professors=[]))
        db.add(PrequizJob(subject='다른 과목', run_id='261102_01', kind='bank', state='held'))
        db.commit()
        before = [(j.id, j.state, j.message) for j in db.scalars(select(PrequizJob))]
        records = service.history_records(db, SUBJECTS, WINDOW)
        assert len(records) == 61 and {j.id for j in older}.issubset({r['id'] for r in records})
        assert any(r['subject'] == '다른 과목' for r in records)
        assert all('requestedBy' not in row and 'worker' not in row for row in records)
        assert [(j.id, j.state, j.message) for j in db.scalars(select(PrequizJob))] == before
    print('Desktop queue checks passed: scope, material readiness, kind isolation, duplicate requests, stop/resume, cancellation, auto cap and preservation.')


if __name__ == '__main__':
    main()
