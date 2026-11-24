"""edits-<n>.json 꼴 검사(에이전트가 스스로 돌린다): python check_edits.py <runId> <n>

- JSON 꼴(scan 스키마), question_id가 그 조각에 있는지
- replacements의 from이 그 문항 글(발문·정답·채점 단위·해설·보기·선지)에 실제로 있는지
- choice_replacements의 choice_id가 그 문항 선지인지, from이 그 선지 text/why_wrong에 있는지
- to에 괄호 겹침(「a(b(c))」, 「…)(」)이 없는지, 영어를 한글로만 바꾸지 않는지
"""
import json
import re
import sys
from pathlib import Path

WORK = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\runs\_development\2026-11-24-term-notation-published')

rid, n = sys.argv[1], sys.argv[2]
rows = {r['question_id']: r for r in json.loads((WORK / rid / 'claude' / f'questions-{n}.json').read_text(encoding='utf-8'))}
data = json.loads((WORK / rid / 'claude' / f'edits-{n}.json').read_text(encoding='utf-8'))
problems = []
assert set(data) >= {'glossary', 'edits'}, 'top-level keys: glossary, edits'
for e in data['edits']:
    qid = e.get('question_id')
    r = rows.get(qid)
    if r is None:
        problems.append(f'{qid}: not in this chunk')
        continue
    blob = '\n'.join([r['question'], r['answer'], *r['answer_units'], r['explanation'], *r['options'],
                      *[c['text'] for c in r['choices']], *[c['why_wrong'] for c in r['choices']]])
    for x in e.get('replacements', []):
        if x['from'] not in blob:
            problems.append(f'{qid}: replacement from not found: {x["from"]!r}')
    choices = {c['choice_id']: c for c in r['choices']}
    for x in e.get('choice_replacements', []):
        c = choices.get(x['choice_id'])
        if c is None:
            problems.append(f'{qid}: unknown choice_id {x["choice_id"]}')
        elif x['from'] not in c['text'] and x['from'] not in c['why_wrong']:
            problems.append(f'{qid}: choice {x["choice_id"]} from not found: {x["from"]!r}')
    for x in e.get('replacements', []) + e.get('choice_replacements', []):
        if re.search(r'\([^()]*\(|\)\(', x['to']):
            problems.append(f'{qid}: nested parentheses in to: {x["to"]!r}')
        if re.search('[A-Za-z]{3}', x['from']) and not re.search('[A-Za-z]{3}', x['to']):
            problems.append(f'{qid}: English turned into Korean: {x["from"]!r} -> {x["to"]!r}')
print(f'{len(data["edits"])} edits, {len(data["glossary"])} glossary, {len(problems)} problems')
print('\n'.join(problems[:80]))
