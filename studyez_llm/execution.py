"""Local process lifecycle and overlap protection; no model calls of its own."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess


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
                encoding='utf-8', errors='replace', creationflags=0):
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=cwd, text=text, encoding=encoding, errors=errors, creationflags=creationflags,
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
