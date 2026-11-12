"""Main-Quiz 문서의 가벼운 사본 — 학습률·목록 요약 계산 전용(2026-11-12).

한 판(revision)의 문서는 JSON 6–11 MB이고 그 92 %가 문항 그림의 `png_base64`다. 학습 상태·학습률·계획 계산은
그림 바이트를 읽지 않는데, 캘린더 학습률과 강의 목록 요약은 요청마다 이 문서를 통째로 DB에서 읽었다
(운영 중앙값 2.4 s·11.5 s). Cloud Run 메모리(512 MiB)에 원본을 담아 둘 수는 없다.

그래서 (강의, 판, digest)마다 한 번만 원본을 읽어 `png_base64`만 뺀 사본을 만들고, 그림이 든 원본으로 계산한
문항 지문(`task_fingerprints`)을 함께 들고 다닌다. 다음 요청부터는 digest만 읽는다.
RootContent 행은 넣기만 하고 고치지 않는다. 키에 digest가 들어 있으니 판이 바뀌면 새로 만든다.

문항을 화면에 그리는 경로(풀이·지도·관리자)는 이 사본을 쓰지 않는다 — 그림이 없다.

인스턴스가 뜰 때 미리 만든다(`warm`, 2026-11-12). 사본은 인스턴스 메모리에만 있어서 배포(하루 여러 번)·새 인스턴스마다
첫 목록 요청이 공개 판 전부(23편 104 MB)를 읽었다(운영 6.5–8.8 s). 그 사이 다른 요청도 같은 원본을 동시에 읽어
512 MiB를 넘겨 인스턴스가 죽었다(운영 로그 2026-11-12 「Memory limit of 512 MiB exceeded」 여러 번) — 숫자 칸이
끝내 비는 원인. 그래서 원본은 한 번에 하나만 읽는다(`_load_lock`). 동시에 같은 판을 찾던 요청은 기다렸다 그 사본을 쓴다.
"""
from __future__ import annotations

import copy
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import select

from app.models.root_learning import RootContent, RootControl
from studyez_contracts.roots import task_fingerprints

# 사본 하나는 파이썬 메모리 약 1.9 MB(운영 23편 43 MB, 2026-11-12 측정). 공개 판이 상한을 넘으면 목록 요청마다
# 처음부터 다시 읽게 되므로(LRU를 차례로 훑으면 하나도 안 맞는다) 넉넉히 둔다.
LIMIT = 64
log = logging.getLogger(__name__)
_lock = threading.Lock()
# 원본(6–12 MB JSON)을 읽고 줄이는 일은 인스턴스 전체에서 한 번에 하나. 동시 요청이 각자 원본을 들고 있지 않게 한다.
_load_lock = threading.Lock()
_cache: OrderedDict[tuple[str, str, str, str], LightDocument] = OrderedDict()


class LightDocument(dict):
    """원본 문서에서 그림 바이트만 뺀 dict. `task_fingerprints`는 원본으로 계산한 값(state.replay_tasks가 쓴다)."""
    task_fingerprints: dict[str, str]


@dataclass(frozen=True)
class LightRow:
    """`RootContent` 행 대신 쓰는 읽기 전용 모양(overview_data·availability가 읽는 칸만)."""
    subject: str
    run_id: str
    revision: str
    document: LightDocument
    reviewed: bool = True


def lighten(document: dict) -> LightDocument:
    bank = document.get('bank_snapshot') or {}
    questions = [{**q, 'stimuli': [{k: v for k, v in s.items() if k != 'png_base64'} for s in q['stimuli']]}
                 if q.get('stimuli') else q for q in bank.get('questions', [])]
    stripped = {**document, 'bank_snapshot': {**bank, 'questions': questions}} if bank else document
    # 요청 사이에 나눠 쓰므로 ORM 행과 떼어 둔다(그림을 뺀 뒤라 복사는 싸다).
    light = LightDocument(copy.deepcopy(stripped))
    light.task_fingerprints = task_fingerprints(document) if document.get('tasks') is not None else {}
    return light


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


def current_rows(db, keys) -> dict[tuple[str, str], LightRow]:
    """강의 키 → 켜진 현재 판의 검토된 문서(가벼운 사본). 판이 없거나 검토 전이면 빠진다. 접근 권한은 부르는 쪽이 본다."""
    wanted = set(keys)
    if not wanted:
        return {}
    controls = {(c.subject, c.run_id): c.revision for c in db.scalars(select(RootControl).where(
        RootControl.revision.is_not(None), RootControl.run_id.in_({r for _, r in wanted})))
        if (c.subject, c.run_id) in wanted}
    if not controls:
        return {}
    heads = db.execute(select(RootContent.subject, RootContent.run_id, RootContent.revision, RootContent.digest)
                       .where(RootContent.reviewed.is_(True), RootContent.run_id.in_({r for _, r in controls}))).all()
    result = {}
    for subject, run_id, revision, digest in heads:
        if controls.get((subject, run_id)) != revision:
            continue
        cache_key = (subject, run_id, revision, digest or '')
        light = _get(cache_key) or _load(db, cache_key)
        if light is None:
            continue
        result[(subject, run_id)] = LightRow(subject, run_id, revision, light)
    return result


def _load(db, cache_key):
    subject, run_id, revision, _ = cache_key
    with _load_lock:
        light = _get(cache_key)      # 기다리는 사이 다른 요청이 만들었으면 그것을 쓴다.
        if light is not None:
            return light
        row = db.get(RootContent, (subject, run_id, revision))
        if not row or not row.reviewed:
            return None
        light = lighten(row.document)
        _put(cache_key, light)
        # 원본 dict를 세션에서 떼어 바로 놓아 준다(요청이 끝날 때까지 들고 있지 않게).
        db.expunge(row)
        return light


def warm(db) -> tuple[int, float]:
    """켜진 공개 판 전부의 사본을 미리 만든다(인스턴스가 요청을 받기 전에, app.main). (만든 수, 걸린 초).

    한 강의가 실패해도 나머지는 만든다. 실패한 강의는 첫 요청 때 원래 경로로 다시 시도된다."""
    started = time.perf_counter()
    keys = [(c.subject, c.run_id) for c in db.scalars(select(RootControl).where(
        RootControl.enabled.is_(True), RootControl.revision.is_not(None)).order_by(RootControl.subject, RootControl.run_id))]
    built = 0
    for key in keys[:LIMIT]:
        try:
            built += len(current_rows(db, [key]))
        except Exception:
            log.exception('Main-Quiz 가벼운 사본 미리 만들기 실패 %s/%s', *key)
            db.rollback()
    return built, time.perf_counter() - started


def clear():
    with _lock:
        _cache.clear()
