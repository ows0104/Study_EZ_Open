"""쇼그렌 공개판 사본에 출제포인트 보강을 적용한다(운영 쓰기 없음). 결과는 <runId>/after/, 보고는 report-<runId>.md.

inplace2/split.py(2026-11-25)를 바탕으로 `edits.json`대로:
- tier: 글은 그대로 두고 문항의 원래 중요도만 바꾼다. 선지·순서 칸은 그대로 붙는다.
- rewrite: 같은 ID·같은 과제 자리에서 발문·정답·채점 단위·형식·해설을 바꾼다(그 카드의 기록만 「살짝」 어긋난다).
- new: 부모 카드를 복사해 새 Q번호를 주고 부모와 같은 목표(direction)에 과제로 붙인다.
손대지 않은 문항·과제는 글자 하나 바뀌지 않으므로 학습 기록이 task_id로 그대로 이어진다.

    python apply.py 261123_07
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
WORK = ROOT / 'runs/_development/2026-11-26-sjogren-points2'
SPEC = {k: v for k, v in json.loads(Path(__file__).with_name('edits.json').read_text(encoding='utf-8')).items()
        if not k.startswith('_')}
CLEAR = {'options': [], 'correct_option_ids': [], 'matching_left': [], 'matching_right': [], 'answer_pairs': [],
         'sequence_items': [], 'correct_order': [], 'option_explanations': [], 'option_pools': []}
TIERS = {'Essential', 'Core', 'Important', 'Optional'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def blanks(text):
    return re.findall(r'\{([^{}]+)\}', text)


def set_text(q, spec):
    units = spec['answer_units']
    assert len(units) == len(set(units)) and all(units), (q['question_id'], '채점 단위')
    if spec['format'] == 'cloze':
        assert blanks(spec['question']) == units, (q['question_id'], 'cloze 빈칸과 채점 단위가 다름')
    else:
        assert not blanks(spec['question']), (q['question_id'], 'cloze가 아닌데 빈칸')
    flat = lambda s: re.sub(r'\s+', '', s)
    assert all(flat(u) in flat(spec['answer']) for u in units), (q['question_id'], '정답 글에 없는 채점 단위')
    assert spec['tier'] in TIERS
    q.update(question=spec['question'], answer=spec['answer'], answer_units=list(units), format=spec['format'],
             mcq_mode='none', tier=spec['tier'], explanation=spec['explanation'], exam_rationale=spec['exam_rationale'],
             retrieval_direction='direct', **copy.deepcopy(CLEAR))
    return q


def apply(rid):
    before, after = WORK / rid / 'before', WORK / rid / 'after'
    doc = load(before / 'document.json')
    mcq, order, evidence, result = (load(before / f) for f in
                                    ('root_mcq.json', 'root_order.json', 'root_evidence.json', 'generation-result.json'))
    spec = SPEC[rid]
    new = copy.deepcopy(doc)
    bank = new['bank_snapshot']
    originals = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    tasked = {t['question_id'] for t in doc['tasks']}
    numbers = [int(m.group(1)) for q in originals for m in [re.fullmatch(r'Q(\d+)', q)] if m]
    next_id = max(numbers) + 1
    by_id = {q['question_id']: q for q in bank['questions']}
    tiered, rewritten, added, lines = [], [], [], []

    for tier, ids in spec.get('tier', {}).items():
        assert tier in TIERS
        for qid in ids:
            assert qid in tasked, (qid, '과제가 아님')
            q = by_id[qid]
            assert q['tier'] != tier, (qid, '이미', tier)
            lines.append(f"- {qid} {q['tier']} → {tier} · {q['question'][:70]}")
            q['tier'] = tier
            tiered.append(qid)

    for qid, edit in spec.get('rewrite', {}).items():
        assert qid in tasked, (qid, '과제가 아님')
        old = originals[qid]
        set_text(by_id[qid], edit)
        rewritten.append(qid)
        lines.append(f"\n### {qid} 다시 쓰기 ({old['tier']} {old['format']} → {edit['tier']} {edit['format']})\n\n"
                     f"전: {old['question']}\n=> {old['answer']}\n\n후: {edit['question']}\n```\n{edit['answer']}\n```\n"
                     f"근거: {edit['basis']}\n")

    for child_spec in spec.get('new', []):
        parent = child_spec['parent']
        assert parent in tasked, (parent, '부모가 과제가 아님')
        index = next(i for i, q in enumerate(bank['questions']) if q['question_id'] == parent)
        task_at = max(i for i, t in enumerate(new['tasks']) if t['question_id'] == parent)
        task = new['tasks'][task_at]
        child = copy.deepcopy(originals[parent])
        child['question_id'] = f'Q{next_id:03d}'
        next_id += 1
        child['prerequisites'] = []
        child['conflict_id'] = ''
        set_text(child, child_spec)
        bank['questions'].insert(index + 1, child)
        new['tasks'].insert(task_at + 1, {'task_id': 'task-' + document_hash([child['question_id'], task['direction_id']])[:24],
                                          'question_id': child['question_id'], 'direction_id': task['direction_id']})
        for m in [m for m in new['review']['mappings'] if m['question_id'] == parent]:
            new['review']['mappings'].append({**copy.deepcopy(m), 'question_id': child['question_id']})
        added.append(child['question_id'])
        lines.append(f"\n### 새 카드 {child['question_id']} ({child_spec['tier']}, 목표 {task['direction_id']}, 부모 {parent})\n\n"
                     f"{child['question']}\n```\n{child['answer']}\n```\n근거: {child_spec['basis']}\n")

    questions = {q['question_id']: q for q in bank['questions']}
    text_touched = set(rewritten) | set(added)
    touched = text_touched | set(tiered)
    for qid, q in questions.items():
        if qid not in touched:
            assert q == originals[qid], (qid, '손대지 않은 문항이 바뀜')
    for qid in tiered:
        assert {k: v for k, v in questions[qid].items() if k != 'tier'} == {k: v for k, v in originals[qid].items() if k != 'tier'}
    assert [t for t in new['tasks'] if t['question_id'] not in set(added)] == doc['tasks'], '기존 과제가 바뀜'
    new['review']['bank_sha256'] = document_hash(bank)
    for m in new['review']['mappings']:
        m['question_sha256'] = links_question_hash(questions[m['question_id']], bank)
    validate_document(new)

    # 선지·순서: 글을 바꾼 카드의 칸만 뺀다(옛 정답 기준). tier만 바꾼 카드는 그대로 붙는다.
    dropped = {'root_mcq': [], 'root_order': []}
    if mcq is not None:
        dropped['root_mcq'] = sorted(set(mcq['questions']) & text_touched)
        mcq = {**mcq, 'questions': {k: v for k, v in mcq['questions'].items() if k not in text_touched}}
    if order is not None:
        dropped['root_order'] = sorted(set(order['questions']) & text_touched)
        order = {**order, 'questions': {k: v for k, v in order['questions'].items() if k not in text_touched}}
        for key in ('not_ordered', 'dropped'):
            if isinstance(order.get(key), dict):
                order[key] = {k: v for k, v in order[key].items() if k not in text_touched}
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
    summary = {'runId': rid, 'title': doc['title'], 'questions': len(questions), 'tiered': tiered, 'rewritten': rewritten,
               'added': added, 'changed': sorted(set(tiered) | set(rewritten)),
               'tasksBefore': len(doc['tasks']), 'tasksAfter': len(new['tasks']), 'dropped': dropped,
               'digestBefore': document_hash(doc), 'digestAfter': document_hash(new)}
    (after / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (WORK / f'report-{rid}.md').write_text('\n'.join([f'# {doc["title"]} ({rid}) 출제포인트 보강', '', '## 등급', *lines]),
                                           encoding='utf-8')
    return summary


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for rid in sys.argv[1:]:
        print(json.dumps(apply(rid), ensure_ascii=False), flush=True)
