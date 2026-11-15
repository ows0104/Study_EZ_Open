"""notes-update/1: a replacement run that takes a corrected notes file of the same page layout
(docs/changes/2026-11-16-replace-updated-notes).

A published revision is bound to the notes it was written from: the document's `review.sources` names their sha256 and
the answer's evidence pages are rendered from that copy. When the notes' author uploads a corrected file with the same
pages (261112_03: v1 → v4, a jokbo answer on p.17, the order of two lines on p.29, the HEV classification on p.7),
a reuse path (unplaced-only/1) may take it: the questions, reviews and the medical review stay the previous run's,
the new revision names the new file, and the pages that differ — with the questions and source conflicts citing
them — are recorded for a person to read. Nothing here decides whether a correction reaches an answer.
"""
import hashlib
from pathlib import Path

import fitz

from studyez_contracts.roots import generation_v3 as v3

POLICY = 'notes-update/1'   # studyez_contracts.roots.generation_v4.NOTES_UPDATE
# Fields of a packet source that name the uploaded file; everything else (id, kind, order) must stay.
FILE_KEYS = {'assetId', 'filename', 'sizeBytes', 'sha256', 'originalKey', 'uploadedAt'}
RENDER_DPI = 40


def changed_sources(old_input, new_input, label):
    """Indexes of the packet sources whose file changed, when nothing but source files differs. `*_input` are
    `connection_dedupe.lecture_input` values; any other difference stops the run as before."""
    if old_input == new_input:
        return []
    old, new = dict(old_input), dict(new_input)
    old_sources, new_sources = old.pop('sources'), new.pop('sources')
    v3.require(old == new, f'{label}: 이전 실행과 강의 입력이 다릅니다.')
    same_layout = len(old_sources) == len(new_sources) and all(
        {k: v for k, v in a.items() if k not in FILE_KEYS} == {k: v for k, v in b.items() if k not in FILE_KEYS}
        for a, b in zip(old_sources, new_sources))
    v3.require(same_layout, f'{label}: 원본 구성(개수·종류·순서)이 이전 실행과 다릅니다 — 처음부터 출제하세요.')
    changed = [i for i, (a, b) in enumerate(zip(old_sources, new_sources)) if a != b]
    for i in changed:
        v3.require(new_sources[i]['kind'] != 'jokbo', f"{label}: 족보 원본({new_sources[i]['filename']})이 바뀌었습니다 — "
                   '족보 교체는 재배치로 잇지 않습니다. 처음부터 출제하세요.')
    return changed


def _file(source, label):
    path = Path(source['localPath'])
    v3.require(path.is_file(), f"{label}: 원본 사본이 없습니다: {path}")
    body = path.read_bytes()
    v3.require(len(body) == source['sizeBytes'] and hashlib.sha256(body).hexdigest() == source['sha256'],
               f"{label}: 원본 사본의 지문이 다릅니다: {path}")
    return path


def changed_pages(old_path, new_path, label):
    """Physical pages whose text or rendering differs. The page count must be the same."""
    with fitz.open(old_path) as a, fitz.open(new_path) as b:
        v3.require(len(a) == len(b), f'{label}: 필기 쪽 수가 바뀌었습니다({len(a)}쪽 → {len(b)}쪽) — 재배치로 이을 수 없습니다. '
                   '처음부터 출제하세요.')
        return [i for i, (pa, pb) in enumerate(zip(a, b), 1)
                if pa.get_text() != pb.get_text()
                or pa.get_pixmap(dpi=RENDER_DPI).samples != pb.get_pixmap(dpi=RENDER_DPI).samples]


def compare(old_packet, packet, indexes, label):
    """The update record: per changed source its old and new file and the pages that differ."""
    rows = []
    for i in indexes:
        old, new = old_packet['sources'][i], packet['sources'][i]
        pages = changed_pages(_file(old, label), _file(new, label), label)
        rows.append({'source_id': new['id'], 'fromFilename': old['filename'], 'fromSha256': old['sha256'],
                     'toFilename': new['filename'], 'toSha256': new['sha256'], 'changedPages': pages})
    return {'policy': POLICY, 'sources': rows}


def on_changed_pages(update, bank, item_reviews):
    """Questions (their citations, learning page and reviewed evidence) and source conflicts on a changed page."""
    hit = {(r['source_id'], p) for r in update['sources'] for p in r['changedPages']}
    notes = {r['source_id'] for r in update['sources']}
    evidence = {r['question_id']: {(sid, s['page']) for s in (r.get('evidence') or {}).get('slides', []) for sid in notes}
                for r in item_reviews}
    questions = []
    for q in bank['questions']:
        pages = set(v3.cited_pages(q.get('source_refs'))) | evidence.get(q['question_id'], set())
        pages |= {(s['source_id'], s['page']) for s in q.get('stimuli', [])}   # its figure stays the earlier crop
        if q.get('learning_page'):
            pages |= {(sid, q['learning_page']) for sid in notes}
        found = sorted(p for sid, p in pages & hit)
        if found:
            questions.append({'question_id': q['question_id'], 'pages': found})
    conflicts = [{'conflict_id': c['conflict_id'], 'pages': sorted(p for sid, p in set(v3.cited_pages(c.get('source_refs'))) & hit)}
                 for c in bank.get('source_conflicts', [])]
    return questions, [c for c in conflicts if c['pages']]
