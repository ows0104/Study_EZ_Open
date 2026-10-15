"""Select the smallest actual exam page set; never infer core evidence from citation order."""
import hashlib
import json
from pathlib import Path
from .coverage import _call
from .points import STR, _array, _object
from .session import SessionError

SCHEMA = _object({'selections': _array(_object({
    'question_id': STR, 'mode': {'type': 'string', 'enum': ['single', 'linked', 'unresolved']},
    'reason': STR, 'pages': _array(_object({'id': STR, 'evidence': STR})),
}))})
PROMPT = '''문제은행의 실제 족보 핵심 지면만 고른다. 문항·정답·해설·검수 등급은 읽기 전용이다.
targets.json의 각 question_id를 정확히 한 번 반환한다. question에는 현재 문항·정답이 있다.
candidates는 원본 PDF에서 렌더한 실제 족보 지면들이다. image를 view_image로 확인하고,
정답의 핵심 판단을 가장 직접적으로 뒷받침하는 최소 지면을 선택한다. 인용 순서·가장 앞 쪽·
기출 연도·단어 일치로 대신하지 않는다. 같은 내용의 기출이 여러 개면 한 지면만 고른다.
기본 mode=single 한 장이다. 실제 채점 핵심이 서로 다른 지면에 분산되어 한 장으로 충분하지
않을 때만 linked로 최소 장수를 선택한다. 각 evidence에 그 장의 실제 문구/정답 표시/그림과
현재 정답의 연결을 적고 reason에 연계가 꼭 필요한 이유를 쓴다. 발문의 주어진 조건을 원본에서
다시 찾거나 주변 해설·오답 배경 전체를 핵심으로 확대하지 않는다. 의미상 같은 표현과 명확한
짧은 추론은 인정한다. 외부 지식으로 빈 근거를 만들지 않는다.
직전 독립 조사 category=exam_only인 항목은 강의 근거 부재와 족보 근거 유무를 이미 대조했다.
이번 작업은 그 실제 증거 지면 가운데 최소 장수를 선택하는 단계다. 그래도 실제 이미지에서
핵심을 입증할 수 없거나 원문 정답이 비어 있으면 임의로 승격하지 말고 unresolved, pages=[]와
이유를 기록한다. id는 candidates의 실제 id만 쓴다. 원본이나 문제은행을 변경하지 않는다.
'''

def shape(raw: dict, targets: list[dict]) -> dict[str, dict]:
    expected = {t['question_id']: t for t in targets}
    found = {}
    for row in raw['selections']:
        qid = row['question_id']
        if qid not in expected or qid in found:
            raise SessionError('족보 핵심 선정: 없는 문항 또는 중복')
        pages, mode = row['pages'], row['mode']
        if not row['reason'].strip() or mode not in ('single', 'linked', 'unresolved') \
                or mode == 'single' and len(pages) != 1 or mode == 'linked' and len(pages) < 2 \
                or mode == 'unresolved' and pages:
            raise SessionError('족보 핵심 선정: 유형·장수·이유가 맞지 않음')
        candidates = {c['id']: c for c in expected[qid]['candidates']}
        ids = [p['id'] for p in pages]
        if len(set(ids)) != len(ids) or any(p['id'] not in candidates or not p['evidence'].strip() for p in pages):
            raise SessionError('족보 핵심 선정: 실제 지면과 구체적인 근거가 필요함')
        found[qid] = {'mode': mode, 'reason': row['reason'], 'pages': [
            {**{k: v for k, v in candidates[p['id']].items() if k not in ('id', 'image')}, 'evidence': p['evidence']}
            for p in pages]}
    if set(found) != set(expected):
        raise SessionError('족보 핵심 선정: 문항 누락')
    return found

def select(targets: list[dict], out: Path, model: str | None = None) -> tuple[dict, list[dict]]:
    if not targets:
        return {}, []
    out.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(json.dumps({'targets': targets, 'prompt': PROMPT}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cached = out / 'exam-focus.json'
    if cached.is_file():
        data = json.loads(cached.read_text(encoding='utf-8'))
        if data.get('inputHash') == signature:
            return data['selections'], []
    (out / 'targets.json').write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding='utf-8')
    raw, usage = _call(PROMPT, SCHEMA, out, model, '족보 핵심 지면 선택')
    result = shape(raw, targets)
    (out / 'exam-focus.raw.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    cached.write_text(json.dumps({'inputHash': signature, 'selections': result}, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'usage.json').write_text(json.dumps(usage), encoding='utf-8')
    return result, [usage]


def resolve(bank: dict, focus: dict, references: dict, paths: dict[str, Path], out: Path,
            run_id: str, model: str | None = None) -> tuple[dict, list[dict]]:
    """Turn source-audited unresolved cases into exam cores or visible, hash-bound source notices."""
    from server.app.bank_validation.slide_focus import question_hash
    from server.app.bank_validation.evidence_resolution import CATEGORIES
    import fitz
    questions, pending = {}, []
    images = out / 'slides'
    images.mkdir(parents=True, exist_ok=True)
    for q in bank['questions']:
        qid = q['question_id']
        source = focus.get('questions', {}).get(qid) or {}
        base = source.get('base') or {}
        category = base.get('unresolved_cause')
        if source.get('questionHash') != question_hash(q) or base.get('mode') != 'unresolved' or category not in CATEGORIES:
            continue
        record = {'questionHash': question_hash(q), 'base': {'category': category, 'reason': base['reason'], 'missingClaim': ''}}
        questions[qid] = record
        if category != 'exam_only':
            continue
        candidates = {}
        allowed = {r['locator'] for r in q.get('source_refs', []) if r['source_id'] == 'S2'}
        linked = references.get('questions', {}).get(qid) or {}
        if linked.get('questionHash') == question_hash(q):
            for locator, refs in linked.get('locators', {}).items():
                if locator not in allowed:
                    continue
                for ref in refs:
                    c = candidates.setdefault(ref['filename'], {**{k: ref[k] for k in ('filename', 'pdfFilename', 'page', 'sourceSha256')},
                        'id': ref['filename'], 'image': str((images / ref['filename']).resolve()), 'references': [], 'embedded': False})
                    label = f"{ref['year']} {ref['number']}번"
                    if label not in c['references']:
                        c['references'].append(label)
        for ref in base.get('exam_pages', []):
            sid = ref.get('source_id') or 'self'
            if sid not in paths:
                continue
            pdf = paths[sid]
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
            expected = focus.get('sourceSha256') if sid == 'self' else focus.get('sources', {}).get(sid, {}).get('sourceSha256')
            if digest != expected:
                raise SessionError('첨부 기출 원본이 핵심 근거 선정 이후 변경되었습니다.')
            page = ref['page']
            filename = f'{run_id}_jbembedded{digest[:16]}_p{page:04d}.png'
            image = images / filename
            with fitz.open(pdf) as doc:
                if not 1 <= page <= doc.page_count:
                    raise SessionError('첨부 기출 쪽이 실제 PDF에 없습니다.')
                if not image.is_file():
                    doc[page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(image)
            candidates[filename] = {'id': filename, 'filename': filename, 'page': page, 'pdfFilename': pdf.name,
                'sourceSha256': digest, 'references': ['첨부 기출'], 'embedded': True, 'image': str(image.resolve())}
        if candidates:
            pending.append({'question_id': qid, 'question': q, 'category': category, 'candidates': list(candidates.values())})
    selected, usage = select(pending, out / 'exam-focus', model)
    for qid, selection in selected.items():
        questions[qid]['base']['examCore'] = selection
    return {'version': 1, 'questions': questions}, usage
