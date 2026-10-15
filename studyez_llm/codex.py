"""ChatGPT 로그인으로 Codex CLI를 실행하고 JSONL을 기존 사용량 계약으로 옮긴다."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

DEFAULT_MODEL = "gpt-6.1-sol"
JUDGE_MODEL = DEFAULT_MODEL

# 독립 평가에 사용자 커넥터·기억·브라우저·다른 에이전트를 싣지 않는다.
DISABLED_FEATURES = (
    "apps", "plugins", "remote_plugin", "memories", "multi_agent", "multi_agent_v2",
    "hooks", "browser_use", "browser_use_external", "computer_use", "in_app_browser",
    "code_mode", "artifact", "image_generation", "workspace_dependencies",
    "skill_search", "shell_snapshot", "goals",
)


class SessionError(RuntimeError):
    pass


def model_name(model: str | None = None) -> str:
    name = model or os.environ.get("STUDYEZ_MODEL") or DEFAULT_MODEL
    if not name.startswith("gpt-"):
        raise SessionError(f"GPT 모델 이름이 필요하다: {name!r}. --model 또는 STUDYEZ_MODEL을 확인해라.")
    return name


def executable() -> str:
    """예약 러너의 PATH에 없는 Windows 데스크톱 번들 CLI도 찾는다."""
    exe = os.environ.get("STUDYEZ_CODEX_BIN") or shutil.which("codex")
    if not exe and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin"
        candidates = list(root.glob("*/codex.exe"))
        if candidates:
            exe = str(max(candidates, key=lambda path: path.stat().st_mtime))
    if not exe:
        raise SessionError("codex CLI를 찾지 못했다. PATH 또는 STUDYEZ_CODEX_BIN을 확인해라.")
    return exe


def command(*, model: str, blind: bool, resume: str | None = None) -> list[str]:
    argv = [executable(), "exec", "--json", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--model", model,
            "--sandbox", "read-only" if blind else "workspace-write"]
    config = {
        "model_provider": "openai", "approval_policy": "never", "web_search": "disabled",
        "project_doc_max_bytes": 0, "mcp_servers": {},
        "sandbox_workspace_write.network_access": False,
        "features.shell_tool": not blind, "features.unified_exec": not blind,
        "features.view_image": not blind,
        "features.code_mode_host": not blind,
    }
    if os.name == "nt":
        # --ignore-user-config는 Windows sandbox 구현 선택도 지운다.
        # 구현을 지정하지 않으면 CLI가 workspace-write 요청을 read-only로 내린다.
        config["windows.sandbox"] = "elevated"
    for key, value in config.items():
        argv += ["-c", f"{key}={json.dumps(value)}"]
    for feature in DISABLED_FEATURES:
        argv += ["--disable", feature]
    if blind:
        argv += ["--ephemeral"]
    if resume:
        argv += ["resume", resume]
    return argv


def parse_events(stdout: str, *, model: str, blind: bool) -> dict:
    text, sid, usage, turns, warnings = "", None, {}, 0, []
    reconnecting = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as cause:
            raise SessionError("codex 출력이 JSONL이 아니다") from cause
        if not isinstance(event, dict):
            raise SessionError("codex 이벤트가 객체가 아니다")
        kind = event.get("type")
        if kind == "error" and str(event.get("message", "")).startswith("Reconnecting..."):
            # CLI can recover the stream and complete the same turn. Only a
            # later turn.completed proves recovery; truncated output still fails.
            reconnecting.append(str(event["message"]))
            continue
        if kind in ("error", "turn.failed"):
            raise SessionError(json.dumps(event.get("error") or event, ensure_ascii=False)[-1500:])
        if kind == "thread.started":
            sid = event.get("thread_id")
        if kind and kind.startswith("item."):
            item = event.get("item") or {}
            if item.get("type") == "error":
                warnings.append(item.get("message", ""))
                continue  # CLI startup diagnostics; turn.failed still fails the run.
            # 새 CLI에 도구가 추가돼도 도구를 쓴 평가 결과를 합격시키지 않는다.
            if blind and item.get("type") not in ("agent_message", "reasoning"):
                raise SessionError(f"가림 세션에서 도구 이벤트를 받았다: {item.get('type')}")
            if kind == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text", "")
        if kind == "turn.completed":
            warnings.extend(reconnecting)
            reconnecting.clear()
            turns += 1
            for key, value in (event.get("usage") or {}).items():
                if isinstance(value, int):
                    usage[key] = usage.get(key, 0) + value
    if reconnecting:
        raise SessionError(reconnecting[-1])
    if not turns:
        raise SessionError("codex 세션 완료 이벤트가 없다 (출력 중단)")
    if not text.strip():
        raise SessionError("codex 최종 응답이 비어 있다")
    cached = usage.get("cached_input_tokens", 0)
    output = usage.get("output_tokens", 0)
    return {"text": text, "session_id": sid, "turns": turns, "cost_usd": None,
            "usage": {"input_tokens": max(0, usage.get("input_tokens", 0) - cached),
                      "output_tokens": output, "cache_read_input_tokens": cached,
                      "cache_creation_input_tokens": 0},
            "models": {model: output}, "provider": "codex", "warnings": warnings}


def run(prompt: str, *, blind: bool, cwd: Path | None = None, model: str | None = None,
        timeout: int = 1800, label: str = "", resume: str | None = None,
        schema: dict | None = None, system: str | None = None,
        previous_usage: dict | None = None) -> dict:
    """가림 실행은 임시 cwd, 저작 실행은 주어진 workspace에서 수행한다."""
    selected = model_name(model)
    if resume and previous_usage is None:
        raise SessionError("Codex 세션 재개에는 이전 응답의 session_usage가 필요하다")
    argv = command(model=selected, blind=blind, resume=resume)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="studyez-codex-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp) if blind else Path(cwd).resolve()
        # 임시 평가 폴더에서 프로젝트 설정을 허용하지 않는다.
        if blind:
            argv += ["-c", f'projects.{json.dumps(work.as_posix())}.trust_level="untrusted"']
        if system:
            instructions = Path(tmp) / "instructions.md"
            instructions.write_text(system, encoding="utf-8")
            argv += ["-c", f"model_instructions_file={json.dumps(instructions.as_posix())}"]
        if schema is not None:
            schema_file = Path(tmp) / "schema.json"
            schema_file.write_text(json.dumps(schema), encoding="utf-8")
            argv += ["--output-schema", str(schema_file)]
        argv += ["-"]
        try:
            proc = subprocess.run(argv, input=prompt, cwd=work, timeout=timeout,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as cause:
            raise SessionError(f"{label or '세션'}: {timeout}초 안에 끝나지 않았다") from cause
        except OSError as cause:
            raise SessionError(f"{label or '세션'}: codex 실행 실패: {cause}") from cause
    if proc.returncode:
        tail = (proc.stdout + "\n" + proc.stderr).strip()[-2000:]
        raise SessionError(f"{label or '세션'}: codex가 {proc.returncode}로 끝났다\n{tail}")
    try:
        info = parse_events(proc.stdout, model=selected, blind=blind)
    except SessionError as cause:
        raise SessionError(f"{label or '세션'}: {cause}") from cause
    # CLI 0.160.0의 turn.completed.usage는 재개한 세션의 누적값이다.
    # 단계마다 그대로 원장에 더하면 ①을 ②·수선에서 거듭 센다.
    info["session_usage"] = dict(info["usage"])
    if resume:
        if any(value < previous_usage.get(key, 0) for key, value in info["usage"].items()):
            raise SessionError("Codex 재개 사용량이 이전 누적값보다 작다. CLI 사용량 형식을 확인해라")
        info["usage"] = {key: value - previous_usage.get(key, 0)
                         for key, value in info["usage"].items()}
        info["models"] = {selected: info["usage"]["output_tokens"]}
    info["duration_ms"] = round((time.monotonic() - started) * 1000)
    return info
