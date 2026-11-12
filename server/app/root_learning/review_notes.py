"""답에 붙는 검수 메모(reviewNotes·reviewIssues)를 출제 기록에서 판마다 한 번만 뽑아 둔다(2026-11-12).

출제 기록 `root_generation.result`는 판당 3.6–9.5 MB(운영 측정)인데, 답 하나에 붙는 것은 「ok가 아닌」 검수 메모와
그 문항을 부르는 이슈뿐이다. 다음 문제 미리 받기(prepare)·답 보기 화면·개인 수정 저장이 이 result를 요청마다 통째로
읽어 prepare가 1.2–4.4 s 걸렸다. 그래서 출제 기록은 result 없이 읽고(routes.root_learning.active_generation),
메모만 (기록 ID, result_digest)마다 한 번 뽑아 인스턴스 메모리에 둔다. result는 넣기만 하고 고치지 않으며
digest가 바뀌면 키가 바뀐다. 뽑은 결과는 예전 revealed_answer가 만들던 값과 같다.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from sqlalchemy import select

LIMIT = 64
_lock = threading.Lock()
_load_lock = threading.Lock()
_cache: OrderedDict[tuple[str, str], dict] = OrderedDict()

REPLACEMENT_POLICIES = ('verified-main-quiz-replacement/1', 'verified-main-quiz-curation/1')


def extract(result: dict) -> dict:
    """{'notes': 문항 ID가 붙은 ok 아닌 메모 전부, 'issues': 기록 전체 이슈}. 문항별 거르기는 부르는 쪽."""
    if result.get('policy') in REPLACEMENT_POLICIES:
        from app.root_learning.replacement_import import report
        summary = report(result)
        return {'notes': summary['questionNotes'], 'issues': summary['issues']}
    medical = '의학 검토' if (result.get('manifest') or {}).get('medicalFinal') else '독립 정답 검수'
    notes = [{'source': label, **r}
             for label, checks in [('원본 대조', result['sourceAudit']['question_checks']), (medical, result['medical'])]
             for r in checks['reviews'] if r['verdict'] != 'ok']
    issues = result['sourceAudit']['input_issues'] + result['validation']['errors'] + result['validation']['warnings']
    return {'notes': notes, 'issues': issues}


def for_generation(db, generation) -> dict:
    """이 출제 기록의 메모 묶음. 처음 한 번만 result를 읽는다(인스턴스 전체에서 한 번에 하나)."""
    key = (generation.id, generation.result_digest or '')
    hit = _get(key)
    if hit is not None:
        return hit
    from app.models.root_generation import RootGeneration
    with _load_lock:
        hit = _get(key)
        if hit is not None:
            return hit
        result = db.scalar(select(RootGeneration.result).where(RootGeneration.id == generation.id))
        value = extract(result) if result else {'notes': [], 'issues': []}
        del result
        _put(key, value)
        return value


def _get(key):
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
        return hit


def _put(key, value):
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > LIMIT:
            _cache.popitem(last=False)


def clear():
    with _lock:
        _cache.clear()
