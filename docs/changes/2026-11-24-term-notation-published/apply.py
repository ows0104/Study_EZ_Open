"""scan 결과를 공개판 사본에 적용하고 검사한다(운영 쓰기 없음). 결과는 <runId>/after/, 보고는 report-<runId>.md.

문항 글(발문·정답·채점 단위·해설·보기)과 그 문항의 선지(오답 글·틀린 이유)만 바꾼다. 같은 판을 그대로 쓰므로
학습 기록은 task_id로 이어진다. 글이 바뀐 문항은 선지·순서·근거 asset의 문항 지문을 새로 맞춘다(내용은 그대로).
"""
import copy
import json
import re
import sys
from pathlib import Path

from studyez_contracts.bank.slide_focus import authored_hash, question_hash
from studyez_contracts.roots import document_hash, validate_document
from studyez_contracts.learning_links.validate import question_hash as links_question_hash
from studyez_contracts.roots import mcq as mcq_contract
from studyez_contracts.roots import order as order_contract

ROOT = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open')
WORK = ROOT / 'runs/_development/2026-11-24-term-notation-published'
HERE = Path(__file__).resolve().parent
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9α-ωΑ-Ω'’\-]*(?:[ /][A-Za-z0-9α-ωΑ-Ω'’\-]+)*")
SPACE = re.compile(r'\s+')


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def text_fields(q):
    """(경로, 값) — 바꿀 수 있는 문항 글."""
    yield ('question',), q['question']
    yield ('answer',), q['answer']
    for i, unit in enumerate(q.get('answer_units') or []):
        yield ('answer_units', i), unit
    yield ('explanation',), q.get('explanation', '')
    for i, option in enumerate(q.get('options') or []):
        yield ('options', i, 'text'), option.get('text', '')


PARTICLES = ('으로서', '으로', '에서', '에게', '까지', '부터', '보다', '처럼', '이다', '이며', '이고', '이나', '이면', '이라',
             '와의', '과의', '이', '가', '을', '를', '은', '는', '의', '에', '와', '과', '로', '도', '만', '인', '라', '나', '및')
HANGUL = re.compile(r'[가-힣]')


VOWEL_E = ('ge', 'te', 'ue', 're', 'de', 've', 'se', 'ce', 'ze', 'ie', 'ee', 'oe')
# (받침 뒤, 받침 없을 때) — 긴 꼴을 먼저 본다. ㄹ 받침 뒤 「으로」는 「로」.
PAIRS = (('으로', '로'), ('과의', '와의'), ('이', '가'), ('을', '를'), ('은', '는'), ('과', '와'))
SKIPPED = []   # (값, src) — 낱말 중간이라 치환하지 않은 곳(보고용)


def english_final(word):
    """영어 낱말을 한국어로 읽을 때 끝소리: 'ㄹ', '받침', '없음'. 대문자 약어는 None(판정하지 않는다)."""
    bare = word.rstrip("'’")
    w = bare.lower()
    if not w or bare.isupper() or not w[-1].isalpha():
        return None
    if w.endswith(('l', 'le')):
        return 'ㄹ'
    if w.endswith(('ng', 'n', 'm', 'ck', 'k', 'p', 'g', 'b', 'me', 'ne', 'pe', 'ke')):
        return '받침'
    return '없음'


def particle_at(head, following):
    """head 뒤 following 첫머리의 조사를 head 끝 영문 낱말의 끝소리에 맞춘다. (바른 조사, 원래 조사 길이) 또는 None."""
    main = re.sub(r'\([^()]*\)$', '', head)          # 괄호 병기 뒤 조사는 괄호 앞 말에 맞춘다
    m = re.search(r"([A-Za-z][A-Za-z'’\-]*)$", main)
    final = english_final(m.group(1)) if m else None
    if final is None:
        return None
    for jong, vowel in PAIRS:
        for form in (jong, vowel):
            nxt = following[len(form):len(form) + 1]
            if following.startswith(form) and not (len(form) == 1 and nxt and HANGUL.match(nxt)):
                want = vowel if final == '없음' or (final == 'ㄹ' and jong == '으로') else jong
                return want, len(form)
    return None


def split_particle(dst):
    """dst 끝에 붙은 조사를 떼어 (본문, 조사)로 돌려준다(scan이 조사까지 포함해 준 치환)."""
    m = re.match(r"(.*[A-Za-z)])(으로서|으로|과의|와의|이다|이며|이고|이나|이면|이라|이|가|을|를|은|는|과|와|로)$", dst)
    return (m.group(1), m.group(2)) if m and re.search('[A-Za-z]', m.group(1)) else (dst, '')


def replace(value, src, dst):
    """src를 dst로.
    - 이미 dst가 있는 자리(앞 치환의 결과) 안의 src는 다시 바꾸지 않는다(「macrophage(macrophage(대식세포))」 방지).
    - src가 한글로 시작하는데 바로 앞 글자가 한글이면 낱말 중간이다(「부갑상선」의 「갑상선」). 바꾸지 않는다.
    - 「…(src)」처럼 괄호 안이면 dst의 앞말만 쓴다(「요산 침착(통풍결절)」→「요산 침착(tophus)」).
    - dst가 괄호 병기로 끝나는데 바로 뒤에 괄호가 또 오면 앞말만 쓴다(「항중심절항체(ACA)」→「anti-centromere(ACA)」).
    - 영문 뒤 조사는 영문의 끝소리에 맞추고, 조사가 아닌 한글 낱말이 붙으면 띄운다(「parotid gland종창」 방지).
    """
    covered = [(m.start(), m.end()) for m in re.finditer(re.escape(dst), value)] if dst else []
    body, own = split_particle(dst)
    head_only = re.sub(r'\([^()]*\)$', '', body).rstrip()
    out, start, pos = [], 0, 0
    while (i := value.find(src, pos)) >= 0:
        j = i + len(src)
        if any(a <= i and j <= b for a, b in covered):
            pos = i + 1
            continue
        if HANGUL.match(src[0]) and i > 0 and HANGUL.match(value[i - 1]):
            SKIPPED.append((value, src))
            pos = i + 1
            continue
        piece = body
        if body.endswith(')') and ((i > 0 and value[i - 1] == '(' and value[j:j + 1] == ')') or value[j:j + 1] == '('):
            piece = head_only
        out.append(value[start:i])
        out.append(piece)
        following = own + value[j:]
        fixed = particle_at(piece, following) if re.search(r"[A-Za-z)]$", piece) else None
        if fixed:
            want, length = fixed
            out.append(want + own[length:])
            if not own:
                j += length
        else:
            out.append(own)
            if not own and re.search(r'[A-Za-z]$', piece) and value[j:j + 1] and HANGUL.match(value[j]) \
                    and not value[j:].startswith(PARTICLES):
                out.append(' ')
        start = pos = j
    out.append(value[start:])
    return ''.join(out)


def put(obj, path, value):
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value


def material_text(doc):
    folder = ROOT / 'runs/_root-generation' / doc['revision'].removeprefix('auto-') / 'generation/material'
    raw = ''.join(p.read_text(encoding='utf-8') for p in sorted(folder.glob('*.md')))
    return SPACE.sub('', raw).lower()


def in_material(term, mat):
    return SPACE.sub('', term).lower() in mat


def apply(rid):
    before, after = WORK / rid / 'before', WORK / rid / 'after'
    doc = load(before / 'document.json')
    mcq, order, evidence, result = (load(before / f) for f in
                                    ('root_mcq.json', 'root_order.json', 'root_evidence.json', 'generation-result.json'))
    # scan2(표기) 다음에 scan3(align.py: 객관식 묶음 표기 맞춤). scan3의 from은 scan2를 적용한 글 기준이다.
    if SOURCE == 'claude':   # Claude 하위 에이전트가 원본부터 본 결과(prep_claude.py). from은 원본 글 기준
        edits = [e for f in sorted((WORK / rid / 'claude').glob('edits-*.json')) for e in load(f)['edits']]
    else:
        edits = [e for d in ('scan2', 'scan3') for f in sorted((WORK / rid / d).glob('chunk-*.json')) for e in load(f)['edits']]
    mat = material_text(doc)
    new = copy.deepcopy(doc)
    questions = {q['question_id']: q for q in new['bank_snapshot']['questions']}
    originals = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    rows = copy.deepcopy((mcq or {}).get('questions') or {})
    lines, rejected, unverified, changed = [], [], [], set()

    overrides = load(HERE / ('overrides-claude.json' if SOURCE == 'claude' else 'overrides.json')).get(rid, {})
    SKIPPED.clear()

    def skipped(qid, src):
        return any(src.startswith(s) for s in (overrides.get(qid) or {}).get('skip', []))

    for edit in edits:
        qid = edit['question_id']
        q = questions.get(qid)
        if q is None:
            rejected.append((qid, '판에 없는 문항'))
            continue
        row = rows.get(qid)
        for r in edit.get('replacements', []):
            src, dst = r['from'], r['to']
            if not src or src.lower() == dst.lower():
                continue   # 대소문자만 다른 치환은 하지 않는다(문장 첫 약물명 등)
            if re.search('[A-Za-z]{3}', src) and not re.search('[A-Za-z]{3}', dst):
                rejected.append((qid, f'「{src}」→「{dst}」 영어를 한글로 바꾸지 않는다'))
                continue
            if skipped(qid, src):
                rejected.append((qid, f'「{src}」 검토 예외(overrides.json)'))
                continue
            hits = 0
            for path, value in list(text_fields(q)):
                if src in value:
                    put(q, path, replace(value, src, dst))
                    hits += value.count(src)
            for w in (row or {}).get('wrong') or []:
                for key in ('text', 'why_wrong'):
                    if src in (w.get(key) or ''):
                        w[key] = replace(w[key], src, dst)
                        hits += 1
            if not hits:
                rejected.append((qid, f'「{src}」가 문항에 없음'))
                continue
            terms = [t for t in LATIN.findall(dst) if len(t) >= 3]
            if terms and not all(in_material(t, mat) for t in terms):
                unverified.append((qid, src, dst))
            lines.append(f'| {qid} | 문항 | {src} | {dst} | {edit.get("basis", "")} |')
        for r in edit.get('choice_replacements', []):
            w = next((w for w in (row or {}).get('wrong') or [] if w['id'] == r['choice_id']), None)
            if r['from'].lower() == r['to'].lower():
                continue
            if skipped(qid, r['from']):
                rejected.append((qid, f'선지 「{r["from"]}」 검토 예외(overrides.json)'))
                continue
            if w is None or (r['from'] not in w['text'] and r['from'] not in (w.get('why_wrong') or '')):
                rejected.append((qid, f'선지 {r["choice_id"]} 「{r["from"]}」 없음'))
                continue
            w['text'] = replace(w['text'], r['from'], r['to'])
            w['why_wrong'] = replace(w.get('why_wrong') or '', r['from'], r['to'])
            lines.append(f'| {qid} | 선지 | {r["from"]} | {r["to"]} | {edit.get("basis", "")} |')

    # 검토 예외의 post: 치환 뒤 그 문항(또는 '*' 강의 전체)의 글·선지에 그대로 적용
    for key, spec in overrides.items():
        for src, dst in spec.get('post', []) if isinstance(spec, dict) else []:
            for qid in (questions if key == '*' else [key]):
                q, hits = questions[qid], 0
                for path, value in list(text_fields(q)):
                    if src in value:
                        put(q, path, value.replace(src, dst))
                        hits += 1
                for w in (rows.get(qid) or {}).get('wrong') or []:
                    for k in ('text', 'why_wrong'):
                        if src in (w.get(k) or ''):
                            w[k] = w[k].replace(src, dst)
                            hits += 1
                if hits:
                    lines.append(f'| {qid} | 검토 | {src} | {dst} | overrides.json |')
    for value, src in SKIPPED:
        rejected.append(('-', f'낱말 중간이라 건너뜀: 「{src}」 in 「{value[:60]}」'))

    # 문항 글의 구조가 그대로인지
    for qid, q in questions.items():
        o = originals[qid]
        if q == o and rows.get(qid) == ((mcq or {}).get('questions') or {}).get(qid):
            continue
        changed.add(qid)
        assert q['question'].count('{') == o['question'].count('{'), (qid, 'cloze 빈칸 수')
        for path, value in text_fields(q):
            assert not re.search(r'\([^()]*\(|\)\(', value) or re.search(r'\([^()]*\(|\)\(', dict(text_fields(o)).get(path, '')), (qid, path, '괄호 겹침', value)
        assert len(q.get('answer_units') or []) == len(o.get('answer_units') or []), (qid, '채점 단위 수')
        if o['answer'] == '; '.join(o.get('answer_units') or []) and q['answer'] != '; '.join(q['answer_units']):
            # 치환이 「…;」처럼 경계를 끼고 정답에만 걸린 경우: 단위마다 바뀐 쪽을 골라 둘을 다시 맞춘다.
            parts = q['answer'].split('; ')
            assert len(parts) == len(o['answer_units']), (qid, '정답 단위 수')
            q['answer_units'] = [p if p != u else n for p, n, u in zip(parts, q['answer_units'], o['answer_units'])]
            q['answer'] = '; '.join(q['answer_units'])
        if o['answer'] == '; '.join(o.get('answer_units') or []):
            assert q['answer'] == '; '.join(q['answer_units']), (qid, '정답·채점 단위 어긋남')
        assert {k for k in q} == {k for k in o} and all(q[k] == o[k] for k in o if k not in
                                                        ('question', 'answer', 'answer_units', 'explanation', 'options')), (qid, '다른 칸이 바뀜')

    # 검토 묶음의 은행·문항 지문(learning-links/1)도 새 글로 맞춘다. 판정(매핑·목표·과제) 자체는 그대로.
    bank = new['bank_snapshot']
    assert new['review']['bank_sha256'] == document_hash(doc['bank_snapshot'])
    new['review']['bank_sha256'] = document_hash(bank)
    for mapping in new['review']['mappings']:
        if mapping['question_id'] in changed:
            assert mapping['question_sha256'] == links_question_hash(originals[mapping['question_id']], doc['bank_snapshot'])
            mapping['question_sha256'] = links_question_hash(questions[mapping['question_id']], bank)
    validate_document(new)

    # 선지: 문항 지문·오답 ID를 새 글로 다시 맞추고 전체를 검사한다
    if mcq is not None:
        for qid, row in rows.items():
            q = questions.get(qid)
            if q is None:
                continue
            if qid in changed:
                row['question_hash'] = authored_hash(q)
                for w in row.get('wrong') or []:
                    w['id'] = mcq_contract.choice_id(qid, w['text'], w.get('group'))
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
               'replacements': len(lines), 'rejected': len(rejected), 'unverified': len(unverified),
               'digestBefore': document_hash(doc), 'digestAfter': document_hash(new)}
    (after / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    report = [f'# {doc["title"]} ({rid})', '', json.dumps(summary, ensure_ascii=False), '',
              '| 문항 | 칸 | 전 | 후 | 근거 |', '|---|---|---|---|---|', *lines, '', '## 버린 것', *[f'- {a}: {b}' for a, b in rejected],
              '', '## 강의자료 글에서 못 찾은 표기', *[f'- {a}: {b} → {c}' for a, b, c in unverified]]
    (WORK / f'report-{rid}.md').write_text('\n'.join(report), encoding='utf-8')
    return summary


SOURCE = 'codex'

if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:2] == ['--source', 'claude']:
        SOURCE, args = 'claude', args[2:]
    for rid in args:
        print(json.dumps(apply(rid), ensure_ascii=False), flush=True)
