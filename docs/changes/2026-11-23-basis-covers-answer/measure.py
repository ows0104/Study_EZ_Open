"""Basis-covers-part report for root-generation/4 results (docs/changes/2026-11-23-basis-covers-answer).

Reads every `<runs>/_root-generation/*/generation*/result.json` of root-generation/4 and reports two things.
Read-only: no model, server, DB or runner call; nothing is written unless `--json` names a file.

A. fix growth: an original question (manifest initialBank) that a kept fix (manifest fixes, not reverted) gave two or
   more answer units whose text appears nowhere in the original question, answer, units or explanation.
B. basis covers part: a question with two or more answer units where a basis row names some of the units in its
   reason/quote but not all, and the tier computed without those rows is lower than the tier the question has.

B is a text heuristic: a row "names" a unit when the unit (or its part after 「:」, without parentheses, or what the
parentheses hold) appears in the row's reason or quote. A row that names no unit is not counted either way (it may describe the whole slide). So B is a
lower bound of rows that back part of an answer, and each listed case should be read before it is quoted as a fact.
Two generation folders of one lecture are both read; rows with the same title, question ID and answer are counted once.

    python docs/changes/2026-11-23-basis-covers-answer/measure.py [--runs runs] [--json out.json] [--show 20]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studyez_contracts.bank import importance  # noqa: E402

SEP = r'[\s·,;:()\[\]{}\-–/\.\'"“”‘’「」『』<>+=~|]+'
OX = {'o', 'x', '예', '아니오', '아니다'}
TOP = ('Core', 'Essential')


def norm(s):
    return re.sub(SEP, '', (s or '').lower())


def units(q):
    return [u for u in (q.get('answer_units') or [q.get('answer', '')]) if norm(u) and norm(u) not in OX]


def keys(unit):
    """Ways a basis reason may name one answer unit: the unit, its part after 「:」, with or without the parentheses,
    and what the parentheses hold (「Gomori Methenamine Silver (GMS) stain」 is named by 「GMS」)."""
    base = re.sub(r'\([^)]*\)', '', unit)
    parts = {unit, base, *base.split(':')[1:], *re.findall(r'\(([^)]*)\)', unit)}
    return {norm(p) for p in parts if norm(p)}


def names(text, unit):
    """True when `text` names `unit`. One-letter keys (산, 열) must stand as their own token."""
    flat, tokens = norm(text), {t for t in re.split(SEP, (text or '').lower()) if t}
    for k in keys(unit):
        if len(k) >= 2 and k in flat:
            return True
        if len(k) == 1 and any(t == k or (t.startswith(k) and len(t) <= 3) for t in tokens):
            return True
    return False


def find_style(value):
    """notebook_profile.emphasis_style wherever the manifest keeps it; slide when absent."""
    stack = [value]
    while stack:
        v = stack.pop()
        if type(v) is dict:
            p = v.get('notebook_profile')
            if type(p) is dict and p.get('emphasis_style') in importance.STYLES:
                return p['emphasis_style']
            stack.extend(v.values())
        elif type(v) is list:
            stack.extend(v)
    return 'slide'


def partial_rows(q, basis):
    """Basis rows that name some but not all of the question's answer units."""
    us = units(q)
    if len(us) < 2:
        return []
    out = []
    for row in basis:
        text = (row.get('reason') or '') + ' ' + (row.get('quote') or '')
        named = [u for u in us if names(text, u)]
        if named and len(named) < len(us):
            out.append({'kind': row['kind'], 'named': named, 'missing': [u for u in us if u not in named],
                        'reason': (row.get('reason') or '')[:160]})
    return out


def read_runs(runs):
    for p in sorted((runs / '_root-generation').glob('*/generation*/result.json')):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        m = d.get('manifest') or {}
        if m.get('pipelineVersion') == 'root-generation/4' and 'initialBank' in m:
            yield p, d, m


def measure(runs):
    count, growth, part, seen = collections.Counter(), [], [], set()
    for path, d, m in read_runs(runs):
        count['results'] += 1
        title = (d['document'].get('title') or '')[:40]
        style = find_style(m)
        init = {q['question_id']: q for q in m['initialBank']['questions']}
        fixed = {f['question_id'] for f in m.get('fixes', []) if not f.get('reverted')}
        basis = m.get('questionImportance') or {}
        for q in d['document']['bank_snapshot']['questions']:
            key = (title, q['question_id'], q.get('answer'))
            if key in seen:
                count['duplicate_rows'] += 1
                continue
            seen.add(key)
            count['questions'] += 1
            run = str(path.parent.relative_to(runs))
            o = init.get(q['question_id'])
            if o and q['question_id'] in fixed:
                count['fixed_original'] += 1
                old = norm(o.get('answer', '') + ' '.join(o.get('answer_units') or []) + o.get('question', '')
                           + o.get('explanation', ''))
                new = [u for u in units(q) if len(norm(u)) >= 2 and norm(u) not in old]
                if len(new) >= 2 and len(units(q)) > len(units(o)):
                    count['fix_grew2'] += 1
                    count[f"fix_grew2 {o.get('tier')}->{q.get('tier')}"] += 1
                    growth.append({'run': run, 'title': title, 'question_id': q['question_id'], 'before': o.get('tier'),
                                   'after': q.get('tier'), 'units_before': len(units(o)), 'units_after': len(units(q)),
                                   'new_units': new[:6], 'question': q.get('question', '')[:120]})
            b = basis.get(q['question_id']) or []
            if q.get('tier') in TOP and len(units(q)) >= 2:
                count['top_tier_multi_unit'] += 1
            rows = partial_rows(q, b)
            if not rows or q.get('tier') not in TOP:
                continue
            drop = {id(r) for r in b for pr in rows
                    if r['kind'] == pr['kind'] and (r.get('reason') or '')[:160] == pr['reason']}
            rest = [r for r in b if id(r) not in drop]
            without = importance.score(rest, style)['tier'] if rest else 'Optional'
            if importance.ORDER[without] < importance.ORDER[q['tier']]:
                count['basis_covers_part'] += 1
                count[f"basis_covers_part {q['tier']}->{without}"] += 1
                count['basis_covers_part ' + ('original' if o else 'added')] += 1
                part.append({'run': run, 'title': title, 'question_id': q['question_id'], 'tier': q['tier'],
                             'without_partial_rows': without, 'origin': 'original' if o else 'added',
                             'fixed': q['question_id'] in fixed, 'question': q.get('question', '')[:120],
                             'units': units(q)[:8], 'partial_rows': rows})
    return {'counts': dict(sorted(count.items())), 'fix_growth': growth, 'basis_covers_part': part}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--runs', default=str(ROOT / 'runs'), help='runs folder (default: this checkout\'s runs)')
    ap.add_argument('--json', help='write the full report here')
    ap.add_argument('--show', type=int, default=15, help='examples to print per list')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    report = measure(pathlib.Path(a.runs))
    for k, v in report['counts'].items():
        print(f'{k}: {v}')
    print('\n# B. basis covers part (tier would drop without the partial rows)')
    for r in report['basis_covers_part'][:a.show]:
        print(f"{r['title']} {r['question_id']} {r['tier']}→{r['without_partial_rows']} ({r['origin']}"
              f"{', fixed' if r['fixed'] else ''}) {r['question']}")
        for pr in r['partial_rows']:
            print(f"   {pr['kind']}: names {pr['named']} not {pr['missing']} | {pr['reason'][:90]}")
    print('\n# A. fix growth ending Core/Essential')
    for r in [g for g in report['fix_growth'] if g['after'] in TOP][:a.show]:
        print(f"{r['title']} {r['question_id']} {r['before']}→{r['after']} units {r['units_before']}→{r['units_after']}"
              f" new {r['new_units']}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
