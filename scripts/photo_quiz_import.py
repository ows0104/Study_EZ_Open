"""Assemble a hand-authored photo Main-Quiz into a `roots/1` document (docs/changes/2026-11-15-photo-quiz-import).

Input is a local spec JSON kept OUTSIDE the repository (it holds lecture and jokbo text):

    {"subject", "run_id", "title", "revision",
     "sources": [{"source_id", "label", "path", "kind", "professor", "year"}],
     "scope": {"label", "included": [...], "excluded": [...], "limitations": [...]},
     "authorization": "사용자 원문 승인 문장",
     "questions": [{"id", "topic", "tier", "question", "clue", "answer", "explanation", "exam",
                    "choices": [...] | null, "correct": "A".."E" | null, "learning_page",
                    "order": [..] (optional task sort key; default [learning_page]),
                    "images": [{"file", "source_id", "page", "crop": [x0,y0,x1,y1]}]}]}

`learning_page` is the page in the question's own source; when one quiz holds several lectures (practical, then
병리 2, then the practical), `order` puts the lectures in sequence, e.g. [lecture_index, learning_page].

Image files are the original pictures at those page positions (embedded photos, stamp captures without the
note-taker's circles, jokbo figures), already encoded as JPEG or PNG. The document has no generation_policy:
it is not a pipeline result and carries no review ledger. `review.provenance.method` is `photo-import/1`, which
is the only thing that unlocks JPEG and the photo image limits (studyez_contracts.roots.media.photo_import).

    python scripts/photo_quiz_import.py SPEC.json OUT.json
"""
import base64
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studyez_contracts.learning_links.validate import question_hash  # noqa: E402
from studyez_contracts.roots import document_hash  # noqa: E402
from studyez_contracts.roots.media import PHOTO_METHOD, JPEG, jpeg_size  # noqa: E402
from studyez_contracts.roots.validate import validate_document  # noqa: E402

IMPORTANCE = {'Essential': 5, 'Core': 4, 'Important': 3, 'Optional': 2}
RANK = ['Optional', 'Important', 'Core', 'Essential']
LETTERS = 'ABCDEFGHIJ'


def page_count(path):
    import fitz
    with fitz.open(path) as pdf:
        return pdf.page_count


def image_size(body):
    if body[:3] == JPEG:
        return jpeg_size(body)
    if body[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', body[16:24])
    raise ValueError('JPEG 또는 PNG가 아닌 그림')


def ref(source_id, pages, locator=None):
    pages = sorted(set(pages))
    return {'source_id': source_id, 'pages': pages,
            'locator': locator or ('원본 physical PDF page ' + ','.join(map(str, pages)))}


def build(spec, base):
    sources = []
    for s in spec['sources']:
        path = (base / s['path']).resolve()
        sources.append({'source_id': s['source_id'], 'label': s['label'],
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'kind': s['kind'],
                        'professor': s.get('professor'), 'year': s.get('year'), 'page_count': page_count(path)})
    by_source = {s['source_id']: s for s in sources}

    topics = []
    for q in spec['questions']:
        if q['topic'] not in topics:
            topics.append(q['topic'])
    concept_of = {t: f'C{i:03d}' for i, t in enumerate(topics, 1)}

    questions, review_targets, relations, mappings = [], [], [], []
    pages_of = {}
    for n, q in enumerate(spec['questions'], 1):
        qid, tid, did, rid = f'Q{n:03d}', f'T{n:03d}', f'D{n:03d}', f'R{n:03d}'
        stimuli, pages = [], {}
        for img in q['images']:
            body = (base / img['file']).read_bytes()
            w, h = image_size(body)
            src = by_source[img['source_id']]
            stimuli.append({'source_id': img['source_id'], 'source_sha256': src['sha256'], 'page': img['page'],
                            'crop': img['crop'], 'sha256': hashlib.sha256(body).hexdigest(), 'width': w, 'height': h,
                            'png_base64': base64.b64encode(body).decode('ascii')})
            pages.setdefault(img['source_id'], []).append(img['page'])
        pages_of[qid] = pages
        refs = [ref(sid, ps) for sid, ps in pages.items()]
        choices = q.get('choices') or []
        item = {'question_id': qid, 'concept_id': concept_of[q['topic']], 'tier': q['tier'],
                'importance': IMPORTANCE[q['tier']], 'advanced': False, 'item_difficulty': 2,
                'format': 'mcq' if choices else 'basic', 'retrieval_direction': 'direct',
                'mcq_mode': 'recall_first' if choices else 'none',
                'question': q['question'], 'answer': q['correct'] if choices else q['answer'],
                'answer_units': [q['correct']] if choices else [q['answer']], 'prerequisites': [],
                'explanation': (('정답: ' + q['answer'] + '\n') if choices else '') + q['explanation'],
                'source_refs': [{'source_id': r['source_id'], 'locator': 'physical PDF page ' + ','.join(map(str, r['pages']))}
                                for r in refs],
                'exam_rationale': q.get('exam') or '', 'conflict_id': '',
                'options': [{'id': LETTERS[i], 'text': c} for i, c in enumerate(choices)],
                'correct_option_ids': [q['correct']] if choices else [],
                'matching_left': [], 'matching_right': [], 'answer_pairs': [], 'sequence_items': [], 'correct_order': [],
                'option_explanations': [{'option_id': q['correct'], 'text': q['answer']}] if choices else [],
                'option_pools': [], 'learning_page': q['learning_page'], 'point_ids': ['P001'], 'stimuli': stimuli}
        if q.get('clue'):
            item['clue'] = q['clue']
        questions.append(item)
        relations.append({'relation_id': rid, 'from_id': concept_of[q['topic']], 'to_id': concept_of[q['topic']],
                          'kind': 'association', 'condition': q['answer'][:300], 'evidence': refs,
                          'review_status': 'reviewed', 'reason': '수작업 반입: 문항 하나가 사진 판독 관계 하나를 묻는다.'})
        unreviewed = {'status': 'unreviewed', 'reason': '수작업 반입 — 중요도는 문항 tier로만 표시한다.', 'evidence': []}
        review_targets.append({'target_id': tid, 'title': q['topic'] + ' · ' + q['question'][:80],
                               'concept_ids': [concept_of[q['topic']]], 'relation_ids': [rid], 'role': 'leaf',
                               'reason': '수작업 반입: 사진 판독 문항 하나가 목표 하나다.', 'evidence': refs,
                               'directions': [{'direction_id': did, 'cue': q['question'], 'answer_scope': q['answer'][:500],
                                               'requirement': 'required', 'relation_ids': [rid],
                                               'components': [{'component_id': f'K{n:03d}_1', 'text': q['answer'][:500]}],
                                               'requires_visual': True}],
                               'importance': {'exam': dict(unreviewed), 'clinical': dict(unreviewed), 'structural': dict(unreviewed)}})

    concepts = []
    for t in topics:
        mine = [q for q in spec['questions'] if q['topic'] == t]
        tier = max((q['tier'] for q in mine), key=RANK.index)
        concepts.append({'concept_id': concept_of[t], 'title': t, 'graph_title': t, 'core_facts': [],
                         'source_refs': [], 'importance': IMPORTANCE[tier],
                         'importance_rationale': '수작업 반입: 문항 tier 중 가장 높은 것.', 'concept_difficulty': 2,
                         'tier': tier, 'exam_signal_strength': 'high' if any(q.get('exam') for q in mine) else 'medium',
                         'related_concepts': []})
    bank = {'build_meta': {'schema_version': '3.3', 'lecture_title': spec['title']},
            'source_summary': [{'source_id': s['source_id'], 'summary': s['label']} for s in sources],
            'source_conflicts': [], 'concepts': concepts,
            'retrieval_plan': [{'concept_id': c['concept_id'], 'directions': ['direct'], 'repetition_budget': 1,
                                'target_mastery': 0.85} for c in concepts],
            'questions': questions,
            'audit_summary': {'summary': '수작업 작성 문항 반입(photo-import/1). 파이프라인 원본·의학 검수 없음.',
                              'rejected_candidate_count': 0, 'changes': []},
            'warnings': ['수작업 작성 문항이다. 파이프라인의 원본 대조·의학 검수를 거치지 않았다.']}

    for q, m in zip(questions, range(len(questions))):
        n = m + 1
        mappings.append({'question_id': q['question_id'], 'question_sha256': question_hash(q, bank),
                         'target_id': f'T{n:03d}', 'direction_id': f'D{n:03d}', 'tested_relation_ids': [f'R{n:03d}'],
                         'provided_relation_ids': [], 'explanation_relation_ids': [],
                         'reason': '수작업 반입: 문항이 이 방향 전체를 묻는다.'})
    all_refs = {}
    for pages in pages_of.values():
        for sid, ps in pages.items():
            all_refs.setdefault(sid, set()).update(ps)
    point_evidence = [ref(sid, ps) for sid, ps in all_refs.items()]
    direction_ids = [t['directions'][0]['direction_id'] for t in review_targets]
    review = {
        'schema_version': 'learning-links/2', 'hash_policy': 'learning-links-question/1',
        'bank_sha256': document_hash(bank), 'lecture_id': f"{spec['subject']}/{spec['run_id']}",
        'scope': {'label': spec['scope']['label'], 'included': spec['scope']['included'],
                  'excluded': spec['scope'].get('excluded', []),
                  'reviewed': ['관리자(사용자)가 문항을 훑어보고 발문 단서를 힌트로 옮기도록 지시한 뒤 반입을 승인했다.'],
                  'limitations': spec['scope'].get('limitations', []) +
                                 ['파이프라인의 원본 대조·의학 검수·중요도 근거 계산을 거치지 않은 수작업 문항이다.'],
                  'outside_list_review': '목록 밖 점검 없음(수작업 반입).'},
        'sources': sources,
        'concepts': [{'concept_id': concept_of[t], 'label': t, 'parent_ids': []} for t in topics],
        'relations': relations, 'targets': review_targets,
        'points': [{'point_id': 'P001', 'text': spec['title'] + ' — 강의 사진 판독 전체', 'evidence': point_evidence,
                    'target_ids': [t['target_id'] for t in review_targets], 'scope_status': 'included',
                    'reason': '수작업 반입: 하나의 포인트가 모든 사진 판독 목표를 묶는다.'}],
        'provenance': {'status': 'reviewed', 'method': PHOTO_METHOD,
                       'reviewer': '수작업 작성(Claude 세션), 관리자 지시로 반입; 독립 원본·의학 검수자 아님',
                       'independent_points': 'unverified',
                       'notes': json.dumps({'authorization': spec['authorization'],
                                            'change': 'docs/changes/2026-11-15-photo-quiz-import'}, ensure_ascii=False)},
        'mappings': mappings,
        'coverage': [{'point_id': 'P001', 'status': 'covered', 'confirmed_direction_ids': direction_ids,
                      'partial_direction_ids': [], 'missing_direction_ids': [], 'unknown_direction_ids': [],
                      'reason': '수작업 반입: 문항마다 자기 방향 전체를 묻는다.', 'exclusion_basis': None}],
    }
    keys = [q.get('order') or [q['learning_page']] for q in spec['questions']]
    order = sorted(range(len(questions)), key=lambda i: (keys[i], i))
    doc = {'schema_version': 'roots/1', 'revision': spec['revision'], 'title': spec['title'], 'review': review,
           'bank_snapshot': bank, 'bank_source': 'standalone', 'bank_build_id': None,
           'adopted_target_ids': [t['target_id'] for t in review_targets],
           'tasks': [{'task_id': f'K{i + 1:03d}', 'question_id': questions[i]['question_id'],
                      'direction_id': f'D{i + 1:03d}'} for i in order],
           'exam_date': spec.get('exam_date'), 'equivalences': [], 'prerequisites': []}
    validate_document(doc)
    return doc


def main(argv):
    spec_path, out_path = Path(argv[1]), Path(argv[2])
    doc = build(json.loads(spec_path.read_text(encoding='utf-8')), spec_path.parent)
    text = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
    out_path.write_text(text, encoding='utf-8')
    images = sum(len(q.get('stimuli', [])) for q in doc['bank_snapshot']['questions'])
    print(f"{len(doc['tasks'])} tasks, {images} images, {len(text.encode()) / 1e6:.1f} MB -> {out_path}")


if __name__ == '__main__':
    main(sys.argv)
