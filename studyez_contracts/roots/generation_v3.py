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

# Add and fix stages write importance only (docs/changes/2026-11-11-tier-from-importance). The tier is its name in
# the bank 3.3 table (one tier per number), so code fills it when the stage is merged. Asking for both let the two
# disagree: the 261113_01 run (2026-11-11) sent 52 questions back to a model fix for that mismatch alone.
TIER_BY_IMPORTANCE = {v: k for k, v in imp.BANK_IMPORTANCE.items()}


def _importance_only(schema):
    value = copy.deepcopy(schema)
    value['properties'].pop('tier')
    value['required'].remove('tier')
    value['properties']['importance'] = {'type': 'integer', 'enum': sorted(TIER_BY_IMPORTANCE)}
    return value


AUTHORED_QUESTION = _importance_only(QUESTION)
AUTHORED_CONCEPT = _importance_only(BANK_CONCEPT)

ADD_OUTPUT = obj(questions=arr(AUTHORED_QUESTION, 1), concepts=arr(AUTHORED_CONCEPT), retrieval_plan=arr(PLAN),
                 source_conflicts=arr(SOURCE_CONFLICT), visual_stimuli=arr(v2.CROP), clinical_conflicts=arr(v2.CONFLICT))
FIX_OUTPUT = obj(questions=arr(AUTHORED_QUESTION, 1), source_conflicts=arr(SOURCE_CONFLICT),
                 visual_stimuli=arr(v2.CROP), clinical_conflicts=arr(v2.CONFLICT))

SUPPLEMENT_NORMALIZE_OUTPUT = obj(targets=arr(copy.deepcopy(v2.BRIEF['properties']['targets']['items']), 1),
                                  points=arr(copy.deepcopy(v2.BRIEF['properties']['points']['items']), 1))
BRIEF_FIX_OUTPUT = obj(brief=copy.deepcopy(v2.BRIEF), map_change_reason=TEXT)

# Clinical context per item (docs/changes/2026-11-10-gen3-item-scope): one row per conflict record, the questions
# whose reviewer-facing text carries review history, and source conflicts the bank does not record. A verdict
# here reaches only the conflict or question it names; it never stops the lecture.
CONTEXT_STATES = ('consistent', 'contamination', 'incomplete', 'unknown')
CONTEXT_OUTPUT = obj(conflicts=arr(obj(conflict_id=TEXT, status=enum(*CONTEXT_STATES), reason=TEXT)),
                     questions=arr(obj(question_id=TEXT, reason=TEXT)), unrecorded=arr(TEXT))

OUTPUTS = {'context': CONTEXT_OUTPUT, 'coverage': COVERAGE_OUTPUT, 'map-check': MAP_CHECK_OUTPUT, 'item-review': ITEM_REVIEW_OUTPUT,
           'supplement': SUPPLEMENT_OUTPUT, 'add': ADD_OUTPUT, 'fix': FIX_OUTPUT}

# ---------------------------------------------------------------- intake projection
def _first_each(items):
    """The list with each value's first occurrence only (order kept)."""
    out = []
    for x in items:
        if x not in out:
            out.append(x)
    return out


def _drop_repeats(bank):
    """Repeated values in lists whose order and count carry no meaning, in place; returns the changes.

    docs/changes/2026-11-11-intake-dedupe: the 261102_02 /4 trial (2026-11-11) stopped before any generation call
    because concept C06's plan listed `reverse` twice; the same slip inside a question (prerequisites, correct
    option IDs) dropped the whole question. Only exact repeats go: two different plans for one concept, or two
    different summaries for one source, still stop the run as before."""
    changes = []

    def dedupe(container, key, field):
        got = container.get(key)
        if type(got) is list:
            kept = _first_each(got)
            if kept != got:
                changes.append({'field': field, 'from': copy.deepcopy(got), 'to': copy.deepcopy(kept)})
                container[key] = kept

    for key, label in (('retrieval_plan', 'concept_id'), ('source_summary', 'source_id')):
        rows = bank.get(key)
        if type(rows) is list and all(type(r) is dict for r in rows):
            kept = _first_each(rows)
            if len(kept) != len(rows):
                gone = [r.get(label) for i, r in enumerate(rows) if r in rows[:i]]
                changes.append({'field': key, 'from': len(rows), 'to': len(kept), 'repeated': gone})
                bank[key] = kept
    for p in bank.get('retrieval_plan') or []:
        if type(p) is dict:
            dedupe(p, 'directions', f"{p.get('concept_id')}.directions")
    for q in bank.get('questions') or []:
        if type(q) is dict:
            dedupe(q, 'prerequisites', f"{q.get('question_id')}.prerequisites")
            dedupe(q, 'correct_option_ids', f"{q.get('question_id')}.correct_option_ids")
    return changes


def intake_projection(bank):
    """Fields of an independently authored bank that the assembly recomputes, set to the current bank format.

    An independent bank (1c) is written before the exam points' tiers exist; the assembly sets tier and
    importance from the point basis (generation_v2.project_importance, bank 3.3). The first real run
    (261102_02, 2026-11-10) wrote build_meta.schema_version "BANK" with 3.2 importance numbers, and the
    whole bank was refused before any question was read. Only build_meta.schema_version, the importance
    of each question and concept (the number of its own tier) and exact repeats in order-free lists
    (`_drop_repeats`) change; every change is returned and recorded."""
    from studyez_contracts.bank.validate import SCHEMA_VERSIONS
    current = SCHEMA_VERSIONS[-1]
    value = copy.deepcopy(bank)
    changes = _drop_repeats(value)
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


_READER = ('question_id', 'format', 'question', 'answer', 'answer_units', 'options', 'correct_option_ids', 'matching_left',
           'matching_right', 'answer_pairs', 'sequence_items', 'correct_order', 'conflict_id', 'option_explanations', 'explanation')


def context_input(bank, clinical_conflicts, conflict_ids=None, question_ids=None):
    """Clinical context: each conflict record with its facts and the questions citing it, the reviewer-facing
    text of the questions to read, and the pages the citing questions cite.

    The whole judgment (both None) takes every conflict and every question. A re-judgment after the repair takes
    the named conflicts and questions only."""
    sources = {c['conflict_id']: c for c in bank.get('source_conflicts', [])}
    facts = {c['conflict_id']: c['facts'] for c in clinical_conflicts}
    wanted = sorted(set(sources) | set(facts)) if conflict_ids is None else sorted(conflict_ids)
    require(set(wanted) <= set(sources) | set(facts), 'v3 context: unknown conflict')
    citing = {}
    for q in bank['questions']:
        if q.get('conflict_id'):
            citing.setdefault(q['conflict_id'], []).append(q)
    read = [q for q in bank['questions'] if question_ids is None or q['question_id'] in set(question_ids)
            or q.get('conflict_id') in set(wanted)]
    return {'conflicts': [{'conflict_id': cid, 'source_conflict': copy.deepcopy(sources.get(cid)), 'facts': facts.get(cid),
                           'question_ids': [q['question_id'] for q in citing.get(cid, [])]} for cid in wanted],
            'questions': [{k: copy.deepcopy(q[k]) for k in _READER if k in q} for q in read],
            'pages': cited_pages([r for cid in wanted for q in citing.get(cid, []) for r in q.get('source_refs', [])])}


def check_context(value, ctx):
    """One row per conflict of the input, flags only on its questions; every conflict unknown is an unperformed
    judgment."""
    validate_shape(value, CONTEXT_OUTPUT, 'v3 context output')
    rows = index_by(value['conflicts'], 'conflict_id')
    require(set(rows) == {c['conflict_id'] for c in ctx['conflicts']}, 'v3 context: one row per conflict record')
    flagged = [r['question_id'] for r in value['questions']]
    require(len(flagged) == len(set(flagged)) and set(flagged) <= {q['question_id'] for q in ctx['questions']},
            'v3 context: a flagged question is not in the input')
    require(not rows or any(r['status'] != 'unknown' for r in rows.values()), UNPERFORMED_CONTEXT)
    return value


def context_merge(first, again, bank, clinical_conflicts, rejudged_questions=()):
    """The judgments that hold for the final bank: the re-judgment replaces the rows of the conflicts and questions
    it was given; rows of conflicts or questions no longer in the bank are dropped. Each row names its stage."""
    present = {c['conflict_id'] for c in [*bank.get('source_conflicts', []), *clinical_conflicts]}
    qids = {q['question_id'] for q in bank['questions']}
    conflicts = {r['conflict_id']: {**r, 'stage': 0} for r in first['conflicts']}
    questions = {r['question_id']: {**r, 'stage': 0} for r in first['questions']}
    unrecorded = list(first['unrecorded'])
    if again is not None:
        for q in rejudged_questions:
            questions.pop(q, None)
        conflicts.update({r['conflict_id']: {**r, 'stage': 1} for r in again['conflicts']})
        questions.update({r['question_id']: {**r, 'stage': 1} for r in again['questions']})
        unrecorded += [x for x in again['unrecorded'] if x not in unrecorded]
    require(present <= set(conflicts), 'v3 context: a conflict record of the final bank was never judged')
    return {'conflicts': [conflicts[c] for c in sorted(present)],
            'questions': [questions[q] for q in sorted(questions) if q in qids], 'unrecorded': unrecorded}


def context_open(judgment):
    """What a context judgment leaves open: conflicts not judged consistent and flagged questions."""
    return {'conflicts': [r['conflict_id'] for r in judgment['conflicts'] if r['status'] != 'consistent'],
            'questions': [r['question_id'] for r in judgment['questions']]}


def context_sent(clinical_conflicts, judgment):
    """The clinical facts the medical review receives: only those of conflicts judged consistent."""
    ok = {r['conflict_id'] for r in judgment['conflicts'] if r['status'] == 'consistent'}
    return [copy.deepcopy(c) for c in clinical_conflicts if c['conflict_id'] in ok and not _marked(c)]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _marked(value):
    return any(re.search(v2.HISTORY_MARKERS, s, re.I) for s in _strings(value))


def history_marked(bank):
    """Questions whose reviewer-facing fields carry an explicit review-history marker. /2 medical_input refuses
    the whole input for one such string; here the question is a fix target, and if it stays it is left out of
    the medical review and recorded (one question never stops the lecture)."""
    marked = []
    for q in bank['questions']:
        try:
            v2.medical_input({'questions': [q]}, [])
        except ValueError:
            marked.append(q['question_id'])
    return marked


UNREVIEWED_NOTE = '의학 검토 판정 없음(코드 기록): '


def medical_parts(bank, sent):
    """(the medical review's clinical input, questions left out of it)."""
    out = history_marked(bank)
    return v2.medical_input({**bank, 'questions': [q for q in bank['questions'] if q['question_id'] not in set(out)]}, sent), out


def unreviewed_row(question_id, why):
    """The row of a question the medical review gave no verdict for. doubt is the review's own 「판단 보류」; the note
    says that no judgment was made, so it is never read as one."""
    return {'question_id': question_id, 'verdict': 'doubt', 'note': UNREVIEWED_NOTE + why, 'suggested_answer': ''}


def context_summary(judgment):
    """The /2 assessment's clinical-context slot, derived by code: the facts that reach the medical review are
    exactly those judged consistent, so the separation it stands for holds for what is sent."""
    left = context_open(judgment)
    total = len(judgment['conflicts'])
    reason = f"root-generation/3 충돌별 임상 정리: 충돌 기록 {total}개 중 일치 {total - len(left['conflicts'])}개."
    if left['conflicts']:
        reason += ' 의학 검토에 사실을 보내지 않은 충돌: ' + ', '.join(left['conflicts']) + '.'
    if left['questions']:
        reason += ' 글에 저작·검수 이력이 남은 문항: ' + ', '.join(left['questions']) + '.'
    return {'clinical_context_status': 'consistent', 'clinical_context_problem': 'none', 'clinical_context_reason': reason}


def context_repair_targets(bank, judgment, attempts):
    """Questions one fix round takes after a context judgment: those citing a conflict not judged consistent and
    those flagged, with fix budget left (FIX_LIMIT, P5)."""
    left = context_open(judgment)
    return [q['question_id'] for q in bank['questions']
            if (q.get('conflict_id') in left['conflicts'] or q['question_id'] in left['questions'])
            and attempts.get(q['question_id'], 0) < FIX_LIMIT]


def context_findings(bank, judgment, question_ids):
    """The context notes each repaired question receives."""
    conflicts = {r['conflict_id']: r for r in judgment['conflicts']}
    flags = {r['question_id']: r for r in judgment['questions']}
    notes = {}
    for q in bank['questions']:
        qid = q['question_id']
        if qid not in set(question_ids):
            continue
        row = conflicts.get(q.get('conflict_id'))
        if row and row['status'] != 'consistent':
            notes.setdefault(qid, []).append(f"임상 정리: 충돌 기록 {row['conflict_id']} — {row['status']}: {row['reason']}")
        if qid in flags:
            notes.setdefault(qid, []).append('임상 정리: 문항 글에 저작·검수 이력 — ' + flags[qid]['reason'])
    return notes


# ---------------------------------------------------------------- stage-local acceptance (adapter)
def check_added(value, ctx, state=None):
    """An add output against its add_input; with the orchestrator's state (P6) also the merge itself.

    `state` = {'bank': authored bank, 'clinical_conflicts': [...]} is what merge_added receives after the stage.
    Running the same merge here lets the runner send its error back into the model's session (one follow-up)
    instead of stopping the lecture after the stage. Existing items written again are set aside (restated)."""
    validate_shape(_authored(value), ADD_OUTPUT, 'v3 add output')
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
    validate_shape(_authored(value), FIX_OUTPUT, 'v3 fix output')
    given = {q['question_id']: q for q in ctx['questions']}
    ids = [q['question_id'] for q in value['questions']]
    require(len(ids) == len(set(ids)) and set(ids) <= set(given), 'v3 fix: only the listed questions may change')
    for q in value['questions']:
        for key in ('concept_id', 'point_ids'):
            require(q.get(key) == given[q['question_id']].get(key), f'v3 fix: {q["question_id"]} changed {key}')
    require(all(s['question_id'] in ids for s in value['visual_stimuli']), 'v3 fix: images only for fixed questions')
    if 'conflict_scope' in ctx:
        check_conflict_scope(value, ctx['conflict_scope'])
    if state is not None:
        merge_fixes(state['bank'], state['clinical_conflicts'], value, list(given))
    return value


def check_conflict_scope(value, scope):
    """A fix in a batch that runs beside others (docs/changes/2026-11-11-root-batch-parallel): a new conflict ID
    starts with the batch's prefix, and the facts it may write again are its own batch's conflicts. Two batches
    then never write the same record, and merging them in batch order is what the one-after-another order gives."""
    prefix, own, known = scope['new_conflict_id_prefix'], set(scope['own_conflict_ids']), set(scope['known_conflict_ids'])
    for key in ('source_conflicts', 'clinical_conflicts'):
        for c in value[key]:
            cid = c['conflict_id']
            if cid not in known:
                require(cid.startswith(prefix), f'v3 fix: a new conflict ID in this batch starts with {prefix} (not {cid})')
    cited = {q.get('conflict_id') for q in value['questions'] if q.get('conflict_id')}
    for c in value['clinical_conflicts']:
        cid = c['conflict_id']
        require(cid not in known or cid not in cited or cid in own,
                f'v3 fix: {cid} belongs to another batch; cite it without writing its facts again')


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


def _authored(output):
    """An add/fix output in its authored shape: a tier written by an earlier run (its cached stage output) is
    dropped, the importance alone stands."""
    value = copy.deepcopy(output)
    for key in ('questions', 'concepts'):
        for row in value.get(key, []) if type(value.get(key)) is list else []:
            if type(row) is dict:
                row.pop('tier', None)
    return value


def cloze_units(bank):
    """Set each inline cloze's answer_units to its {blanks} in order, in place; returns what changed.

    The blanks are what a learner and the coverage judge see (_front: one unit per blank). An author may also
    write answer_units that merge a table row's blanks into one unit or drop a repeated blank; the site then put
    the wrong unit in every later cell (2026-11-12: 92 of 696 published cloze, 13 with another count). Applied
    where a model's questions enter the bank: the generators' intake and merge_added/merge_fixes. The server does
    not re-derive those, so a runner and a server of either version still accept each other's results."""
    changes = []
    for q in bank.get('questions', []):
        if q.get('format') != 'cloze':
            continue
        units = normalize_cloze(q).get('answer_units') or []
        if units and units != q.get('answer_units'):
            changes.append({'question_id': q['question_id'], 'from': q.get('answer_units'), 'to': list(units)})
            q['answer_units'] = list(units)
    return changes


def with_tier(output):
    """Each question and concept takes the tier its importance names (bank 3.3 table)."""
    value = copy.deepcopy(output)
    for key in ('questions', 'concepts'):
        for row in value.get(key, []):
            row['tier'] = TIER_BY_IMPORTANCE[row['importance']]
    return value


def merge_added(bank, clinical_conflicts, output, allowed_ids):
    """Append an add stage's questions. Existing questions, concepts, conflicts and facts stay byte-identical."""
    output = _authored(output)
    validate_shape(output, ADD_OUTPUT, 'v3 add output')
    output = with_tier(output)
    cloze_units(output)
    output = _without(output, restated(bank, clinical_conflicts, output))
    ids = [q['question_id'] for q in output['questions']]
    require(len(ids) == len(set(ids)), 'v3 add: duplicate question IDs')
    require(set(ids) <= set(allowed_ids), 'v3 add: question IDs outside the allowed range')
    require(not set(ids) & {q['question_id'] for q in bank['questions']}, 'v3 add: an add stage cannot rewrite an existing question')
    require(all(s['question_id'] in ids for s in output['visual_stimuli']), 'v3 add: images only for new questions')
    new_ids = {c['conflict_id'] for c in output['source_conflicts']}
    require({c['conflict_id'] for c in output['clinical_conflicts']} <= new_ids, 'v3 add: clinical facts only for its new source conflicts')
    require(new_ids <= {q.get('conflict_id') for q in output['questions']}, 'v3 add: a new source conflict must be cited by a new question')
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
    output = _authored(output)
    validate_shape(output, FIX_OUTPUT, 'v3 fix output')
    output = with_tier(output)
    cloze_units(output)
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
    require(all(c['conflict_id'] in cited for c in output['source_conflicts']), 'v3 fix: a new source conflict must be cited by a fixed question')
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
UNPERFORMED_CONTEXT = 'v3 context: the clinical context was left unknown'
UNPERFORMED_MAP = 'v3 map check: the check judged nothing (every relation, target and goal unknown)'


# ---------------------------------------------------------------- reverts and the clinical context
def fixes_of(output, question_ids):
    """The part of a fix output that belongs to `question_ids`: their questions and images and the conflicts
    they cite. A revert merges this part again so nothing of a reverted question stays behind."""
    keep = set(question_ids)
    cited = {q['conflict_id'] for q in output['questions'] if q['question_id'] in keep and q.get('conflict_id')}
    value = copy.deepcopy(output)
    value['questions'] = [q for q in value['questions'] if q['question_id'] in keep]
    value['visual_stimuli'] = [s for s in value['visual_stimuli'] if s['question_id'] in keep]
    value['source_conflicts'] = [c for c in value['source_conflicts'] if c['conflict_id'] in cited]
    value['clinical_conflicts'] = [c for c in value['clinical_conflicts'] if c['conflict_id'] in cited]
    return value


def drop_orphans(bank, clinical_conflicts, intake_conflict_ids=()):
    """(bank, clinical_conflicts, dropped ids) without the conflict records no question cites, except those the
    intake bank brought (they stay as they came)."""
    keep = {q['conflict_id'] for q in bank['questions'] if q.get('conflict_id')} | set(intake_conflict_ids)
    gone = sorted({c['conflict_id'] for c in [*bank.get('source_conflicts', []), *clinical_conflicts]} - keep)
    if not gone:
        return bank, clinical_conflicts, []
    value = copy.deepcopy(bank)
    value['source_conflicts'] = [c for c in value.get('source_conflicts', []) if c['conflict_id'] in keep]
    return value, [c for c in clinical_conflicts if c['conflict_id'] in keep], gone


def check_integrity(bank, clinical_conflicts, stimuli, intake_conflict_ids=()):
    """Before the context judgment: every conflict record a stage added is cited by a question, and the image
    list is what the bank shows. A record no question cites made the context judgment incomplete and every
    goal blocked (CF-POLIO-28, 261102_02)."""
    cited = {q['conflict_id'] for q in bank['questions'] if q.get('conflict_id')}
    for c in [*bank.get('source_conflicts', []), *clinical_conflicts]:
        require(c['conflict_id'] in cited or c['conflict_id'] in set(intake_conflict_ids),
                'v3 assembly: a conflict record no question cites: ' + c['conflict_id'])
    shown = sorted((q['question_id'], s['source_id'], s['page'], tuple(s['crop'])) for q in bank['questions'] for s in q.get('stimuli', []))
    listed = sorted((s['question_id'], s['source_id'], s['page'], tuple(s['crop'])) for s in stimuli)
    require(shown == listed, 'v3 assembly: the image list differs from the images the bank shows')


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
    judged = [r['status'] for r in value['relation_checks'] + value['target_checks']] + [r['scope_status'] for r in value['direction_checks']]
    require(not judged or any(s != 'unknown' for s in judged), UNPERFORMED_MAP)
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
            # The row's status is the judgment. Evidence that would by itself make a whole-goal task under a row
            # judged missing is kept as evidence but claims no tested relation (found by the any-verdict test:
            # such a goal was listed not ready and had a task).
            if row['status'] != 'covered' and all(p['location'] == 'answer' for p in e['components']):
                continue
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


def readiness(brief, bank, assessment, doc):
    """Why each goal is or is not a task, from the same judgments the assembly used (never a new judgment).

    Reasons: no-question (no question answers the whole goal), coverage-unknown, question-not-ok (every covering
    question is doubt/wrong in the item review), relation, target, scope, visual, prerequisite-check, no-point,
    dependency (its own judgments pass; a prerequisite question or target is not ready)."""
    a = assessment
    ready = {t['direction_id'] for t in doc['tasks']}
    rels = {r['relation_id']: r['status'] for r in a['relation_checks']}
    targets = {r['target_id']: r['status'] for r in a['target_checks']}
    scope = {r['direction_id']: r for r in a['direction_checks']}
    verdict = {r['question_id']: r['verdict'] for r in a['question_reviews']}
    pre = {(r['question_id'], r['prerequisite_id']): r['status'] for r in a['prerequisite_checks']}
    qs = {q['question_id']: q for q in bank['questions']}
    pointed = {tid for p in brief['points'] for tid in p['target_ids']}
    rows = []
    for t in brief['targets']:
        for d in t['directions']:
            did = d['direction_id']
            if did in ready:
                rows.append({'direction_id': did, 'ready': True, 'reasons': []})
                continue
            reasons = []
            evidence = [e for e in a['direction_evidence'] if e['direction_id'] == did]
            whole = [e for e in evidence if all(p['location'] == 'answer' for p in e['components'])]
            if scope[did]['status'] == 'unknown':
                reasons.append('coverage-unknown')
            elif not whole:
                reasons.append('no-question')
            else:
                if all(verdict[e['question_id']] != 'ok' for e in whole):
                    reasons.append('question-not-ok')
                if all(e['visual_verdict'] not in ('ok', 'not_applicable') for e in whole):
                    reasons.append('visual')
                if all(any(pre.get((e['question_id'], p)) != 'supported' for p in qs[e['question_id']].get('prerequisites', [])) for e in whole):
                    reasons.append('prerequisite-check')
            if any(rels[r] != 'supported' for r in d['relation_ids']):
                reasons.append('relation')
            if targets[t['target_id']] != 'consistent':
                reasons.append('target')
            if scope[did]['scope_status'] != 'consistent':
                reasons.append('scope')
            if t['target_id'] not in pointed:
                reasons.append('no-point')
            rows.append({'direction_id': did, 'ready': False, 'reasons': reasons or ['dependency']})
    return rows


def readiness_counts(rows):
    counts = {}
    for r in rows:
        for reason in r['reasons'] or ['ready']:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


# ---------------------------------------------------------------- result
MANIFEST_KEYS = {'pipelineVersion', 'inputHash', 'briefHash', 'bankHash', 'model', 'runtimeHash', 'stages', 'verdictLedger',
                 'verdictLedgerHash', 'addRounds', 'notReady', 'offGoalQuestions', 'rejectedAtIntake', 'supplement',
                 'initialBank', 'initialBrief', 'supplementPoints', 'intakeProjection', 'coverage', 'mapCheck', 'itemReviews', 'clinicalContext',
                 'clinicalConflicts', 'medicalFinal', 'contextJudgments', 'medicalUnreviewed', 'readiness',
                 'sourceAssessment', 'fixes'}


def validate_result(value, packet):
    """Artifacts, document and add-only invariants of a /3 result. The stage-proof chain is checked with
    the generator's stage names (PR B)."""
    return check_result(value, packet, FLAVOR)


def check_result(value, packet, flavor):
    """The checks /3 and /4 share (/4: docs/changes/2026-11-10-importance-at-authoring). `flavor` names the
    policy, its manifest keys and its judgment/assembly part."""
    POLICY = flavor['policy']
    require(set(value) == {'brief', 'document', 'sourceAudit', 'medical', 'validation', 'manifest'}, 'result3: unknown/missing artifacts')
    meta = value['manifest']
    require(flavor['keys'] <= set(meta), 'result3: incomplete manifest')
    require(meta['pipelineVersion'] == POLICY, f'result3: not a {POLICY} result')
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
    # /4 review-evidence/1: notes citations aligned to the review evidence are compared in their intake form.
    unalign = flavor.get('unalign')
    if unalign is None:
        require('citationAlignments' not in meta and 'reviewEvidence' not in meta, 'result3: citation alignments are a /4 record')
    intake_form = unalign(meta, final) if unalign else final
    off = {r['question_id'] for r in meta['offGoalQuestions']}
    for q in meta['initialBank']['questions']:
        qid = q['question_id']
        require(qid in final or qid in off or qid in {r['question_id'] for r in meta['rejectedAtIntake']},
                'result3: an intake question disappeared')
        if qid in final and qid not in fixed:
            strip = lambda x: {k: ([p for p in v if p not in off] if k == 'prerequisites' else v) for k, v in x.items()
                               if k not in ('stimuli', 'tier', 'importance', 'concept_id', 'point_ids')}
            require(strip(intake_form[qid]) == strip(q), f'result3: {qid} changed without a fix')
    tasks = {t['question_id'] for t in doc['tasks']}
    require(not tasks & off, 'result3: an out-of-scope question became a task')
    # The audit is the compile of the gathered judgments on the reviewed bank; the document is its assembly.
    flavor['judgments'](value, packet, brief, reviewed, meta, doc)
    _check_stages(value, packet, reviewed, meta, POLICY, flavor.get('prefix', 'v3-'))
    return doc


def _judgments3(value, packet, brief, reviewed, meta, doc):
    """/3: the audit is the /2 compile; not-ready goals have no task; tiers come from the point table."""
    from .source_assessment import envelope
    raw = assessment_raw(brief, reviewed, meta['coverage'], meta['mapCheck'], meta['itemReviews'],
                         context_summary(meta['clinicalContext']), meta['sourceAssessment']['summary'])
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
    require(meta['readiness'] == readiness(brief, reviewed, raw, doc), 'result3: the readiness table is not of these judgments')


FLAVOR = {'policy': POLICY, 'keys': MANIFEST_KEYS, 'judgments': _judgments3}


def _check_stages(value, packet, reviewed, meta, POLICY, X='v3-'):
    """X: the stage-name prefix of the policy (v3- for /3, v4- for /4)."""
    # Stage records: fingerprints of the stages whose output the result carries.
    stages = {s['name']: s for s in meta['stages']}
    require(all(s['status'] == 'completed' for s in stages.values()), 'result3: incomplete stages')
    require(all(re.fullmatch(r'[a-f0-9]{64}', s.get(k, '')) for s in stages.values() for k in ('inputHash', 'outputHash')),
            'result3: missing stage fingerprints')
    require(stages['normalize']['outputHash'] == document_hash(meta['initialBrief']), 'result3: initial brief proof mismatch')
    # The context is judged per conflict record: once, and once more for what one repair round touched. The
    # merged judgment covers every conflict record of the final bank; only facts judged consistent reach the
    # medical review (docs/changes/2026-11-10-gen3-item-scope).
    require(not any(re.fullmatch(r'(?:v[34]-)?context-\d+', n) and n not in (X + 'context-0', X + 'context-1') for n in stages),
            'result3: the context is judged at most twice, per conflict')
    judgments = meta['contextJudgments']
    require(type(judgments) is list and len(judgments) == (2 if X + 'context-1' in stages else 1) and X + 'context-0' in stages,
            'result3: context judgments differ from the context stages')
    require(all(stages[f'{X}context-{i}']['outputHash'] == document_hash(j) for i, j in enumerate(judgments)), 'result3: context proof mismatch')
    repairs = meta.get('contextRepairs') or []
    require((X + 'context-1' in stages) <= bool(repairs) and (X + 'fix-context-0' in stages) <= bool(repairs),
            'result3: a second context judgment needs its repair record')
    merged = context_merge(judgments[0], judgments[1] if len(judgments) == 2 else None, reviewed, meta['clinicalConflicts'],
                           repairs[0]['targets'] if repairs else ())
    require(merged == meta['clinicalContext'], 'result3: the clinical context is not the merged judgments')
    clinical_input, left_out = medical_parts(reviewed, context_sent(meta['clinicalConflicts'], meta['clinicalContext']))
    med_input = {'title': packet['title'], 'bank': reviewed, 'clinicalInput': clinical_input,
                 'medicalFinal': True, '_pipeline_version': POLICY}
    require(stages['medical-0']['inputHash'] == document_hash(med_input) and stages['medical-0']['outputHash'] == document_hash(value['medical']),
            'result3: the medical review is not of this bank')
    unreviewed = {r['question_id'] for r in meta['medicalUnreviewed']}
    require(set(left_out) <= unreviewed, 'result3: a question left out of the medical review is not recorded')
    rows = {r['question_id']: r for r in value['medical']['reviews']}
    require(all(q in rows and rows[q]['verdict'] == 'doubt' and rows[q]['note'].startswith(UNREVIEWED_NOTE) for q in unreviewed),
            'result3: an unreviewed question carries a medical verdict')
    require(not any(re.fullmatch(r'medical-[1-9]\d*', n) for n in stages), 'result3: the medical review runs once')
    require(meta['addRounds'] == len([n for n in stages if re.fullmatch(re.escape(X) + r'add-\d+', n)]), 'result3: add rounds differ from add stages')
    for f in meta['fixes']:
        require(f['stage'] in stages, 'result3: a fix without its stage')
