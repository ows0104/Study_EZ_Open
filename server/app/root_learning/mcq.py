"""Main-Quiz 선지: 판마다 러너가 올린 `root_mcq` JSON을 문항에 붙인다.

2026-11-14 객관식 모드(docs/changes/2026-11-14-mcq-mode, `root-mcq/1`)로 시작해, 같은 날 주관식 「선지 보기」와
합쳤다(docs/changes/2026-11-14-choices-merge, `root-mcq/2`). 두 모드가 같은 `mcq_choices`를 쓴다.
asset 종류 `root_mcq`, 파일명 `<revision>.json`(`quizbank/root_mcq.py`). 문항·판·학습 기록은 읽기만 한다.
판이 다르거나 판의 문항 글이 달라졌거나 파일이 깨졌으면 그 문항은 선지 없이 보인다.
개인 수정본(2026-11-15, docs/changes/2026-11-15-edited-question-choices)은 판의 원문으로 짝을 찾는다:
발문만 고쳤으면 원문의 선지 그대로, 단답의 정답을 고쳤으면 고친 정답을 정답 선지로 쓴다.
정답을 고친 나열·빈칸·순서·묶음 문항은 칸을 나눌 수 없어 선지 없이 둔다.

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


def current(db, doc) -> bool:
    """이 판에 새 선지(root-mcq/2)가 올라와 있나. 있으면 예전 「선지 보기」(root_choices)는 쓰지 않는다 —
    새 선지가 없는 문항(괜찮은 오답 2개 미만)은 선지 없이 둔다(사용자 2026-11-14 「0개이거나 1개이면 그냥 선택지가 안 보이게」,
    「주관식 선택 시에는 v키로 그 문제에서 지금 만든 선택지 볼 수 있도록」)."""
    asset = stored(db, doc)
    return isinstance(asset, dict) and asset.get('schema') == contract.SCHEMA_V2 and asset.get('revision') == getattr(doc, 'revision', None)


def _authored(doc, question):
    """선지 짝을 찾을 판의 원문. 개인 수정본이 아니면 받은 문항 그대로."""
    if not question.get('personalEdited'):
        return question
    return next((q for q in doc.document['bank_snapshot']['questions']
                 if q['question_id'] == question.get('question_id')), None)


def _resolve(db, doc, question):
    """(판 형식, 칸, 선지를 만들 문항) 또는 None."""
    if question.get('personalFormat'):
        return None   # 형식을 바꾼 내 수정본: 판 선지는 원래 형식의 칸이다(2026-11-17 personal-edit-format)
    original = _authored(doc, question)
    if original is None or original.get('format') not in contract.FORMATS:
        return None
    asset = stored(db, doc)
    row = contract.attachable_v2(asset, doc.revision, original)
    edited_answer = question is not original and question.get('answer') != original.get('answer')
    if row is not None:
        if not edited_answer:
            return 2, row, original
        # 고친 정답이 새 정답 선지. 원문의 정답 단위·묶음이 없는 단답만 — 나머지는 칸을 다시 나눌 수 없다.
        if original['format'] != 'basic' or contract.groups(original) or question.get('format') != 'basic':
            return None
        mine = contract.normalized(question.get('answer', ''))
        wrong = [w for w in row['wrong'] if contract.normalized(w['text']) != mine]
        if not mine or contract.shortfall(question, wrong):
            return None
        return 2, {**row, 'wrong': wrong}, question
    row = contract.attachable(asset, doc.revision, original)
    # v1 칸은 정답 ID가 고정이라 고친 정답과 맞출 수 없다.
    return (1, row, original) if row is not None and not edited_answer else None


def entry(db, doc, question):
    """이 판·이 문항 글에 맞는 (판 형식, 칸) 또는 None."""
    found = _resolve(db, doc, question)
    return found[:2] if found else None


def seed(user_id, question, when) -> str:
    """같은 사용자·문항·날(한국 시간)이면 같은 선지."""
    return f"{user_id or ''}|{question.get('question_id')}|{when.astimezone(KST).date().isoformat()}"


def attach_front(db, doc, question, front, *, user_id=None, when=None):
    found = _resolve(db, doc, question)
    if not found:
        return front
    version, row, question = found
    if version == 2:
        picked = contract.select(question, row, seed(user_id, question, when or datetime.now(UTC)))
        front['mcq_choices'] = picked['choices']
        if picked['groups']:
            # 나눠 묻는 문항: 묶음마다 제목과 선지(사용자 2026-11-14 「묻는 게 여러개이면 선지를 나눠서 제시」).
            front['mcq_groups'] = picked['groups']
    else:
        front['mcq_choices'] = [{'id': c['id'], 'text': c['text']} for c in row['choices']]
    return front


def attach_answer(db, doc, question, answer):
    found = _resolve(db, doc, question)
    if not found:
        return answer
    version, row, question = found
    if version == 2:
        answer['mcqCorrectIds'] = [contract.choice_id(question['question_id'], t, g) for g, t in contract.answer_choices(question)]
        # 오답 풀 전부(많아야 10개). 화면은 이번에 보인 선지의 것만 쓴다 — 답면이 씨앗을 몰라도 된다.
        answer['mcqWrongNotes'] = {w['id']: {'why': w['why_wrong'], 'source': contract.source_label(w)} for w in row['wrong']}
    else:
        answer['mcqCorrectIds'] = list(row['correct_ids'])
    return answer
