"""Local process lifecycle and overlap protection; no model calls of its own."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class AlreadyRunning(RuntimeError):
    pass


def usage_root():
    return Path(os.environ.get('STUDYEZ_CODEX_USAGE_DIR') or
                Path(__file__).resolve().parents[1] / 'runs/_llm/usage')


@contextmanager
def exclusive(request):
    key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = usage_root() / 'locks' / (key + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as cause:
            raise AlreadyRunning('동일한 CLI 요청이 이미 실행 중입니다. 중복 실행을 차단했습니다.') from cause
        try:
            yield key
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# Model CLI sessions on this machine at once, over every process that uses this install
# (docs/changes/2026-11-11-pipeline-resilience). One Main-Quiz run now asks up to six stages side by side and the
# runner works on two lectures at a time; without a cap that is twelve sessions where three were the rule before.
SLOTS_ENV = 'STUDYEZ_CODEX_SLOTS'
DEFAULT_SLOTS = 8


def slot_limit():
    try:
        return max(1, int(os.environ.get(SLOTS_ENV) or DEFAULT_SLOTS))
    except ValueError:
        return DEFAULT_SLOTS


def _try_lock(handle):
    handle.seek(0, 2)
    if not handle.tell():
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle):
    handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def slot(limit=None, *, poll=2.0, sleep=time.sleep, waiting=None):
    """Hold one of `limit` session slots while a model CLI call runs; wait (never fail) while all are taken.

    A slot is a locked file under <usage>/slots, so a process that dies gives its slot back with its handle.
    `waiting()` is called once, when the first pass finds every slot taken."""
    limit = slot_limit() if limit is None else max(1, int(limit))
    folder = usage_root() / 'slots'
    folder.mkdir(parents=True, exist_ok=True)
    told = False
    while True:
        for i in range(limit):
            handle = (folder / f'{i}.lock').open('a+b')
            if not _try_lock(handle):
                handle.close()
                continue
            try:
                yield i
            finally:
                try:
                    _unlock(handle)
                finally:
                    handle.close()
            return
        if not told and waiting is not None:
            waiting()
        told = True
        sleep(poll)


def terminate_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        # subprocess.run(timeout=...) kills only its immediate child on Windows.
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
            capture_output=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        os.killpg(proc.pid, signal.SIGKILL)
    if proc.poll() is None:
        proc.kill()


def run_process(argv, *, input, cwd, timeout, capture_output=True, text=True,
                encoding='utf-8', errors='replace', creationflags=0, env=None):
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=cwd, text=text, encoding=encoding, errors=errors, creationflags=creationflags, env=env,
        start_new_session=os.name != 'nt')
    try:
        stdout, stderr = proc.communicate(input, timeout=timeout)
    except BaseException as cause:
        try:
            terminate_tree(proc)
        finally:
            # Reap the direct child even when taskkill itself fails.
            if proc.poll() is None:
                proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout = stderr = None
        if isinstance(cause, subprocess.TimeoutExpired):
            cause.output, cause.stderr = stdout, stderr
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
