"""Main-Quiz 긴 나열 답 판정(`long-list-judge/1`, docs/changes/2026-11-25-long-list-answers).

답이 긴 나열 문항마다 근거 쪽 원본을 보고 둘 중 하나로 판정한다.
- grouped: 원본이 그 목록을 묶음(표의 열·칸, 약물 계열, 소제목)으로 나눠 놓았다.
  고칠 때는 원래 문항을 한 묶음(`keep_group`)으로 좁히고, 나머지 묶음은 새 문항으로 얹는다(spec R1).
- overlapping: 원본 묶음은 있지만 묶음끼리 원소가 대부분 겹친다(중증도·치료 단계 열마다 같은 약이 반복되는 도표).
  어느 묶음으로 좁혀도 부담이 줄지 않아 자동으로 고치지 않고 사람에게 보인다.
- ungrouped: 원본 묶음이 없다. 한 카드로 두고 정답 칸을 「**대표: …**」 + 「갈래: 축 — 원소」로 보인다(spec R2).
  대표는 원본 강조로 고르고, 갈래는 의학적으로 통하는 축이 있을 때만 둔다.

판정은 제안이다. 문항·판·학습 기록은 읽기만 한다. DB·서버·모델 실행에 의존하지 않는다.
「6개」는 후보를 고르는 눈금이지 상한이 아니다(사용자 2026-11-25 「6개 정도?」 → 원본 한 묶음은 「그냥 놔두자」).
"""
from __future__ import annotations

import re

from studyez_contracts.roots.generation_v3 import locator_pages

SCHEMA = 'long-list-judge/1'
MIN_UNITS = 6
KINDS = ('grouped', 'overlapping', 'ungrouped')
# 11-16 결정 「강의에 없는 묶음 이름(「비…」「나머지 …」)을 만들지 않는다」는 갈래에도 남긴다.
# 「비…」는 「비뇨기」「비강」 같은 말과 글자로 가를 수 없어 지시문에만 둔다(2026-11-25 261123_03 Q181).
_BAD_AXIS = re.compile(r'^\s*(나머지|기타|그 ?밖|그 ?외)')


def units(question: dict) -> list[str]:
    return [u.strip() for u in question.get('answer_units') or [] if isinstance(u, str) and u.strip()]


def eligible(question: dict) -> bool:
    return question.get('format') == 'list' and len(units(question)) >= MIN_UNITS


def cited(question: dict) -> list[tuple[str, int]]:
    """문항 근거 쪽 [(source_id, page)]. 판정기는 이 쪽들만 본다."""
    found = set()
    for ref in question.get('source_refs') or []:
        for page in locator_pages(ref.get('locator')):
            found.add((ref.get('source_id'), int(page)))
    return sorted(found)


def goals(document: dict) -> dict[str, list[dict]]:
    """문항 → 그 문항이 배치된 학습 목표(cue·answer_scope). 판정기가 원래 질문이 가리킨 묶음을 고르는 데 쓴다."""
    review = document.get('review') or {}
    dirs = {d['direction_id']: d for t in review.get('targets') or [] for d in t.get('directions') or []}
    out: dict[str, list[dict]] = {}
    for m in review.get('mappings') or []:
        d = dirs.get(m.get('direction_id'))
        if d and m.get('question_id'):
            row = {'cue': d.get('cue', ''), 'answer_scope': d.get('answer_scope', '')}
            if row not in out.setdefault(m['question_id'], []):
                out[m['question_id']].append(row)
    return out


def _indices(values, count: int, what: str) -> list[int]:
    if not isinstance(values, list) or not all(isinstance(v, int) for v in values):
        raise ValueError(f'{what}: 번호 목록이 아님')
    if any(not 0 <= v < count for v in values):
        raise ValueError(f'{what}: 없는 단위 번호')
    if len(set(values)) != len(values):
        raise ValueError(f'{what}: 같은 번호가 두 번')
    return values


def check(question: dict, judgment: dict) -> dict:
    """판정 한 줄을 문항에 대조해 정리한 줄을 돌려준다. 어긋나면 ValueError(이유)."""
    count = len(units(question))
    kind = judgment.get('kind')
    if kind not in KINDS:
        raise ValueError('kind가 grouped/ungrouped가 아님')
    groups, branches = judgment.get('groups') or [], judgment.get('branches') or []
    reps = _indices(judgment.get('representatives') or [], count, '대표')
    basis = str(judgment.get('basis') or '').strip()
    if not basis:
        raise ValueError('판정 근거가 비었음')
    row = {'kind': kind, 'basis': basis, 'note': str(judgment.get('note') or '').strip()}
    if kind in ('grouped', 'overlapping'):
        if len(groups) < 2:
            raise ValueError(f'{kind}인데 묶음이 둘 미만')
        if reps or branches:
            raise ValueError(f'{kind}에 대표·갈래를 적음')
        pages = {p for _, p in cited(question)}
        covered = set()
        clean = []
        for n, g in enumerate(groups):
            name = str(g.get('name') or '').strip()
            if not name:
                raise ValueError(f'묶음 {n}: 이름이 비었음')
            members = _indices(g.get('unit_indices'), count, f'묶음 {n}')
            if not members:
                raise ValueError(f'묶음 {n}: 원소가 없음')
            if pages and g.get('page') not in pages:
                raise ValueError(f'묶음 {n}: 근거 쪽 밖의 쪽')
            covered.update(members)
            clean.append({'name': name, 'unit_indices': members, 'page': g.get('page')})
        if covered != set(range(count)):
            raise ValueError('묶음이 답 단위를 다 덮지 않음')
        if kind == 'overlapping':
            row.update(fixable=False, groups=clean, keep_group=-1)
            return row
        keep = judgment.get('keep_group')
        if not isinstance(keep, int) or not 0 <= keep < len(clean):
            raise ValueError('keep_group이 묶음 번호가 아님')
        row.update(fixable=True, groups=clean, keep_group=keep)
        return row
    if groups or judgment.get('keep_group') not in (None, -1):
        raise ValueError('ungrouped에 원본 묶음을 적음')
    if reps:
        if len(reps) >= count:
            raise ValueError('대표가 답 전체임')
        if not str(judgment.get('representative_basis') or '').strip():
            raise ValueError('대표의 원본 강조 근거가 비었음')
    clean = []
    if branches:
        if len(branches) < 2:
            raise ValueError('갈래가 하나뿐')
        covered = []
        for n, b in enumerate(branches):
            axis = str(b.get('axis') or '').strip()
            if not axis or _BAD_AXIS.search(axis):
                raise ValueError(f'갈래 {n}: 쓸 수 없는 이름 「{axis}」')
            members = _indices(b.get('unit_indices'), count, f'갈래 {n}')
            if not members:
                raise ValueError(f'갈래 {n}: 원소가 없음')
            covered += members
            clean.append({'axis': axis, 'unit_indices': members})
        if sorted(covered) != list(range(count)):
            raise ValueError('갈래가 답 단위를 정확히 한 번씩 덮지 않음')
    row.update(fixable=bool(reps or clean),   # 둘 다 없으면 고칠 방법이 없는 목록으로 남긴다
representatives=reps, representative_basis=str(judgment.get('representative_basis') or '').strip(),
               branches=clean)
    return row


def answer_preview(question: dict, row: dict) -> str:
    """ungrouped 판정을 정답 칸 모양으로 보인다(사용자 2026-11-25 선택 「한 카드, 정답 칸에 둘 다」)."""
    found = units(question)
    lines = []
    if row.get('representatives'):
        lines.append('**대표: ' + ', '.join(found[i] for i in row['representatives']) + '**')
    if row.get('branches'):
        lines.append('갈래:')
        lines += [f"  {b['axis']} — " + ', '.join(found[i] for i in b['unit_indices']) for b in row['branches']]
    elif row.get('representatives'):
        rest = [u for i, u in enumerate(found) if i not in row['representatives']]
        lines.append('그 밖에: ' + ', '.join(rest))
    return '\n'.join(lines)
