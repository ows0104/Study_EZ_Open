"""Add CLI-authored explanations without changing any web-authored question or answer."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import fitz

from studyez_llm.pdf import render

from .coverage import _call
from .points import STR, _array, _object
from .session import SessionError
from .slides import cited_pages

PROMPT = Path(__file__).parent / 'prompts' / 'explain.md'
REPORT = _object({'annotations': _array(_object({
    'question_id': STR, 'verdict': {'type': 'string', 'enum': ['ok', 'doubt', 'wrong']}, 'note': STR,
    'option_explanations': _array(_object({'option_id': STR, 'text': STR})), 'ox_explanation': STR,
    'pool_explanations': _array(_object({'pool_id': STR, 'candidate_id': STR,
                                       'true_explanation': STR, 'false_explanation': STR})),
}))})


def enabled(version: str) -> bool:
    match = re.fullmatch(r'v?(\d+)\.(\d+)(?:\.\d+)?', version)
    return bool(match and int(match[1]) == 1 and int(match[2]) >= 32)


def targets(bank: dict) -> list[dict]:
    return [q for q in bank['questions'] if q['format'] in ('mcq', 'multi_select', 'ox')]


def apply(bank: dict, report: dict) -> tuple[dict, dict]:
    out = copy.deepcopy(bank)
    questions = {q['question_id']: q for q in targets(out)}
    seen = set()
    for row in report['annotations']:
        qid = row['question_id']
        if qid not in questions or qid in seen:
            raise SessionError('CLI 해설의 문항 ID가 없거나 중복됐습니다.')
        seen.add(qid)
        if row['verdict'] != 'ok' and not row['note'].strip():
            raise SessionError(f'{qid}: 의심·오류 판정의 이유가 없습니다.')
        q = questions[qid]
        explanations = row['option_explanations']
        expected = {o['id'] for o in q['options']}
        actual = [e['option_id'] for e in explanations]
        if set(actual) != expected or len(actual) != len(expected) or any(not e['text'].strip() for e in explanations):
            raise SessionError(f'{qid}: CLI 해설에서 모든 선지를 정확히 한 번 설명해야 합니다.')
        ox = row['ox_explanation'].strip()
        if bool(ox) != (q['format'] == 'ox'):
            raise SessionError(f'{qid}: OX 해설이 없거나 다른 형식에 작성됐습니다.')
        pool_expected = {(p['pool_id'], c['candidate_id']) for p in q['option_pools'] for c in p['candidates']}
        pool_actual = [(p['pool_id'], p['candidate_id']) for p in row['pool_explanations']]
        if set(pool_actual) != pool_expected or len(pool_actual) != len(pool_expected):
            raise SessionError(f'{qid}: CLI 보기 풀 해설의 후보가 빠지거나 중복됐습니다.')
        pool_map = {(p['pool_id'], p['candidate_id']): p for p in row['pool_explanations']}
        for p in q['option_pools']:
            for c in p['candidates']:
                annotation = pool_map[(p['pool_id'], c['candidate_id'])]
                for key in ('true_explanation', 'false_explanation'):
                    if not annotation[key].strip():
                        raise SessionError(f'{qid}: 빈 보기 풀 해설')
                    c[key] = annotation[key]
        q['option_explanations'] = explanations
        # Existing authored reasons are scoring units, not a list to which each
        # newly worded CLI explanation should be appended. The new explanation
        # remains in the report for inspection; repairs own scoring changes.
        has_reason = any(u.strip().upper() not in ('O', 'X') for u in q['answer_units'])
        if ox and not has_reason and not q.get('explanation', '').strip():
            q['explanation'] = ox
    if seen != set(questions):
        raise SessionError('일부 문항의 CLI 해설이 없습니다.')
    return out, {'annotatedCount': len(seen), 'requiresRevision': any(
        row['verdict'] == 'wrong' for row in report['annotations']), **report}


def write(bank: dict, pdf: Path, title: str, out: Path, *, pdf_source: str = 'S1',
          jokbo: Path | None = None, model: str | None = None) -> tuple[dict, dict, dict]:
    work = out / 'explain'
    work.mkdir(exist_ok=True)
    subset = {**bank, 'questions': targets(bank)}
    (work / 'bank.json').write_text(json.dumps(subset, ensure_ascii=False), encoding='utf-8')
    if not subset['questions']:
        return bank, {'annotatedCount': 0, 'requiresRevision': False, 'annotations': []}, {}
    with fitz.open(pdf) as doc:
        text = '\n\n'.join(f'## PDF p.{i + 1}\n{p.get_text()}' for i, p in enumerate(doc))
    (work / 'source-text.md').write_text(text, encoding='utf-8')
    pages = sorted({p for ps in cited_pages(subset, pdf_source).values() for p in ps})
    images = render(pdf, ','.join(map(str, pages)), work / 'source-pages') if pages else []
    (work / 'source-pages.json').write_text(json.dumps([str(p.resolve()) for p in images]), encoding='utf-8')
    if jokbo:
        (work / 'jokbo.md').write_text(jokbo.read_text(encoding='utf-8'), encoding='utf-8')
    prompt = PROMPT.read_text(encoding='utf-8') + '\n강의: ' + title
    report, usage = _call(prompt, REPORT, work, model, '정답 확인·해설 작성')
    result, checked = apply(bank, report)
    (out / 'explanations.json').write_text(json.dumps(checked, ensure_ascii=False, indent=2), encoding='utf-8')
    return result, checked, usage
