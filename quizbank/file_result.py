"""Read a validated CLI result file without printing its entire JSON again."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .coverage import _call, WRITTEN
from .session import SessionError


def write(prompt: str, schema: dict, work: Path, model: str | None, label: str,
          filename: str) -> tuple[dict, dict]:
    target = work / filename
    target.unlink(missing_ok=True)
    schema_name = target.stem + '.schema.json'
    (work / schema_name).write_text(json.dumps(schema, ensure_ascii=False), encoding='utf-8')
    task = prompt + '\n\n' + (
        f'결과 전체를 {schema_name}에 맞게 {filename}에 UTF-8 JSON으로 저장한다. '
        '입력 파일은 변경하지 않는다. 코드로 공통 빈 필드를 구성해도 되지만 실제 판단·해설은 직접 작성한다. '
        '저장한 파일을 확인하고 최종 응답에는 전체 JSON을 다시 출력하지 않고 {"written":true}만 반환한다.')
    _, info = _call(task, WRITTEN, work, model, label)
    try:
        result = json.loads(target.read_text(encoding='utf-8'))
        jsonschema.validate(result, schema)
    except (OSError, ValueError, jsonschema.ValidationError) as cause:
        raise SessionError(f'{label}: 결과 파일이 없거나 형식에 맞지 않습니다: {str(cause)[:500]}') from cause
    return result, info
