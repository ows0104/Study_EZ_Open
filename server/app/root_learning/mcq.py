"""Main-Quiz 선지: 판마다 러너가 올린 `root_mcq` JSON을 문항에 붙인다.

2026-11-14 객관식 모드(docs/changes/2026-11-14-mcq-mode, `root-mcq/1`)로 시작해, 같은 날 주관식 「선지 보기」와
합쳤다(docs/changes/2026-11-14-choices-merge, `root-mcq/2`). 두 모드가 같은 `mcq_choices`를 쓴다.
asset 종류 `root_mcq`, 파일명 `<revision>.json`(`quizbank/root_mcq.py`). 문항·판·학습 기록은 읽기만 한다.
판이 다르거나 문항 글이 달라졌거나(개인 수정본 포함) 파일이 깨졌으면 그 문항은 선지 없이 보인다.

v2: asset에는 오답 풀만 있다. 앞면에 보일 선지(정답 전부 + 오답 4~5개)와 순서는 씨앗(사용자·문항·학습일)으로 고른다 —
같은 날은 늘 같고, 다음 복습 날엔 다른 조합이다. 선지 ID는 글에서 만든 해시라 앞면만으로는 정답을 알 수 없다.
답면에는 정답 ID(`mcqCorrectIds`)와 오답마다 「왜 틀렸나」·족보 출처(`mcqWrongNotes`)를 싣는다.
"""
import json
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select
from studyez_contracts.roots import mcq as contract

from app.models import Asset
from app.storage import ObjectStorage

KIND = 'root_mcq'
_CACHE: dict[tuple, dict | None] = {}
_LIMIT = 32
KST = timezone(timedelta(hours=9))


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
    """이 판·이 문항 글에 맞는 (판 형식, 칸) 또는 None."""
    if question.get('format') not in contract.FORMATS:
        return None
    asset = stored(db, doc)
    row = contract.attachable_v2(asset, doc.revision, question)
    if row is not None:
        return 2, row
    row = contract.attachable(asset, doc.revision, question)
    return (1, row) if row is not None else None


def seed(user_id, question, when) -> str:
    """같은 사용자·문항·날(한국 시간)이면 같은 선지."""
    return f"{user_id or ''}|{question.get('question_id')}|{when.astimezone(KST).date().isoformat()}"


def attach_front(db, doc, question, front, *, user_id=None, when=None):
    found = entry(db, doc, question)
    if not found:
        return front
    version, row = found
    if version == 2:
        picked = contract.select(question, row, seed(user_id, question, when or datetime.now(UTC)))
        front['mcq_choices'] = picked['choices']
    else:
        front['mcq_choices'] = [{'id': c['id'], 'text': c['text']} for c in row['choices']]
    return front


def attach_answer(db, doc, question, answer):
    found = entry(db, doc, question)
    if not found:
        return answer
    version, row = found
    if version == 2:
        answer['mcqCorrectIds'] = [contract.choice_id(question['question_id'], t) for t in contract.correct_texts(question)]
        # 오답 풀 전부(많아야 10개). 화면은 이번에 보인 선지의 것만 쓴다 — 답면이 씨앗을 몰라도 된다.
        answer['mcqWrongNotes'] = {w['id']: {'why': w['why_wrong'], 'source': contract.source_label(w)} for w in row['wrong']}
    else:
        answer['mcqCorrectIds'] = list(row['correct_ids'])
    return answer
