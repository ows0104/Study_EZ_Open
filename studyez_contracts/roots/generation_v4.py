"""root-generation/4 contracts: exam points are a coverage checklist (docs/changes/2026-11-10-importance-at-authoring).

The /3 stages, their inputs and their proof chain are reused. What changes (spec R1-R8):
- Exam points carry no importance. Authoring writes a basis per question; it travels beside the bank
  (manifest `questionImportance`) because bank 3.3 questions take no extra field (R1, R2).
- A goal is covered when every component is asked as an answer by some question: the union, not one
  question that answers it all (R5).
- Every question whose source verdict is ok is a task, except true duplicates merged by the coverage
  judgment (R6). The medical review never removes a task (medical-final/1).
- Importance, target, scope and visual judgments never decide a task; they steer what is added and are
  recorded (R3, R7). Unreviewed relations still cannot be tested (learning_links contract).
Pure functions only: no model, DB or server.
"""
import copy

from studyez_contracts.learning_links.schema import obj, arr, TEXT
from studyez_contracts.learning_links.validate import require, validate_shape, index_by
from studyez_contracts.bank import importance as imp
from .validate import document_hash, validate_document
from . import generation_v2 as v2
from . import generation_v3 as v3
from . import recall_units as recall

POLICY = 'root-generation/4'
_STRING = {'type': 'string'}

# ---------------------------------------------------------------- stage outputs
POINT = copy.deepcopy(v3.POINT)                       # R1: a point is {point, source_refs}
POINT['properties'].pop('importance_basis')
POINT['required'].remove('importance_basis')
BASIS = copy.deepcopy(v3.POINT['properties']['importance_basis'])

DUPLICATE = obj(question_ids=arr(TEXT, 2), reason=TEXT)
_COVERAGE_ROW = copy.deepcopy(v3.COVERAGE_OUTPUT['properties']['rows']['items'])
_COVERAGE_ROW['properties']['duplicates'] = arr(DUPLICATE)
_COVERAGE_ROW['required'].append('duplicates')
COVERAGE_OUTPUT = copy.deepcopy(v3.COVERAGE_OUTPUT)
COVERAGE_OUTPUT['properties']['rows']['items'] = _COVERAGE_ROW

_REVIEW = copy.deepcopy(v3.ITEM_REVIEW_OUTPUT['properties']['reviews']['items'])
_REVIEW['properties']['importance_note'] = _STRING    # R3: recorded, never a verdict
_REVIEW['required'].append('importance_note')
ITEM_REVIEW_OUTPUT = copy.deepcopy(v3.ITEM_REVIEW_OUTPUT)
ITEM_REVIEW_OUTPUT['properties']['reviews']['items'] = _REVIEW

# R2: authoring outputs name each question's basis beside the questions (bank 3.3 questions take no extra field).
QUESTION_IMPORTANCE = obj(question_id=TEXT, importance_basis=BASIS)


def _with_basis(schema, minimum=1):
    value = copy.deepcopy(schema)
    value['properties']['question_importance'] = arr(QUESTION_IMPORTANCE, minimum)
    value['required'].append('question_importance')
    return value


INTAKE_OUTPUT = _with_basis(v3.INTAKE_OUTPUT)
ADD_OUTPUT = _with_basis(v3.ADD_OUTPUT)
FIX_OUTPUT = _with_basis(v3.FIX_OUTPUT)
SUPPLEMENT_OUTPUT = obj(rows=arr(obj(question_id=TEXT, decision=v3.SUPPLEMENT_OUTPUT['properties']['rows']['items']['properties']['decision'],
                                     point={'anyOf': [POINT, {'type': 'null'}]}, duplicate_of=v3._NULLABLE, reason=TEXT), 1))
OUTPUTS = {**v3.OUTPUTS, 'coverage': COVERAGE_OUTPUT, 'item-review': ITEM_REVIEW_OUTPUT, 'supplement': SUPPLEMENT_OUTPUT,
           'add': ADD_OUTPUT, 'fix': FIX_OUTPUT}


# ---------------------------------------------------------------- importance per question (R2)
def collect_basis(rows, question_ids):
    """`question_importance` rows of an authoring output -> basis by question_id.

    Exactly one row per question the output wrote; an empty list means no basis was found. Contents are
    not judged here (R3); a malformed row is a format error of that stage (no new retry)."""
    require(type(rows) is list, 'v4 authoring: question_importance list required')
    found = {}
    for row in rows:
        require(type(row) is dict and set(row) == {'question_id', 'importance_basis'}, 'v4 authoring: malformed question_importance row')
        qid = row['question_id']
        require(qid not in found, f'v4 authoring: {qid} has two importance rows')
        b = row['importance_basis']
        require(type(b) is list and all(type(x) is dict and set(x) == {'kind', 'refs', 'quote', 'reason', 'year'}
                                         and (x['year'] is None or type(x['year']) is int)
                                         and type(x['refs']) is list and all(type(r) is dict and set(r) == {'source_id', 'pages'} for r in x['refs'])
                                         for x in b), f'v4 authoring: {qid} malformed importance_basis row')
        try:
            imp.validate_basis(b)
        except imp.ImportanceError as e:
            raise ValueError(f'v4 authoring: {qid} {e}') from None
        found[qid] = copy.deepcopy(b)
    missing = [q for q in question_ids if q not in found]
    require(not missing, 'v4 authoring: importance_basis missing for ' + ', '.join(missing) + ' (an empty list when none)')
    require(set(found) <= set(question_ids), 'v4 authoring: importance rows for questions this output did not write')
    return found


def without_basis(value):
    """The /3 shape of a /4 authoring output (for the /3 checks and merges)."""
    return {k: v for k, v in value.items() if k != 'question_importance'}


def check_intake(value):
    """The independent bank (1c) of map-tree/3: /3 shape plus one basis row per question."""
    require(type(value) is dict and set(value) == set(INTAKE_OUTPUT['properties']), 'v4 intake bank: fields')
    validate_shape(without_basis(value), v3.INTAKE_OUTPUT, 'v4 intake bank')
    return collect_basis(value['question_importance'], [q['question_id'] for q in value['bank']['questions']])


def check_added(value, ctx, state=None):
    require(type(value) is dict and set(value) == set(ADD_OUTPUT['properties']), 'v4 add output: fields')
    collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']])
    v3.check_added(without_basis(value), ctx, state)
    return value


def check_fixed(value, ctx, state=None):
    require(type(value) is dict and set(value) == set(FIX_OUTPUT['properties']), 'v4 fix output: fields')
    collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']])
    v3.check_fixed(without_basis(value), ctx, state)
    return value


def check_review_input(value, ctx):
    validate_shape(value, ITEM_REVIEW_OUTPUT, 'v4 review output')
    v3.check_review_input({'reviews': [{k: v for k, v in r.items() if k != 'importance_note'} for r in value['reviews']]}, ctx)
    return value


def _as_v3_points(value):
    """A /4 supplement output or points doc in /3 form (an empty basis on every point) so the /3 checks and
    attach_points run unchanged; the basis is dropped again afterwards."""
    value = copy.deepcopy(value)
    for p in value.get('points', []):
        require('importance_basis' not in p, 'v4: exam points carry no importance (R1)')
        p['importance_basis'] = []
    for r in value.get('rows', []):
        if type(r) is dict and type(r.get('point')) is dict:
            require('importance_basis' not in r['point'], 'v4 supplement: a point carries no importance (R1)')
            r['point']['importance_basis'] = []
    return value


def check_supplement(value, ctx, state=None):
    v3.check_supplement(_as_v3_points(value), ctx, {'points_doc': _as_v3_points(state['points_doc'])} if state is not None else None)
    return value


def attach_points(points_doc, output, off_goal_ids, page_counts):
    """v3.attach_points for /4 points (no basis): returns (points_doc, decisions)."""
    value, _, decisions = v3.attach_points(_as_v3_points(points_doc), _as_v3_points(output), off_goal_ids, page_counts)
    for p in value['points']:
        p.pop('importance_basis')
    return value, decisions


def check_points(points_doc):
    """A /4 exam-point document: schema version, IDs, the notebook profile; no basis on any point."""
    require(type(points_doc) is dict and points_doc.get('schema_version') == 'exam-point-extract/4', 'v4: points are not exam-point-extract/4')
    profile = points_doc.get('notebook_profile')
    require(type(profile) is dict and profile.get('emphasis_style') in imp.STYLES, 'v4: notebook_profile.emphasis_style required')
    ids = [p.get('point_id') for p in points_doc.get('points', [])]
    require(ids and len(ids) == len(set(ids)), 'v4: point IDs')
    require(all('importance_basis' not in p for p in points_doc['points']), 'v4: exam points carry no importance (R1)')
    return points_doc


def question_table(basis, profile, bank):
    """The importance table of the final bank: every question needs its basis, nothing else is accepted."""
    qids = [q['question_id'] for q in bank['questions']]
    require(set(basis) == set(qids), 'v4 importance: every question of the bank needs exactly one basis')
    return imp.question_table({qid: basis[qid] for qid in qids}, profile)


def project_importance(bank, table):
    """Bank 3.3 snapshot: question tier/importance from its own basis, concepts take their questions' max.

    The proof has the /2 shape, so `v2.restore_importance` restores the bank behind it."""
    value = copy.deepcopy(bank)
    rows = table['questions']
    for q in value['questions']:
        d = rows[q['question_id']]
        q.update(tier=d['tier'], importance=d['importance'])
    for c in value['concepts']:
        own = [rows[q['question_id']]['tier'] for q in value['questions'] if q['concept_id'] == c['concept_id']]
        tier = max(own, key=imp.ORDER.get) if own else c['tier']
        c.update(tier=tier, importance=imp.BANK_IMPORTANCE[tier])
    value['build_meta']['schema_version'] = '3.3'
    proof = {'policy': imp.POLICY, 'table': table, 'sourceBankHash': document_hash(bank), 'schemaVersion': bank['build_meta']['schema_version'],
             'original': {x.get('question_id', x.get('concept_id')): {'tier': x['tier'], 'importance': x['importance']}
                          for x in [*bank['questions'], *bank['concepts']]},
             'fallback': []}
    return value, proof


def target_questions(brief, review, bank):
    """Questions of each target: its mappings, else the targets of the question's own exam points."""
    owned = {t['target_id']: [] for t in brief['targets']}
    mapped = set()
    for m in review['mappings']:
        if m['target_id'] in owned and m['question_id'] not in owned[m['target_id']]:
            owned[m['target_id']].append(m['question_id'])
            mapped.add(m['question_id'])
    point_targets = {p['point_id']: p.get('target_ids', []) for p in brief['points']}
    for q in bank['questions']:
        if q['question_id'] in mapped:
            continue
        for pid in q.get('point_ids') or []:
            for tid in point_targets.get(pid, []):
                if tid in owned and q['question_id'] not in owned[tid]:
                    owned[tid].append(q['question_id'])
    return owned


def target_importance(brief, review, bank, table):
    counts = {x['source_id']: x.get('page_count') for x in brief['sources']}
    return {tid: imp.target_axes(table, qids, counts) for tid, qids in target_questions(brief, review, bank).items()}


def importance_warnings(table):
    """Reported, never blocking (spec R2): Must-Know share and one forecast quote on many questions."""
    rows = table['questions']
    _, warn = imp.must_know_share(list(rows.values()))
    spread = imp.forecast_spread([{'point_id': qid, 'importance_basis': r['basis']} for qid, r in rows.items()])
    return {'mustKnow': warn, 'forecastSpread': {k: v for k, v in spread.items() if len(v) > 1}}


def importance_notes(reviews):
    """R3: the item review may doubt a basis; that is a note for the admin, never a verdict."""
    return [{'question_id': r['question_id'], 'note': r['importance_note']} for r in reviews if r.get('importance_note', '').strip()]


def with_importance(ctx, basis):
    """A review/fix input plus the current basis of its questions (the fix copies it unless the content changes;
    the review may note a basis the source contradicts)."""
    return {**ctx, 'question_importance': [{'question_id': q['question_id'], 'importance_basis': copy.deepcopy(basis.get(q['question_id'], []))}
                                           for q in ctx['questions']]}


def map_check_input(brief, target_ids=None):
    """C2m without importance (R3): goals, relations and their cited pages only."""
    value = v3.map_check_input(brief, None, target_ids)
    for row in value['targets']:
        row.pop('importance_basis')
    return value


# ---------------------------------------------------------------- coverage (R5)
def answered(evidence):
    return {p['component_id'] for p in evidence['components'] if p['location'] == 'answer'}


def full(row, goal):
    """Every component answered by some question, and a visual goal asked through an identified image."""
    comps = {c['component_id'] for c in goal['components']}
    union = set().union(*(answered(e) for e in row['evidence'])) if row['evidence'] else set()
    visual = (not goal['requires_visual']) or any(answered(e) and e['visual_verdict'] == 'ok' for e in row['evidence'])
    return union == comps and visual


def check_coverage(value, goals, questions):
    """/3 shape and references; covered is the union of answered components (R5); duplicates are named
    only among questions that answer in that goal, and one question sits in at most one group."""
    validate_shape(value, COVERAGE_OUTPUT, 'v4 coverage output')
    rows = index_by(value['rows'], 'direction_id')
    require(set(rows) == {g['direction_id'] for g in goals}, 'v4 coverage: one row per goal')
    qids = {q['question_id'] for q in questions}
    goals = {g['direction_id']: g for g in goals}
    units = {q['question_id']: len(q.get('answer_units', [])) for q in questions}
    for did, row in rows.items():
        allowed = {r['relation_id'] for r in goals[did]['relations']}
        comps = {c['component_id'] for c in goals[did]['components']}
        index_by(row['evidence'], 'question_id')
        for e in row['evidence']:
            require(e['question_id'] in qids, 'v4 coverage: evidence names a question outside the batch')
            require(set(e['tested_relation_ids']) <= allowed, 'v4 coverage: tested relation outside the goal')
            require({p['component_id'] for p in e['components']} == comps, 'v4 coverage: each component needs evidence')
            for p in e['components']:
                ix = p['answer_unit_indices']
                require(len(ix) == len(set(ix)) and all(i < units[e['question_id']] for i in ix), 'v4 coverage: nonexistent answer unit')
                require(bool(ix) == (p['location'] == 'answer'), 'v4 coverage: only answer units are recalled evidence')
        if row['status'] != 'unknown':
            want = 'covered' if full(row, goals[did]) else 'missing'
            require(row['status'] == want, f'v4 coverage: {did} is {want} by its evidence (union of answered components)')
        # A duplicate group names questions the judgment reviewed for this goal (its evidence rows), whether or not
        # they answer a whole component (docs/changes/2026-11-11-place-by-evidence).
        asking = {e['question_id'] for e in row['evidence']}
        seen = set()
        for g in row['duplicates']:
            require(set(g['question_ids']) <= asking, 'v4 coverage: a duplicate group names a question that does not answer this goal')
            require(not seen & set(g['question_ids']), 'v4 coverage: a question is in two duplicate groups')
            seen |= set(g['question_ids'])
    require(any(r['status'] != 'unknown' for r in value['rows']), v3.UNPERFORMED_COVERAGE)
    return value


def covering(row):
    """Questions that ask some component of the goal as an answer."""
    if row['status'] == 'unknown':
        return []
    return [e['question_id'] for e in row['evidence'] if answered(e)]


def missing_components(row, goal):
    """Components no question answers: what an add stage fills (R5)."""
    union = set().union(*(answered(e) for e in row['evidence'])) if row['evidence'] else set()
    return [c['component_id'] for c in goal['components'] if c['component_id'] not in union]


def add_input(brief, bank, gaps, allowed_ids):
    """C3 for /4: each gap goal carries only its unasked components (gaps: direction_id -> component ids).
    A visual goal whose components are all asked but not through an image keeps its components."""
    value = v3.add_input(brief, bank, list(gaps), allowed_ids)
    for goal in value['goals']:
        keep = set(gaps[goal['direction_id']])
        if keep:
            goal['components'] = [c for c in goal['components'] if c['component_id'] in keep]
        goal['missing_component_ids'] = sorted(keep)
    return value


def not_ready(brief, coverage_rows, reviews):
    """Goals not fully asked yet, with the reason (reported; never removes a task)."""
    rows = index_by(coverage_rows, 'direction_id')
    verdict = {r['question_id']: r['verdict'] for r in reviews}
    out = []
    for t in brief['targets']:
        for d in t['directions']:
            row = rows.get(d['direction_id'])
            qids = covering(row) if row else []
            if row is None or row['status'] == 'unknown':
                out.append({'direction_id': d['direction_id'], 'reason': 'coverage-unknown'})
            elif not qids:
                out.append({'direction_id': d['direction_id'], 'reason': 'no-question'})
            elif row['status'] != 'covered':
                out.append({'direction_id': d['direction_id'], 'reason': 'visual' if not missing_components(row, d) else 'partial'})
            elif all(verdict.get(q) == 'wrong' for q in qids):
                out.append({'direction_id': d['direction_id'], 'reason': 'question-defect'})
    return out


# ---------------------------------------------------------------- assessment and compile
def assessment_raw(brief, bank, coverage_rows, map_check, reviews, context, summary):
    """source-assessment/2 from the /4 judgments. A question claims the tested relations its evidence row names
    for every goal the coverage judgment reviewed it against, whether or not it answers a whole component: placing a
    question follows the evidence, completeness (`full`) follows the answered components
    (docs/changes/2026-11-11-place-by-evidence). Nothing is filled in."""
    dirs = v3._directions(brief)
    rows = index_by(coverage_rows, 'direction_id')
    require(set(rows) == set(dirs), 'v4 assembly: every goal needs a coverage judgment')
    qs = {q['question_id'] for q in bank['questions']}
    reviews = index_by(reviews, 'question_id')
    require(set(reviews) == qs, 'v4 assembly: every question needs an item review')
    v3.check_map(map_check, brief)
    v2.validate_context(context)
    scope = {r['direction_id']: r for r in map_check['direction_checks']}
    claims, evidence = {}, []
    for did, row in rows.items():
        if row['status'] == 'unknown':
            continue
        for e in row['evidence']:
            require(e['question_id'] in qs, 'v4 assembly: coverage names a missing question')
            evidence.append({k: copy.deepcopy(e[k]) for k in ('question_id', 'components', 'visual_verdict', 'reason')} | {'direction_id': did})
            for rid in e['tested_relation_ids']:
                claims.setdefault((e['question_id'], rid), set()).add(did)
    question_reviews = []
    for q in bank['questions']:
        qid = q['question_id']
        r = reviews[qid]
        relations = [{'relation_id': rid, 'role': 'tested', 'direction_ids': sorted(ds), 'reason': 'v4 coverage judgment'}
                     for (cq, rid), ds in sorted(claims.items()) if cq == qid]
        question_reviews.append({'question_id': qid, 'verdict': r['verdict'], 'note': r['note'] or 'v4 문항 검토: 지적 없음',
                                 'suggested_answer': r['suggested_answer'], 'relations': relations})
    issues = []

    def issue(kind, text, question_ids, direction_ids):
        issues.append({'issue_id': f'I{len(issues) + 1:03d}', 'kind': kind, 'text': text,
                       'question_ids': question_ids, 'direction_ids': direction_ids})
    for row in map_check['issues']:
        issue('map_fix', row['text'], [], list(row['direction_ids']))
    for qid, r in reviews.items():
        if v3.needs_fix(r):
            issue('question_fix', r['note'] or r['fix'] or 'v4 item review', [qid], [])
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
        'design_checks': [{'question_id': qid, 'verdict': r['design'], 'reason': r['note'] or 'v4 item review'} for qid, r in reviews.items()],
    }
    if not recall.enabled(brief):
        value.pop('design_checks')
    validate_shape(value, v2.SOURCE, 'v4 assembly: source-assessment/2')
    return value


def compile_assessment(brief, bank, raw):
    """The /2 compile with the /4 acceptance: a question tests a goal where it answers one of its
    components and its relation is supported. Visual, target, scope, prerequisite and clinical-context
    judgments stay in the audit notes and do not decide (R7)."""
    v2.validate_brief(brief)
    require(raw == v2.envelope(brief, bank, raw.get('assessment')), 'assessment4: input revision mismatch')
    validate_shape(raw['assessment'], v2.SOURCE, 'assessment4')
    v2.require_judgment(raw['assessment'])
    if not recall.enabled(brief):
        return _compile(brief, bank, raw)
    projected, proof, groups = recall.project_assessment(brief, bank, raw)
    audit = _compile(projected, bank, proof)
    audit['assessment'] = copy.deepcopy(raw)
    audit['goal_coverage'] = recall.summarize(groups, audit)
    return audit


def _compile(brief, bank, raw):
    """v2._compile_assessment with the /4 acceptance predicate (kept apart so /2 and /3 stay byte-identical)."""
    from .source_assessment import compile_source_assessment as compile1
    v2.validate_brief(brief)
    v2.validate_images(bank, brief['sources'])
    require(type(raw) is dict and set(raw) == {'briefHash', 'bankHash', 'assessment'}, 'assessment4: malformed input envelope')
    a = raw['assessment']
    dirs = {d['direction_id']: (t, d) for t in brief['targets'] for d in t['directions']}
    qs = index_by(bank['questions'], 'question_id')
    rels = index_by(a['relation_checks'], 'relation_id')
    targets = index_by(a['target_checks'], 'target_id')
    question_reviews = index_by(a['question_reviews'], 'question_id')
    require(set(question_reviews) == set(qs), 'assessment4: every question needs one review')
    direction_checks = index_by(a['direction_checks'], 'direction_id')
    require(set(direction_checks) == set(dirs), 'assessment4: missing direction checks')
    require(set(rels) == {r['relation_id'] for r in brief['relations']}, 'assessment4: missing relation checks')
    require(set(targets) == {t['target_id'] for t in brief['targets']}, 'assessment4: missing target checks')
    pres = {(q['question_id'], p) for q in bank['questions'] for p in q.get('prerequisites', [])}
    pre_checks = {(r['question_id'], r['prerequisite_id']): r for r in a['prerequisite_checks']}
    require(len(pre_checks) == len(a['prerequisite_checks']) and set(pre_checks) == pres, 'assessment4: every prerequisite needs one check')
    evid, asks = {}, set()
    for row in a['direction_evidence']:
        key = (row['question_id'], row['direction_id'])
        require(key not in evid, 'assessment4: duplicate evidence')
        qid, did = key
        require(qid in qs and did in dirs, 'assessment4: unknown evidence reference')
        _, d = dirs[did]
        parts = index_by(row['components'], 'component_id')
        require(set(parts) == {c['component_id'] for c in d['components']}, 'assessment4: each component needs explicit evidence')
        for part in parts.values():
            ix = part['answer_unit_indices']
            require(len(ix) == len(set(ix)) and all(i < len(qs[qid]['answer_units']) for i in ix), 'assessment4: nonexistent answer unit')
            require(bool(ix) == (part['location'] == 'answer'), 'assessment4: only actual answer units are recalled evidence')
        asks.add(key)       # placement follows the evidence row (2026-11-11-place-by-evidence), not the answered parts
        evid[key] = row
    for row in a['issues']:
        require(set(row['question_ids']) <= set(qs) and set(row['direction_ids']) <= set(dirs), 'assessment4: issue references missing objects')
        if row['kind'] == 'required_gap':
            require(row['direction_ids'] and all(dirs[d][1]['requirement'] == 'required' for d in row['direction_ids']),
                    'assessment4: required gaps must reference required directions; unmapped goals need map_fix')
    index_by(a['issues'], 'issue_id')
    projected = v2.legacy_brief(brief)
    for r in projected['relations']:
        r['review_status'] = 'reviewed' if rels[r['relation_id']]['status'] == 'supported' else 'unreviewed'
    rows = copy.deepcopy(a['question_reviews'])
    for row in rows:
        qid, kept = row['question_id'], []
        for claim in row['relations']:
            if claim['role'] == 'tested':
                if rels[claim['relation_id']]['status'] != 'supported':
                    continue                     # learning_links: an unreviewed relation cannot be tested
                claim['direction_ids'] = [d for d in claim['direction_ids'] if (qid, d) in asks and row['verdict'] == 'ok']
            kept.append(claim)
        row['relations'] = kept
    projected_checks = [{'direction_id': c['direction_id'], 'status': c['status'], 'reason': c['reason']} for c in a['direction_checks']]
    old = {'schema_version': 'source-assessment/1', 'summary': a['summary'], 'question_reviews': rows,
           'direction_checks': projected_checks, 'input_issues': list(dict.fromkeys(i['text'] for i in a['issues']))}
    audit = compile1(projected, bank, v2.envelope(projected, bank, old))
    audit['review']['schema_version'] = 'learning-links/2'
    audit['review']['targets'] = copy.deepcopy(brief['targets'])
    audit['review']['provenance']['method'] = POLICY + '; ' + v2.VERSION + '; deterministic reference adapter; ' + brief['provenance']['method']
    labels = {'provided': '발문에서 제공', 'explanation': '해설에만 있음', 'missing': '직접 회상 없음', 'unknown': '판단 보류'}
    for coverage in audit['review']['coverage']:
        relevant = set(coverage['confirmed_direction_ids'] + coverage['partial_direction_ids'] + coverage['missing_direction_ids']
                       + coverage['unknown_direction_ids'])
        notes = []
        for row in a['direction_evidence']:
            if row['direction_id'] not in relevant:
                continue
            if row['visual_verdict'] in ('doubt', 'wrong'):
                notes.append(row['direction_id'] + ': 그림 확인 필요 · ' + row['reason'])
        for did in sorted(relevant):
            if direction_checks[did]['scope_status'] != 'consistent':
                notes.append(did + ': ' + direction_checks[did]['reason'])
            target = dirs[did][0]
            if targets[target['target_id']]['status'] != 'consistent':
                notes.append(did + ': ' + targets[target['target_id']]['reason'])
        if notes:
            coverage['reason'] += '; ' + '; '.join(dict.fromkeys(notes))
    audit.update(schema_version='source-audit/2', assessment=copy.deepcopy(raw))
    return audit


def validate_audit(brief, bank, audit):
    require(v2.equivalent_audit(audit, compile_assessment(brief, bank, audit['assessment'])), 'audit4: derived result differs from raw judgments')
    return audit


# ---------------------------------------------------------------- tasks (R6, R7)
def merged_duplicates(coverage_rows, bank, verdict, placeable=None):
    """One task per true-duplicate group. The kept member is an ok, placeable question: one already kept for
    another group if the group has one (a keeper is never merged away), else the highest importance, then
    bank order. The others stay in the bank and are recorded (question_id, kept, direction_id, reason)."""
    order = {q['question_id']: i for i, q in enumerate(bank['questions'])}
    importance = {q['question_id']: q['importance'] for q in bank['questions']}
    merged, keepers = {}, set()
    for row in coverage_rows:
        if row['status'] == 'unknown':
            continue
        for g in row.get('duplicates', []):
            ok = [q for q in g['question_ids'] if q in order and q not in merged and verdict.get(q) == 'ok'
                  and (placeable is None or q in placeable)]
            if len(ok) < 2:
                continue
            kept = [q for q in ok if q in keepers]
            keep = min(kept or ok, key=lambda q: (-importance[q], order[q]))
            keepers.add(keep)
            for q in ok:
                if q != keep and q not in keepers:
                    merged[q] = {'question_id': q, 'kept': keep, 'direction_id': row['direction_id'], 'reason': g['reason']}
    return [merged[q] for q in sorted(merged, key=order.get)]


def unit_parents(brief):
    """Recall-unit direction id -> its parent direction id (identity without recall units)."""
    if not recall.enabled(brief):
        return {d['direction_id']: d['direction_id'] for t in brief['targets'] for d in t['directions']}
    _, groups = recall.project_brief(brief)
    return {u: g['direction_id'] for g in groups for u in g['unit_direction_ids']}


def place(brief, review, raw, parents=None):
    """The direction of each mapped question: most components answered there, then map order.
    `parents`: recall-unit id -> the parent id the raw evidence uses (identity without recall units)."""
    order = {d['direction_id']: i for i, d in enumerate(d for t in brief['targets'] for d in t['directions'])}
    count = {(e['question_id'], e['direction_id']): len(answered(e)) for e in raw['direction_evidence']}
    parents = parents or {}
    best = {}
    for m in review['mappings']:
        if not m['tested_relation_ids']:
            continue
        key = (-count.get((m['question_id'], parents.get(m['direction_id'], m['direction_id'])), 0), order[m['direction_id']])
        if m['question_id'] not in best or key < best[m['question_id']][0]:
            best[m['question_id']] = (key, m['direction_id'])
    return {q: did for q, (_, did) in best.items()}


def make_document(brief, bank, audit, coverage_rows, *, revision, title, exam_date, snapshot=None, importance=None):
    """roots/1 document of a /4 run and its placement record {mergedDuplicates, unplacedQuestions}.

    `snapshot`/`importance` as in /2 (container concepts, question-basis importance)."""
    validate_audit(brief, bank, audit)
    parents = unit_parents(brief)
    if recall.enabled(brief):
        brief = recall.project_brief(brief)[0]
    review = audit['review']
    verdict = {r['question_id']: r['verdict'] for r in audit['question_checks']['reviews']}
    where = place(brief, review, audit['assessment']['assessment'], parents)
    weighed = snapshot if snapshot is not None else bank
    merged = merged_duplicates(coverage_rows, weighed, verdict, set(where))
    gone = {m['question_id'] for m in merged}
    candidates, unplaced = [], []
    for q in bank['questions']:
        qid = q['question_id']
        if verdict[qid] != 'ok' or qid in gone:
            continue
        if qid not in where:
            unplaced.append({'question_id': qid, 'reason': 'no-goal: 어느 목표의 component도 답으로 묻지 않거나 그 관계가 검토되지 않았다'})
            continue
        candidates.append({'task_id': 'task-' + document_hash([qid, where[qid]])[:24], 'question_id': qid, 'direction_id': where[qid]})
    order = v2.graph_order(bank)
    qs = {q['question_id']: q for q in bank['questions']}
    owners = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    reviewed_relations = {r['relation_id'] for r in review['relations'] if r['review_status'] == 'reviewed'}
    while True:
        prepared = {t['question_id'] for t in candidates}
        kept = [t for t in candidates if set(qs[t['question_id']].get('prerequisites', [])) <= prepared]
        if kept == candidates:
            break
        for t in candidates:
            if t not in kept:
                unplaced.append({'question_id': t['question_id'], 'reason': 'dependency: 선행 문항이 과제가 아니다'})
        candidates = kept
    prepared_targets = {owners[t['direction_id']] for t in candidates}
    edges = [e for e in brief['prerequisites'] if e['relation_id'] in reviewed_relations and e['before_target'] in prepared_targets]
    candidates.sort(key=lambda t: order.index(t['question_id']))
    doc = {'schema_version': 'roots/1', 'generation_policy': POLICY, 'revision': revision, 'title': title,
           'review': review, 'bank_snapshot': bank, 'bank_source': 'standalone', 'bank_build_id': None,
           'adopted_target_ids': [t['target_id'] for t in brief['targets']], 'tasks': candidates, 'exam_date': exam_date,
           'equivalences': [], 'prerequisites': edges}
    doc['tasks'] = [{k: t[k] for k in ('task_id', 'question_id', 'direction_id')}
                    for t in v2.order_plan(doc, candidates, {t['task_id'] for t in candidates}, set())]
    if snapshot is not None:
        strip = lambda rows: [{k: v for k, v in q.items() if k not in ('tier', 'importance')} for q in rows]
        require(snapshot['questions'] == bank['questions'] or (importance is not None and strip(snapshot['questions']) == strip(bank['questions'])),
                'container projection changed questions')
        from studyez_contracts.learning_links.validate import question_hash
        review = copy.deepcopy(review)
        qmap = {q['question_id']: q for q in snapshot['questions']}
        review['bank_sha256'] = document_hash(snapshot)
        for m in review['mappings']:
            m['question_sha256'] = question_hash(qmap[m['question_id']], snapshot)
        doc.update(review=review, bank_snapshot=snapshot)
    if importance is not None:
        review = copy.deepcopy(doc['review'])
        for t in review['targets']:
            if t['target_id'] in importance:
                t['importance'] = copy.deepcopy(importance[t['target_id']])
        doc['review'] = review
    unplaced.sort(key=lambda r: order.index(r['question_id']))
    return validate_document(doc), {'mergedDuplicates': merged, 'unplacedQuestions': unplaced}


def notebook_profile(packet, meta):
    """The lecture-level notebook profile stays with the exam points (R1); a /4 packet must carry it."""
    import json
    try:
        points = json.loads(packet.get('points') or 'null')
    except (TypeError, ValueError):
        points = None
    require(type(points) is dict and type(points.get('notebook_profile')) is dict, 'result4: the exam points carry no notebook profile')
    if meta['supplementPoints'] is not None:
        extended = meta['supplementPoints']
        require(extended['points'][:len(points['points'])] == points['points'] and extended['notebook_profile'] == points['notebook_profile'],
                'result4: supplement changed the exam points')
        require(all(p.get('origin') == 'question' and 'importance_basis' not in p for p in extended['points'][len(points['points']):]),
                'result4: unmarked supplement point or a point with importance')
    else:
        require(not meta['supplement'], 'result4: supplement decisions without points')
    require(all('importance_basis' not in p for p in points['points']), 'result4: /4 exam points carry no importance (R1)')
    return points['notebook_profile']


def assemble(brief, reviewed, audit, coverage_rows, basis, profile, *, revision, title, exam_date):
    """Importance from the question basis, container concepts, then the /4 document (one function for the
    generator and the consumer, so both build the same thing)."""
    table = question_table(basis, profile, reviewed)
    snapshot, projection = v2.project_container_concepts(reviewed)
    snapshot, proof = project_importance(snapshot, table)
    doc, placed = make_document(brief, reviewed, audit, coverage_rows, revision=revision, title=title, exam_date=exam_date,
                                snapshot=snapshot, importance=target_importance(brief, audit['review'], reviewed, table))
    return doc, placed, {'bankProjection': projection, 'importanceProjection': proof, 'importanceWarnings': importance_warnings(table)}


def _judgments4(value, packet, brief, reviewed, meta, doc):
    raw = assessment_raw(brief, reviewed, meta['coverage'], meta['mapCheck'], meta['itemReviews'],
                         v3.context_summary(meta['clinicalContext']), meta['sourceAssessment']['summary'])
    require(raw == meta['sourceAssessment'], 'result4: assessment is not the gathered judgments')
    require(value['sourceAudit'] == compile_assessment(brief, reviewed, v2.envelope(brief, reviewed, raw)), 'result4: audit is not the compile')
    require(meta['notReady'] == not_ready(brief, meta['coverage'], meta['itemReviews']), 'result4: not-ready goals differ')
    profile = notebook_profile(packet, meta)
    again, placed, proofs = assemble(brief, reviewed, value['sourceAudit'], meta['coverage'], meta['questionImportance'], profile,
                                     revision=packet['revision'], title=packet['title'], exam_date=packet['examDate'])
    require(proofs['bankProjection'] == meta.get('bankProjection') and proofs['importanceProjection'] == meta.get('importanceProjection'),
            'result4: projections differ')
    require(again == doc, 'result4: the document is not the assembly of the reviewed judgments')
    require(placed == {k: meta[k] for k in placed}, 'result4: merged duplicates or unplaced questions differ')
    require(meta['readiness'] == readiness(brief, meta['coverage'], doc), 'result4: the readiness table is not of these judgments')
    require(meta['importanceNotes'] == importance_notes(meta['itemReviews']), 'result4: importance notes differ from the item reviews')
    # The basis of an intake question nobody fixed is the intake bank's (added/fixed ones come from their stages).
    intake = {r['question_id']: r['importance_basis'] for r in packet['intakeBank'].get('question_importance', [])}
    fixed = {f['question_id'] for f in meta['fixes'] if not f['reverted']}
    for qid, b in meta['questionImportance'].items():
        if qid in intake and qid not in fixed:
            require(b == intake[qid], f'result4: {qid} importance basis differs from the intake bank')


MANIFEST_KEYS = v3.MANIFEST_KEYS | {'questionImportance', 'mergedDuplicates', 'unplacedQuestions', 'importanceNotes'}
FLAVOR = {'policy': POLICY, 'keys': MANIFEST_KEYS, 'judgments': _judgments4, 'prefix': 'v4-'}


def validate_result(value, packet):
    """A /4 result: the /3 checks (artifacts, add-only, stages, context, medical) with the /4 judgments."""
    return v3.check_result(value, packet, FLAVOR)


def readiness(brief, coverage_rows, doc):
    """Per goal: does it have a task, is it fully asked, and why not (a coverage report, never a gate)."""
    rows = index_by(coverage_rows, 'direction_id')
    parents = unit_parents(brief)
    tasks = {}
    for t in doc['tasks']:
        did = parents.get(t['direction_id'], t['direction_id'])
        tasks[did] = tasks.get(did, 0) + 1
    out = []
    for t in brief['targets']:
        for d in t['directions']:
            did = d['direction_id']
            row = rows[did]
            reasons = []
            if row['status'] == 'unknown':
                reasons.append('coverage-unknown')
            elif row['status'] != 'covered':
                reasons.append('partial' if missing_components(row, d) else 'visual')
            out.append({'direction_id': did, 'tasks': tasks.get(did, 0), 'covered': row['status'] == 'covered', 'reasons': reasons})
    return out
