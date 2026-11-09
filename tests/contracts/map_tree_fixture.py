"""Synthetic map-tree/1 front-stage answers and generation model (runner and server tests). Nonmedical; no models."""
import hashlib
import json
from pathlib import Path

TITLE = 'Synthetic lecture'
BASIS = [{'kind': 'current_exam', 'year': 2023, 'quote': '', 'reason': 'synthetic exam', 'refs': [{'source_id': 'S1', 'pages': [1]}]},
         {'kind': 'slide_emphasis', 'year': None, 'quote': '', 'reason': 'synthetic box', 'refs': [{'source_id': 'S1', 'pages': [1]}]}]


def pdf_bytes(name, pages):
    import pymupdf
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f'Synthetic {name} page {i + 1}')
    body = doc.tobytes(); doc.close()
    return body


def pdf(path, pages):
    Path(path).write_bytes(pdf_bytes(Path(path).stem, pages))
    return Path(path)


def concept_map(title=TITLE):
    return {'schema_version': 'concept-map-extract/3', 'title': title, 'overview': 'Synthetic overview', 'relations': [], 'notes': [],
            'concepts': [{'concept_id': cid, 'parent_id': parent, 'title': 'T' + cid, 'core_facts': ['Synthetic fact'],
                          'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}]}
                         for cid, parent in (('C001', None), ('C002', 'C001'), ('C003', 'C002'), ('C004', 'C001'))]}


def points(title=TITLE, extra=False):
    rows = [{'point_id': 'P001', 'point': 'Synthetic A/B point', 'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}],
             'importance_basis': BASIS}]
    if extra:
        rows.append({'point_id': 'P002', 'point': 'Synthetic page-two point', 'source_refs': [{'source_id': 'S1', 'pages': [2], 'locator': None}],
                     'importance_basis': BASIS})
    return {'schema_version': 'exam-point-extract/3', 'title': title, 'notes': [],
            'notebook_profile': {'legend': '', 'emphasis_style': 'slide', 'reason': 'synthetic'}, 'points': rows}


def audit(n_points, pages, title=TITLE, issues=False):
    found = [{'issue_id': 'I1', 'kind': 'missing', 'point_ids': ['P001'], 'source_refs': [{'source_id': 'S1', 'pages': [2], 'locator': None}],
              'reason': 'Page 2 states a separate goal', 'suggested_goal': 'Synthetic page-two point'}] if issues else []
    return {'title': title, 'point_count': n_points, 'verdict': 'needs_revision' if issues else 'ready',
            'page_review': [{'source_id': sid, 'pages': list(range(1, n + 1)), 'status': 'covered' if sid == 'S1' else 'out_of_scope',
                             'reason': 'read'} for sid, n in pages.items()],
            'issues': found, 'suggestions': [], 'summary': 'Synthetic audit'}


def fake_codex(calls, *, title=TITLE, issues=False, fail=(), tamper=None):
    """A Codex CLI call that writes the stage's file in its work folder and returns the receipt."""
    fail = list(fail)

    def run(task, *, cwd, label, **kwargs):
        stage = Path(cwd).name; calls.append((stage, task))
        if stage in fail:
            fail.remove(stage); raise RuntimeError('synthetic interrupted call in ' + stage)
        if stage == 'map': name, value = 'concept-map.json', concept_map(title)
        elif stage == 'point': name, value = 'exam-points.json', points(title)
        elif stage == 'point-repair': name, value = 'exam-points.json', points(title, extra=True)
        else:
            name = 'audit.json'
            count = len(json.loads((Path(cwd) / 'exam-points.json').read_text(encoding='utf-8'))['points'])
            pages = {s['source_id']: s['page_count'] for s in json.loads((Path(cwd) / 'input.json').read_text(encoding='utf-8'))['sources']}
            value = audit(count, pages, title, issues=issues and stage == 'audit')
        path = Path(cwd) / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        if tamper == stage: (Path(cwd) / 'input.json').write_text('{}', encoding='utf-8')
        return {'text': json.dumps({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}),
                'session_id': 'session-' + stage, 'duration_ms': 3, 'usage': {'input_tokens': 1}}
    return run


def generation_model(stage, ctx, *args):
    """generation_v2_fixture.model for a derived map-tree packet: context stages, lecture id, point IDs."""
    import generation_v2_fixture as f2
    if stage.startswith('context-'):
        return {'clinical_context_status': 'consistent', 'clinical_context_reason': 'synthetic', 'clinical_context_problem': 'none'}, {}
    value, info = f2.model(stage, ctx, *args)
    if stage == 'normalize': value['lecture_id'] = ctx['lecture_id']
    if stage == 'generate' or stage.startswith('repair-'):
        for q in value['bank']['questions']: q['point_ids'] = ['P001']
    return value, info
