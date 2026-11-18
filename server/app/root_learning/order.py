"""Main-Quiz 순서 맞추기: 판마다 러너가 올린 `root_order` JSON(`root-order/1`)으로 순서형 나열 문항을 가른다.

docs/changes/2026-11-18-ordering-screen. asset 종류 `root_order`, 파일명 `<revision>.json`(`quizbank/root_order.py`).
문항·판·학습 기록은 읽기만 한다. 판이 다르거나 문항 글이 달라졌거나 파일이 깨졌으면 그 문항은 지금처럼(선지로) 보인다.
붙이는 자리는 `mcq.attach_front`·`attach_answer`다 — 순서형이면 선지 대신 순서 칸을 붙인다.
"""
import json

from sqlalchemy import select
from studyez_contracts.roots import order as contract

from app.models import Asset
from app.storage import ObjectStorage

KIND = 'root_order'
_CACHE: dict[tuple, dict | None] = {}
_LIMIT = 32


def stored(db, doc):
    revision = getattr(doc, 'revision', None)
    if db is None or not revision:
        return None
    asset = db.scalar(select(Asset).where(Asset.subject == doc.subject, Asset.run_id == doc.run_id,
                                          Asset.kind == KIND, Asset.filename == f'{revision}.json'))
    if asset is None:
        return None
    key = (asset.object_key, asset.size_bytes, str(asset.uploaded_at))
    if key not in _CACHE:
        try:
            body = ObjectStorage().get_bytes(asset.object_key)
            data = json.loads(body) if body else None
        except Exception:  # noqa: BLE001 — 못 읽는 판정은 없는 것과 같다
            data = None
        while len(_CACHE) >= _LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = data
    return _CACHE[key]


def row(db, doc, question):
    """이 판·이 문항 글에 맞는 순서 칸, 아니면 None. 형식을 바꾸거나 정답을 고친 내 수정본은 대상이 아니다."""
    if question.get('personalFormat'):
        return None
    original = question
    if question.get('personalEdited'):
        original = next((q for q in doc.document['bank_snapshot']['questions']
                         if q['question_id'] == question.get('question_id')), None)
        if original is None or question.get('answer') != original.get('answer'):
            return None
    found = contract.attachable(stored(db, doc), getattr(doc, 'revision', None), original)
    return (found, original) if found is not None else None


def attach_front(db, doc, question, front, seed: str) -> bool:
    """순서형이면 섞은 단계를 붙이고 True. 정답 순서는 앞면에 없다."""
    found = row(db, doc, question)
    if not found:
        return False
    front['order_items'] = contract.shuffled(found[1], found[0], seed)
    return True


def attach_answer(db, doc, question, answer) -> bool:
    found = row(db, doc, question)
    if not found:
        return False
    answer['orderCorrectIds'] = [c['id'] for c in contract.correct(found[1], found[0])]
    return True
