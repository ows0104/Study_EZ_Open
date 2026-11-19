"""operator-stage-result/1: a stage answer a person brought from outside the runner (docs/changes/2026-11-19-operator-normalize-import).

The record sits beside the generation folder (`<generation id>/operator-stage-results.json`), like operator-exclusions.json:

    {"version": 1, "stages": {"normalize": {"file": "operator-normalize.json", "sha256": "<64 hex>",
      "producer": "ChatGPT 웹 …", "reason": "…", "approval": "…", "at": "…"}}}

The file it names is the full result.json of that stage, in the same folder. The runner then does not call a model for
that stage: the same acceptance checks decide, and the receipt says who produced it instead of carrying model evidence.
"""
import hashlib
import json
import re
from pathlib import Path

POLICY = 'operator-stage-result/1'
FILENAME = 'operator-stage-results.json'
STAGES = ('normalize',)
FIELDS = ('producer', 'reason', 'approval', 'at')


class OperatorStageError(ValueError):
    pass


def record_path(out):
    """`out` is the generation folder (`<generation id>/generation`)."""
    return Path(out).resolve().parent / FILENAME


def load(out):
    """The validated record, or None when there is none."""
    path = record_path(out)
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding='utf-8'))
    stages = doc.get('stages') if isinstance(doc, dict) else None
    if doc.get('version') != 1 or not isinstance(stages, dict) or not stages:
        raise OperatorStageError(f'{FILENAME}: version 1 with stages is required')
    for name, row in stages.items():
        if name not in STAGES:
            raise OperatorStageError(f'{FILENAME}: {name}: only {", ".join(STAGES)} can be brought from outside')
        if not isinstance(row, dict) or set(row) != {'file', 'sha256', *FIELDS}:
            raise OperatorStageError(f'{FILENAME}: {name}: file, sha256, {", ".join(FIELDS)} are required (nothing else)')
        if not all(isinstance(row[k], str) and row[k].strip() for k in ('file', *FIELDS)):
            raise OperatorStageError(f'{FILENAME}: {name}: empty field')
        if not re.fullmatch(r'[0-9a-f]{64}', str(row['sha256'])):
            raise OperatorStageError(f'{FILENAME}: {name}: sha256 must be 64 lowercase hex')
        if Path(row['file']).name != row['file'] or row['file'] in (FILENAME, '.', '..'):
            raise OperatorStageError(f'{FILENAME}: {name}: file must be a plain name in the same folder')
    return doc


def entry(out, stage):
    """(row, body, record sha256) for `stage`, or None when the record does not name it."""
    doc = load(out)
    if doc is None or stage not in doc['stages']:
        return None
    row = doc['stages'][stage]
    path = record_path(out).parent / row['file']
    if not path.is_file() or path.is_symlink():
        raise OperatorStageError(f'{FILENAME}: {stage}: {row["file"]} is missing')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != row['sha256']:
        raise OperatorStageError(f'{FILENAME}: {stage}: {row["file"]} is not the file the record names (sha256)')
    return row, body, hashlib.sha256(record_path(out).read_bytes()).hexdigest()
