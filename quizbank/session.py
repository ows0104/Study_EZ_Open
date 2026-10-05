"""도구를 끈 Codex GPT 세션에서 스키마에 맞는 문제은행 JSON을 받는다."""

from __future__ import annotations

import json

import jsonschema

from studyez_llm import codex
from studyez_llm.codex import SessionError


def run_structured(prompt: str, schema: dict, *, system: str, label: str,
                   timeout: int = 1200, model: str | None = None) -> tuple[dict, dict]:
    """`(structured_output, info)`. 기존 생성기·서버의 사용량 필드를 유지한다."""
    result = codex.run(prompt, blind=True, model=model, timeout=timeout, label=label,
                       schema=schema, system=system)
    try:
        output = json.loads(result["text"])
        jsonschema.validate(output, schema)
    except (ValueError, jsonschema.ValidationError) as cause:
        raise SessionError(f"{label}: 구조화 출력이 스키마에 맞지 않는다: {cause}") from cause
    usage = result["usage"]
    return output, {
        "seconds": round(result["duration_ms"] / 1000, 1),
        "cost_usd": result["cost_usd"],
        "input_tokens": usage["input_tokens"] + usage["cache_read_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "models": sorted(result["models"]),
    }
