"""root-generation/3 contracts: add-only coverage, one job per judgment, minimal stage inputs.

docs/changes/2026-11-10-root-generation-3 (spec.md, plan.md). Pure functions only: no model, DB or server.

- Stage outputs carry only what that stage may change (P1): an add stage has no room for existing
  questions or the Map, a fix stage only for the questions it was asked to fix.
- Verdicts are recorded per question content and reused while the content is unchanged (P2).
- Each stage input is built here from named fields only (P3); pages are the ones the items cite.
- The final document reuses /2 `compile_assessment` and `make_document` through `assessment_raw`,
  which only gathers judgments the /3 stages actually made (no field is filled in).
"""
import copy
import re

from studyez_contracts.learning_links.schema import obj, arr, enum, TEXT
from studyez_contracts.learning_links.validate import require, validate_shape, index_by
from studyez_contracts.bank import importance as imp
from studyez_contracts.bank.cloze import normalize_cloze
from .validate import document_hash
from . import generation_v2 as v2

POLICY = 'root-generation/3'
SOURCE_LIMIT = 'S1'          # the lecture's own notes bound new points (scope rule of the map-tree packets)
VERDICTS = ('ok', 'doubt', 'wrong')
RANK = {'ok': 0, 'doubt': 1, 'wrong': 2}
FIX_LIMIT = 2                # fixes per question (spec R4)
ADD_LIMIT = 2                # add + scoped coverage passes (spec R3)

# ---------------------------------------------------------------- stage outputs
_STRING = {'type': 'string'}
_NULLABLE = {'type': ['string', 'null']}
QUESTION = copy.deepcopy(v2.AUTHOR_BANK['properties']['questions']['items'])
SOURCE_CONFLICT = copy.deepcopy(v2.AUTHOR_BANK['properties']['source_conflicts']['items'])
BANK_CONCEPT = copy.deepcopy(v2.AUTHOR_BANK['properties']['concepts']['items'])
PLAN = copy.deepcopy(v2.AUTHOR_BANK['properties']['retrieval_plan']['items'])

COVERAGE_EVIDENCE = obj(question_id=TEXT, tested_relation_ids=arr(TEXT), components=arr(v2.PART, 1),
                        visual_verdict=enum('ok', 'doubt', 'wrong', 'not_applicable'), reason=TEXT)
COVERAGE_OUTPUT = obj(rows=arr(obj(direction_id=TEXT, status=enum('covered', 'missing', 'unknown'),
                                   evidence=arr(COVERAGE_EVIDENCE), reason=TEXT), 1))

MAP_CHECK_OUTPUT = obj(
    relation_checks=arr(v2.REL_CHECK),
    target_checks=arr(v2.TARGET_CHECK),
    direction_checks=arr(obj(direction_id=TEXT, scope_status=enum('consistent', 'conflict', 'unknown'), reason=TEXT)),
    issues=arr(obj(text=TEXT, direction_ids=arr(TEXT))))

PREREQUISITE_CHECK = obj(prerequisite_id=TEXT, status=enum('supported', 'unnecessary', 'unknown'), reason=TEXT)
ITEM_REVIEW_OUTPUT = obj(reviews=arr(obj(
    question_id=TEXT, verdict=enum(*VERDICTS), design=enum(*VERDICTS), note=_STRING, suggested_answer=_STRING,
    fix=_STRING, prerequisite_checks=arr(PREREQUISITE_CHECK)), 1))

# The exam-point-extract/3 point item without point_id (content/prompts/learning-links/point-output-v3.schema.json;
# tests/contracts/test_generation_v3.py keeps the two equal). Supplement points take the same form (spec R2a).
_PAGES_ITEM = {'type': 'integer', 'minimum': 1}
POINT = {'type': 'object', 'additionalProperties': False, 'required': ['point', 'source_refs', 'importance_basis'], 'properties': {
    'point': {'type': 'string', 'minLength': 1},
    'source_refs': {'type': 'array', 'minItems': 1, 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['source_id', 'pages', 'locator'],
        'properties': {'source_id': {'type': 'string', 'minLength': 1},
                       'pages': {'type': 'array', 'items': _PAGES_ITEM, 'uniqueItems': True},
                       'locator': {'type': ['string', 'null'], 'minLength': 1}},
        'anyOf': [{'properties': {'pages': {'minItems': 1}}}, {'properties': {'locator': {'type': 'string', 'minLength': 1}}}]}},
    'importance_basis': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['kind', 'refs', 'quote', 'reason', 'year'],
        'properties': {'kind': {'enum': list(imp.KINDS)},
                       'refs': {'type': 'array', 'minItems': 1, 'items': {
                           'type': 'object', 'additionalProperties': False, 'required': ['source_id', 'pages'],
                           'properties': {'source_id': {'type': 'string', 'minLength': 1},
                                          'pages': {'type': 'array', 'items': _PAGES_ITEM, 'minItems': 1, 'uniqueItems': True}}}},
                       'quote': {'type': 'string'}, 'reason': {'type': 'string', 'minLength': 1},
                       'year': {'type': ['integer', 'null']}}}}}}
SUPPLEMENT_OUTPUT = obj(rows=arr(obj(question_id=TEXT, decision=enum('point', 'out_of_scope', 'duplicate_of'),
                                     point={'anyOf': [POINT, {'type': 'null'}]}, duplicate_of=_NULLABLE, reason=TEXT), 1))

# The independent bank of map-tree/2 (1c): the authored bank, its source crops and clinical facts.
INTAKE_OUTPUT = obj(bank=copy.deepcopy(v2.AUTHOR_BANK), visual_stimuli=arr(v2.CROP), clinical_conflicts=arr(v2.CONFLICT))

ADD_OUTPUT = obj(questions=arr(QUESTION, 1), concepts=arr(BANK_CONCEPT), retrieval_plan=arr(PLAN),
                 source_conflicts=arr(SOURCE_CONFLICT), visual_stimuli=arr(v2.CROP), clinical_conflicts=arr(v2.CONFLICT))
FIX_OUTPUT = obj(questions=arr(QUESTION, 1), source_conflicts=arr(SOURCE_CONFLICT),
                 visual_stimuli=arr(v2.CROP), clinical_conflicts=arr(v2.CONFLICT))

SUPPLEMENT_NORMALIZE_OUTPUT = obj(targets=arr(copy.deepcopy(v2.BRIEF['properties']['targets']['items']), 1),
                                  points=arr(copy.deepcopy(v2.BRIEF['properties']['points']['items']), 1))
BRIEF_FIX_OUTPUT = obj(brief=copy.deepcopy(v2.BRIEF), map_change_reason=TEXT)

OUTPUTS = {'coverage': COVERAGE_OUTPUT, 'map-check': MAP_CHECK_OUTPUT, 'item-review': ITEM_REVIEW_OUTPUT,
           'supplement': SUPPLEMENT_OUTPUT, 'add': ADD_OUTPUT, 'fix': FIX_OUTPUT}

# ---------------------------------------------------------------- intake projection
def intake_projection(bank):
    """Fields of an independently authored bank that the assembly recomputes, set to the current bank format.

    An independent bank (1c) is written before the exam points' tiers exist; the assembly sets tier and
    importance from the point basis (generation_v2.project_importance, bank 3.3). The first real run
    (261102_02, 2026-11-10) wrote build_meta.schema_version "BANK" with 3.2 importance numbers, and the
    whole bank was refused before any question was read. Only build_meta.schema_version and the importance
    of each question and concept (the number of its own tier) change; every change is returned and recorded."""
    from studyez_contracts.bank.validate import SCHEMA_VERSIONS
    current = SCHEMA_VERSIONS[-1]
    value = copy.deepcopy(bank)
    changes = []
    if value['build_meta'].get('schema_version') != current:
        changes.append({'field': 'build_meta.schema_version', 'from': value['build_meta'].get('schema_version'), 'to': current})
        value['build_meta']['schema_version'] = current
    for row, key in [*((q, 'question_id') for q in value['questions']), *((c, 'concept_id') for c in value['concepts'])]:
        want = imp.BANK_IMPORTANCE.get(row.get('tier'))
        if want is not None and row.get('importance') != want:
            changes.append({'field': row[key] + '.importance', 'from': row.get('importance'), 'to': want})
            row['importance'] = want
    return value, changes


# ---------------------------------------------------------------- pages and hashes
_PAGES = re.compile(r'(\d+)\s*(?:[–~-]\s*(\d+))?')


def locator_pages(locator):
    """Physical pages named in a bank locator such as 「물리 PDF 12–13쪽」 or 「물리 PDF 3,14쪽」."""
    if not isinstance(locator, str) or 'PDF' not in locator:
        return []
    text = locator.split('PDF', 1)[1]
    pages = []
    for start, end in _PAGES.findall(text):
        first = int(start)
        last = int(end) if end else first
        if 0 < first <= last <= first + 40:
            pages.extend(range(first, last + 1))
    return sorted(set(pages))


def cited_pages(refs):
    """[(source_id, page)] from brief/point refs (`pages`) or bank refs (`locator`), deduplicated and sorted."""
    found = set()
    for r in refs or []:
        pages = r.get('pages') or locator_pages(r.get('locator'))
        for p in pages:
            found.add((r['source_id'], int(p)))
    return sorted(found)


def item_hash(question, bank, clinical_conflicts):
    """Content identity of one question for the verdict ledger: the question, the source conflict and the
    clinical facts it refers to. Unlike learning_links.question_hash it ignores the rest of the bank, so
    adding questions does not void earlier verdicts (P2)."""
    cid = question.get('conflict_id')
    source = next((c for c in bank.get('source_conflicts', []) if c.get('conflict_id') == cid), None) if cid else None
    clinical = next((c for c in clinical_conflicts if c.get('conflict_id') == cid), None) if cid else None
    plain = {k: v for k, v in question.items() if k != 'stimuli'}
    stimuli = [s.get('sha256') for s in question.get('stimuli', [])]
    return document_hash({'policy': POLICY, 'question': plain, 'stimuli': stimuli, 'source': source, 'clinical': clinical})


# ---------------------------------------------------------------- inputs (P3)
_FRONT = ('question_id', 'format', 'question', 'answer', 'answer_units', 'correct_option_ids', 'matching_left',
          'matching_right', 'answer_pairs', 'sequence_items', 'correct_order')


def _directions(brief):
    return {d['direction_id']: (t, d) for t in brief['targets'] for d in t['directions']}


def _relation_text(brief, rid):
    concepts = {c['concept_id']: c['label'] for c in brief['concepts']}
    r = next(r for r in brief['relations'] if r['relation_id'] == rid)
    return {'relation_id': rid, 'kind': r['kind'], 'from': concepts.get(r['from_id'], r['from_id']),
            'to': concepts.get(r['to_id'], r['to_id']), 'condition': r.get('condition')}


def _goal(brief, did):
    target, d = _directions(brief)[did]
    return {'direction_id': did, 'target_id': target['target_id'], 'cue': d['cue'], 'answer_scope': d['answer_scope'],
            'components': copy.deepcopy(d['components']), 'requires_visual': d['requires_visual'],
            'relations': [_relation_text(brief, rid) for rid in d['relation_ids']]}


def _front(q):
    """What a learner sees plus the scored answer: cloze answers are masked in the stem (as /2 questionFronts)."""
    shown = normalize_cloze(q)
    row = {k: copy.deepcopy(shown[k]) for k in _FRONT if k in shown}
    row['options'] = [{k: o[k] for k in ('id', 'text') if k in o} for o in q.get('options', [])]
    row['stimuli'] = [s['sha256'] for s in q.get('stimuli', [])]
    return row


def coverage_input(brief, bank, direction_ids=None, question_ids=None):
    """C2: goals and question fronts only — no explanations, source pages, importance or earlier verdicts."""
    dirs = _directions(brief)
    wanted = list(dirs) if direction_ids is None else list(direction_ids)
    require(set(wanted) <= set(dirs), 'v3 coverage: unknown goal')
    questions = [q for q in bank['questions'] if question_ids is None or q['question_id'] in set(question_ids)]
    require(question_ids is None or len(questions) == len(set(question_ids)), 'v3 coverage: unknown question')
    return {'goals': [_goal(brief, did) for did in wanted], 'questions': [_front(q) for q in questions]}


def coverage_images(bank, value):
    """Stimulus images of the questions in a coverage input (nothing else is attached)."""
    wanted = {q['question_id'] for q in value['questions']}
    return [s['sha256'] for q in bank['questions'] if q['question_id'] in wanted for s in q.get('stimuli', [])]


def map_check_input(brief, table, target_ids=None):
    """C2m: goals, relations and the importance basis of their points, with cited pages. No questions.

    The whole check (target_ids None) takes every relation of the map: the assembly (v2.compile_assessment) needs a
    judgment for each, and a relation need not belong to a target (261102_02: 21 of 102 did not; found by the local
    run to the end, 2026-11-10). A supplement check (target_ids given) takes only the new targets' relations."""
    targets = [t for t in brief['targets'] if target_ids is None or t['target_id'] in set(target_ids)]
    rids = sorted({r for t in targets for r in t['relation_ids']} | {r for t in targets for d in t['directions'] for r in d['relation_ids']})
    if target_ids is None:
        rids = sorted({r['relation_id'] for r in brief['relations']})
    relations = {r['relation_id']: r for r in brief['relations']}
    basis = {}
    for p in brief['points']:
        for tid in p['target_ids']:
            if table is not None and p['point_id'] in table['points']:
                basis.setdefault(tid, []).append({'point_id': p['point_id'], 'basis': copy.deepcopy(table['points'][p['point_id']]['basis'])})
    rows = [{'target_id': t['target_id'], 'title': t['title'], 'evidence': copy.deepcopy(t['evidence']),
             'goals': [{k: copy.deepcopy(d[k]) for k in ('direction_id', 'cue', 'answer_scope', 'components')} for d in t['directions']],
             'importance_basis': basis.get(t['target_id'], [])} for t in targets]
    rels = [{**_relation_text(brief, rid), 'evidence': copy.deepcopy(relations[rid].get('evidence', []))} for rid in rids]
    refs = [e for t in targets for e in t['evidence']] + [e for rid in rids for e in relations[rid].get('evidence', [])]
    refs += [r for row in rows for b in row['importance_basis'] for x in b['basis'] for r in x['refs']]
    return {'targets': rows, 'relations': rels, 'pages': cited_pages(refs)}


def supplement_input(bank, question_ids, points_doc, page_counts):
    """C2a: off-goal question fronts and sources, existing point texts, the notebook profile, cited pages."""
    questions = [q for q in bank['questions'] if q['question_id'] in set(question_ids)]
    require(len(questions) == len(set(question_ids)), 'v3 supplement: unknown question')
    return {'questions': [{**_front(q), 'source_refs': copy.deepcopy(q.get('source_refs', []))} for q in questions],
            'points': [{'point_id': p['point_id'], 'point': p['point']} for p in points_doc['points']],
            'notebook_profile': copy.deepcopy(points_doc['notebook_profile']), 'page_counts': dict(page_counts),
            'pages': cited_pages([r for q in questions for r in q.get('source_refs', [])])}


def supplement_normalize_input(brief, new_points, allowed):
    """C2a': the new points only, the existing concepts/relations to reference, the IDs the new goals may take."""
    return {'points': copy.deepcopy(new_points),
            'concepts': [{'concept_id': c['concept_id'], 'label': c['label'], 'parent_ids': list(c['parent_ids'])} for c in brief['concepts']],
            'relations': [_relation_text(brief, r['relation_id']) for r in brief['relations']],
            'allowed': copy.deepcopy(allowed),
            'pages': cited_pages([r for p in new_points for r in p['source_refs']])}


def supplement_ids(brief, count):
    """New target/direction IDs for supplement goals: TQ001.../DQ001... after any earlier ones."""
    used = [int(m.group(1)) for t in brief['targets'] for m in [re.fullmatch(r'TQ(\d+)', t['target_id'])] if m]
    start = max(used, default=0) + 1
    return {'target_ids': [f'TQ{n:03d}' for n in range(start, start + count)],
            'direction_ids': [f'DQ{n:03d}' for n in range(start, start + count)]}


def next_question_ids(bank, count):
    numbers = [int(m.group(1)) for q in bank['questions'] for m in [re.fullmatch(r'Q(\d+)', q['question_id'])] if m]
    start = max(numbers, default=0) + 1
    return [f'Q{n:03d}' for n in range(start, start + count)]


def add_input(brief, bank, gap_direction_ids, allowed_ids):
    """C3: the uncovered goals with their sources, existing fronts for deduplication, the allowed new IDs."""
    dirs = _directions(brief)
    require(gap_direction_ids and set(gap_direction_ids) <= set(dirs), 'v3 add: unknown or empty gap goals')
    goals = []
    for did in gap_direction_ids:
        target, _ = dirs[did]
        goals.append({**_goal(brief, did), 'concept_ids': list(target['concept_ids']), 'evidence': copy.deepcopy(target['evidence']),
                      'point_ids': [p['point_id'] for p in brief['points'] if target['target_id'] in p['target_ids']]})
    return {'goals': goals, 'existing': [{k: q[k] for k in ('question_id', 'question', 'answer')} for q in bank['questions']],
            'bank_concepts': [{'concept_id': c['concept_id'], 'title': c['title']} for c in bank['concepts']],
            'source_conflict_ids': [c['conflict_id'] for c in bank.get('source_conflicts', [])],
            'allowed_question_ids': list(allowed_ids), 'pages': cited_pages([e for g in goals for e in g['evidence']])}


def review_input(bank, question_ids, clinical_conflicts):
    """C4: whole questions of one batch, fronts of their prerequisites, the clinical facts they cite, cited pages."""
    wanted = set(question_ids)
    questions = [q for q in bank['questions'] if q['question_id'] in wanted]
    require(len(questions) == len(wanted), 'v3 review: unknown question')
    plain = [{k: copy.deepcopy(v) for k, v in q.items() if k != 'stimuli'} | {'stimuli': [s['sha256'] for s in q.get('stimuli', [])]}
             for q in questions]
    prerequisites = sorted({p for q in questions for p in q.get('prerequisites', [])} - wanted)
    by_id = {q['question_id']: q for q in bank['questions']}
    cids = {q.get('conflict_id') for q in questions if q.get('conflict_id')}
    return {'questions': plain, 'prerequisites': [_front(by_id[p]) for p in prerequisites if p in by_id],
            'source_conflicts': [c for c in bank.get('source_conflicts', []) if c['conflict_id'] in cids],
            'clinical_conflicts': [c for c in clinical_conflicts if c['conflict_id'] in cids],
            'pages': cited_pages([r for q in questions for r in q.get('source_refs', [])])}


def fix_input(bank, reviews, question_ids, clinical_conflicts, covered):
    """C5: the questions to fix with their findings and the goals each one covers."""
    value = review_input(bank, question_ids, clinical_conflicts)
    findings = {r['question_id']: r for r in reviews}
    value['findings'] = [findings[q] for q in question_ids if q in findings]
    value['covered_goals'] = {q: sorted(covered.get(q, [])) for q in question_ids}
    return value


# ---------------------------------------------------------------- stage-local acceptance (adapter)
def check_added(value, ctx, state=None):
    """An add output against its add_input; with the orchestrator's state (P6) also the merge itself.

    `state` = {'bank': authored bank, 'clinical_conflicts': [...]} is what merge_added receives after the stage.
    Running the same merge here lets the runner send its error back into the model's session (one follow-up)
    instead of stopping the lecture after the stage. Existing items written again are set aside (restated)."""
    validate_shape(value, ADD_OUTPUT, 'v3 add output')
    ids = [q['question_id'] for q in value['questions']]
    require(len(ids) == len(set(ids)) and set(ids) <= set(ctx['allowed_question_ids']), 'v3 add: question IDs outside the allowed range')
    require(not set(ids) & {q['question_id'] for q in ctx['existing']}, 'v3 add: an add stage cannot rewrite an existing question')
    known = {c['concept_id'] for c in ctx['bank_concepts']}
    new = [c['concept_id'] for c in value['concepts'] if c['concept_id'] not in known]
    points = {p for g in ctx['goals'] for p in g['point_ids']}
    for q in value['questions']:
        require(q['concept_id'] in known | set(new), 'v3 add: question concept is unknown')
        require(q.get('point_ids') and set(q['point_ids']) <= points, "v3 add: point_ids must be the gap goals' points")
    require(all(s['question_id'] in ids for s in value['visual_stimuli']), 'v3 add: images only for new questions')
    if state is not None:
        merge_added(state['bank'], state['clinical_conflicts'], value, ctx['allowed_question_ids'])
    return value


def check_fixed(value, ctx, state=None):
    """A fix output against its fix_input; with the orchestrator's state (P6) also merge_fixes itself."""
    validate_shape(value, FIX_OUTPUT, 'v3 fix output')
    given = {q['question_id']: q for q in ctx['questions']}
    ids = [q['question_id'] for q in value['questions']]
    require(len(ids) == len(set(ids)) and set(ids) <= set(given), 'v3 fix: only the listed questions may change')
    for q in value['questions']:
        for key in ('concept_id', 'point_ids'):
            require(q.get(key) == given[q['question_id']].get(key), f'v3 fix: {q["question_id"]} changed {key}')
    require(all(s['question_id'] in ids for s in value['visual_stimuli']), 'v3 fix: images only for fixed questions')
    if state is not None:
        merge_fixes(state['bank'], state['clinical_conflicts'], value, list(given))
    return value


def check_supplement(value, ctx, state=None):
    """With the orchestrator's state (P6: {'points_doc': ...}) also attach_points, which scores each new point."""
    _supplement_rows(value, [q['question_id'] for q in ctx['questions']], {p['point_id'] for p in ctx['points']}, ctx['page_counts'])
    if state is not None:
        attach_points(state['points_doc'], value, [q['question_id'] for q in ctx['questions']], ctx['page_counts'])
    return value


def check_supplement_normalize(value, ctx, state=None):
    validate_shape(value, SUPPLEMENT_NORMALIZE_OUTPUT, 'v3 supplement normalize output')
    require({t['target_id'] for t in value['targets']} <= set(ctx['allowed']['target_ids']), 'v3 extend: target IDs outside the allowed range')
    require({d['direction_id'] for t in value['targets'] for d in t['directions']} <= set(ctx['allowed']['direction_ids']),
            'v3 extend: goal IDs outside the allowed range')
    require({p['point_id'] for p in value['points']} == {p['point_id'] for p in ctx['points']}, 'v3 extend: exactly the supplement points')
    concepts = {c['concept_id'] for c in ctx['concepts']}
    relations = {r['relation_id'] for r in ctx['relations']}
    for t in value['targets']:
        require(set(t['concept_ids']) <= concepts and set(t['relation_ids']) <= relations, 'v3 extend: new targets use the existing map')
    if state is not None:
        extend_brief(state['brief'], supplement_addition(state['brief'], value, state['blank']), [p['point_id'] for p in ctx['points']])
    return value


def check_brief_fix(value, ctx):
    validate_shape(value, BRIEF_FIX_OUTPUT, 'v3 brief fix output')
    v2.validate_initial_correction(ctx['brief'], value['brief'], value['map_change_reason'])
    return value


# ---------------------------------------------------------------- merge guards (P1, P6)
def _bank_conflicts(bank, new_conflicts):
    known = {c['conflict_id'] for c in bank.get('source_conflicts', [])}
    for c in new_conflicts:
        require(c['conflict_id'] not in known, 'v3: a stage may add source conflicts, not rewrite one: ' + c['conflict_id'])
        known.add(c['conflict_id'])
    return [*copy.deepcopy(bank.get('source_conflicts', [])), *copy.deepcopy(new_conflicts)]


def restated(bank, clinical_conflicts, output, cited=()):
    """Existing items an add or fix output wrote again (P6). They are not taken; the existing ones stay (P1).

    Concepts, their retrieval plans, source conflicts, and clinical facts of existing conflicts (except the facts of
    `cited`: conflicts a fixed question cites, which a fix may restate). `changed` records whether the copy differed.
    The first real run (261102_02, 2026-11-10) stopped twice on such copies: an add stage rewrote CF01–CF03's facts and
    a fix copied CF03 back unchanged, both following the copied /2 rule 「모든 conflict_id마다」."""
    rows = []
    concepts = {c['concept_id']: c for c in bank['concepts']}
    plans = {p['concept_id']: p for p in bank.get('retrieval_plan', [])}
    sources = {c['conflict_id']: c for c in bank.get('source_conflicts', [])}
    facts = {c['conflict_id']: c for c in clinical_conflicts}
    for c in output.get('concepts', []):
        if c['concept_id'] in concepts:
            rows.append({'kind': 'concept', 'id': c['concept_id'], 'changed': c != concepts[c['concept_id']]})
    for p in output.get('retrieval_plan', []):
        if p['concept_id'] in concepts:
            rows.append({'kind': 'retrieval_plan', 'id': p['concept_id'], 'changed': p != plans.get(p['concept_id'])})
    for c in output['source_conflicts']:
        if c['conflict_id'] in sources:
            rows.append({'kind': 'source_conflict', 'id': c['conflict_id'], 'changed': c != sources[c['conflict_id']]})
    for c in output['clinical_conflicts']:
        if c['conflict_id'] not in set(cited) and (c['conflict_id'] in facts or c['conflict_id'] in sources):
            rows.append({'kind': 'clinical_fact', 'id': c['conflict_id'], 'changed': c != facts.get(c['conflict_id'])})
    return rows


def _without(output, rows):
    """The output without its restated items."""
    gone = {(r['kind'], r['id']) for r in rows}
    value = copy.deepcopy(output)
    for key, kind, field in (('concepts', 'concept', 'concept_id'), ('retrieval_plan', 'retrieval_plan', 'concept_id'),
                             ('source_conflicts', 'source_conflict', 'conflict_id'), ('clinical_conflicts', 'clinical_fact', 'conflict_id')):
        if key in value:
            value[key] = [x for x in value[key] if (kind, x[field]) not in gone]
    return value


def merge_added(bank, clinical_conflicts, output, allowed_ids):
    """Append an add stage's questions. Existing questions, concepts, conflicts and facts stay byte-identical."""
    validate_shape(output, ADD_OUTPUT, 'v3 add output')
    output = _without(output, restated(bank, clinical_conflicts, output))
    ids = [q['question_id'] for q in output['questions']]
    require(len(ids) == len(set(ids)), 'v3 add: duplicate question IDs')
    require(set(ids) <= set(allowed_ids), 'v3 add: question IDs outside the allowed range')
    require(not set(ids) & {q['question_id'] for q in bank['questions']}, 'v3 add: an add stage cannot rewrite an existing question')
    require(all(s['question_id'] in ids for s in output['visual_stimuli']), 'v3 add: images only for new questions')
    new_ids = {c['conflict_id'] for c in output['source_conflicts']}
    require({c['conflict_id'] for c in output['clinical_conflicts']} <= new_ids, 'v3 add: clinical facts only for its new source conflicts')
    known = {c['concept_id'] for c in bank['concepts']}
    new_concepts = [c['concept_id'] for c in output['concepts']]
    require(len(new_concepts) == len(set(new_concepts)), 'v3 add: duplicate new concepts')
    require({p['concept_id'] for p in output['retrieval_plan']} == set(new_concepts) and len(output['retrieval_plan']) == len(new_concepts),
            'v3 add: one retrieval plan per new concept')
    require(all(q['concept_id'] in known | set(new_concepts) for q in output['questions']), 'v3 add: question concept is unknown')
    merged = copy.deepcopy(bank)
    merged['source_conflicts'] = _bank_conflicts(bank, output['source_conflicts'])
    merged['concepts'] = [*merged['concepts'], *copy.deepcopy(output['concepts'])]
    merged['retrieval_plan'] = [*merged['retrieval_plan'], *copy.deepcopy(output['retrieval_plan'])]
    merged['questions'] = [*merged['questions'], *copy.deepcopy(output['questions'])]
    return merged, [*copy.deepcopy(clinical_conflicts), *copy.deepcopy(output['clinical_conflicts'])]


def merge_fixes(bank, clinical_conflicts, output, targets):
    """Replace only the questions a fix stage was given; identity, concept and points stay."""
    validate_shape(output, FIX_OUTPUT, 'v3 fix output')
    cited = {q.get('conflict_id') for q in output['questions'] if q.get('conflict_id')}
    output = _without(output, restated(bank, clinical_conflicts, output, cited))
    ids = [q['question_id'] for q in output['questions']]
    require(len(ids) == len(set(ids)) and set(ids) <= set(targets), 'v3 fix: only the listed questions may change')
    before = {q['question_id']: q for q in bank['questions']}
    for q in output['questions']:
        old = before[q['question_id']]
        for key in ('concept_id', 'point_ids'):
            require(q.get(key) == old.get(key), f'v3 fix: {q["question_id"]} changed {key}')
    require(all(s['question_id'] in ids for s in output['visual_stimuli']), 'v3 fix: images only for fixed questions')
    require(all(c['conflict_id'] in cited for c in output['clinical_conflicts']), 'v3 fix: facts only for the fixed questions')
    replaced = {q['question_id']: copy.deepcopy(q) for q in output['questions']}
    merged = copy.deepcopy(bank)
    merged['source_conflicts'] = _bank_conflicts(bank, output['source_conflicts'])
    merged['questions'] = [replaced.get(q['question_id'], q) for q in merged['questions']]
    facts = {c['conflict_id']: c for c in clinical_conflicts}
    for c in output['clinical_conflicts']:
        facts[c['conflict_id']] = copy.deepcopy(c)   # a fixed question may restate the facts of its own conflict
    return merged, list(facts.values()), sorted(replaced)


def supplement_addition(brief, value, blank):
    """The targets/points a supplement-normalize output adds, as extend_brief receives them."""
    targets = v2.blank_target_importance({**brief, 'targets': value['targets']})['targets'] if blank else value['targets']
    return {'targets': targets, 'points': value['points']}


def worse(before, after):
    """True when a re-review is worse than the review before the fix (the fix is then reverted)."""
    def level(r):
        return max(RANK[r['verdict']], RANK[r['design']])
    return level(after) > level(before)


def needs_fix(review):
    return review['verdict'] != 'ok' or review['design'] != 'ok'


# ---------------------------------------------------------------- verdict ledger (P2)
def ledger_entry(kind, key, content_hash, value, stage):
    require(kind in ('item', 'coverage'), 'v3 ledger: unknown kind')
    return {'kind': kind, 'key': key, 'contentHash': content_hash, 'value': copy.deepcopy(value), 'stage': stage}


def reusable(ledger, kind, key, content_hash):
    """The latest recorded judgment for this exact content, or None."""
    rows = [r for r in ledger if r['kind'] == kind and r['key'] == key and r['contentHash'] == content_hash]
    return copy.deepcopy(rows[-1]['value']) if rows else None


def coverage_key(direction_id, question_ids):
    return direction_id + '|' + ','.join(sorted(question_ids))


# ---------------------------------------------------------------- unperformed judgments
UNPERFORMED_COVERAGE = 'v3 coverage: the batch judged nothing (every goal unknown)'
UNPERFORMED_REVIEW = 'v3 review: the batch judged nothing (every question doubt, no design judgment)'


def check_coverage(value, goals, questions):
    """Shape, one row per goal, evidence only on given questions; all-unknown is an unperformed review."""
    validate_shape(value, COVERAGE_OUTPUT, 'v3 coverage output')
    rows = index_by(value['rows'], 'direction_id')
    require(set(rows) == {g['direction_id'] for g in goals}, 'v3 coverage: one row per goal')
    qids = {q['question_id'] for q in questions}
    goals = {g['direction_id']: g for g in goals}
    units = {q['question_id']: len(q.get('answer_units', [])) for q in questions}
    for did, row in rows.items():
        allowed = {r['relation_id'] for r in goals[did]['relations']}
        comps = {c['component_id'] for c in goals[did]['components']}
        for e in row['evidence']:
            require(e['question_id'] in qids, 'v3 coverage: evidence names a question outside the batch')
            require(set(e['tested_relation_ids']) <= allowed, 'v3 coverage: tested relation outside the goal')
            require({p['component_id'] for p in e['components']} == comps, 'v3 coverage: each component needs evidence')
            for p in e['components']:
                ix = p['answer_unit_indices']
                require(len(ix) == len(set(ix)) and all(i < units[e['question_id']] for i in ix), 'v3 coverage: nonexistent answer unit')
                require(bool(ix) == (p['location'] == 'answer'), 'v3 coverage: only answer units are recalled evidence')
        whole = [e for e in row['evidence'] if all(p['location'] == 'answer' for p in e['components'])
                 and set(e['tested_relation_ids']) == allowed]
        if row['status'] == 'covered':
            require(whole, 'v3 coverage: covered needs one question that answers the whole goal')
    require(any(r['status'] != 'unknown' for r in value['rows']), UNPERFORMED_COVERAGE)
    return value


def covering(row):
    """Questions that answer the whole goal in a coverage row (all components in the answer)."""
    if row['status'] != 'covered':
        return []
    return [e['question_id'] for e in row['evidence'] if all(p['location'] == 'answer' for p in e['components'])]


def check_review(value, question_ids, bank):
    by_id = {q['question_id']: q for q in bank['questions']}
    return _check_review(value, {q: by_id[q].get('prerequisites', []) for q in question_ids})


def check_review_input(value, ctx):
    return _check_review(value, {q['question_id']: q.get('prerequisites', []) for q in ctx['questions']})


def _check_review(value, prerequisites):
    validate_shape(value, ITEM_REVIEW_OUTPUT, 'v3 review output')
    rows = index_by(value['reviews'], 'question_id')
    require(set(rows) == set(prerequisites), 'v3 review: one review per question in the batch')
    for qid, r in rows.items():
        wanted = set(prerequisites[qid])
        got = [p['prerequisite_id'] for p in r['prerequisite_checks']]
        require(len(got) == len(set(got)) and set(got) == wanted, 'v3 review: every prerequisite needs one check')
    require(any(r['verdict'] != 'doubt' or r['design'] != 'doubt' for r in value['reviews']), UNPERFORMED_REVIEW)
    return value


def _check_map_ids(value, rids, tids, dids):
    validate_shape(value, MAP_CHECK_OUTPUT, 'v3 map check output')
    require({r['relation_id'] for r in value['relation_checks']} == set(rids) and len(value['relation_checks']) == len(set(rids)),
            'v3 map check: one judgment per relation')
    require({r['target_id'] for r in value['target_checks']} == set(tids) and len(value['target_checks']) == len(set(tids)),
            'v3 map check: one judgment per target')
    require({r['direction_id'] for r in value['direction_checks']} == set(dids) and len(value['direction_checks']) == len(set(dids)),
            'v3 map check: one scope judgment per goal')
    for issue in value['issues']:
        require(set(issue['direction_ids']) <= set(dids), 'v3 map check: issue names an unknown goal')
    return value


def check_map(value, brief, target_ids=None):
    """The map check against the brief: the same relations, targets and goals map_check_input gives (one rule)."""
    targets = [t for t in brief['targets'] if target_ids is None or t['target_id'] in set(target_ids)]
    rids = [r['relation_id'] for r in map_check_input(brief, None, target_ids)['relations']]
    return _check_map_ids(value, rids, [t['target_id'] for t in targets], [d['direction_id'] for t in targets for d in t['directions']])


def check_map_input(value, ctx):
    """The same check from a map_check_input (the adapter sees only the stage input)."""
    return _check_map_ids(value, [r['relation_id'] for r in ctx['relations']], [t['target_id'] for t in ctx['targets']],
                          [g['direction_id'] for t in ctx['targets'] for g in t['goals']])


# ---------------------------------------------------------------- off-goal questions → supplement points (R2a)
def _check_point(p):
    """POINT checked without jsonschema (pure module): fields, refs and the importance basis."""
    require(type(p) is dict and set(p) == {'point', 'source_refs', 'importance_basis'}, 'v3 supplement: point fields')
    require(type(p['point']) is str and p['point'].strip(), 'v3 supplement: point text required')
    require(type(p['source_refs']) is list and p['source_refs'], 'v3 supplement: source_refs required')
    for r in p['source_refs']:
        require(type(r) is dict and set(r) == {'source_id', 'pages', 'locator'} and type(r['source_id']) is str and r['source_id'],
                'v3 supplement: source ref fields')
        pages, locator = r['pages'], r['locator']
        require(type(pages) is list and all(type(x) is int and x >= 1 for x in pages) and len(pages) == len(set(pages)),
                'v3 supplement: source ref pages')
        require(locator is None or (type(locator) is str and locator.strip()), 'v3 supplement: source ref locator')
        require(pages or locator, 'v3 supplement: a source ref needs pages or a locator')
    imp.validate_basis(p['importance_basis'])


def _supplement_rows(output, off_goal_ids, existing, page_counts):
    """Row shape and decisions of a supplement output (shared by the adapter and attach_points)."""
    require(type(output) is dict and set(output) == {'rows'} and type(output['rows']) is list and output['rows'],
            'v3 supplement output: rows required')
    for r in output['rows']:
        require(type(r) is dict and set(r) == {'question_id', 'decision', 'point', 'duplicate_of', 'reason'}
                and r['decision'] in ('point', 'out_of_scope', 'duplicate_of') and type(r['reason']) is str and r['reason'].strip(),
                'v3 supplement output: malformed row')
        if r['decision'] == 'point':
            require(r['point'] is not None and r['duplicate_of'] is None, 'v3 supplement: a point decision carries one point')
            p = r['point']
            _check_point(p)
            for ref in p['source_refs'] + [x for b in p['importance_basis'] for x in b['refs']]:
                require(ref['source_id'] in page_counts, 'v3 supplement: unknown source')
                count = page_counts[ref['source_id']]
                require(count is None or all(1 <= x <= count for x in ref['pages']), 'v3 supplement: pages outside the source')
            require(any(ref['source_id'] == SOURCE_LIMIT for ref in p['source_refs']), 'v3 supplement: a new point needs the lecture notes')
        elif r['decision'] == 'duplicate_of':
            require(r['point'] is None and r['duplicate_of'] in existing, 'v3 supplement: duplicate_of names an existing point')
        else:
            require(r['point'] is None and r['duplicate_of'] is None, 'v3 supplement: out_of_scope carries no point')
    rows = index_by(output['rows'], 'question_id')
    require(set(rows) == set(off_goal_ids), 'v3 supplement: one decision per off-goal question')
    return rows


def attach_points(points_doc, output, off_goal_ids, page_counts):
    """New exam points (exam-point-extract/3 form) for off-goal questions; tiers by the same point table.

    Returns (points_doc, table, decisions). Existing points and their tiers stay unchanged.
    SUPPLEMENT_OUTPUT is the model-facing JSON Schema (anyOf); this pure module checks the same shape by hand."""
    existing = {p['point_id'] for p in points_doc['points']}
    rows = _supplement_rows(output, off_goal_ids, existing, page_counts)
    before = imp.point_table(points_doc['points'], points_doc['notebook_profile'])
    numbers = [int(m.group(1)) for p in points_doc['points'] for m in [re.fullmatch(r'P(\d+)', p['point_id'])] if m]
    nxt = max(numbers, default=0) + 1
    value = copy.deepcopy(points_doc)
    decisions = []
    for qid in off_goal_ids:
        row = rows[qid]
        if row['decision'] == 'point':
            p = row['point']
            pid = f'P{nxt:03d}'
            nxt += 1
            value['points'].append({'point_id': pid, **copy.deepcopy(p), 'origin': 'question', 'origin_question_id': qid})
            decisions.append({'question_id': qid, 'decision': 'point', 'point_id': pid, 'reason': row['reason']})
        elif row['decision'] == 'duplicate_of':
            decisions.append({'question_id': qid, 'decision': 'duplicate_of', 'point_id': row['duplicate_of'], 'reason': row['reason']})
        else:
            decisions.append({'question_id': qid, 'decision': 'out_of_scope', 'point_id': None, 'reason': row['reason']})
    table = imp.point_table([{k: p[k] for k in ('point_id', 'point', 'source_refs', 'importance_basis')} for p in value['points']],
                            value['notebook_profile'])
    require(all(table['points'][pid] == before['points'][pid] for pid in before['points']), 'v3 supplement: existing tiers changed')
    return value, table, decisions


_MAP_PARTS = ('concepts', 'relations', 'targets', 'points', 'prerequisites')


def map_projection(brief, new_target_ids=(), new_point_ids=()):
    """The brief without the targets/points R2a added; it must equal the brief before R2a."""
    value = copy.deepcopy(brief)
    value['targets'] = [t for t in value['targets'] if t['target_id'] not in set(new_target_ids)]
    value['points'] = [p for p in value['points'] if p['point_id'] not in set(new_point_ids)]
    return value


def extend_brief(brief, addition, new_point_ids):
    """Add the targets/points normalized from supplement points. Nothing existing may change."""
    require(set(addition) == {'targets', 'points'}, 'v3 extend: only new targets and points')
    old_targets = {t['target_id'] for t in brief['targets']}
    old_points = {p['point_id'] for p in brief['points']}
    new_targets = [t['target_id'] for t in addition['targets']]
    require(new_targets and not set(new_targets) & old_targets, 'v3 extend: new targets only')
    require({p['point_id'] for p in addition['points']} == set(new_point_ids) and not set(new_point_ids) & old_points,
            'v3 extend: exactly the supplement points')
    old_dirs = {d['direction_id'] for t in brief['targets'] for d in t['directions']}
    require(not {d['direction_id'] for t in addition['targets'] for d in t['directions']} & old_dirs, 'v3 extend: new goals only')
    require(all(set(p['target_ids']) <= set(new_targets) and p['target_ids'] for p in addition['points']),
            'v3 extend: supplement points map to the new targets')
    concepts = {c['concept_id'] for c in brief['concepts']}
    relations = {r['relation_id'] for r in brief['relations']}
    for t in addition['targets']:
        require(set(t['concept_ids']) <= concepts and set(t['relation_ids']) <= relations, 'v3 extend: new targets use the existing map')
        for d in t['directions']:
            require(set(d['relation_ids']) <= set(t['relation_ids']), 'v3 extend: goal relations belong to its target')
    value = copy.deepcopy(brief)
    value['targets'] += copy.deepcopy(addition['targets'])
    value['points'] += copy.deepcopy(addition['points'])
    require(map_projection(value, new_targets, new_point_ids) == brief, 'v3 extend: the existing map changed')
    v2.validate_brief(value)
    return value, new_targets


# ---------------------------------------------------------------- assembly adapter
def assessment_raw(brief, bank, coverage_rows, map_check, reviews, context, summary):
    """source-assessment/2 from the /3 judgments only, for /2 compile_assessment and make_document.

    coverage_rows: latest coverage row per goal; map_check: one MAP_CHECK_OUTPUT for every target;
    reviews: latest item review per question; context: the /2 context stage output. Every slot must
    come from an actual judgment: a missing one is an error, never filled in."""
    dirs = _directions(brief)
    rows = index_by(coverage_rows, 'direction_id')
    require(set(rows) == set(dirs), 'v3 assembly: every goal needs a coverage judgment')
    qs = {q['question_id'] for q in bank['questions']}
    reviews = index_by(reviews, 'question_id')
    require(set(reviews) == qs, 'v3 assembly: every question needs an item review')
    check_map(map_check, brief)
    v2.validate_context(context)
    scope = {r['direction_id']: r for r in map_check['direction_checks']}
    claims = {}
    evidence = []
    for did, row in rows.items():
        if row['status'] == 'unknown':
            continue
        for e in row['evidence']:
            require(e['question_id'] in qs, 'v3 assembly: coverage names a missing question')
            evidence.append({k: copy.deepcopy(e[k]) for k in ('question_id', 'components', 'visual_verdict', 'reason')} | {'direction_id': did})
            for rid in e['tested_relation_ids']:
                claims.setdefault((e['question_id'], rid), set()).add(did)
    question_reviews = []
    for q in bank['questions']:
        qid = q['question_id']
        r = reviews[qid]
        relations = [{'relation_id': rid, 'role': 'tested', 'direction_ids': sorted(ds), 'reason': 'v3 coverage judgment'}
                     for (cq, rid), ds in sorted(claims.items()) if cq == qid]
        question_reviews.append({'question_id': qid, 'verdict': r['verdict'], 'note': r['note'] or 'v3 문항 검토: 지적 없음',
                                 'suggested_answer': r['suggested_answer'], 'relations': relations})
    issues = []

    def issue(kind, text, question_ids, direction_ids):
        issues.append({'issue_id': f'I{len(issues) + 1:03d}', 'kind': kind, 'text': text,
                       'question_ids': question_ids, 'direction_ids': direction_ids})
    for row in map_check['issues']:
        issue('map_fix', row['text'], [], list(row['direction_ids']))
    for qid, r in reviews.items():
        if needs_fix(r):
            issue('question_fix', r['note'] or r['fix'] or 'v3 item review', [qid], [])
    for did, row in rows.items():
        if row['status'] == 'missing' and dirs[did][1]['requirement'] == 'required':
            issue('required_gap', row['reason'], [], [did])
    value = {
        'schema_version': v2.VERSION, 'summary': summary, 'question_reviews': question_reviews,
        'direction_checks': [{'direction_id': did, 'status': 'unknown' if rows[did]['status'] == 'unknown' else 'reviewed',
                              'reason': rows[did]['reason'], 'scope_status': scope[did]['scope_status']} for did in dirs],
        'direction_evidence': evidence,
        'relation_checks': copy.deepcopy(map_check['relation_checks']),
        'target_checks': copy.deepcopy(map_check['target_checks']),
        'prerequisite_checks': [{'question_id': qid, **copy.deepcopy(p)} for qid, r in reviews.items() for p in r['prerequisite_checks']],
        'issues': issues,
        'clinical_context_status': context['clinical_context_status'],
        'clinical_context_reason': context['clinical_context_reason'],
        'design_checks': [{'question_id': qid, 'verdict': r['design'], 'reason': r['note'] or 'v3 item review'} for qid, r in reviews.items()],
    }
    if not v2.recall.enabled(brief):
        value.pop('design_checks')
    validate_shape(value, v2.SOURCE, 'v3 assembly: source-assessment/2')  # ID binding is checked by compile_assessment
    return value


def not_ready(brief, coverage_rows, reviews):
    """Goals with no whole-goal question, or whose only covering questions are still wrong after the limit."""
    rows = index_by(coverage_rows, 'direction_id')
    verdict = {r['question_id']: r for r in reviews}
    out = []
    for t in brief['targets']:
        for d in t['directions']:
            row = rows.get(d['direction_id'])
            qids = covering(row) if row else []
            if not qids:
                out.append({'direction_id': d['direction_id'], 'reason': 'no-question'})
            elif all(verdict[q]['verdict'] == 'wrong' for q in qids if q in verdict):
                out.append({'direction_id': d['direction_id'], 'reason': 'question-defect'})
    return out


# ---------------------------------------------------------------- result
MANIFEST_KEYS = {'pipelineVersion', 'inputHash', 'briefHash', 'bankHash', 'model', 'runtimeHash', 'stages', 'verdictLedger',
                 'verdictLedgerHash', 'addRounds', 'notReady', 'offGoalQuestions', 'rejectedAtIntake', 'supplement',
                 'initialBank', 'initialBrief', 'supplementPoints', 'intakeProjection', 'coverage', 'mapCheck', 'itemReviews', 'clinicalContext',
                 'clinicalConflicts', 'medicalFinal',
                 'sourceAssessment', 'fixes'}


def validate_result(value, packet):
    """Artifacts, document and add-only invariants of a /3 result. The stage-proof chain is checked with
    the generator's stage names (PR B)."""
    from .source_assessment import envelope
    require(set(value) == {'brief', 'document', 'sourceAudit', 'medical', 'validation', 'manifest'}, 'result3: unknown/missing artifacts')
    meta = value['manifest']
    require(MANIFEST_KEYS <= set(meta), 'result3: incomplete manifest')
    require(meta['pipelineVersion'] == POLICY, 'result3: not a root-generation/3 result')
    brief, doc = value['brief'], value['document']
    bank = doc['bank_snapshot']
    require(meta['inputHash'] == packet['inputHash'], 'result3: input mismatch')
    # map-tree/2: the derived generation packet travels in the manifest so the server can re-derive it.
    require(('derivedPacket' in meta) == ('derivedFrom' in packet), 'result3: derived generation packet evidence mismatch')
    if 'derivedFrom' in packet:
        from .map_tree import public
        require(meta['derivedPacket'] == public(packet), 'result3: the manifest carries another generation packet')
        require(meta.get('auditOpen') == packet['frontStages']['openPoints'], 'result3: open audit points differ')
    require(meta['briefHash'] == document_hash(brief) and meta['bankHash'] == document_hash(bank), 'result3: stale manifest')
    require(meta['verdictLedgerHash'] == document_hash(meta['verdictLedger']), 'result3: verdict ledger mismatch')
    require(type(meta['addRounds']) is int and 0 <= meta['addRounds'] <= ADD_LIMIT, 'result3: add budget exceeded')
    require(meta['medicalFinal'] is True, 'result3: the medical review runs once at the end (medical-final/1)')
    require(meta['intakeProjection'] == intake_projection(packet['intakeBank']['bank'])[1], 'result3: intake projection differs')
    # Add-only: every intake question survives with the same content unless it was a listed fix target.
    fixed = {f['question_id'] for f in meta['fixes']}
    require(all(f['attempt'] <= FIX_LIMIT for f in meta['fixes']), 'result3: fix budget exceeded')
    reviewed = v2.restore_container_concepts(v2.restore_importance(bank, meta.get('importanceProjection')), meta.get('bankProjection'))
    final = {q['question_id']: q for q in reviewed['questions']}
    off = {r['question_id'] for r in meta['offGoalQuestions']}
    for q in meta['initialBank']['questions']:
        qid = q['question_id']
        require(qid in final or qid in off or qid in {r['question_id'] for r in meta['rejectedAtIntake']},
                'result3: an intake question disappeared')
        if qid in final and qid not in fixed:
            strip = lambda x: {k: v for k, v in x.items() if k not in ('stimuli', 'tier', 'importance', 'concept_id', 'point_ids')}
            require(strip(final[qid]) == strip(q), f'result3: {qid} changed without a fix')
    tasks = {t['question_id'] for t in doc['tasks']}
    require(not tasks & off, 'result3: an out-of-scope question became a task')
    # The audit is the /2 compile of the gathered /3 judgments on the reviewed bank. Rebuilding the
    # document itself (importance projection, container concepts) is checked with the stage chain (PR B).
    raw = assessment_raw(brief, reviewed, meta['coverage'], meta['mapCheck'], meta['itemReviews'],
                         meta['clinicalContext'], meta['sourceAssessment']['summary'])
    require(raw == meta['sourceAssessment'], 'result3: assessment is not the gathered judgments')
    require(value['sourceAudit'] == v2.compile_assessment(brief, reviewed, envelope(brief, reviewed, raw)), 'result3: audit is not the compile')
    ready = {t['direction_id'] for t in doc['tasks']}
    for row in meta['notReady']:
        require(row['direction_id'] not in ready, 'result3: a not-ready goal has a task')
    require(meta['notReady'] == not_ready(brief, meta['coverage'], meta['itemReviews']), 'result3: not-ready goals differ')
    # Supplement points extend the packet's points; tiers come from the same table (spec R2a).
    import json
    table = v2.importance_table(packet)
    if meta['supplementPoints'] is not None:
        original = json.loads(packet['points'])
        extended = meta['supplementPoints']
        require(extended['points'][:len(original['points'])] == original['points'] and extended['notebook_profile'] == original['notebook_profile'],
                'result3: supplement changed the exam points')
        require(all(p.get('origin') == 'question' for p in extended['points'][len(original['points']):]), 'result3: unmarked supplement point')
        table = v2.importance_table({'points': json.dumps({**extended, 'points': [{k: p[k] for k in ('point_id', 'point', 'source_refs', 'importance_basis')}
                                                                                  for p in extended['points']]})})
    else:
        require(not meta['supplement'], 'result3: supplement decisions without points')
    # The document is the /2 assembly of this reviewed bank and audit.
    snapshot, projection = v2.project_container_concepts(reviewed)
    iproof = None
    if table is not None:
        snapshot, iproof = v2.project_importance(snapshot, brief, table)
    require(projection == meta.get('bankProjection') and iproof == meta.get('importanceProjection'), 'result3: projections differ')
    again = v2.make_document(brief, reviewed, value['sourceAudit'], revision=packet['revision'], title=packet['title'],
                             exam_date=packet['examDate'], snapshot=snapshot if projection or iproof else None,
                             importance=v2.target_importance(brief, table) if iproof else None)
    require(again == doc, 'result3: the document is not the assembly of the reviewed judgments')
    # Stage records: fingerprints of the stages whose output the result carries.
    stages = {s['name']: s for s in meta['stages']}
    require(all(s['status'] == 'completed' for s in stages.values()), 'result3: incomplete stages')
    require(all(re.fullmatch(r'[a-f0-9]{64}', s.get(k, '')) for s in stages.values() for k in ('inputHash', 'outputHash')),
            'result3: missing stage fingerprints')
    require(stages['normalize']['outputHash'] == document_hash(meta['initialBrief']), 'result3: initial brief proof mismatch')
    require(stages['context-0']['outputHash'] == document_hash(meta['clinicalContext']), 'result3: context proof mismatch')
    v2.validate_context(meta['clinicalContext'])
    require(not v2.context_blocks_medical(meta['clinicalContext']), 'result3: medical review ran without a clean context')
    med_input = {'title': packet['title'], 'bank': reviewed, 'clinicalInput': v2.medical_input(reviewed, meta['clinicalConflicts']),
                 'medicalFinal': True, '_pipeline_version': POLICY}
    require(stages['medical-0']['inputHash'] == document_hash(med_input) and stages['medical-0']['outputHash'] == document_hash(value['medical']),
            'result3: the medical review is not of this bank')
    require(not any(re.fullmatch(r'medical-[1-9]\d*', n) for n in stages), 'result3: the medical review runs once')
    require(meta['addRounds'] == len([n for n in stages if re.fullmatch(r'v3-add-\d+', n)]), 'result3: add rounds differ from add stages')
    for f in meta['fixes']:
        require(f['stage'] in stages, 'result3: a fix without its stage')
    return doc
