"""Local desktop choices. No model calls, server credentials or generated content."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

CONTROL = 'desktop-control.json'
GLOBAL_STAGE = '프로그램 전체 일시정지'
JOB_STAGE = '프로그램에서 중지'


def job_key(subject: str, run_id: str, kind: str) -> str:
    return json.dumps([subject, run_id, kind], ensure_ascii=True, separators=(',', ':'))


def read(runs: Path) -> dict:
    try:
        value = json.loads((runs / CONTROL).read_text(encoding='utf-8'))
        if not isinstance(value, dict) or not isinstance(value.get('jobs', {}), dict):
            raise ValueError('invalid control file')
        return value
    except FileNotFoundError:
        return {'paused': False, 'jobs': {}}
    except (OSError, ValueError):
        # An unreadable choice must never silently start paid work.
        return {'paused': True, 'jobs': {}, 'error': '실행 설정을 읽지 못했습니다.'}


@contextmanager
def locked(runs: Path):
    """OS lock is released on crash; the persistent file is never a stale PID lock."""
    runs.mkdir(parents=True, exist_ok=True)
    with (runs / 'desktop-control.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + 30
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise TimeoutError('다른 창에서 작업을 처리 중입니다.') from None
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def write(runs: Path, value: dict):
    """Caller holds locked(); replace only our own small configuration file."""
    target = runs / CONTROL
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    deadline = time.monotonic() + 3
    while True:
        try:
            temp.replace(target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def decision(runs: Path, subject='', run_id='', kind='') -> str:
    value = read(runs)
    choice = value.get('jobs', {}).get(job_key(subject, run_id, kind), '')
    return choice or ('paused' if value.get('paused') else '')


def wait(runs: Path, seconds: float, job=None) -> str:
    deadline = time.monotonic() + seconds
    while True:
        choice = decision(runs, job.subject, job.run_id, job.kind) if job else decision(runs)
        if choice or time.monotonic() >= deadline:
            return choice
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))


class AutoStart:
    def __init__(self, now: float, seconds: float = 60):
        self.deadline = now + seconds
        self.pending = True

    def cancel(self):
        self.pending = False

    def due(self, now: float) -> bool:
        if not self.pending or now < self.deadline:
            return False
        self.pending = False
        return True
