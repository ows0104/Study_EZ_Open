"""눈먼 `claude -p` 한 번 — 스키마를 주고 구조화 출력을 받는다.

quizgen/session.py 와 같은 원칙이다: 도구 없음, 사용자·프로젝트 설정 없음. 다른 점 셋.

    --json-schema        답을 `structured_output` 으로 받는다. 본문에서 JSON 을 오려 낼 일이 없다
    --strict-mcp-config  계정의 MCP 커넥터가 세션마다 따라붙는다. 2026-10-03 한 줄 프롬프트로
                         잰 입력이 131,232 토큰 → 이 플래그로 3,566
    --system-prompt      코딩용 기본 지시를 짧은 한 줄로 바꾼다 → 1,387

quizgen 을 import 하지 않는다(덩이 경계). 같은 일을 하는 30줄을 둘 둔다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time

# 강의 하나의 문제은행 JSON 은 길다. CLI 기본 출력 상한에서 잘린다.
MAX_OUTPUT_TOKENS = "64000"


class SessionError(RuntimeError):
    pass


def run_structured(prompt: str, schema: dict, *, system: str, label: str,
                   timeout: int = 1200, model: str | None = None) -> tuple[dict, dict]:
    """`(structured_output, info)`. info 는 seconds·cost_usd·usage·model."""
    exe = os.environ.get("STUDYEZ_CLAUDE_BIN") or shutil.which("claude")
    if not exe:
        raise SessionError("claude CLI 를 찾지 못했다. PATH 를 확인해라.")
    argv = [exe, "-p", "--output-format", "json", "--setting-sources", "", "--tools", "",
            "--strict-mcp-config", "--system-prompt", system, "--json-schema", json.dumps(schema)]
    if model:
        argv += ["--model", model]
    env = {**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": os.environ.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS", MAX_OUTPUT_TOKENS)}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="quizbank-blind-", ignore_cleanup_errors=True) as cwd:
        try:
            proc = subprocess.run(argv, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  cwd=cwd, env=env, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise SessionError(f"{label}: {timeout // 60}분 안에 끝나지 않았다") from e
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise SessionError(f"{label}: claude 가 {proc.returncode} 로 끝났다\n{tail}")
    try:
        envelope = json.loads(proc.stdout)
    except ValueError as e:
        raise SessionError(f"{label}: claude 출력이 JSON 이 아니다\n{proc.stdout[-800:]}") from e
    output = envelope.get("structured_output")
    if envelope.get("is_error") or not isinstance(output, dict):
        raise SessionError(f"{label}: 구조화 출력이 없다 ({envelope.get('subtype')} · {envelope.get('stop_reason')})")
    usage = envelope.get("usage") or {}
    info = {
        "seconds": round(time.monotonic() - started, 1),
        "cost_usd": envelope.get("total_cost_usd"),
        "input_tokens": sum(usage.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
        "output_tokens": usage.get("output_tokens"),
        "models": sorted((envelope.get("modelUsage") or {}).keys()),
    }
    return output, info
