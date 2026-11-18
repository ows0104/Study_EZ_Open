"""Main-Quiz 순서 맞추기(`root-order/1`, docs/changes/2026-11-18-ordering-screen).

순서가 곧 내용인 나열 문항(예: 「폭스바이러스의 복제주기 단계는?」)은 선지 대신 단계를 순서대로 놓아 푼다.
출제는 sequence 형식을 쓰지 않아 이런 문항도 `list`로 저장되고, 문항에는 순서형 표시가 없다.
그래서 판(revision)마다 판별 asset 하나(`root_order`, `<revision>.json`)에 모델 판정을 둔다.
문항·판·학습 기록·선지 asset은 읽기만 한다. DB·서버·모델 실행에 의존하지 않는다.

asset 모양:
    {"schema": "root-order/1", "revision": "...", "questions": {qid: {"question_hash", "order", "basis"}},
     "not_ordered": {qid: "이유"}}
`order`는 정답 단위(`answer_units`) 번호의 순열이다 — 올바른 순서로 늘어놓은 단위 번호.
"""
from __future__ import annotations

import hashlib

from studyez_contracts.bank.slide_focus import authored_hash
from studyez_contracts.roots import mcq
from studyez_contracts.roots.choices import normalized

SCHEMA = 'root-order/1'
# 2개는 순서를 맞춰도 반반이라 뺀다(spec R1). 많아도 선지 상한과 같게 둔다.
MIN_UNITS = 3
MAX_UNITS = mcq.MAX_LIST_UNITS


def units(question: dict) -> list[str]:
    return [u.strip() for u in question.get('answer_units') or [] if isinstance(u, str) and u.strip()]


def eligible(question: dict) -> bool:
    """판정 대상: 자체 선지가 없는 list, 단위 3~12개, 단위 글이 서로 다르고, 「항목: 값」 묶음 문항이 아니다."""
    if question.get('format') != 'list' or question.get('options'):
        return False
    found = units(question)
    if not MIN_UNITS <= len(found) <= MAX_UNITS:
        return False
    keys = [normalized(u) for u in found]
    return all(keys) and len(set(keys)) == len(keys) and not mcq.groups(question)


def item_id(question_id: str, text: str) -> str:
    """단계 ID. 글에서 만들어 앞면만으로는 순서를 알 수 없다. 같은 글이면 늘 같다."""
    return 'o' + hashlib.sha256(f'order\n{question_id}\n{normalized(text)}'.encode()).hexdigest()[:8]


def row_errors(question: dict, row) -> list[str]:
    """한 문항 칸을 문항과 대조한다(만들 때·서버가 붙이기 전)."""
    if not eligible(question):
        return ['순서 맞추기 대상이 아닌 문항']
    if not isinstance(row, dict):
        return ['순서 칸 형식 오류']
    if row.get('question_hash') != authored_hash(question):
        return ['문항 지문 불일치']
    order = row.get('order')
    n = len(units(question))
    if not isinstance(order, list) or any(not isinstance(i, int) or isinstance(i, bool) for i in order) \
            or sorted(order) != list(range(n)):
        return [f'order가 단위 {n}개의 순열이 아님']
    if not str(row.get('basis') or '').strip():
        return ['근거 없음']
    return []


def entry(question: dict, order: list[int], basis: str) -> dict:
    row = {'question_hash': authored_hash(question), 'order': list(order), 'basis': str(basis).strip()}
    errors = row_errors(question, row)
    if errors:
        raise ValueError(f"{question.get('question_id')}: {'; '.join(errors)}")
    return row


def validate(asset, document: dict) -> None:
    if not isinstance(asset, dict) or asset.get('schema') != SCHEMA:
        raise ValueError('root-order/1: schema 오류')
    if asset.get('revision') != document.get('revision'):
        raise ValueError('root-order/1: 다른 판의 판정')
    questions = {q['question_id']: q for q in document['bank_snapshot']['questions']}
    rows, rest = asset.get('questions'), asset.get('not_ordered')
    if not isinstance(rows, dict) or not isinstance(rest, dict):
        raise ValueError('root-order/1: questions·not_ordered 필요')
    for qid, row in rows.items():
        errors = row_errors(questions[qid], row) if qid in questions else ['판에 없는 문항']
        if errors:
            raise ValueError(f'root-order/1 {qid}: {"; ".join(errors)}')


def attachable(asset, revision: str, question: dict):
    """서버용: 이 판·이 문항 글에 맞는 순서 칸, 없거나 안 맞으면 None. 예외를 내지 않는다."""
    try:
        if not isinstance(asset, dict) or asset.get('schema') != SCHEMA or asset.get('revision') != revision:
            return None
        row = (asset.get('questions') or {}).get(question.get('question_id'))
        return row if row is not None and not row_errors(question, row) else None
    except Exception:  # noqa: BLE001 — 깨진 asset은 판정 없음과 같다
        return None


def correct(question: dict, row: dict) -> list[dict]:
    """올바른 순서의 단계 [{id, text}]."""
    found = units(question)
    return [{'id': item_id(question['question_id'], found[i]), 'text': found[i]} for i in row['order']]


def _rank(seed: str, salt: str, key: str) -> str:
    return hashlib.sha256(f'{salt}\n{seed}\n{key}'.encode()).hexdigest()


def shuffled(question: dict, row: dict, seed: str) -> list[dict]:
    """앞면에 보일 섞은 단계. 같은 씨앗이면 늘 같다. 올바른 순서와 같게 섞이면 다른 소금으로 다시 섞는다."""
    right = correct(question, row)
    ids = [c['id'] for c in right]
    for attempt in range(8):
        out = sorted(right, key=lambda c: _rank(seed, f'order-items-{attempt}', c['id']))
        if [c['id'] for c in out] != ids:
            return out
    return right[1:] + right[:1]   # 여덟 번 다 같게 나올 일은 사실상 없다. 그래도 정답 순서는 보이지 않게 한다.
