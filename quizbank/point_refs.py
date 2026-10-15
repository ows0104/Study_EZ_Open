"""One source-only CLI repair of invalid parent/target page references."""
from __future__ import annotations

import json
from pathlib import Path

from .points import PLAN, shape_plan
from .session import SessionError


def _content(plan: dict) -> list:
    return [(o['objective_id'], o['objective'], [(t['point_id'], t['target'])
             for t in o['retrieval_targets']]) for o in plan['objectives']]


def checked_plan(raw: dict, count: int, work: Path, out: Path, model, call) -> tuple[dict, list]:
    try:
        return shape_plan(raw, count), []
    except SessionError as cause:
        if str(cause) != '출제 포인트 계획: 포인트의 실제 근거 쪽이 필요합니다.':
            raise
    (work / 'reference-plan.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    prompt = (Path(__file__).parent / 'prompts/points-reference-repair.md').read_text(encoding='utf-8')
    fixed, info = call(prompt, PLAN, work, model, '원본 포인트 근거 연결 복구 1회')
    (out / 'independent-plan.reference-repair.raw.json').write_text(
        json.dumps(fixed, ensure_ascii=False, indent=2), encoding='utf-8')
    if (_content(fixed) != _content(raw)
            or fixed['rejected_candidates'] != raw['rejected_candidates']
            or not set(raw['unreadable_pages']).issubset(fixed['unreadable_pages'])):
        raise SessionError('포인트 근거 연결 복구에서 목표·포인트 내용·ID·제외 기록이 바뀌었습니다.')
    plan = shape_plan(fixed, count)  # A second failure ends this attempt; never loop or auto-pass.
    (out / 'independent-plan.reference-repair.json').write_text(json.dumps({
        'attempts': 1, 'contentAndIdsPreserved': True, 'usage': info,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return plan, [{'step': '원본 포인트 근거 연결 복구 1회', **info}]
