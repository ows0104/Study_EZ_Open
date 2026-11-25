"""큰 나열 카드를 공개판 사본에서 좁히고 쪼갠다(운영 쓰기 없음). 결과는 <runId>/after/, 보고는 report-<runId>.md.

`splits.json`(Claude가 근거 쪽을 보고 직접 쓴 것)대로:
- 원래 카드: 발문·정답·채점 단위를 바꾼다(대표만 묻기, 계열 이름 묻기, 한 묶음으로 좁히기). 같은 ID·같은 과제 자리.
- 새 카드: 원래 카드의 나머지 묶음. 원래 카드를 복사해 새 ID를 주고 같은 목표(direction)에 과제로 붙인다.
같은 판을 그대로 쓴다. 손대지 않은 문항·과제는 글자 하나 바뀌지 않으므로 학습 기록이 task_id로 그대로 이어진다.
바뀐 카드는 같은 task_id라 기록이 이어지지만 묻는 것이 달라졌다(사용자 「고친 카드의 학습기록은 살짝은 깨져도 돼」).
선지·순서 asset에서 바뀐 카드의 칸은 뺀다(옛 정답 기준이라). 근거 지문은 새 글로 맞춘다.

    python split.py 261123_06 [...]
"""
import copy
import json
import re
import sys
from pathlib import Path

from studyez_contracts.bank.slide_focus import question_hash
from studyez_contracts.learning_links.validate import question_hash as links_question_hash
from studyez_contracts.roots import document_hash, validate_document

ROOT = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open')
WORK = ROOT / 'runs/_development/2026-11-25-long-list-answers/inplace2'
SPEC = {k: v for k, v in json.loads(Path(__file__).with_name('splits.json').read_text(encoding='utf-8')).items() if not k.startswith('_')}


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def visible(text):
    return re.sub(r'\s+', '', text.replace('**', ''))


def rewrite(q, spec, old_units):
    units = [old_units[u] if isinstance(u, int) else u for u in spec['units']]
    assert len(units) == len(set(units)) and all(units), (q['question_id'], '채점 단위')
    answer = spec.get('answer') or '; '.join(units)
    assert all(visible(u) in visible(answer) for u in units), (q['question_id'], '정답 글에 없는 채점 단위')
    assert ';' not in answer or 'answer' not in spec, (q['question_id'], '모양 답에 「;」')
    q.update(answer=answer, answer_units=units)
    if spec.get('question'):
        q['question'] = spec['question']
    if spec.get('explanation'):
        q['explanation'] = (q.get('explanation') or '').strip() + ('\n' if (q.get('explanation') or '').strip() else '') + spec['explanation']
    return q


def split(rid):
    before, after = WORK / rid / 'before', WORK / rid / 'after'
    doc = load(before / 'document.json')
    mcq, order, evidence, result = (load(before / f) for f in
                                    ('root_mcq.json', 'root_order.json', 'root_evidence.json', 'generation-result.json'))
    new = copy.deepcopy(doc)
    bank = new['bank_snapshot']
    originals = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    numbers = [int(m.group(1)) for q in originals for m in [re.fullmatch(r'Q(\d+)', q)] if m]
    next_id = max(numbers) + 1
    changed, added, lines = [], [], []
    tasked = {t['question_id'] for t in doc['tasks']}
    for qid, spec in SPEC[rid].items():
        if qid not in tasked:
            lines.append(f"- {qid}: 과제가 아니라(학습 경로에 없음) 그대로 둔다.")
            continue
        index = next(i for i, q in enumerate(bank['questions']) if q['question_id'] == qid)
        parent, old = bank['questions'][index], originals[qid]
        rewrite(parent, spec, old['answer_units'])
        changed.append(qid)
        lines.append(f"### {qid} · {old['question'][:80]}\n\n전({len(old['answer_units'])}개): {old['answer']}\n\n후({len(parent['answer_units'])}개) · {parent['question']}\n```\n{parent['answer']}\n```\n근거: {spec.get('basis', '')}\n")
        task_at = next(i for i, t in enumerate(new['tasks']) if t['question_id'] == qid)
        task = new['tasks'][task_at]
        mappings = [m for m in new['review']['mappings'] if m['question_id'] == qid]
        for n, child_spec in enumerate(spec.get('new', []), 1):
            child = copy.deepcopy(old)
            child['question_id'] = f'Q{next_id:03d}'
            next_id += 1
            child['prerequisites'] = []
            child['exam_rationale'] = f'long-list-split/1(2026-11-25): {qid}의 원본 묶음을 따로 묻는다. ' + spec.get('basis', '')
            rewrite(child, {'question': child_spec['question'], **child_spec}, old['answer_units'])
            bank['questions'].insert(index + n, child)
            new['tasks'].insert(task_at + n, {'task_id': 'task-' + document_hash([child['question_id'], task['direction_id']])[:24],
                                              'question_id': child['question_id'], 'direction_id': task['direction_id']})
            for m in mappings:
                new['review']['mappings'].append({**copy.deepcopy(m), 'question_id': child['question_id']})
            added.append(child['question_id'])
            lines.append(f"- 새 카드 {child['question_id']} · {child['question']}\n```\n{child['answer']}\n```\n")

    questions = {q['question_id']: q for q in bank['questions']}
    touched = set(changed) | set(added)
    for qid, q in questions.items():
        if qid not in touched:
            assert q == originals[qid], (qid, '손대지 않은 문항이 바뀜')
    assert [t for t in new['tasks'] if t['question_id'] not in set(added)] == doc['tasks'], '기존 과제가 바뀜'
    new['review']['bank_sha256'] = document_hash(bank)
    for m in new['review']['mappings']:
        m['question_sha256'] = links_question_hash(questions[m['question_id']], bank)
    validate_document(new)

    dropped = {'root_mcq': [], 'root_order': []}
    if mcq is not None:
        mcq = {**mcq, 'questions': {k: v for k, v in mcq['questions'].items() if k not in touched}}
        dropped['root_mcq'] = sorted(set(load(before / 'root_mcq.json')['questions']) & touched)
    if order is not None:
        dropped['root_order'] = sorted(set(order['questions']) & touched)
        order = {**order, 'questions': {k: v for k, v in order['questions'].items() if k not in touched}}
        for key in ('not_ordered', 'dropped'):
            if isinstance(order.get(key), dict):
                order[key] = {k: v for k, v in order[key].items() if k not in touched}
    if evidence is not None:
        for block in ('slideFocus', 'evidenceResolution'):
            for qid, record in ((evidence.get(block) or {}).get('questions') or {}).items():
                if qid in touched and record.get('questionHash') == question_hash(originals[qid]):
                    record['questionHash'] = question_hash(questions[qid])
    if result is not None:
        assert result['document'] == doc
        manifest = dict(result['manifest'])
        if manifest.get('bankHash') == document_hash(doc['bank_snapshot']):
            manifest['bankHash'] = document_hash(bank)
        result = {**result, 'document': new, 'manifest': manifest}

    after.mkdir(parents=True, exist_ok=True)
    (after / 'document.json').write_text(json.dumps(new, ensure_ascii=False), encoding='utf-8')
    for name, value in (('root_mcq.json', mcq), ('root_order.json', order), ('root_evidence.json', evidence),
                        ('generation-result.json', result)):
        if value is not None:
            (after / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    summary = {'runId': rid, 'title': doc['title'], 'questions': len(questions), 'changed': changed, 'added': added,
               'tasksBefore': len(doc['tasks']), 'tasksAfter': len(new['tasks']), 'dropped': dropped,
               'digestBefore': document_hash(doc), 'digestAfter': document_hash(new)}
    (after / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (WORK / f'report-{rid}.md').write_text('\n'.join([f'# {doc["title"]} ({rid})', '', *lines]), encoding='utf-8')
    return summary


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for rid in sys.argv[1:]:
        print(json.dumps(split(rid), ensure_ascii=False), flush=True)
