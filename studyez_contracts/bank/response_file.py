"""Dispatch new authored JSON and preserved legacy Markdown without guessing."""
import json
import re
from . import authored_json, markdown_file

required = markdown_file.required


def is_json(raw):
    return isinstance(raw, str) and raw.removeprefix('\ufeff').lstrip().startswith('{')


def metadata(raw):
    if is_json(raw):
        return authored_json.loads(raw)
    match = re.match(r'<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->', raw.removeprefix('\ufeff'))
    if not match:
        raise ValueError('파일의 관리 정보가 없습니다.')
    return json.loads(match[1])


def validate(raw, filename, subject, run_id, metadata=None):
    if is_json(raw) or filename.endswith('.json'):
        return authored_json.validate(raw, filename, subject, run_id, metadata)
    result = markdown_file.validate(raw, filename, subject, run_id, metadata)
    if authored_json.json_version(result['promptVersion']):
        raise ValueError('프롬프트 1.80 이상은 실제 순수 JSON 파일이 필요합니다.')
    return result
