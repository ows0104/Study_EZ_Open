"""Read an existing local runner's status; never contact the API or control workers."""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobStatus:
    run_id: str
    title: str
    pid: int
    kind: str
    stages: tuple[str, ...]
    lines: tuple[str, ...]
    log_age: int | None
    owner: str = "로컬 러너"


@dataclass(frozen=True)
class Snapshot:
    checked_at: float
    agent_pid: int | None
    heartbeat_age: int | None
    jobs: tuple[JobStatus, ...]
    events: tuple[str, ...]
    error: str = ""
    queue: dict | None = None
    queue_checked_at: float = 0.0
    queue_error: str = ""
    batches: tuple[dict, ...] = ()


def tail(path: Path, count: int = 40) -> tuple[str, ...]:
    """Bound reads even when a CLI writes a very large response to its log."""
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(max(0, size - 131072))
            data = stream.read()
        lines = data.decode("utf-8", errors="replace").splitlines()
        if size > 131072:
            lines = lines[1:]  # first line can start halfway through a UTF-8 character
        return tuple(line[:600] for line in lines[-count:] if line.strip())
    except OSError:
        return ()


def option(command: str, name: str) -> str:
    tokens = re.findall(r'"[^"]*"|\S+', command or "")
    try:
        return tokens[tokens.index(name) + 1].strip('"')
    except (ValueError, IndexError):
        return ""


def process_list() -> list[dict]:
    # This fixed, read-only query cannot execute commands found in logs or arguments.
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe' OR Name='codex.exe'\" "
        "-ErrorAction Stop | Select-Object ProcessId,ParentProcessId,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, encoding="utf-8", errors="replace", timeout=12,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True,
    )
    value = json.loads(result.stdout.strip() or "[]")
    return value if isinstance(value, list) else [value]


def _age(path: Path, now: float) -> int | None:
    try:
        return max(0, int(now - path.stat().st_mtime))
    except OSError:
        return None


def collect(runs: Path, processes: list[dict] | None = None, now: float | None = None) -> Snapshot:
    now = time.time() if now is None else now
    events = tail(runs / "agent.log", 22)
    lock = runs / "agent.lock"
    try:
        match = re.search(r"\bpid\s+(\d+)", lock.read_text(encoding="utf-8"))
        pid = int(match[1]) if match else None
    except (OSError, ValueError):
        pid = None
    try:
        processes = process_list() if processes is None else processes
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return Snapshot(now, None, _age(lock, now), (), events,
                        f"프로세스 상태 확인 실패 ({type(error).__name__}) · 다음 주기에 재시도합니다")
    agent = next((p for p in processes if p["ProcessId"] == pid and
                  re.search(r"-m\s+runner\s+agent\b", p.get("CommandLine") or "")), None)
    jobs = []
    if agent:
        for process in processes:
            command = process.get("CommandLine") or ""
            if process["ParentProcessId"] != pid or not re.search(r"-m\s+runner\s+bank\b", command):
                continue
            run_id = option(command, "--run-id")
            # Never interpret arbitrary command text as a filesystem path.
            if not re.fullmatch(r"[\w-]+", run_id):
                continue
            children = [p for p in processes if p["ParentProcessId"] == process["ProcessId"]]
            title = next((option(p.get("CommandLine") or "", "--title") for p in children
                          if option(p.get("CommandLine") or "", "--title")), run_id)
            if title == run_id:
                try:
                    source = json.loads((runs / run_id / "source.json").read_text(encoding="utf-8"))
                    title = source.get("stem") or source.get("title") or run_id
                except (OSError, ValueError):
                    pass
            log = runs / f"agent.{run_id}.log"
            lines = tail(log, 400)
            stages = tuple(line.removeprefix("── ").strip() for line in lines if line.startswith("── "))
            from .status_artifacts import observe
            artifact = observe(runs, run_id, children, log, now)
            recent, log_age = lines[-5:], _age(log, now)
            if artifact:
                stage, details, log_age = artifact
                stages += (stage,)
                recent += details
            jobs.append(JobStatus(run_id, title, process["ProcessId"],
                                  "출제 포인트 준비" if "--points-only" in command else "퀴즈 생성 · 검수",
                                  stages[-5:], recent, log_age))
    # Other sessions opt in by registering their local script and output paths.
    from .status_external import collect_external
    external, external_events = collect_external(runs, processes, now)
    from .status_batch import collect_batches
    batches, batch_jobs = collect_batches(runs, processes)
    return Snapshot(now, pid if agent else None, _age(lock, now), tuple(jobs) + external + batch_jobs,
                    events + external_events, batches=batches)
