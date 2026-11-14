"""Claude Code CLI(로그인 구독)로 한 단계를 실행하고 결과를 Codex 실행기와 같은 사용량 계약으로 옮긴다.

`codex.run`이 `claude-…` 모델 이름을 받으면 이 모듈로 넘긴다(docs/changes/2026-11-14-root-claude-provider).
호출 인자·반환 형식은 `codex.run`과 같다. 모델·프롬프트·스키마·검사 기준은 호출한 쪽이 정하며 여기서 바꾸지 않는다.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .codex import SessionError  # 호출부가 잡는 예외 하나를 공유한다
from .execution import run_process

# 작업 세션이 쓸 수 있는 내장 도구. 웹 검색·웹 가져오기·하위 에이전트·MCP는 싣지 않는다.
WORK_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep", "Bash")
# 한 메시지에 바로 붙이는 이미지 한도. 넘으면 파일 경로만 알려 Read 도구로 열게 한다(같은 바이트).
INLINE_IMAGE_LIMIT = 20
INLINE_IMAGE_BYTES = 20_000_000
# 공급자 거절은 원장의 model_content_restricted 판정이 읽는 표식으로 올린다(runner.root_native_json.classify_error).
REFUSAL_MARKER = "[CLAUDE_CONTENT_RESTRICTED]"
LIMIT_MARKERS = ("usage limit", "rate limit", "limit reached", "quota", "overloaded")
# Windows 명령줄(약 32,000자)을 넘지 않게, 긴 시스템 지시·스키마는 인자 대신 첫 메시지 앞에 싣는다.
ARG_LIMIT = 8000


def executable() -> str:
    exe = os.environ.get("STUDYEZ_CLAUDE_BIN") or shutil.which("claude")
    if not exe:
        for candidate in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude"):
            if candidate.is_file():
                exe = str(candidate)
                break
    if not exe:
        raise SessionError("claude CLI를 찾지 못했다. PATH 또는 STUDYEZ_CLAUDE_BIN을 확인해라.")
    return exe


def child_env() -> dict[str, str]:
    """uv 실행기의 PYTHONHOME은 모델이 시작하는 Python을 깨뜨린다(codex.child_env와 같은 이유)."""
    env = dict(os.environ)
    home = env.pop("UV_INTERNAL__PYTHONHOME", None)
    if home is not None and env.get("PYTHONHOME") == home:
        env.pop("PYTHONHOME")
    # 사용자 대화형 설정의 자동 업데이트·원격 측정 프롬프트가 하위 프로세스를 멈추지 않게 한다.
    env.setdefault("DISABLE_AUTOUPDATER", "1")
    return env


def inline_images(images: list[Path] | None) -> tuple[list[Path], list[Path]]:
    """(메시지에 붙일 이미지, 경로로만 알릴 이미지). 한도를 넘으면 전부 경로로 알린다(일부만 붙이지 않는다)."""
    images = [Path(p).resolve() for p in images or []]
    if not images:
        return [], []
    if len(images) <= INLINE_IMAGE_LIMIT and sum(p.stat().st_size for p in images) <= INLINE_IMAGE_BYTES:
        return images, []
    return [], images


def command(*, model: str, blind: bool, resume: str | None = None, schema: dict | None = None,
            system: str | None = None, writable: list[Path] | None = None) -> list[str]:
    argv = [executable(), "-p", "--model", model,
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            # 사용자·프로젝트 설정, CLAUDE.md, 스킬, 플러그인, 훅, MCP를 싣지 않는다. 인증·내장 도구만 남는다.
            "--safe-mode", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--tools", "" if blind else ",".join(WORK_TOOLS)]
    if not blind:
        # 셸·파일 도구를 묻지 않고 쓰게 한다. 작업 폴더(cwd)와 명시한 쓰기 폴더만 연다.
        argv += ["--permission-mode", "bypassPermissions"]
        for folder in writable or []:
            argv += ["--add-dir", str(Path(folder).resolve())]
    else:
        argv += ["--no-session-persistence"]
    if system and len(system) <= ARG_LIMIT:
        argv += ["--system-prompt", system]
    if schema is not None and len(json.dumps(schema, ensure_ascii=False)) <= ARG_LIMIT:
        argv += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    if resume:
        argv += ["--resume", resume]
    return argv


def prompt_text(prompt: str, *, system: str | None = None, schema: dict | None = None) -> str:
    """인자로 싣지 못한 긴 시스템 지시·스키마를 첫 메시지에 그대로 옮긴다(내용은 바꾸지 않는다)."""
    head = ""
    if system and len(system) > ARG_LIMIT:
        head += "SYSTEM INSTRUCTIONS (follow before the task below):\n" + system + "\n\n"
    tail = ""
    if schema is not None and len(json.dumps(schema, ensure_ascii=False)) > ARG_LIMIT:
        tail = ("\n\nYour final response must be ONLY one JSON value (no code fence, no other text) valid against this "
                "JSON Schema:\n" + json.dumps(schema, ensure_ascii=False))
    return head + prompt + tail


def final_text(text: str) -> str:
    """스키마를 프롬프트로 넘긴 경우 모델이 붙인 코드 울타리만 걷는다."""
    body = text.strip()
    if body.startswith("```") and body.endswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body[:-3].strip()
    return body


def first_message(prompt: str, inline: list[Path], listed: list[Path]) -> str:
    """stream-json 입력 한 줄. 붙이지 못한 이미지는 같은 파일의 경로를 알려 Read로 열게 한다."""
    text = prompt
    if listed:
        text += ("\n\nThe images named above are NOT attached to this message. Open every one of these files with the Read "
                 "tool before working (same bytes): " + ", ".join(str(p) for p in listed))
    content: list[dict] = [{"type": "text", "text": text}]
    for path in inline:
        media = mimetypes.guess_type(path.name)[0] or "image/png"
        content.append({"type": "image", "source": {"type": "base64", "media_type": media,
                                                    "data": base64.b64encode(path.read_bytes()).decode("ascii")}})
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n"


def parse_events(stdout: str, *, model: str) -> dict:
    result, refused = None, False
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as cause:
            raise SessionError("claude 출력이 JSONL이 아니다") from cause
        if not isinstance(event, dict):
            raise SessionError("claude 이벤트가 객체가 아니다")
        if event.get("type") == "assistant":
            message = event.get("message") or {}
            refused = refused or message.get("stop_reason") == "refusal"
        if event.get("type") == "result":
            result = event
    if result is None:
        raise SessionError("claude 세션 완료 이벤트가 없다 (출력 중단)")
    refused = refused or result.get("stop_reason") == "refusal"
    if refused:
        raise SessionError(REFUSAL_MARKER + " Claude가 안전상 이유로 응답을 거절했다 (stop_reason=refusal)")
    if result.get("is_error") or result.get("subtype") != "success":
        detail = str(result.get("result") or result.get("subtype") or "")[-1500:]
        raise SessionError(f"claude 세션 오류: {detail}")
    if "structured_output" in result and result["structured_output"] is not None:
        text = json.dumps(result["structured_output"], ensure_ascii=False)
    else:
        text = final_text(result.get("result") or "")
    if not str(text).strip():
        raise SessionError("claude 최종 응답이 비어 있다")
    usage = result.get("usage") or {}
    counts = {"input_tokens": int(usage.get("input_tokens") or 0),
              "output_tokens": int(usage.get("output_tokens") or 0),
              "cache_read_input_tokens": int(usage.get("cache_read_input_tokens") or 0),
              "cache_creation_input_tokens": int(usage.get("cache_creation_input_tokens") or 0)}
    return {"text": text, "session_id": result.get("session_id"), "turns": int(result.get("num_turns") or 0),
            "cost_usd": result.get("total_cost_usd"), "usage": counts,
            "models": {model: counts["output_tokens"]}, "provider": "claude", "warnings": []}


def run(prompt: str, *, blind: bool, cwd: Path | None = None, model: str, timeout: int = 1800, label: str = "",
        resume: str | None = None, schema: dict | None = None, system: str | None = None,
        previous_usage: dict | None = None, images: list[Path] | None = None,
        writable: list[Path] | None = None) -> dict:
    """한 번의 Claude Code 세션. 가림 실행은 도구 없이 임시 폴더, 작업 실행은 주어진 cwd에서 돈다."""
    if resume and previous_usage is None:
        raise SessionError("Claude 세션 재개에는 이전 응답의 session_usage가 필요하다")
    started = time.monotonic()
    inline, listed = inline_images(images)
    with tempfile.TemporaryDirectory(prefix="studyez-claude-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp) if blind else Path(cwd).resolve()
        argv = command(model=model, blind=blind, resume=resume, schema=schema, system=system, writable=writable)
        message = first_message(prompt_text(prompt, system=system, schema=schema), inline, listed)
        try:
            proc = run_process(argv, input=message, cwd=work, timeout=timeout,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=child_env())
        except subprocess.TimeoutExpired as cause:
            raise SessionError(f"{label or '세션'}: {timeout}초 안에 끝나지 않았다") from cause
        except OSError as cause:
            raise SessionError(f"{label or '세션'}: claude 실행 실패: {cause}") from cause
    try:
        info = parse_events(proc.stdout or "", model=model)
    except SessionError as cause:
        tail = (proc.stderr or "").strip()[-800:]
        raise SessionError(f"{label or '세션'}: {cause}" + (f"\n{tail}" if tail else "")) from cause
    if proc.returncode:
        tail = ((proc.stdout or "")[-1200:] + "\n" + (proc.stderr or "")[-800:]).strip()
        raise SessionError(f"{label or '세션'}: claude가 {proc.returncode}로 끝났다\n{tail}")
    # Claude의 result.usage는 그 호출분이다. Codex 재개(누적값)와 달리 빼지 않는다.
    info["session_usage"] = {key: info["usage"][key] + (previous_usage or {}).get(key, 0) for key in info["usage"]}
    info["duration_ms"] = round((time.monotonic() - started) * 1000)
    return info
