"""Read-only question evidence, bound to the exact authored source snapshots.

Quiz Bank 수준의 근거(2026-11-08): 판마다 러너가 올린 `root-evidence/1` JSON(asset 종류
`root_evidence`, 파일명 `<revision>.json`)이 있고 revision·원본 지문이 맞으면 Quiz Bank와 같은
계약 함수로 핵심 슬라이드·족보 지면·족보 핵심·근거 상태를 붙인다. 없거나 맞지 않으면 인용 쪽만 쓴다.
"""
import json
import re
from urllib.parse import quote
from sqlalchemy import select
from studyez_contracts.bank.evidence_resolution import primary_references as exam_primary_references
from studyez_contracts.bank.evidence_resolution import status as evidence_status
from studyez_contracts.bank.jokbo_pages import references as jokbo_references
from studyez_contracts.bank.pages import pages_of
from studyez_contracts.bank.slide_focus import all_selected_pages, question_hash, selected_references
from app.models import Asset, QuizBank
from app.root_learning.content import bank_hash
from app.storage import ObjectStorage

EVIDENCE_KIND = 'root_evidence'
EVIDENCE_SCHEMA = 'root-evidence/1'
# (object_key, size, uploaded_at) -> parsed JSON. A revision's evidence is replaced only by a new upload.
_EVIDENCE: dict[tuple, dict | None] = {}
_EVIDENCE_LIMIT = 32


def proxy_path(doc, source):
    """API path that streams the frozen PDF. PDF.js must fetch() the bytes and the R2
    bucket has no CORS rule, so the signed URL only works for links (원본 열기)."""
    return (f"/api/root-learning/lectures/{quote(doc.subject, safe='')}/{quote(doc.run_id, safe='')}"
            f"/sources/{quote(source['id'], safe='')}?sha={source['sha256']}")


def is_pdf(source):
    """정리본 족보처럼 파일명 뒤에 설명이 붙은 PDF(`…족보-김지은.pdf (감염성 질환의 병리 1·2, …)`)도 PDF다."""
    return source.get('contentType') == 'application/pdf' or re.search(r'\.pdf(?:$|\s)', source['filename'], re.I) is not None


def frozen_pdf(doc, generation, source_id):
    """The verified PDF snapshot for one source of the active document, or None."""
    if generation is None:
        return None
    from app.root_learning.reviewed_import import source_records
    known = {s['source_id']: s for s in doc.document['review']['sources']}
    for source in source_records(generation):
        expected = known.get(source['id'])
        if source['id'] != source_id or not expected or expected['sha256'] != source['sha256']:
            continue
        if is_pdf(source):
            return source
    return None


def stored_evidence(db, doc):
    """The evidence JSON for exactly this revision and these source snapshots, or None."""
    revision = getattr(doc, 'revision', None)
    if db is None or not revision:
        return None
    asset = db.scalar(select(Asset).where(Asset.subject == doc.subject, Asset.run_id == doc.run_id,
                                          Asset.kind == EVIDENCE_KIND, Asset.filename == f'{revision}.json'))
    if asset is None:
        return None
    key = (asset.object_key, asset.size_bytes, str(asset.uploaded_at))
    if key not in _EVIDENCE:
        try:
            body = ObjectStorage().get_bytes(asset.object_key)
            data = json.loads(body) if body else None
        except Exception:  # noqa: BLE001 — missing/unreadable evidence falls back to cited pages
            data = None
        while len(_EVIDENCE) >= _EVIDENCE_LIMIT:
            _EVIDENCE.pop(next(iter(_EVIDENCE)))
        _EVIDENCE[key] = data
    data = _EVIDENCE[key]
    known = {s['source_id']: s['sha256'] for s in doc.document['review']['sources']}
    if not isinstance(data, dict) or data.get('schema') != EVIDENCE_SCHEMA or data.get('revision') != revision \
            or not data.get('sources') or any(known.get(sid) != sha for sid, sha in data['sources'].items()):
        return None
    return data


def _label(ref):
    labels = ref.get('references') or ([f"{ref['year']} {ref['number']}번"] if ref.get('year') and ref.get('number') else [])
    return [label for label in labels if label]


def attach_evidence(db, doc, question, generation, answer):
    if doc.document['bank_source'] == 'quizbank':
        row = db.get(QuizBank, (doc.subject, doc.run_id))
        if row and row.build_id == doc.document['bank_build_id'] and bank_hash(row) == doc.document['review']['bank_sha256']:
            from app.routes.bank_api.presentation import _slides, _jokbo_slides
            answer['slides'] = _slides(db, row, question['question_id'])
            answer['jokboSlides'] = _jokbo_slides(db, row, question)
    if generation is None:
        return
    from app.root_learning.reviewed_import import source_records
    sources = source_records(generation)
    storage = ObjectStorage()
    known = {s['source_id']: s for s in doc.document['review']['sources']}
    signed = {}
    answer['sourceLinks'] = []
    for source in sources:
        expected = known.get(source['id'])
        if not expected or expected['sha256'] != source['sha256']:
            continue
        pdf = is_pdf(source)
        url = storage.presign_download(source['snapshotKey'], filename=source['filename'],
            inline=pdf, content_type='application/pdf' if pdf else None)
        answer['sourceLinks'].append({'label': source['filename'], 'url': url})
        if pdf:
            signed[source['id']] = (source, url)
    exams = {sid for sid, s in known.items() if s.get('kind') == 'exam'}
    # 족보 지면은 족보 원본 또는 강의록에 첨부된 기출(`embedded`)일 수 있다 — 지문으로 원본을 찾는다.
    by_sha = {pair[0]['sha256']: sid for sid, pair in signed.items()}

    slides, exam_slides = {}, {}

    def add(source_id, page, exam=None):
        pair = signed.get(source_id)
        if pair is None:
            return None
        source, url = pair
        count = source.get('pageCount') or source.get('page_count') or known[source['id']].get('page_count')
        if type(page) is not int or page < 1 or (type(count) is int and page > count):
            return None
        exam = source_id in exams if exam is None else exam
        target = exam_slides if exam else slides
        return target.setdefault((source_id, page), {'sourceId': source_id, 'sourceSha256': source['sha256'],
            'sourceFilename': source['filename'], 'page': page, 'url': url, 'proxyPath': proxy_path(doc, source),
            'primary': False, **({'references': []} if exam else {})})

    references = list(question.get('source_refs', [])) + [
        {'source_id': s['source_id'], 'pages': [s['page']]} for s in question.get('stimuli', [])]
    for ref in references:
        for page in ref.get('pages') or pages_of(ref.get('locator', '')):
            add(ref['source_id'], page)

    evidence = stored_evidence(db, doc)
    if evidence is not None:
        qid = question.get('question_id')
        original = next((q for q in doc.document['bank_snapshot']['questions'] if q['question_id'] == qid), None)
        if original is not None:
            _attach_reviewed(evidence, original, question, add, slides, exam_slides, by_sha, answer)
    key = lambda s: (not s['primary'], s['page'])  # noqa: E731 — 핵심 먼저, 나머지는 쪽 순서
    answer['pdfSlides'] = sorted(slides.values(), key=key) if evidence is not None else list(slides.values())
    answer['jokboPdfSlides'] = sorted(exam_slides.values(), key=key)


def _attach_reviewed(evidence, original, question, add, slides, exam_slides, by_sha, answer):
    """Quiz Bank와 같은 계약 함수로 핵심·족보·근거 상태를 붙인다. 문항 hash가 다르면 아무것도 붙이지 않는다."""
    focus, resolution = evidence.get('slideFocus') or {}, evidence.get('evidenceResolution')
    notes = evidence.get('notesSource')
    answer['slideFocusKnown'] = True
    record = (focus.get('questions') or {}).get(original['question_id']) or {}
    if record.get('questionHash') == question_hash(original):
        for page in sorted(all_selected_pages(focus, original['question_id'])):
            add(notes, page)
    available = {('self', page) for sid, page in slides if sid == notes}
    for _, page in selected_references(focus, original, available, question):
        slides[(notes, page)]['primary'] = True
    core = exam_primary_references(resolution, original, question)
    for ref in jokbo_references(evidence.get('jokboPages'), original, question) + core:
        sid = by_sha.get(ref.get('sourceSha256'))
        slide = add(sid, ref.get('page'), exam=True) if sid else None
        if slide is not None:
            slide['references'] += [label for label in _label(ref) if label not in slide['references']]
    core_keys = {(by_sha.get(ref.get('sourceSha256')), ref['page']) for ref in core}
    # 족보 핵심은 모든 핵심 지면이 실제로 있을 때만 표시한다(Quiz Bank `_jokbo_slides`와 같다).
    if core_keys and core_keys <= set(exam_slides):
        for k in core_keys:
            exam_slides[k]['primary'] = True
    status = evidence_status(resolution, original, question, focus=focus)
    if status:
        if status['category'] == 'exam_only':
            status['primaryAvailable'] = any(s['primary'] for s in exam_slides.values())
        answer['evidenceStatus'] = status
