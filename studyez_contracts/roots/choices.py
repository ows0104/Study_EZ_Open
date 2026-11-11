"""Main-Quiz 단답·나열 문항에 덧붙이는 선지(`root-choices/1`).

문항·판은 그대로 두고 판(revision)마다 선지 JSON 하나를 따로 둔다(docs/changes/2026-11-12-recall-choices).
모델은 오답만 쓴다. 정답 선지는 문항의 정답 단위를 그대로 쓰므로 「정답이 선지에 없다」는 생길 수 없다.
DB·서버·모델 실행에 의존하지 않는다.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from studyez_contracts.bank.slide_focus import authored_hash

SCHEMA = 'root-choices/1'
FORMATS = ('basic', 'list')
# 제안값(spec): 단답은 오답 3~4개, 나열은 오답 2~4개·전체 10개 이하·정답 단위 8개까지.
WRONG_RANGE = {'basic': (3, 4), 'list': (2, 4)}
MAX_CHOICES = 10
MAX_LIST_UNITS = 8
IDS = 'ABCDEFGHIJ'


def normalized(text) -> str:
    """같은 선지인지 볼 때만 쓴다. 글자·숫자만 남기고 대소문자·전각을 접는다."""
    folded = unicodedata.normalize('NFKC', text if isinstance(text, str) else '').casefold()
    return ''.join(ch for ch in folded if ch.isalnum())


def correct_texts(question: dict) -> list[str]:
    """선지에 그대로 들어갈 정답 글. 단답은 하나, 나열은 정답 단위 전부."""
    units = [u for u in question.get('answer_units') or [] if isinstance(u, str) and u.strip()]
    if question.get('format') == 'list':
        return units
    return units if len(units) == 1 else [question.get('answer', '')]


def eligible(question: dict) -> bool:
    if question.get('format') not in FORMATS or question.get('options'):
        return False
    texts = correct_texts(question)
    if not texts or any(not normalized(t) for t in texts) or len({normalized(t) for t in texts}) != len(texts):
        return False
    return question['format'] == 'basic' or 2 <= len(texts) <= MAX_LIST_UNITS


def wrong_errors(question: dict, wrong: list) -> list[str]:
    """모델이 쓴 오답 목록의 결함. 비어 있으면 통과."""
    if not eligible(question):
        return ['선지를 붙일 수 없는 문항']
    if not isinstance(wrong, list) or any(not isinstance(w, dict) for w in wrong):
        return ['오답 목록 형식 오류']
    low, high = WRONG_RANGE[question['format']]
    correct = correct_texts(question)
    errors = []
    if not low <= len(wrong) <= high:
        errors.append(f'오답 {low}~{high}개 필요')
    if len(correct) + len(wrong) > MAX_CHOICES:
        errors.append(f'선지 {MAX_CHOICES}개 초과')
    taken = {normalized(t) for t in correct}
    stem = normalized(question.get('question', ''))
    for row in wrong:
        text, reason = row.get('text'), row.get('why_wrong')
        key = normalized(text)
        if not key or not isinstance(reason, str) or not reason.strip():
            errors.append('빈 오답 또는 오답 이유 없음')
            continue
        if key in taken:
            errors.append(f'정답과 같거나 겹치는 오답: {text}')
        taken.add(key)
    if len(stem) >= 4:
        # 선지 하나만 질문에 그대로 있으면 그것이 답이거나 답이 아님을 알려 준다.
        inside = [t for t in [*correct, *(r.get('text') or '' for r in wrong)] if len(normalized(t)) >= 2 and normalized(t) in stem]
        if inside and len(inside) < len(correct) + len(wrong):
            errors.append(f'질문에 그대로 들어 있는 선지: {inside[0]}')
    return list(dict.fromkeys(errors))


def _order(question_id: str, texts: list[str]) -> list[str]:
    """정답 위치가 고정되지 않게 문항 ID로 정해지는 순서. 같은 입력이면 늘 같다."""
    return sorted(texts, key=lambda t: hashlib.sha256(f'{question_id}\n{normalized(t)}'.encode()).hexdigest())


def entry(question: dict, wrong: list[dict]) -> dict:
    """검사를 통과한 오답으로 asset의 문항 한 칸을 만든다."""
    errors = wrong_errors(question, wrong)
    if errors:
        raise ValueError(f"{question.get('question_id')}: {'; '.join(errors)}")
    correct = correct_texts(question)
    reasons = {normalized(r['text']): r['why_wrong'].strip() for r in wrong}
    ordered = _order(question['question_id'], [*correct, *(r['text'].strip() for r in wrong)])
    right = {normalized(t) for t in correct}
    choices = [{'id': IDS[i], 'text': text} for i, text in enumerate(ordered)]
    return {'question_hash': authored_hash(question), 'choices': choices,
            'correct_ids': [c['id'] for c in choices if normalized(c['text']) in right],
            'wrong_reasons': {c['id']: reasons[normalized(c['text'])] for c in choices if normalized(c['text']) not in right}}


def entry_errors(question: dict, row) -> list[str]:
    """이미 만들어진 칸을 문항과 다시 대조한다(서버가 붙이기 전·asset 전체 검사)."""
    if not isinstance(row, dict) or not eligible(question):
        return ['선지 칸 형식 오류']
    choices, correct_ids = row.get('choices'), row.get('correct_ids')
    if not isinstance(choices, list) or not isinstance(correct_ids, list) or any(
            not isinstance(c, dict) or not isinstance(c.get('id'), str) or not isinstance(c.get('text'), str) for c in choices):
        return ['선지 칸 형식 오류']
    if row.get('question_hash') != authored_hash(question):
        return ['문항 지문 불일치']
    ids = [c['id'] for c in choices]
    if len(set(ids)) != len(ids) or not set(correct_ids) <= set(ids) or len(set(correct_ids)) != len(correct_ids):
        return ['선지 ID 오류']
    right = sorted(normalized(c['text']) for c in choices if c['id'] in correct_ids)
    if right != sorted(normalized(t) for t in correct_texts(question)):
        return ['정답 선지가 문항의 정답과 다름']
    reasons = row.get('wrong_reasons') if isinstance(row.get('wrong_reasons'), dict) else {}
    wrong = [{'text': c['text'], 'why_wrong': reasons.get(c['id'], '')} for c in choices if c['id'] not in correct_ids]
    return wrong_errors(question, wrong)


def validate(asset, document: dict) -> None:
    """asset 전체가 이 판의 것이고 모든 칸이 검사를 통과하는지. 아니면 ValueError."""
    if not isinstance(asset, dict) or asset.get('schema') != SCHEMA:
        raise ValueError('root-choices: schema 오류')
    if asset.get('revision') != document.get('revision'):
        raise ValueError('root-choices: 다른 판의 선지')
    questions = {q['question_id']: q for q in document['bank_snapshot']['questions']}
    rows = asset.get('questions')
    if not isinstance(rows, dict) or not isinstance(asset.get('skipped'), dict):
        raise ValueError('root-choices: questions·skipped 필요')
    for qid, row in rows.items():
        errors = entry_errors(questions[qid], row) if qid in questions else ['판에 없는 문항']
        if errors:
            raise ValueError(f'root-choices {qid}: {"; ".join(errors)}')


def attachable(asset, revision: str, question: dict):
    """서버용: 이 판·이 문항 글에 맞는 선지 칸, 없거나 안 맞으면 None. 예외를 내지 않는다."""
    try:
        if not isinstance(asset, dict) or asset.get('schema') != SCHEMA or asset.get('revision') != revision:
            return None
        row = (asset.get('questions') or {}).get(question.get('question_id'))
        return row if row is not None and not entry_errors(question, row) else None
    except Exception:  # noqa: BLE001 — 깨진 asset은 선지 없음과 같다
        return None


_SPACE = re.compile(r'\s+')


def distractor_pool(questions: list[dict], question: dict, limit: int = 60) -> list[str]:
    """같은 강의의 다른 문항 정답(짧은 것)에서 고른 오답 후보. 모델이 먼저 여기서 고른다."""
    own = {normalized(t) for t in correct_texts(question)}
    seen, pool = set(own), []
    for other in questions:
        if other.get('question_id') == question.get('question_id'):
            continue
        for text in other.get('answer_units') or []:
            key = normalized(text)
            if isinstance(text, str) and key and key not in seen and len(text) <= 80:
                seen.add(key)
                pool.append(_SPACE.sub(' ', text).strip())
    return pool[:limit]
