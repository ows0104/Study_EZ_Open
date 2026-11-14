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

`root-mcq/2`(2026-11-14, docs/changes/2026-11-14-choices-merge)는 아래 「v2」 절. 주관식 「선지 보기」와 객관식 모드가 같이 쓴다.
v1 함수는 이미 올라간 v1 asset을 읽기 위해 남긴다.
"""
from __future__ import annotations

import hashlib
import re

from studyez_contracts.bank.cloze import INLINE
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
        return blank_count(question) == len(_units(question))
    return True


def blank_count(question: dict) -> int:
    """cloze 빈칸 수. 게시된 판은 `{답}` 꼴(작성 원문), 변환된 문항은 `{{c1}}` 꼴이다(2026-11-14: `{답}`을 못 세어 cloze 0)."""
    text = question.get('question', '') or ''
    return len(_BLANK.findall(text)) or len(INLINE.findall(text))


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


# ── v2: 두 모드가 같이 쓰는 선지(`root-mcq/2`, 2026-11-14 docs/changes/2026-11-14-choices-merge) ─────────────────
# 사용자 결정: 오답 출처는 같은 강의·다른 강의·족보·직접 작성. 오답 수는 맞추지 않고 괜찮은 만큼, 한 번에 4~5개.
# 정답이 표기(영어 vs 한국어)·길이·단정 표현으로 티 나는 오답은 코드가 뺀다. 「선을 넘는」 오답은 마지막 의학 검토가 뺀다.
# asset에는 문항마다 오답 풀만 둔다. 정답 선지와 이번 풀이에 보일 오답·순서는 `select`가 씨앗으로 정한다.

SCHEMA_V2 = 'root-mcq/2'
SOURCES = ('lecture', 'block', 'jokbo', 'made')
SHOW = {'basic': 5, 'cloze': 5, 'sequence': 5, 'list': 4}
MAX_POOL = 10
JOKBO_KEYS = ('run_id', 'title', 'year', 'number', 'professor')
_HANGUL = re.compile('[가-힣]')
_LATIN = re.compile('[A-Za-z]')
# 오답에만 있으면 오답 티가 나는 단정 표현(사용자 「1 적용」).
# 낱말로 선 것만 센다 — 「절대혐기성」 같은 용어는 단정 표현이 아니다.
ABSOLUTE = re.compile(r'(?:^|\s)(항상|절대로?|반드시|전혀)(?=\s|$)|에만(?=\s|$)|뿐이다|\b(always|never|only)\b', re.I)
_LENGTH_FLOOR = 8      # 이보다 짧은 정답(균 이름·약어 등)은 길이 단서를 보지 않는다
_LENGTH_RATIO = 3.0    # 오답 길이가 정답 평균의 1/3 미만이거나 3배 초과면 티가 난다(시범 분포로 조정)


_GLOSS = re.compile(r'\(([^()]*)\)')


def script(text: str) -> str:
    """표기 갈래: 한글이 없으면 en, 라틴 문자가 없으면 ko, 둘 다 있으면 mixed, 둘 다 없으면 other.
    글자 수로 주된 표기를 가르면 「독소(TSST-1)」처럼 짧은 한국어+약어가 뒤집혀 오답을 잘못 뺀다(2026-11-14 실측)."""
    ko, en = bool(_HANGUL.search(text)), bool(_LATIN.search(text))
    return 'mixed' if ko and en else 'ko' if ko else 'en' if en else 'other'


def _glossed(text: str) -> bool:
    """「한글(영문)」·「영문(한글)」 병기: 괄호 안과 밖의 표기가 다르다."""
    for m in _GLOSS.finditer(text):
        inside, outside = script(m.group(1)), script(text[:m.start()] + text[m.end():])
        if {inside, outside} == {'ko', 'en'}:
            return True
    return False


def _language_gap(correct: list[str], text: str) -> bool:
    """정답이 모두 한 언어로만 쓰였는데 오답이 다른 언어로만 쓰였다(예: 정답 둘이 영어, 오답이 한국어 문장)."""
    kinds = {script(t) for t in correct}
    mine = script(text)
    return (kinds == {'en'} and mine == 'ko') or (kinds == {'ko'} and mine == 'en')


def choice_id(question_id: str, text: str, group: int | None = None) -> str:
    """선지 ID. 정답·오답이 같은 방식으로 만들어져 ID로는 정답을 알 수 없고, 같은 글이면 늘 같다.
    나눠 묻는 문항은 묶음 번호를 넣는다(두 빈칸의 답이 같은 글일 수 있다)."""
    key = normalized(text) if group is None else f'{group}|{normalized(text)}'
    return 'k' + hashlib.sha256(f'choice\n{question_id}\n{key}'.encode()).hexdigest()[:8]


# 나눠 묻는 문항(사용자 2026-11-14 「묻는 게 여러개이면 선지를 나눠서 제시해야할 것 같아. 지금 섞여서 고르기가 너무 어려워」).
# 코드가 정한다: 빈칸이 둘 이상인 cloze는 빈칸마다, 정답 단위가 모두 「항목: 값」 꼴인 basic·list는 항목마다 한 묶음.
_LABELED = re.compile(r'^\s*([^:：\n]{1,24}?)\s*[:：]\s*(\S.*)$')
MAX_GROUPS = 12


def groups(question: dict) -> list[dict] | None:
    """묶음 [{label, correct}] 또는 None(한 묶음). 묶음마다 정답은 하나다."""
    fmt, units = question.get('format'), _units(question)
    if len(units) < 2 or len(units) > MAX_GROUPS:
        return None
    if fmt == 'cloze' and blank_count(question) == len(units):
        return [{'label': f'빈칸 {i + 1}', 'correct': u.strip()} for i, u in enumerate(units)]
    if fmt in ('basic', 'list'):
        found = [_LABELED.match(u) for u in units]
        if all(found) and len({normalized(m.group(1)) for m in found}) == len(found):
            return [{'label': m.group(1).strip(), 'correct': m.group(2).strip()} for m in found]
    return None


def answer_choices(question: dict) -> list[tuple[int | None, str]]:
    """정답 선지 (묶음 번호, 글). 묶음이 없으면 번호는 None."""
    found = groups(question)
    return [(i, g['correct']) for i, g in enumerate(found)] if found else [(None, t) for t in correct_texts(question)]


def _absolute(text: str) -> set[str]:
    return {m.group(0).strip().lower() for m in ABSOLUTE.finditer(text)}


# 정답에 부정·반대말만 붙인 오답(사용자 2026-11-14 「이런 건 좀 억지인듯」: 기회감염 → 「기회감염에 대한 감수성 감소」).
NEGATION = re.compile(r'억제|감소|저하|없음|없다|없는|없이|아님|아니다|아닌|결여|불가|차단|방지|소실|부재|하지 않|되지 않')


def _negated(correct: list[str], text: str) -> bool:
    if not NEGATION.search(text):
        return False
    return any(len(normalized(t)) >= 2 and normalized(t) in normalized(text) and not NEGATION.search(t) for t in correct)


def cue_errors(correct: list[str], text: str) -> list[str]:
    """정답 선지들과 견주어 오답 티가 나는 표기. 비어 있으면 통과."""
    errors = []
    if _language_gap(correct, text):
        errors.append('표기 언어가 정답과 다름')
    elif correct and all(_glossed(t) for t in correct) and not _glossed(text):
        errors.append('표기 방식이 정답과 다름(정답은 한글·영문 병기)')
    lengths = [len(t) for t in correct]
    mean = sum(lengths) / len(lengths) if lengths else 0
    if mean >= _LENGTH_FLOOR and not mean / _LENGTH_RATIO <= len(text) <= mean * _LENGTH_RATIO:
        errors.append('길이가 정답과 크게 다름')
    if _absolute(text) - set().union(*(_absolute(t) for t in correct)):
        errors.append('오답에만 단정 표현')
    if _negated(correct, text):
        errors.append('정답에 부정·반대말만 붙인 오답')
    return errors


def _group_of(question: dict, row: dict) -> int | None:
    value = row.get('group')
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def text_v2(question: dict, row: dict) -> str:
    """v2 오답의 선지 글. 묶음 문항은 text 그대로(그 묶음의 값), 아니면 v1과 같다(sequence는 순서를 잇는다)."""
    if groups(question):
        text = row.get('text')
        return text.strip() if isinstance(text, str) else ''
    return wrong_text(question, row)


def row_errors(question: dict, row) -> list[str]:
    """모델이 쓴 오답 한 줄의 결함. 다른 오답과의 중복은 `entry_v2`가 뺀다."""
    if not isinstance(row, dict):
        return ['오답 형식 오류']
    found = groups(question)
    if found:
        group = _group_of(question, row)
        if group is None or group >= len(found):
            return ['나눠 묻는 문항은 오답마다 묶음 번호(group) 필요']
        correct = [found[group]['correct']]
    else:
        if _group_of(question, row) is not None:
            return ['한 묶음 문항에 묶음 번호']
        need = parts_needed(question)
        if need:
            parts = row.get('parts')
            if not isinstance(parts, list) or len(parts) != need or any(not isinstance(p, str) or not normalized(p) for p in parts):
                return [f'조합 오답은 {need}칸이 필요']
            if question['format'] == 'sequence' and sorted(normalized(p) for p in parts) != sorted(
                    normalized(s) for s in question.get('correct_order') or []):
                return ['순서 오답은 같은 항목의 다른 순서여야 함']
        correct = correct_texts(question)
    text = text_v2(question, row)
    if not normalized(text):
        return ['빈 오답']
    if row.get('source') not in SOURCES:
        return ['오답 출처(lecture·block·jokbo·made) 필요']
    if any(not str(row.get(k) or '').strip() for k in ('basis', 'why_tempting', 'why_wrong')):
        return ['basis·why_tempting·why_wrong 필요']
    if row['source'] == 'jokbo':
        jokbo = row.get('jokbo')
        if not isinstance(jokbo, dict) or not str(jokbo.get('year') or '').strip() or not str(jokbo.get('number') or '').strip():
            return ['족보 오답은 연도·번호 필요']
    if normalized(text) in {normalized(t) for t in correct}:
        return ['정답과 같은 오답']
    return cue_errors(correct, text)


def wrong_row(question: dict, row: dict) -> dict:
    """검사를 통과한 오답 한 줄을 asset 모양으로."""
    text, group = text_v2(question, row), (_group_of(question, row) if groups(question) else None)
    out = {'id': choice_id(question['question_id'], text, group), 'text': text, 'source': row['source'],
           'basis': str(row['basis']).strip(), 'why_tempting': str(row['why_tempting']).strip(),
           'why_wrong': str(row['why_wrong']).strip()}
    if group is not None:
        out['group'] = group
    if row['source'] == 'jokbo':
        out['jokbo'] = {k: str(row['jokbo'].get(k) or '').strip() for k in JOKBO_KEYS}
    return out


def entry_v2(question: dict, wrong: list[dict]) -> dict:
    """통과한 오답(1개 이상)으로 asset의 문항 한 칸. 결함 있는 줄·중복은 빼고 풀 상한까지만(묶음 문항은 묶음마다)."""
    if not eligible(question):
        raise ValueError(f"{question.get('question_id')}: 선지를 붙일 수 없는 문항")
    seen = {(g, normalized(t)) for g, t in answer_choices(question)}
    rows, per_group = [], {}
    for row in wrong:
        if row_errors(question, row):
            continue
        out = wrong_row(question, row)
        key = (out.get('group'), normalized(out['text']))
        if key in seen or per_group.get(out.get('group'), 0) >= MAX_POOL:
            continue
        seen.add(key)
        per_group[out.get('group')] = per_group.get(out.get('group'), 0) + 1
        rows.append(out)
    if not rows:
        raise ValueError(f"{question.get('question_id')}: 통과한 오답 없음")
    return {'question_hash': authored_hash(question), 'wrong': rows}


def entry_errors_v2(question: dict, row) -> list[str]:
    """올라간 칸을 문항과 다시 대조한다(서버가 붙이기 전·asset 전체 검사)."""
    if not isinstance(row, dict) or not eligible(question):
        return ['선지 칸 형식 오류']
    if row.get('question_hash') != authored_hash(question):
        return ['문항 지문 불일치']
    found = groups(question)
    wrong = row.get('wrong')
    limit = MAX_POOL * (len(found) if found else 1)
    if not isinstance(wrong, list) or not 1 <= len(wrong) <= limit or any(not isinstance(w, dict) for w in wrong):
        return ['오답 풀 형식 오류']
    qid = question['question_id']
    keys = {(g, normalized(t)) for g, t in answer_choices(question)}
    ids = {choice_id(qid, t, g) for g, t in answer_choices(question)}
    for w in wrong:
        text, group = w.get('text'), w.get('group')
        if found and (not isinstance(group, int) or not 0 <= group < len(found)) or not found and group is not None:
            return ['묶음 번호 오류']
        if not isinstance(text, str) or not normalized(text) or (group, normalized(text)) in keys:
            return ['빈 오답이거나 정답·다른 오답과 겹침']
        if w.get('id') != choice_id(qid, text, group) or w['id'] in ids:
            return ['선지 ID 오류']
        if w.get('source') not in SOURCES or not str(w.get('why_wrong') or '').strip():
            return ['오답 출처·이유 없음']
        keys.add((group, normalized(text)))
        ids.add(w['id'])
    return []


def validate_v2(asset, document: dict) -> None:
    if not isinstance(asset, dict) or asset.get('schema') != SCHEMA_V2:
        raise ValueError('root-mcq/2: schema 오류')
    if asset.get('revision') != document.get('revision'):
        raise ValueError('root-mcq/2: 다른 판의 선지')
    questions = {q['question_id']: q for q in document['bank_snapshot']['questions']}
    rows = asset.get('questions')
    if not isinstance(rows, dict) or not isinstance(asset.get('skipped'), dict):
        raise ValueError('root-mcq/2: questions·skipped 필요')
    for qid, row in rows.items():
        errors = entry_errors_v2(questions[qid], row) if qid in questions else ['판에 없는 문항']
        if errors:
            raise ValueError(f'root-mcq/2 {qid}: {"; ".join(errors)}')


def attachable_v2(asset, revision: str, question: dict):
    """서버용: 이 판·이 문항 글에 맞는 v2 칸, 없거나 안 맞으면 None. 예외를 내지 않는다."""
    try:
        if not isinstance(asset, dict) or asset.get('schema') != SCHEMA_V2 or asset.get('revision') != revision:
            return None
        row = (asset.get('questions') or {}).get(question.get('question_id'))
        return row if row is not None and not entry_errors_v2(question, row) else None
    except Exception:  # noqa: BLE001 — 깨진 asset은 선지 없음과 같다
        return None


def _rank(seed: str, salt: str, key: str) -> str:
    return hashlib.sha256(f'{salt}\n{seed}\n{key}'.encode()).hexdigest()


def show_count(question: dict) -> int:
    """한 번에 보일 오답 수(사용자 「4-5개 정도」). list는 정답 단위와 합쳐 MAX_CHOICES 이하. 묶음 문항은 묶음마다 `group_show`."""
    return max(0, min(SHOW.get(question.get('format'), 4), MAX_CHOICES - len(correct_texts(question))))


def group_show(count: int) -> int:
    """묶음마다 보일 오답 수. 묶음이 많으면 줄여 화면이 너무 길어지지 않게 한다."""
    return 3 if count <= 4 else 2 if count <= 8 else 1


def source_label(row: dict) -> str:
    """답면에 보이는 출처. 족보만 표시한다(사용자 「6 보여줘」)."""
    jokbo = row.get('jokbo') if row.get('source') == 'jokbo' else None
    if not isinstance(jokbo, dict):
        return ''
    label = f"{jokbo.get('year', '')} 족보" + (f" {jokbo['number']}번" if jokbo.get('number') else '')
    return label + (f" · {jokbo['title']}" if jokbo.get('title') else '')


def select(question: dict, row: dict, seed: str) -> dict:
    """이번 풀이에 보일 선지: 정답 전부 + 오답 풀에서 씨앗으로 고른 것, 씨앗으로 섞은 순서.

    같은 씨앗이면 늘 같다(새로고침·되돌리기). 서버는 씨앗을 사용자·문항·학습일로 만든다 — 다음 복습 날엔 다른 조합이다.
    묶음 문항은 묶음마다 정답 하나 + 오답 `group_show`개를 그 묶음 안에서 섞고, 묶음 순서는 그대로 둔다.
    반환: choices(앞면, 묶음 순서로 이은 것), groups(묶음 문항만 [{label, ids}]), correct_ids, notes(보인 오답의 이유·출처, 답면 전용)."""
    qid = question['question_id']
    found = groups(question)
    if not found:
        wrong = sorted(row['wrong'], key=lambda w: _rank(seed, 'pick', w['id']))[:show_count(question)]
        correct = [{'id': choice_id(qid, t), 'text': t} for _, t in answer_choices(question)]
        shown = sorted([*correct, *({'id': w['id'], 'text': w['text']} for w in wrong)],
                       key=lambda c: _rank(seed, 'order', c['id']))
        return {'choices': shown, 'groups': None, 'correct_ids': [c['id'] for c in correct],
                'notes': {w['id']: {'why': w['why_wrong'], 'source': source_label(w)} for w in wrong}}
    choices, labeled, correct_ids, notes = [], [], [], {}
    take = group_show(len(found))
    for index, group in enumerate(found):
        right = {'id': choice_id(qid, group['correct'], index), 'text': group['correct']}
        mine = sorted((w for w in row['wrong'] if w.get('group') == index), key=lambda w: _rank(seed, 'pick', w['id']))[:take]
        part = sorted([right, *({'id': w['id'], 'text': w['text']} for w in mine)], key=lambda c: _rank(seed, 'order', c['id']))
        choices += part
        labeled.append({'label': group['label'], 'ids': [c['id'] for c in part]})
        correct_ids.append(right['id'])
        notes.update({w['id']: {'why': w['why_wrong'], 'source': source_label(w)} for w in mine})
    return {'choices': choices, 'groups': labeled, 'correct_ids': correct_ids, 'notes': notes}
