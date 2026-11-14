"""관리자가 Main-Quiz 요청(generation)마다 지정한 출제 모델을 읽는다.

`runs/model-overrides.json` (docs/changes/2026-11-14-root-claude-provider):

    {"version": 1, "generations": {"<32자리 generationId>": {
        "model": "claude-opus-5-5", "reason": "…", "approval": "사용자 발언 원문", "at": "ISO 시각"}}}

파일이 없거나 그 ID가 없으면 None — 러너 명령은 지금과 같다. 형식이 틀리면 OverrideError로 그 일감을 보류한다.
기본 모델로 조용히 넘어가지 않는다(지정한 강의가 의도와 다른 모델로 도는 일을 막는다).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FILENAME = "model-overrides.json"
_ID = re.compile(r"[a-f0-9]{32}")
_MODEL = re.compile(r"(gpt|claude)-[A-Za-z0-9.\-]+")


class OverrideError(ValueError):
    pass


def path(runs_dir: Path) -> Path:
    return Path(runs_dir) / FILENAME


def load(runs_dir: Path) -> dict[str, dict]:
    """generationId → 지정 행. 파일이 없으면 빈 dict."""
    target = path(runs_dir)
    if not target.exists():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as cause:
        raise OverrideError(f"{FILENAME}을 읽지 못했다: {cause}") from cause
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("generations"), dict):
        raise OverrideError(f'{FILENAME} 형식이 다르다: {{"version": 1, "generations": {{…}}}}이어야 한다')
    rows = {}
    for generation_id, row in value["generations"].items():
        if not _ID.fullmatch(str(generation_id)):
            raise OverrideError(f"{FILENAME}: generation ID가 32자리 소문자 16진수가 아니다: {generation_id!r}")
        if not isinstance(row, dict) or not _MODEL.fullmatch(str(row.get("model") or "")):
            raise OverrideError(f"{FILENAME}: {generation_id}의 model이 gpt-… 또는 claude-… 이름이 아니다")
        for key in ("reason", "approval", "at"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise OverrideError(f"{FILENAME}: {generation_id}에 {key}가 없다(지정 이유·승인 발언·시각을 남긴다)")
        rows[str(generation_id)] = row
    return rows


def model_for(runs_dir: Path, generation_id: str) -> str | None:
    """이 요청에 지정된 모델, 없으면 None."""
    row = load(runs_dir).get(generation_id)
    return str(row["model"]) if row else None
