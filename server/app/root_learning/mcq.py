"""「객관식 모드」 선지: 판마다 러너가 올린 `root-mcq/1` JSON을 문항에 붙인다(2026-11-14, docs/changes/2026-11-14-mcq-mode).

asset 종류 `root_mcq`, 파일명 `<revision>.json`(`quizbank/root_mcq.py`). 문항·판·학습 기록은 읽기만 한다.
판이 다르거나 문항 글이 달라졌거나(개인 수정본 포함) 파일이 깨졌으면 그 문항은 선지 없이 보인다.
앞면에는 선지 글만(`mcq_choices`), 정답 ID는 답을 편 응답에만(`mcqCorrectIds`) 싣는다. 화면이 모드에 따라 쓴다.
"""
import json

from sqlalchemy import select
from studyez_contracts.roots import mcq as contract

from app.models import Asset
from app.storage import ObjectStorage

KIND = 'root_mcq'
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
        except Exception:  # noqa: BLE001 — 못 읽는 선지는 없는 것과 같다
            data = None
        while len(_CACHE) >= _LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = data
    return _CACHE[key]


def entry(db, doc, question):
    """이 판·이 문항 글에 맞는 객관식 칸 또는 None."""
    if question.get('format') not in contract.FORMATS:
        return None
    return contract.attachable(stored(db, doc), doc.revision, question)


def attach_front(db, doc, question, front):
    row = entry(db, doc, question)
    if row:
        front['mcq_choices'] = [{'id': c['id'], 'text': c['text']} for c in row['choices']]
    return front


def attach_answer(db, doc, question, answer):
    row = entry(db, doc, question)
    if row:
        answer['mcqCorrectIds'] = list(row['correct_ids'])
    return answer
