"""Main-Quiz 문서의 가벼운 사본 — 학습률·목록 요약 계산 전용(2026-11-12).

한 판(revision)의 문서는 JSON 6–11 MB이고 그 92 %가 문항 그림의 `png_base64`다. 학습 상태·학습률·계획 계산은
그림 바이트를 읽지 않는데, 캘린더 학습률과 강의 목록 요약은 요청마다 이 문서를 통째로 DB에서 읽었다
(운영 중앙값 2.4 s·11.5 s). Cloud Run 메모리(512 MiB)에 원본을 담아 둘 수는 없다.

그래서 (강의, 판, digest)마다 한 번만 원본을 읽어 `png_base64`만 뺀 사본을 만들고, 그림이 든 원본으로 계산한
문항 지문(`task_fingerprints`)을 함께 들고 다닌다. 다음 요청부터는 digest만 읽는다.
RootContent 행은 넣기만 하고 고치지 않는다. 키에 digest가 들어 있으니 판이 바뀌면 새로 만든다.

문항을 화면에 그리는 경로(풀이·지도·관리자)는 이 사본을 쓰지 않는다 — 그림이 없다.
"""
from __future__ import annotations

import copy
import threading
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import select

from app.models.root_learning import RootContent, RootControl
from studyez_contracts.roots import task_fingerprints

LIMIT = 32
_lock = threading.Lock()
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
        light = _get(cache_key)
        if light is None:
            row = db.get(RootContent, (subject, run_id, revision))
            if not row or not row.reviewed:
                continue
            light = lighten(row.document)
            _put(cache_key, light)
        result[(subject, run_id)] = LightRow(subject, run_id, revision, light)
    return result


def clear():
    with _lock:
        _cache.clear()
