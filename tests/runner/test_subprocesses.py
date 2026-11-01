import subprocess
import sys
from pathlib import Path

from runner.background import launch


def test_nested_console_free_child_forwards_stage_stderr_and_exit_code(tmp_path):
    log = tmp_path / "nested.log"
    child = "import sys; print('── 원본 검수',flush=True); print('상세 기록',file=sys.stderr,flush=True); assert sys.stdin.read()==''; sys.exit(7)"
    driver = ("from runner.subprocesses import run_forwarded; import sys; "
              f"p=run_forwarded([sys.executable,'-c',{child!r}]); "
              "print('child exit',p.returncode,flush=True)")
    process = launch([sys.executable, "-c", driver], cwd=Path(__file__).resolve().parents[2], log=log)
    assert process.wait(timeout=15) == 0
    text = log.read_text(encoding="utf-8")
    assert "── 원본 검수" in text and "상세 기록" in text and "child exit 7" in text


def test_forwarded_runs_set_all_standard_handles_and_hide_windows(monkeypatch):
    from runner.subprocesses import run_forwarded
    seen = {}
    def run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(subprocess, "run", run)
    run_forwarded(["python", "-m", "quizbank.run"])
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["stderr"] == subprocess.STDOUT
    assert seen["stdout"] is not None
    assert seen["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
