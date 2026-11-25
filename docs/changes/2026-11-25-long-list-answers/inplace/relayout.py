"""긴 나열 답의 정답 칸 모양만 공개판 사본에서 바꾸고 검사한다(운영 쓰기 없음). 결과는 <runId>/after/, 보고는 report-<runId>.md.

바꾸는 것은 문항의 `answer` 글 하나다. 발문·채점 단위(answer_units)·해설·보기는 그대로다. 그래서 같은 판을
그대로 쓰고 학습 기록은 task_id로 이어진다(11-24 표기 제자리 수정과 같은 길, ../../2026-11-24-term-notation-published).
글이 바뀐 문항은 선지·순서·근거 asset과 검토 묶음의 문항 지문을 새 글로 다시 맞춘다(내용은 그대로).

정답 글은 판정(`runs/_development/2026-11-25-long-list-answers/<runId>.json`, long-list-judge/1)에서 만든다.
- ungrouped: 「**대표: …**」 + 「갈래: / 축 — 원소」(studyez_contracts.roots.long_list.answer_preview)
- grouped: 원본 묶음 이름마다 「묶음 — 원소」 줄
- overlapping·고칠 방법 없음·쪽 번호 이름 묶음·한 묶음이 다른 묶음 안에 든 것·대부분 한 개짜리 묶음: 건너뛴다

    python relayout.py 261123_06 [...]
"""
import copy
import json
import re
import sys
from pathlib import Path

from studyez_contracts.bank.slide_focus import authored_hash, question_hash
from studyez_contracts.learning_links.validate import question_hash as links_question_hash
from studyez_contracts.roots import document_hash, validate_document
from studyez_contracts.roots import long_list as long_list
from studyez_contracts.roots import mcq as mcq_contract
from studyez_contracts.roots import order as order_contract

ROOT = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open')
DEV = ROOT / 'runs/_development/2026-11-25-long-list-answers'
WORK = DEV / 'inplace'
SKIP_KINDS = ('overlapping',)
FIXES = {'폐실질 (paranchyma) 침범': '폐실질(parenchyma) 침범'}   # 원본 슬라이드 오타


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def visible(text):
    return re.sub(r'\s+', '', text.replace('**', ''))


def layout(q, judgment):
    """(새 정답 글, 건너뛴 이유). 판정을 지금 계약으로 다시 검사한다."""
    raw = {'question_id': q['question_id'], **{k: judgment.get(k, d) for k, d in (
        ('kind', ''), ('groups', []), ('keep_group', -1), ('representatives', []), ('representative_basis', ''),
        ('branches', []), ('note', ''), ('basis', ''))}}
    try:
        row = long_list.check(q, raw)
    except ValueError as cause:
        return None, f'판정 검사: {cause}'
    units = long_list.units(q)
    if any(re.search(r' — |: ', u) for u in units):
        return None, '채점 단위가 이미 「항목 — 값」 짝(분류해서 묻는 문항)'
    if row['kind'] in SKIP_KINDS:
        return None, '겹치는 묶음(사람이 정함)'
    if not row['fixable']:
        return None, '고칠 방법 없음'
    if row['kind'] == 'ungrouped':
        if len(row['representatives']) * 3 > len(units) * 2:
            # 대표가 거의 전부면 대표 줄은 뜻이 없다(통풍 GQ055: 6개 중 5개). 갈래만 남긴다.
            row = {**row, 'representatives': []}
            if not row['branches']:
                return None, '대표가 거의 전부이고 갈래 없음'
        return long_list.answer_preview(q, row), None
    groups = row['groups']
    if sum(len(g['unit_indices']) == 1 for g in groups) * 2 > len(groups):
        return None, '원본 묶음이 대부분 한 개짜리'
    if any(re.search(r'\(\d\)', g['name']) for g in groups):
        return None, '묶음 이름이 쪽 번호'
    sets = [set(g['unit_indices']) for g in groups]
    if any(a < b for a in sets for b in sets):
        return None, '한 묶음이 다른 묶음 안에 듦'
    # 여러 층 묶음 이름(「바깥 — 안쪽」): 바깥이 모두 같으면 안쪽만, 다르면 「바깥: 안쪽」. 「—」는 줄 구분에만 쓴다.
    parts = [[re.sub(r'^[①-⑳]\s*', '', p).strip() for p in g['name'].split(' — ')] for g in groups]
    same_outer = len({tuple(p[:-1]) for p in parts}) == 1
    names = [p[-1] if same_outer or len(p) == 1 else ': '.join(p) for p in parts]
    names = [FIXES.get(n, n) for n in names]
    return '\n'.join(f"{n} — " + ', '.join(units[i] for i in g['unit_indices']) for n, g in zip(names, groups)), None


SHORT = {k: v for k, v in load(Path(__file__).with_name('short-names.json')).items() if not k.startswith('_')}


def shorten(text, names):
    """사용자 2026-11-25 「갈래 이름이 너무 길어」: 「이름 — 원소」 줄의 이름을 짧은 이름으로(줄 순서대로).
    대표 줄이 없으면 「갈래:」 머리 줄과 들여쓰기를 뺀다(좋은 예로 든 「경보 — … / 작용 — …」 모양)."""
    lines = text.splitlines()
    named = [i for i, line in enumerate(lines) if ' — ' in line]
    if names is not None:
        assert len(names) == len(named), ('짧은 이름 수가 줄 수와 다름', names, lines)
        for i, short in zip(named, names):
            lines[i] = re.sub(r'^(\s*).*? — ', lambda m: m.group(1) + short + ' — ', lines[i], count=1)
    if lines and lines[0] == '갈래:':
        lines = [line.strip() for line in lines[1:]]
    return '\n'.join(lines)


def relayout(rid):
    before, after = WORK / rid / 'before', WORK / rid / 'after'
    doc = load(before / 'document.json')
    mcq, order, evidence, result = (load(before / f) for f in
                                    ('root_mcq.json', 'root_order.json', 'root_evidence.json', 'generation-result.json'))
    judged = load(DEV / f'{rid}.json')
    new = copy.deepcopy(doc)
    questions = {q['question_id']: q for q in new['bank_snapshot']['questions']}
    originals = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    changed, lines, skipped = set(), [], []
    for qid, judgment in judged['judgments'].items():
        q = questions[qid]
        text, why = layout(originals[qid], judgment)
        if why:
            skipped.append((qid, why))
            continue
        text = shorten(text, SHORT.get(rid, {}).get(qid))
        # 채점 단위는 그대로, 단위마다 새 글에 있어야 한다(모양만 바꾼다)
        missing = [u for u in long_list.units(q) if visible(u) not in visible(text)]
        assert not missing, (rid, qid, '새 글에 없는 채점 단위', missing)
        assert ';' not in text, (rid, qid, '「;」가 남음')
        q['answer'] = text
        changed.add(qid)
        lines.append(f"### {qid} · {q['question'][:80]}\n\n전: {originals[qid]['answer']}\n\n후:\n```\n{text}\n```\n")
    for qid in changed:
        q, o = questions[qid], originals[qid]
        assert {k for k in q} == {k for k in o} and all(q[k] == o[k] for k in o if k != 'answer'), (qid, '다른 칸이 바뀜')

    bank = new['bank_snapshot']
    assert new['review']['bank_sha256'] == document_hash(doc['bank_snapshot'])
    new['review']['bank_sha256'] = document_hash(bank)
    for mapping in new['review']['mappings']:
        if mapping['question_id'] in changed:
            assert mapping['question_sha256'] == links_question_hash(originals[mapping['question_id']], doc['bank_snapshot'])
            mapping['question_sha256'] = links_question_hash(questions[mapping['question_id']], bank)
    validate_document(new)

    if mcq is not None:
        rows = copy.deepcopy(mcq['questions'])
        for qid, row in rows.items():
            if qid in changed:
                row['question_hash'] = authored_hash(questions[qid])
        bad = {qid: mcq_contract.entry_errors_v2(questions[qid], row) for qid, row in rows.items() if qid in questions}
        before_bad = {qid: mcq_contract.entry_errors_v2(originals[qid], row) for qid, row in mcq['questions'].items() if qid in originals}
        newly = {k: v for k, v in bad.items() if v and not before_bad.get(k)}
        assert not newly, ('선지 검사 실패', newly)
        mcq = {**mcq, 'questions': rows}
    if order is not None:
        old_rows = copy.deepcopy(order['questions'])
        for qid, row in order['questions'].items():
            if qid in changed:
                row['question_hash'] = authored_hash(questions[qid])
            was_ok = not order_contract.row_errors(originals[qid], old_rows[qid])
            assert not was_ok or not order_contract.row_errors(questions[qid], row), (qid, '순서 칸 검사 실패')
    if evidence is not None:
        for block in ('slideFocus', 'evidenceResolution'):
            for qid, record in ((evidence.get(block) or {}).get('questions') or {}).items():
                if qid in changed and record.get('questionHash') == question_hash(originals[qid]):
                    record['questionHash'] = question_hash(questions[qid])
    if result is not None:
        assert result['document'] == doc
        manifest = dict(result['manifest'])
        if manifest.get('bankHash') == document_hash(doc['bank_snapshot']):
            manifest['bankHash'] = document_hash(new['bank_snapshot'])
        result = {**result, 'document': new, 'manifest': manifest}

    after.mkdir(parents=True, exist_ok=True)
    (after / 'document.json').write_text(json.dumps(new, ensure_ascii=False), encoding='utf-8')
    for name, value in (('root_mcq.json', mcq), ('root_order.json', order), ('root_evidence.json', evidence),
                        ('generation-result.json', result)):
        if value is not None:
            (after / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    summary = {'runId': rid, 'title': doc['title'], 'questions': len(questions), 'changedQuestions': len(changed),
               'skipped': len(skipped), 'digestBefore': document_hash(doc), 'digestAfter': document_hash(new)}
    (after / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    report = [f'# {doc["title"]} ({rid})', '', json.dumps(summary, ensure_ascii=False), '', *lines,
              '## 건너뛴 것', *[f'- {a}: {b}' for a, b in skipped]]
    (WORK / f'report-{rid}.md').write_text('\n'.join(report), encoding='utf-8')
    return summary


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for rid in sys.argv[1:]:
        print(json.dumps(relayout(rid), ensure_ascii=False), flush=True)
