"""R5 of docs/changes/2026-11-15-tree-edge-goals: what a published /4 result presupposes and leaves unasked. No model.

    python -m quizbank.presuppose_report <generation folder or result.json> [...]

A result of presuppose/1 is counted from its records (manifest `presuppositions`): links judged, recalled by a task,
given an existence goal, still open, and the prerequisites. An older result has no records; it gets the rough
baseline of the 2026-11-15 diagnosis instead: English terms its stems show that no answer ever contains (noisy, a
trend only), and its prerequisite count.
"""
import json
import re
import sys
from pathlib import Path

from studyez_contracts.roots import presuppose as pre

_WORD = re.compile(r'[A-Za-z][A-Za-z0-9\-]{3,}')


def _answer(q):
    text = q['answer'] if isinstance(q['answer'], str) else json.dumps(q['answer'], ensure_ascii=False)
    if q.get('format') == 'cloze':
        text += ' ' + ' '.join(re.findall(r'\{([^}]*)\}', q['question']))
    return text


def baseline(doc):
    """Terms the stems show (cloze answers masked) that no answer contains."""
    stems, answers = set(), set()
    for q in doc['bank_snapshot']['questions']:
        stems |= set(_WORD.findall(re.sub(r'\{[^}]*\}', '', q['question'])))
        answers |= set(_WORD.findall(_answer(q)))
    return {'stemTerms': len(stems), 'neverAnswered': sorted(stems - answers)}


def report(result):
    doc, meta = result['document'], result['manifest']
    row = {'title': doc['title'], 'questions': len(doc['bank_snapshot']['questions']), 'tasks': len(doc['tasks']),
           'prerequisites': len(doc['prerequisites'])}
    if 'presuppositions' in meta:
        counts = pre.report(meta['presuppositions'], doc)
        made = sorted({r['point_id'] for r in meta['presuppositions'] if r['point_id']})
        return {**row, 'policy': pre.PRESUPPOSE, **counts, 'existencePoints': made}
    return {**row, 'policy': None, 'baseline': baseline(doc)}


def _load(path):
    path = Path(path)
    if path.is_dir():
        path = path / 'generation' / 'result.json' if (path / 'generation').is_dir() else path / 'result.json'
    return json.loads(path.read_text(encoding='utf-8'))


def main(argv=None):
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print(__doc__)
        return 2
    for path in paths:
        r = report(_load(path))
        if r['policy']:
            print(f"{r['title']}: 전제 {r['presupposed']} · 답으로 묻는 과제 {r['recalledByTask']} · 존재 목표 {r['existenceGoal']} · "
                  f"남음 {len(r['open'])} · 선행 연결 {r['prerequisites']} · 문항 {r['questions']}")
            for o in r['open'][:20]:
                print(f"   남음 {o['question_id']}: {o['link']}")
        else:
            b = r['baseline']
            share = len(b['neverAnswered']) / b['stemTerms'] if b['stemTerms'] else 0
            print(f"{r['title']}: (presuppose/1 이전 판) 발문 영어 용어 {b['stemTerms']} 중 답에 없음 {len(b['neverAnswered'])} ({share:.0%}) · "
                  f"선행 연결 {r['prerequisites']} · 문항 {r['questions']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
