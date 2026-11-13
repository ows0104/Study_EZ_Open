"""Main-Quiz 「객관식 모드」 선지(`root-mcq/1`, docs/changes/2026-11-14-mcq-mode).

객관식 모드에서는 모든 문항을 선지로 푼다. 문항·판·학습 기록은 그대로 두고, 판(revision)마다 선지 JSON 하나를 따로 둔다.
모델은 오답만 쓴다. 정답 선지는 코드가 문항의 정답에서 만든다.
오답은 둘 중 하나여야 한다(사용자 2026-11-14):
- `block`: 같은 블록의 다른 병원체·주제의 기전·특징에서 가져온 것(`basis`에 그 병원체·주제).
- `subtle`: 정답의 헷갈리는 사소한 부분을 바꾼 것(Fe2+→Fe3+, 기전 순서 바꾸기 등, `basis`에 바꾼 것).

형식별 선지:
- basic: 정답 하나 + 오답 3~4.
- list: 정답 단위 전부 + 오답 2~4 (다중선택).
- cloze: 빈칸 하나면 그 답 하나, 여럿이면 빈칸 답을 순서대로 이은 조합 하나가 정답. 오답도 같은 수의 칸을 이은 조합.
- sequence: 올바른 순서를 이은 것이 정답. 오답은 순서를 바꾼 조합.
ox·mcq·multi_select는 문항 자체가 선지를 가지므로 이 asset에 넣지 않는다(화면이 그대로 선지로 보인다).
DB·서버·모델 실행에 의존하지 않는다.
"""
from __future__ import annotations

import hashlib
import re

from studyez_contracts.bank.slide_focus import authored_hash
from studyez_contracts.roots.choices import normalized

SCHEMA = 'root-mcq/1'
FORMATS = ('basic', 'list', 'cloze', 'sequence')
KINDS = ('block', 'subtle')
WRONG_RANGE = {'basic': (3, 4), 'list': (2, 4), 'cloze': (3, 4), 'sequence': (3, 4)}
MAX_LIST_UNITS = 12
MAX_CHOICES = 16
IDS = 'ABCDEFGHIJKLMNOP'
JOIN = {'cloze': ' / ', 'sequence': ' → '}
_BLANK = re.compile(r'\{\{c\d+\}\}')


def parts_needed(question: dict) -> int:
    """오답 한 줄이 몇 칸을 이어야 하나. 0이면 글 하나."""
    fmt = question.get('format')
    if fmt == 'cloze':
        n = len(_units(question))
        return n if n >= 2 else 0
    if fmt == 'sequence':
        return len(question.get('correct_order') or [])
    return 0


def _units(question: dict) -> list[str]:
    return [u for u in question.get('answer_units') or [] if isinstance(u, str) and u.strip()]


def correct_texts(question: dict) -> list[str]:
    """선지에 그대로 들어갈 정답 글."""
    fmt = question.get('format')
    units = _units(question)
    if fmt == 'list':
        return units
    if fmt == 'cloze':
        return [JOIN['cloze'].join(u.strip() for u in units)] if units else []
    if fmt == 'sequence':
        order = [s for s in question.get('correct_order') or [] if isinstance(s, str) and s.strip()]
        return [JOIN['sequence'].join(s.strip() for s in order)] if len(order) >= 2 else []
    text = units[0] if len(units) == 1 else question.get('answer', '')
    return [text] if isinstance(text, str) and text.strip() else []


def eligible(question: dict) -> bool:
    fmt = question.get('format')
    if fmt not in FORMATS or question.get('options'):
        return False
    texts = correct_texts(question)
    if not texts or any(not normalized(t) for t in texts) or len({normalized(t) for t in texts}) != len(texts):
        return False
    if fmt == 'list':
        return 2 <= len(texts) <= MAX_LIST_UNITS
    if fmt == 'cloze':
        return len(_BLANK.findall(question.get('question', ''))) == len(_units(question))
    return True


def wrong_text(question: dict, row: dict) -> str:
    """오답 한 줄의 선지 글. 조합 형식이면 칸을 정답과 같은 방식으로 잇는다."""
    need = parts_needed(question)
    if need:
        parts = row.get('parts') if isinstance(row.get('parts'), list) else []
        return JOIN[question['format']].join(p.strip() for p in parts if isinstance(p, str))
    text = row.get('text')
    return text.strip() if isinstance(text, str) else ''


def wrong_errors(question: dict, wrong: list) -> list[str]:
    """모델이 쓴 오답 목록의 결함. 비어 있으면 통과."""
    if not eligible(question):
        return ['선지를 붙일 수 없는 문항']
    if not isinstance(wrong, list) or any(not isinstance(w, dict) for w in wrong):
        return ['오답 목록 형식 오류']
    fmt = question['format']
    low, high = WRONG_RANGE[fmt]
    correct = correct_texts(question)
    need = parts_needed(question)
    errors = []
    if not low <= len(wrong) <= high:
        errors.append(f'오답 {low}~{high}개 필요')
    if len(correct) + len(wrong) > MAX_CHOICES:
        errors.append(f'선지 {MAX_CHOICES}개 초과')
    taken = {normalized(t) for t in correct}
    for row in wrong:
        if need:
            parts = row.get('parts')
            if not isinstance(parts, list) or len(parts) != need or any(not isinstance(p, str) or not normalized(p) for p in parts):
                errors.append(f'조합 오답은 {need}칸이 필요')
                continue
        text = wrong_text(question, row)
        key = normalized(text)
        if not key or not str(row.get('why_wrong') or '').strip():
            errors.append('빈 오답 또는 오답 이유 없음')
            continue
        if row.get('kind') not in KINDS or not str(row.get('basis') or '').strip():
            errors.append(f'오답 종류(block·subtle)와 근거 필요: {text}')
            continue
        if key in taken:
            errors.append(f'정답과 같거나 겹치는 오답: {text}')
        taken.add(key)
    if fmt == 'sequence':
        order = sorted(normalized(s) for s in question.get('correct_order') or [])
        for row in wrong:
            if isinstance(row.get('parts'), list) and sorted(normalized(p) for p in row['parts']) != order:
                errors.append('순서 오답은 같은 항목의 다른 순서여야 함')
                break
    return list(dict.fromkeys(errors))


def _order(question_id: str, texts: list[str]) -> list[str]:
    """정답 위치가 고정되지 않게 문항 ID로 정해지는 순서. 같은 입력이면 늘 같다."""
    return sorted(texts, key=lambda t: hashlib.sha256(f'mcq\n{question_id}\n{normalized(t)}'.encode()).hexdigest())


def entry(question: dict, wrong: list[dict]) -> dict:
    """검사를 통과한 오답으로 asset의 문항 한 칸을 만든다."""
    errors = wrong_errors(question, wrong)
    if errors:
        raise ValueError(f"{question.get('question_id')}: {'; '.join(errors)}")
    correct = correct_texts(question)
    meta = {normalized(wrong_text(question, r)): {'kind': r['kind'], 'basis': str(r['basis']).strip(),
                                                    'why_wrong': str(r['why_wrong']).strip()} for r in wrong}
    ordered = _order(question['question_id'], [*correct, *(wrong_text(question, r) for r in wrong)])
    right = {normalized(t) for t in correct}
    choices = [{'id': IDS[i], 'text': text} for i, text in enumerate(ordered)]
    return {'question_hash': authored_hash(question), 'choices': choices,
            'correct_ids': [c['id'] for c in choices if normalized(c['text']) in right],
            'wrong': {c['id']: meta[normalized(c['text'])] for c in choices if normalized(c['text']) not in right}}


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
    meta = row.get('wrong') if isinstance(row.get('wrong'), dict) else {}
    keys = len(choices) - len(correct_ids)
    low, high = WRONG_RANGE[question['format']]
    if not low <= keys <= high or len(choices) > MAX_CHOICES:
        return ['오답 수 범위 밖']
    if any(not isinstance(meta.get(c['id']), dict) or meta[c['id']].get('kind') not in KINDS
           for c in choices if c['id'] not in correct_ids):
        return ['오답 종류 기록 없음']
    if len({normalized(c['text']) for c in choices}) != len(choices):
        return ['선지 중복']
    return []


def validate(asset, document: dict) -> None:
    """asset 전체가 이 판의 것이고 모든 칸이 검사를 통과하는지. 아니면 ValueError."""
    if not isinstance(asset, dict) or asset.get('schema') != SCHEMA:
        raise ValueError('root-mcq: schema 오류')
    if asset.get('revision') != document.get('revision'):
        raise ValueError('root-mcq: 다른 판의 선지')
    questions = {q['question_id']: q for q in document['bank_snapshot']['questions']}
    rows = asset.get('questions')
    if not isinstance(rows, dict) or not isinstance(asset.get('skipped'), dict):
        raise ValueError('root-mcq: questions·skipped 필요')
    for qid, row in rows.items():
        errors = entry_errors(questions[qid], row) if qid in questions else ['판에 없는 문항']
        if errors:
            raise ValueError(f'root-mcq {qid}: {"; ".join(errors)}')


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


def _short(text) -> str | None:
    if not isinstance(text, str):
        return None
    text = _SPACE.sub(' ', text).strip()
    return text if text and len(text) <= 90 else None


def lecture_facts(document: dict, limit: int = 40) -> list[str]:
    """한 강의 판에서 다른 강의 문항의 오답 재료로 쓸 짧은 사실(정답 단위·짧은 정답)."""
    seen, facts = set(), []
    for q in document.get('bank_snapshot', {}).get('questions', []):
        for text in [*(q.get('answer_units') or []), q.get('answer')]:
            short = _short(text)
            if short and normalized(short) not in seen and len(normalized(short)) >= 2:
                seen.add(normalized(short))
                facts.append(short)
    if len(facts) <= limit:
        return facts
    step = len(facts) / limit   # 강의 전체에 고르게
    return [facts[int(i * step)] for i in range(limit)]


def same_lecture_pool(questions: list[dict], question: dict, limit: int = 40) -> list[str]:
    """같은 강의의 다른 문항 정답(짧은 것)."""
    own = {normalized(t) for t in correct_texts(question)}
    seen, pool = set(own), []
    for other in questions:
        if other.get('question_id') == question.get('question_id'):
            continue
        for text in other.get('answer_units') or []:
            short = _short(text)
            if short and normalized(short) not in seen:
                seen.add(normalized(short))
                pool.append(short)
    return pool[:limit]
