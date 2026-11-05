"""Resume approved material-resolution failures through the existing desktop adapter."""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'server'))

from dotenv import load_dotenv
load_dotenv(ROOT / 'server/.env')
from fastapi.security import HTTPAuthorizationCredentials
from app.auth import require_runner
from app.config import get_settings
from app.database import SessionLocal
from runner import desktop_control
from scripts import runner_desktop_jobs as adapter


def main(apply=False):
    subjects, scope_note, window = adapter.scope()
    assert '감염과 면역' in subjects
    runs = ROOT / 'runs'
    result = []
    with SessionLocal() as db:
        token = os.getenv('STUDYEZ_RUNNER_TOKEN') or get_settings().runner_token
        user = require_runner(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        rows = adapter.tasks(db, subjects, runs, window)
        for row in rows:
            if row['subject'] != '감염과 면역' or row['kind'] != 'pre':
                continue
            if row['state'] != 'failed' or not row['ready'] or row['choice'] or row['cancelRequested']:
                continue
            if not any(s in row['message'] for s in ('작년 짝', '로컬에서 이 강의')):
                continue  # Do not reset content failures or an exhausted review attempt.
            record = dict(runId=row['runId'], previousJobId=row['jobId'], priorMessage=row['message'])
            if apply:
                with desktop_control.locked(runs):
                    # operate rechecks live readiness, pause, latest job and active queue.
                    adapter.operate(db, user, runs, subjects,
                                    dict(action='start', subject=row['subject'], runId=row['runId'], kind='pre'), window)
                from app.models import PrequizJob
                from sqlalchemy import select
                job = db.scalars(select(PrequizJob).where(PrequizJob.subject == row['subject'],
                    PrequizJob.run_id == row['runId'], PrequizJob.kind == 'pre').order_by(PrequizJob.id.desc())).first()
                record.update(jobId=job.id, state=job.state, force=job.force)
                assert not job.force
            result.append(record)
    value = dict(applied=apply, scope=scope_note, jobs=result)
    target = HERE / ('resumed-jobs.json' if apply else 'resume-candidates.json')
    if target.exists() and apply:
        target = HERE / f'resumed-jobs-followup-{__import__("time").time_ns()}.json'
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
