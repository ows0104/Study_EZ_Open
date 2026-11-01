"""Read explicitly registered local QA jobs, including existing CLI processes."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .status import JobStatus, _age, tail


def _read(path: Path) -> dict:
    try:
        if path.stat().st_size > 65536:
            return {}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _local(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Status paths must stay inside the project")
    return path


def _tokens(command: str) -> list[str]:
    return [token.strip('"').replace("\\", "/") for token in re.findall(r'"[^"]*"|\S+', command or "")]


def _script_arg(command: str, script: str) -> tuple[bool, str]:
    for index, token in enumerate(_tokens(command)):
        # Relative commands are registered by their project path, never by basename.
        if token.casefold() == script.casefold() or token.casefold().endswith("/" + script.casefold()):
            tokens = _tokens(command)
            return True, tokens[index + 1] if index + 1 < len(tokens) else ""
    return False, ""


def _descendants(pid: int, processes: list[dict]) -> set[int]:
    found, pending = set(), {pid}
    while pending:
        children = {p["ProcessId"] for p in processes if p["ParentProcessId"] in pending}
        pending = children - found - {pid}
        found.update(pending)
    return found


def _event(line: str, config: dict | None = None) -> str:
    try:
        event = json.loads(line)
    except ValueError:
        return line
    if not isinstance(event, dict):
        return line
    run_id = event.get("run_id", "")
    if config and config.get("activity") == "metadata":
        states = config.get("stages", {})
        label = states.get(event.get("state")) or states.get(event.get("phase"))
        if not label:
            label = ("이전 검수본 게시 기록 확인" if event.get("published") is True else
                     "복원 결과 확인 필요" if event.get("published") is False else config["label"])
        return f"{run_id} · {label}".lstrip(" ·")
    if event.get("applied") is True:
        return f"{run_id} · 대조 반영 완료 · 원본 문항·학습 기록 보존"
    if event.get("error"):
        return f"{run_id} · 확인 필요: {event['error']}"
    if event.get("stage"):
        return f"{run_id} · 원본 추가 대조 시작"
    return f"{run_id} · 대조 결과 저장"


def collect_external(runs: Path, processes: list[dict], now: float) -> tuple[tuple[JobStatus, ...], tuple[str, ...]]:
    root = runs.resolve().parent
    jobs, events = [], []
    for manifest in sorted((runs / "status-jobs").glob("*.json"))[:32]:
        config = _read(manifest)
        try:
            script = _local(root, config["script"]).relative_to(root).as_posix()
            log = _local(root, config["log"])
            outputs = _local(root, config["outputs"])
            key, label = config["id"], config["label"]
            owner = config.get("owner", "다른 세션")
            targets = config.get("targets", {})
            state_file = _local(root, config["state_file"]) if config.get("state_file") else None
            if not isinstance(targets, dict) or not isinstance(config.get("stages", {}), dict):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        log_lines = tail(log, 15)
        if log_lines:
            events += [f"\n[{label} · {owner}]", *(_event(line, config) for line in log_lines[-4:])]
        matches = [p for p in processes if _script_arg(p.get("CommandLine") or "", script)[0]]
        if config.get('overview') is True and state_file and isinstance(_read(state_file).get("states"), dict):
            continue  # Multi-lecture batches have one card per active lecture.
        # uv launches a shim with the same command. Show the actual work once.
        parents = {p["ParentProcessId"] for p in matches}
        leaves = [p for p in matches if p["ProcessId"] not in parents]
        for process in leaves:
            status = _read(state_file) if state_file else {}
            if status.get("pid") != process["ProcessId"]:
                status = {}  # A stale status file must not describe a new process.
            _, argument = _script_arg(process.get("CommandLine") or "", script)
            run_id = status.get("run_id") or config.get("run_id", "")
            if not run_id:
                candidate = Path(argument).name
                if re.fullmatch(r"\d{6}_\d{2}", candidate):
                    run_id = candidate
            if not run_id:
                for line in reversed(log_lines):
                    try:
                        entry = json.loads(line)
                        run_id = entry.get("run_id", "")
                    except (ValueError, AttributeError):
                        continue
                    if run_id:
                        break
            if not re.fullmatch(r"\d{6}_\d{2}", run_id):
                run_id = ""
            output = outputs / run_id if run_id else outputs
            metadata = config.get("activity") == "metadata"
            context = _read(output / "web-audit/context.json") if run_id and not metadata else {}
            title = context.get("title") or targets.get(run_id) or label
            descendants = _descendants(process["ProcessId"], processes)
            cli = any(p["ProcessId"] in descendants and (p.get("Name", "").casefold() == "codex.exe" or
                      re.search(r'\bcodex(?:\.exe)?["\s]+exec\b', p.get("CommandLine") or "", re.I))
                      for p in processes)
            if metadata:
                stage = config.get("stages", {}).get(status.get("state"), label)
            elif cli:
                stage = "CLI 원본·출제 포인트 대조 중"
            elif _read(output / "ready.json"):
                stage = "대조 결과 반영·확인 중"
            elif (output / "web-audit.raw.json").is_file():
                stage = "대조 결과 정리·검증 중"
            else:
                stage = "자료·원본 준비 중"
            # Sparse logs are normal during one long CLI call; file age is not a heartbeat.
            observed = [log, output / "runtime.json", output / "attempt.json",
                        output / "web-audit/context.json", output / "web-audit.raw.json",
                        output / "ready.json", output / "applied.json"]
            if state_file:
                observed.append(state_file)
            ages = [value for path in observed if (value := _age(path, now)) is not None]
            details = tail(output / "prepare.log", 3)
            if not details:
                details = tuple(_event(line, config) for line in log_lines[-3:])
            jobs.append(JobStatus(f"{key}/{run_id}" if run_id else key, title,
                                  process["ProcessId"], label, (stage,), details,
                                  min(ages) if ages else None, owner))
    return tuple(jobs), tuple(events)
