"""root-generation/3 contracts (docs/changes/2026-11-10-root-generation-3/spec.md). Pure functions, synthetic data."""
import copy
import json
from pathlib import Path

import pytest
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as c
from studyez_contracts.roots.automation import validate_result as consume
from studyez_contracts.roots.source_assessment import envelope
from studyez_contracts.roots import document_hash

ROOT = Path(__file__).resolve().parents[2]


def answer(*units):
    return [{'component_id': 'fact', 'location': 'answer', 'answer_unit_indices': list(units), 'reason': 'Synthetic recall'}]


def row(did, status, qid=None, rid=None, location='answer'):
    evidence = []
    if qid:
        parts = answer(0) if location == 'answer' else [{'component_id': 'fact', 'location': location, 'answer_unit_indices': [], 'reason': 'x'}]
        evidence.append({'question_id': qid, 'tested_relation_ids': [rid] if rid else [], 'components': parts,
                         'visual_verdict': 'not_applicable', 'reason': 'Synthetic'})
    return {'direction_id': did, 'status': status, 'evidence': evidence, 'reason': 'Synthetic coverage'}


def covered(b):
    return [row('D1', 'covered', 'Q1', 'R1'), row('D2', 'covered', 'Q2', 'R2')]


def map_ok(b):
    return {'relation_checks': [{'relation_id': r['relation_id'], 'status': 'supported', 'reason': 'Synthetic'} for r in b['relations']],
            'target_checks': [{'target_id': t['target_id'], 'status': 'consistent', 'reason': 'Synthetic'} for t in b['targets']],
            'direction_checks': [{'direction_id': d['direction_id'], 'scope_status': 'consistent', 'reason': 'Synthetic'}
                                 for t in b['targets'] for d in t['directions']], 'issues': []}


def review(qid, verdict='ok', design='ok'):
    return {'question_id': qid, 'verdict': verdict, 'design': design, 'note': '' if verdict == 'ok' else 'Synthetic note',
            'suggested_answer': '', 'fix': '', 'prerequisite_checks': []}


CONTEXT = {'clinical_context_status': 'consistent', 'clinical_context_reason': 'Synthetic', 'clinical_context_problem': 'none'}


def authored_bank():
    bank = f.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
    return bank


def question(qid, base):
    q = copy.deepcopy(base)
    q.pop('stimuli', None)
    q['question_id'] = qid
    q['question'] = 'Synthetic new question ' + qid
    return q


# ---------------------------------------------------------------- schemas and inputs
def test_supplement_point_has_the_exam_point_extract_form():
    content = json.loads((ROOT / 'content/prompts/learning-links/point-output-v3.schema.json').read_text(encoding='utf-8'))
    item = copy.deepcopy(content['properties']['points']['items'])
    item['properties'].pop('point_id')
    item['required'].remove('point_id')
    assert c.POINT == item


def test_coverage_input_carries_goals_and_fronts_only():
    b, bank = f.brief(), f.old.bank()
    value = c.coverage_input(b, bank)
    assert set(value) == {'goals', 'questions'}
    assert [g['direction_id'] for g in value['goals']] == ['D1', 'D2']
    q = value['questions'][0]
    assert 'explanation' not in q and 'option_explanations' not in q and 'exam_rationale' not in q and 'source_refs' not in q
    assert set(value['goals'][0]) == {'direction_id', 'target_id', 'cue', 'answer_scope', 'components', 'requires_visual', 'relations'}
    narrow = c.coverage_input(b, bank, ['D2'], ['Q2'])
    assert [g['direction_id'] for g in narrow['goals']] == ['D2'] and [q['question_id'] for q in narrow['questions']] == ['Q2']
    with pytest.raises(ValueError):
        c.coverage_input(b, bank, ['D9'])


def test_add_input_has_gap_goals_fronts_and_allowed_ids_only():
    b, bank = f.brief(), f.old.bank()
    ids = c.next_question_ids(bank, 2)
    assert ids == ['Q003', 'Q004']
    value = c.add_input(b, bank, ['D2'], ids)
    assert set(value) == {'goals', 'existing', 'bank_concepts', 'source_conflict_ids', 'allowed_question_ids', 'pages'}
    assert set(value['existing'][0]) == {'question_id', 'question', 'answer'}
    assert value['goals'][0]['point_ids'] == ['P1']


def test_review_input_is_the_batch_its_prerequisites_and_cited_facts():
    b, bank = f.brief(), f.old.bank()
    bank['questions'][1]['prerequisites'] = ['Q1']
    value = c.review_input(bank, ['Q2'], [])
    assert [q['question_id'] for q in value['questions']] == ['Q2']
    assert [q['question_id'] for q in value['prerequisites']] == ['Q1']
    assert 'explanation' not in value['prerequisites'][0]


def test_locator_pages_and_cited_pages():
    assert c.locator_pages('물리 PDF 12–13쪽') == [12, 13]
    assert c.locator_pages('물리 PDF 3,14쪽') == [3, 14]
    assert c.locator_pages('synthetic paragraph') == []
    assert c.cited_pages([{'source_id': 'S1', 'pages': [2, 2]}, {'source_id': 'S2', 'locator': '물리 PDF 1쪽'}]) == [('S1', 2), ('S2', 1)]


# ---------------------------------------------------------------- coverage judgment (P4)
def test_covered_needs_one_question_with_the_whole_goal_and_all_unknown_is_unperformed():
    b, bank = f.brief(), f.old.bank()
    inp = c.coverage_input(b, bank)
    c.check_coverage({'rows': covered(b)}, inp['goals'], inp['questions'])
    partial = {'rows': [row('D1', 'covered', 'Q1', 'R1', location='explanation'), row('D2', 'covered', 'Q2', 'R2')]}
    with pytest.raises(ValueError, match='whole goal'):
        c.check_coverage(partial, inp['goals'], inp['questions'])
    with pytest.raises(ValueError, match='judged nothing'):
        c.check_coverage({'rows': [row('D1', 'unknown'), row('D2', 'unknown')]}, inp['goals'], inp['questions'])
    with pytest.raises(ValueError, match='outside the batch'):
        narrow = c.coverage_input(b, bank, None, ['Q2'])
        c.check_coverage({'rows': covered(b)}, narrow['goals'], narrow['questions'])


def test_a_doubt_question_still_covers_its_goal():
    """Coverage and item quality are separate judgments; /2 made 15 of 23 trial goals unknown this way."""
    b = f.brief()
    rows = covered(b)
    reviews = [review('Q1', 'doubt'), review('Q2')]
    assert c.covering(rows[0]) == ['Q1']
    assert [r['direction_id'] for r in c.not_ready(b, rows, reviews)] == []
    assert c.not_ready(b, rows, [review('Q1', 'wrong'), review('Q2')]) == [{'direction_id': 'D1', 'reason': 'question-defect'}]
    assert c.not_ready(b, [rows[0], row('D2', 'missing')], reviews) == [{'direction_id': 'D2', 'reason': 'no-question'}]


# ---------------------------------------------------------------- add-only and fixes (P1)
def test_add_stage_appends_and_cannot_touch_existing_questions():
    bank = authored_bank()
    ids = c.next_question_ids(bank, 2)
    new = question(ids[0], bank['questions'][0])
    out = {'questions': [new], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
    merged, facts = c.merge_added(bank, [], out, ids)
    assert merged['questions'][:2] == bank['questions'] and merged['questions'][2]['question_id'] == 'Q003'
    rewrite = copy.deepcopy(out)
    rewrite['questions'][0]['question_id'] = 'Q1'
    with pytest.raises(ValueError):
        c.merge_added(bank, [], rewrite, ids + ['Q1'])
    outside = copy.deepcopy(out)
    outside['questions'][0]['question_id'] = 'Q099'
    with pytest.raises(ValueError, match='allowed range'):
        c.merge_added(bank, [], outside, ids)
    stray = copy.deepcopy(out)
    stray['questions'][0]['concept_id'] = 'Z'
    with pytest.raises(ValueError, match='concept is unknown'):
        c.merge_added(bank, [], stray, ids)


def test_coverage_fronts_mask_cloze_answers():
    bank = authored_bank()
    q = bank['questions'][0]
    q.update(format='cloze', question='A is {B} and {C}.', answer='A is B and C.', answer_units=['B', 'C'])
    front = c.coverage_input(f.brief(), bank)['questions'][0]
    assert 'B' not in front['question'].replace('{{c1}}', '') and front['answer_units'] == ['B', 'C']


def test_fix_stage_replaces_only_listed_questions_and_keeps_their_identity():
    bank = authored_bank()
    fixed = copy.deepcopy(bank['questions'][0])
    fixed['explanation'] = 'Synthetic corrected explanation'
    out = {'questions': [fixed], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
    merged, _, changed = c.merge_fixes(bank, [], out, ['Q1'])
    assert changed == ['Q1'] and merged['questions'][1] == bank['questions'][1]
    with pytest.raises(ValueError, match='only the listed'):
        c.merge_fixes(bank, [], out, ['Q2'])
    moved = copy.deepcopy(out)
    moved['questions'][0]['concept_id'] = 'B'
    with pytest.raises(ValueError, match='concept_id'):
        c.merge_fixes(bank, [], moved, ['Q1'])


def cloze(q, stem, units):
    return {**q, 'format': 'cloze', 'question': stem, 'answer': '; '.join(units), 'answer_units': list(units)}


def test_cloze_answer_units_follow_the_stem_blanks_where_questions_enter():
    """2026-11-12: a table row merged into one unit (261105_01 Q023) or a repeated blank dropped (261104_03 Q186)
    put the wrong unit in every later cell. Units become the blanks in order when questions enter the bank."""
    table = '| 감염 | 연령군 | 위생 |\n|---|---|---|\n| 인두염 | {5–15세} | — |\n| 농피증 | {2–5세} | {불량한 위생} |'
    bank = authored_bank()
    bank['questions'][0] = cloze(bank['questions'][0], table, ['인두염: 5–15세', '농피증: 2–5세, 불량한 위생'])
    plain = cloze(bank['questions'][1], '{{c1}} shown', ['stored'])   # no inline blank: left as stored
    bank['questions'][1] = plain
    changes = c.cloze_units(bank)
    assert changes == [{'question_id': 'Q1', 'from': ['인두염: 5–15세', '농피증: 2–5세, 불량한 위생'], 'to': ['5–15세', '2–5세', '불량한 위생']}]
    assert bank['questions'][0]['answer_units'] == ['5–15세', '2–5세', '불량한 위생'] and bank['questions'][1] == plain
    assert c.cloze_units(bank) == []   # idempotent

    base = authored_bank()
    ids = c.next_question_ids(base, 1)
    new = cloze(question(ids[0], base['questions'][0]), '|a|b|\n|---|---|\n|x|{혈관}|\n|y|{혈관}, {넓음}|', ['혈관', '넓음'])
    out = {'questions': [new], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
    merged, _ = c.merge_added(base, [], out, ids)
    assert merged['questions'][-1]['answer_units'] == ['혈관', '혈관', '넓음'] and out['questions'][0]['answer_units'] == ['혈관', '넓음']
    fixed = cloze(base['questions'][0], 'A {one} and {two}', ['one and two'])
    merged, _, _ = c.merge_fixes(base, [], {'questions': [fixed], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}, ['Q1'])
    assert merged['questions'][0]['answer_units'] == ['one', 'two']


def test_fix_stage_restating_an_existing_source_conflict_keeps_the_bank_conflict():
    """261102_02 (2026-11-10, v3-fix-1-0): Q046's fix copied its own conflict CF03 back."""
    bank = authored_bank()
    cf = {'conflict_id': 'CF01', 'description': 'Synthetic', 'source_refs': [{'source_id': 'S1', 'locator': 'x'}], 'unresolved': False}
    bank['source_conflicts'] = [cf]
    fixed = copy.deepcopy(bank['questions'][0])
    fixed['explanation'] = 'Synthetic corrected explanation'
    out = {'questions': [fixed], 'source_conflicts': [copy.deepcopy(cf)], 'visual_stimuli': [], 'clinical_conflicts': []}
    assert c.restated(bank, [], out) == [{'kind': 'source_conflict', 'id': 'CF01', 'changed': False}]
    merged, _, changed = c.merge_fixes(bank, [], out, ['Q1'])
    assert merged['source_conflicts'] == [cf] and changed == ['Q1']
    rewritten = copy.deepcopy(out)
    rewritten['source_conflicts'][0]['description'] = 'Synthetic rewritten'
    added = {**cf, 'conflict_id': 'CF02'}
    rewritten['source_conflicts'].append(added)
    assert c.restated(bank, [], rewritten) == [{'kind': 'source_conflict', 'id': 'CF01', 'changed': True}]
    # A new conflict no fixed question cites is a dangling record (CF-POLIO-28, 261102_02): refused in the stage.
    with pytest.raises(ValueError, match='must be cited'):
        c.merge_fixes(bank, [], rewritten, ['Q1'])
    rewritten['questions'][0]['conflict_id'] = 'CF02'
    merged, _, _ = c.merge_fixes(bank, [], rewritten, ['Q1'])
    assert merged['source_conflicts'] == [cf, added]


def test_a_worse_re_review_is_reverted():
    assert c.worse(review('Q1'), review('Q1', 'doubt'))
    assert c.worse(review('Q1', 'doubt'), review('Q1', 'ok', 'wrong'))
    assert not c.worse(review('Q1', 'wrong'), review('Q1', 'doubt'))


# ---------------------------------------------------------------- verdict ledger (P2)
def test_item_hash_ignores_other_questions_so_verdicts_survive_additions():
    bank = authored_bank()
    h = c.item_hash(bank['questions'][0], bank, [])
    grown, _ = c.merge_added(bank, [], {'questions': [question('Q003', bank['questions'][1])], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [],
                                        'visual_stimuli': [], 'clinical_conflicts': []}, ['Q003'])
    assert c.item_hash(grown['questions'][0], grown, []) == h
    changed = copy.deepcopy(bank['questions'][0])
    changed['answer'] = 'Synthetic other'
    assert c.item_hash(changed, bank, []) != h
    ledger = [c.ledger_entry('item', 'Q1', h, review('Q1', 'doubt'), 'review-1')]
    assert c.reusable(ledger, 'item', 'Q1', h)['verdict'] == 'doubt'
    assert c.reusable(ledger, 'item', 'Q1', c.item_hash(changed, bank, [])) is None


# ---------------------------------------------------------------- supplement points (R2a)
def points_doc():
    basis = [{'kind': 'learning_objective', 'refs': [{'source_id': 'S1', 'pages': [1]}], 'quote': '', 'reason': 'Objective', 'year': None}]
    return {'schema_version': 'exam-point-extract/3', 'title': 'Synthetic', 'notes': [],
            'notebook_profile': {'legend': 'Synthetic', 'emphasis_style': 'slide', 'reason': 'Synthetic'},
            'points': [{'point_id': 'P001', 'point': 'Existing', 'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}],
                        'importance_basis': basis}]}


def supplement(basis):
    return {'point': 'Missed point', 'source_refs': [{'source_id': 'S1', 'pages': [2], 'locator': None}], 'importance_basis': basis}


@pytest.mark.parametrize('basis,tier', [
    ([{'kind': 'exam_forecast', 'refs': [{'source_id': 'S1', 'pages': [2]}], 'quote': '시험에 나온다', 'reason': 'Forecast', 'year': None}], 'Essential'),
    ([{'kind': 'learning_objective', 'refs': [{'source_id': 'S1', 'pages': [2]}], 'quote': '', 'reason': 'Objective', 'year': None}], 'Core'),
    ([], 'Optional'),
])
def test_supplement_points_take_tiers_from_the_same_point_table(basis, tier):
    rows = {'rows': [{'question_id': 'Q7', 'decision': 'point', 'point': supplement(basis), 'duplicate_of': None, 'reason': 'Missed'},
                     {'question_id': 'Q8', 'decision': 'out_of_scope', 'point': None, 'duplicate_of': None, 'reason': 'S2 only'},
                     {'question_id': 'Q9', 'decision': 'duplicate_of', 'point': None, 'duplicate_of': 'P001', 'reason': 'Same'}]}
    doc, table, decisions = c.attach_points(points_doc(), rows, ['Q7', 'Q8', 'Q9'], {'S1': 10, 'S2': 8})
    assert [p['point_id'] for p in doc['points']] == ['P001', 'P002']
    assert doc['points'][1]['origin'] == 'question' and doc['points'][1]['origin_question_id'] == 'Q7'
    assert table['points']['P002']['tier'] == tier and table['points']['P001']['tier'] == 'Core'
    assert [d['decision'] for d in decisions] == ['point', 'out_of_scope', 'duplicate_of']


def test_supplement_point_ids_skip_brief_only_points():
    """261113_02: a brief fix added P088–P093 to the brief only; the supplement point took P088 and extend_brief stopped."""
    rows = {'rows': [{'question_id': 'Q7', 'decision': 'point', 'point': supplement([]), 'duplicate_of': None, 'reason': 'Missed'}]}
    doc, _, decisions = c.attach_points(points_doc(), rows, ['Q7'], {'S1': 10}, reserved=['P001', 'P002', 'P003', 'T9'])
    assert [p['point_id'] for p in doc['points']] == ['P001', 'P004'] and decisions[0]['point_id'] == 'P004'
    doc, _, _ = c.attach_points(points_doc(), rows, ['Q7'], {'S1': 10})
    assert [p['point_id'] for p in doc['points']] == ['P001', 'P002']        # no reserved IDs: numbering as before
    dup = {'rows': [{'question_id': 'Q7', 'decision': 'duplicate_of', 'point': None, 'duplicate_of': 'P003', 'reason': 'x'}]}
    with pytest.raises(ValueError):                                            # a brief-only ID is no duplicate target
        c.attach_points(points_doc(), dup, ['Q7'], {'S1': 10}, reserved=['P003'])


def test_supplement_points_need_the_lecture_notes_and_valid_pages():
    rows = lambda p: {'rows': [{'question_id': 'Q7', 'decision': 'point', 'point': p, 'duplicate_of': None, 'reason': 'x'}]}
    jokbo = supplement([])
    jokbo['source_refs'] = [{'source_id': 'S2', 'pages': [1], 'locator': None}]
    with pytest.raises(ValueError, match='lecture notes'):
        c.attach_points(points_doc(), rows(jokbo), ['Q7'], {'S1': 10, 'S2': 8})
    far = supplement([])
    far['source_refs'][0]['pages'] = [40]
    with pytest.raises(ValueError, match='outside the source'):
        c.attach_points(points_doc(), rows(far), ['Q7'], {'S1': 10})
    with pytest.raises(ValueError, match='one decision'):
        c.attach_points(points_doc(), rows(supplement([])), ['Q7', 'Q8'], {'S1': 10})


def test_extend_brief_adds_goals_without_touching_the_map():
    b = f.brief()
    t = copy.deepcopy(b['targets'][0])
    t['target_id'] = 'T9'
    t['relation_ids'] = ['R1']
    t['directions'] = [{**copy.deepcopy(t['directions'][0]), 'direction_id': 'D9', 'relation_ids': ['R1']}]
    p = {**copy.deepcopy(b['points'][0]), 'point_id': 'P9', 'target_ids': ['T9']}
    extended, new = c.extend_brief(b, {'targets': [t], 'points': [p]}, ['P9'])
    assert new == ['T9'] and c.map_projection(extended, ['T9'], ['P9']) == b
    with pytest.raises(ValueError, match='new targets only'):
        c.extend_brief(b, {'targets': [b['targets'][0]], 'points': [p]}, ['P9'])
    with pytest.raises(ValueError, match='only new targets and points'):
        c.extend_brief(b, {'targets': [t], 'points': [p], 'relations': []}, ['P9'])


# ---------------------------------------------------------------- assembly (R2m)
def gathered(b, bank, reviews=None):
    return c.assessment_raw(b, bank, covered(b), map_ok(b), reviews or [review('Q1'), review('Q2')], CONTEXT, 'Synthetic /3 judgments')


def test_gathered_judgments_compile_into_the_v2_document():
    b, bank = f.brief(), f.old.bank()
    raw = gathered(b, bank)
    audit = v2.compile_assessment(b, bank, envelope(b, bank, raw))
    doc = v2.make_document(b, bank, audit, revision='test', title='Synthetic', exam_date=None)
    assert {t['direction_id'] for t in doc['tasks']} == {'D1', 'D2'}
    doubt = gathered(b, bank, [review('Q1', 'doubt'), review('Q2')])
    doc = v2.make_document(b, bank, v2.compile_assessment(b, bank, envelope(b, bank, doubt)), revision='test', title='Synthetic', exam_date=None)
    assert {t['direction_id'] for t in doc['tasks']} == {'D2'}


def test_assembly_never_fills_in_a_missing_judgment():
    b, bank = f.brief(), f.old.bank()
    with pytest.raises(ValueError, match='item review'):
        c.assessment_raw(b, bank, covered(b), map_ok(b), [review('Q1')], CONTEXT, 'x')
    with pytest.raises(ValueError, match='coverage judgment'):
        c.assessment_raw(b, bank, covered(b)[:1], map_ok(b), [review('Q1'), review('Q2')], CONTEXT, 'x')
    partial = map_ok(b)
    partial['relation_checks'] = partial['relation_checks'][:1]
    with pytest.raises(ValueError, match='one judgment per relation'):
        c.assessment_raw(b, bank, covered(b), partial, [review('Q1'), review('Q2')], CONTEXT, 'x')


def test_unknown_map_judgment_keeps_the_goal_unprepared():
    b, bank = f.brief(), f.old.bank()
    m = map_ok(b)
    m['relation_checks'][0]['status'] = 'unknown'
    raw = c.assessment_raw(b, bank, covered(b), m, [review('Q1'), review('Q2')], CONTEXT, 'x')
    doc = v2.make_document(b, bank, v2.compile_assessment(b, bank, envelope(b, bank, raw)), revision='t', title='S', exam_date=None)
    assert 'D1' not in {t['direction_id'] for t in doc['tasks']}


# ---------------------------------------------------------------- result
JUDGMENT = {'conflicts': [], 'questions': [], 'unrecorded': []}


def result(p):
    b, bank = f.brief(), f.old.bank()
    b['lecture_id'] = p['subject'] + '/' + p['runId']
    raw = gathered(b, bank)
    raw['clinical_context_reason'] = c.context_summary(JUDGMENT)['clinical_context_reason']
    audit = v2.compile_assessment(b, bank, envelope(b, bank, raw))
    doc = v2.make_document(b, bank, audit, revision=p['revision'], title=p['title'], exam_date=p['examDate'])
    ledger = [c.ledger_entry('item', q['question_id'], c.item_hash(q, bank, []), review(q['question_id']), 'review-1') for q in bank['questions']]
    medical = f.old.checks(bank)
    med_input = {'title': p['title'], 'bank': bank, 'clinicalInput': v2.medical_input(bank, []), 'medicalFinal': True,
                 '_pipeline_version': c.POLICY}
    stage = lambda name, inp, out: {'name': name, 'status': 'completed', 'inputHash': document_hash(inp), 'outputHash': document_hash(out)}
    stages = [stage('normalize', {}, b), stage('v3-add-0', {}, {}), stage('v3-context-0', {}, JUDGMENT), stage('medical-0', med_input, medical)]
    stages[-1]['inputHash'] = document_hash(med_input)
    meta = {'pipelineVersion': c.POLICY, 'inputHash': p['inputHash'], 'briefHash': document_hash(b), 'bankHash': document_hash(bank),
            'model': 'synthetic', 'runtimeHash': '0' * 64, 'stages': stages, 'verdictLedger': ledger, 'verdictLedgerHash': document_hash(ledger),
            'addRounds': 1, 'notReady': [], 'offGoalQuestions': [], 'rejectedAtIntake': [], 'supplement': [],
            'initialBrief': b, 'supplementPoints': None, 'intakeProjection': c.intake_projection(bank)[1],
            'initialBank': copy.deepcopy(bank), 'coverage': covered(b), 'mapCheck': map_ok(b),
            'itemReviews': [review('Q1'), review('Q2')], 'clinicalContext': JUDGMENT, 'contextJudgments': [JUDGMENT], 'medicalUnreviewed': [],
            'readiness': c.readiness(b, bank, raw, doc), 'clinicalConflicts': [], 'medicalFinal': True,
            'sourceAssessment': raw, 'fixes': []}
    return {'brief': b, 'document': doc, 'sourceAudit': audit, 'medical': medical, 'validation': {}, 'manifest': meta}


def v3_packet():
    p = f.packet()
    p['generationPolicy'] = c.POLICY
    p['intakeBank'] = {'bank': f.old.bank(), 'visual_stimuli': [], 'clinical_conflicts': []}
    return p


def test_a_v3_result_is_checked_by_the_v3_contract():
    p = v3_packet()
    value = result(p)
    assert consume(value, p) == value['document']


@pytest.mark.parametrize('tamper,message', [
    (lambda v: v['manifest'].update(addRounds=3), 'add budget'),
    (lambda v: v['manifest'].update(medicalFinal=False), 'medical review runs once'),
    (lambda v: v['manifest']['initialBank']['questions'][0].update(answer='Synthetic original'), 'changed without a fix'),
    (lambda v: v['manifest'].update(offGoalQuestions=[{'question_id': 'Q1', 'reason': 'x'}]), 'out-of-scope question became a task'),
    (lambda v: v['manifest'].update(notReady=[{'direction_id': 'D1', 'reason': 'no-question'}]), 'not-ready goal has a task'),
    (lambda v: v['manifest']['itemReviews'][0].update(verdict='doubt', note='x'), 'gathered judgments'),
    (lambda v: v['manifest'].update(verdictLedgerHash='0' * 64), 'verdict ledger'),
])
def test_tampered_v3_results_are_rejected(tamper, message):
    p = v3_packet()
    value = result(p)
    tamper(value)
    with pytest.raises(ValueError, match=message):
        consume(value, p)


def test_a_v2_packet_never_accepts_a_v3_result():
    p = v3_packet()
    value = result(p)
    with pytest.raises(Exception):
        consume(value, f.packet())


def test_intake_projection_sets_only_the_recomputed_bank_fields():
    """261102_02 (2026-11-10): schema_version "BANK" with 3.2 importance numbers refused the whole bank."""
    from studyez_contracts.bank.validate import validate_bank
    bank = f.old.bank()
    bank['build_meta']['schema_version'] = 'BANK'
    bank['questions'][0].update(tier='Core', importance=5)
    if bank['concepts'] and 'tier' in c.v2.AUTHOR_BANK['properties']['concepts']['items']['properties']:
        bank['concepts'][0].update(tier='Important', importance=4)
    value, changes = c.intake_projection(bank)
    if bank['concepts'] and bank['concepts'][0].get('tier') == 'Important':
        assert value['concepts'][0]['importance'] == 3
    assert value['build_meta']['schema_version'] == '3.3' and value['questions'][0]['importance'] == 4
    assert {'field': 'build_meta.schema_version', 'from': 'BANK', 'to': '3.3'} in changes
    assert {'field': 'Q1.importance', 'from': 5, 'to': 4} in changes
    strip = lambda b: [{k: v for k, v in q.items() if k != 'importance'} for q in b['questions']]
    assert strip(value) == strip(bank)
    assert not any('schema_version' in e or '중요도 수치' in e for e in validate_bank(value, ['S1'])['errors'])
    assert c.intake_projection(value)[1] == []


def test_restated_existing_items_of_an_add_are_left_out_and_recorded():
    """261102_02 (2026-11-10): an add stage rewrote CF01-CF03's facts. Concepts, plans and conflicts are treated alike (P6)."""
    bank = authored_bank()
    bank['source_conflicts'] = [{'conflict_id': 'CF01', 'description': 'Synthetic', 'source_refs': [{'source_id': 'S1', 'locator': 'x'}], 'unresolved': False}]
    facts = [{'conflict_id': 'CF01', 'facts': 'Synthetic original facts'}]
    ids = c.next_question_ids(bank, 1)
    concept = copy.deepcopy(bank['concepts'][0])
    plan = copy.deepcopy(bank['retrieval_plan'][0]) if bank['retrieval_plan'] else None
    out = {'questions': [question(ids[0], bank['questions'][0])], 'concepts': [concept], 'retrieval_plan': [plan] if plan else [],
           'source_conflicts': [copy.deepcopy(bank['source_conflicts'][0])], 'visual_stimuli': [],
           'clinical_conflicts': [{'conflict_id': 'CF01', 'facts': 'Synthetic rewritten facts'}]}
    kinds = [(r['kind'], r['id'], r['changed']) for r in c.restated(bank, facts, out)]
    assert ('concept', concept['concept_id'], False) in kinds and ('source_conflict', 'CF01', False) in kinds
    assert ('clinical_fact', 'CF01', True) in kinds
    merged, kept = c.merge_added(bank, facts, out, ids)
    assert kept == facts and merged['concepts'] == bank['concepts'] and merged['source_conflicts'] == bank['source_conflicts']
    assert merged['questions'][-1]['question_id'] == ids[0]
    stray = copy.deepcopy(out)
    stray['clinical_conflicts'] = [{'conflict_id': 'CF09', 'facts': 'No such source conflict'}]
    with pytest.raises(ValueError, match='only for its new source conflicts'):
        c.merge_added(bank, facts, stray, ids)


def _add_case(bank):
    ids = c.next_question_ids(bank, 1)
    goal = {'direction_id': 'D1', 'point_ids': ['P1']}
    q = question(ids[0], bank['questions'][0])
    q['point_ids'] = ['P1']
    ctx = {'allowed_question_ids': ids, 'existing': [{'question_id': x['question_id'], 'question': '', 'answer': ''} for x in bank['questions']],
           'bank_concepts': [{'concept_id': x['concept_id'], 'title': ''} for x in bank['concepts']], 'goals': [goal],
           'source_conflict_ids': [x['conflict_id'] for x in bank.get('source_conflicts', [])]}
    out = {'questions': [q], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
    return ctx, out


NEW_CF = {'conflict_id': 'CF07', 'description': 'Synthetic', 'source_refs': [{'source_id': 'S1', 'locator': 'x'}], 'unresolved': False}


@pytest.mark.parametrize('spoil,message', [
    (lambda o: o.update(clinical_conflicts=[{'conflict_id': 'CF09', 'facts': 'x'}]), 'only for its new source conflicts'),
    (lambda o: (o.update(source_conflicts=[NEW_CF, {**NEW_CF, 'description': 'Other'}]), o['questions'][0].update(conflict_id='CF07')), 'not rewrite one'),
    (lambda o: o.update(source_conflicts=[NEW_CF]), 'must be cited by a new question'),
    (lambda o: o.update(concepts=[{**copy.deepcopy(authored_bank()['concepts'][0]), 'concept_id': 'NEW'}]), 'one retrieval plan per new concept'),
])
def test_every_add_merge_error_is_found_by_the_stage_check(spoil, message):
    """P6: what would stop the lecture after an add stage is found inside it, where the model gets a follow-up."""
    bank = authored_bank()
    ctx, out = _add_case(bank)
    spoil(out)
    with pytest.raises(ValueError, match=message):
        c.merge_added(bank, [], out, ctx['allowed_question_ids'])
    with pytest.raises(ValueError, match=message):
        c.check_added(out, ctx, {'bank': bank, 'clinical_conflicts': []})


@pytest.mark.parametrize('spoil,message', [
    (lambda o: o.update(clinical_conflicts=[{'conflict_id': 'CF09', 'facts': 'x'}]), 'facts only for the fixed questions'),
    (lambda o: (o.update(source_conflicts=[NEW_CF, {**NEW_CF, 'description': 'Other'}]), o['questions'][0].update(conflict_id='CF07')), 'not rewrite one'),
    (lambda o: o.update(source_conflicts=[NEW_CF]), 'must be cited by a fixed question'),
])
def test_every_fix_merge_error_is_found_by_the_stage_check(spoil, message):
    bank = authored_bank()
    fixed = copy.deepcopy(bank['questions'][0])
    out = {'questions': [fixed], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
    spoil(out)
    ctx = {'questions': [copy.deepcopy(bank['questions'][0])]}
    with pytest.raises(ValueError, match=message):
        c.merge_fixes(bank, [], out, ['Q1'])
    with pytest.raises(ValueError, match=message):
        c.check_fixed(out, ctx, {'bank': bank, 'clinical_conflicts': []})


def test_the_whole_map_check_takes_every_relation_even_one_without_a_target():
    """261102_02 (2026-11-10): 21 of 102 relations belonged to no target; the assembly needs a judgment for each."""
    b = f.brief()
    loose = {**copy.deepcopy(b['relations'][0]), 'relation_id': 'R_LOOSE'}
    b['relations'].append(loose)
    whole = c.map_check_input(b, None)
    assert 'R_LOOSE' in {r['relation_id'] for r in whole['relations']}
    assert {r['relation_id'] for r in whole['relations']} == {r['relation_id'] for r in b['relations']}
    part = c.map_check_input(b, None, [b['targets'][0]['target_id']])
    assert 'R_LOOSE' not in {r['relation_id'] for r in part['relations']}


# ---------------------------------------------------------------- intake: exact repeats (2026-11-11-intake-dedupe)
def _repeating_bank():
    """f.old.bank() with one of each repeat the intake now cleans up."""
    bank = f.old.bank()
    bank['build_meta']['schema_version'] = c.intake_projection(bank)[0]['build_meta']['schema_version']
    plan = bank['retrieval_plan'][0]
    plan['directions'] = plan['directions'] + [plan['directions'][0]]
    bank['retrieval_plan'].append(copy.deepcopy(bank['retrieval_plan'][0]))
    bank['source_summary'].append(copy.deepcopy(bank['source_summary'][0]))
    q1, q2 = bank['questions'][0], bank['questions'][1]
    q2['prerequisites'] = ['Q1', 'Q1']
    q1['format'], q1['options'] = 'mcq', [{'id': 'A', 'text': 'Synthetic A'}, {'id': 'B', 'text': 'Synthetic B'}]
    q1['correct_option_ids'], q1['mcq_mode'] = ['A', 'A'], 'recall_first'
    return bank


def test_intake_drops_exact_repeats_and_records_them():
    """261102_02 /4 trial: C06 directions listed `reverse` twice and the run stopped before any generation call."""
    from studyez_contracts.bank.validate import validate_bank
    bank = _repeating_bank()
    before = validate_bank(copy.deepcopy(bank), ['S1'])['errors']
    assert any(e.endswith('directions: ID/값 중복') for e in before) and 'retrieval_plan: ID/값 중복' in before
    value, changes = c.intake_projection(bank)
    fields = [x['field'] for x in changes]
    cid = bank['retrieval_plan'][0]['concept_id']
    assert 'retrieval_plan' in fields and 'source_summary' in fields and f'{cid}.directions' in fields
    assert 'Q2.prerequisites' in fields and 'Q1.correct_option_ids' in fields
    assert value['questions'][1]['prerequisites'] == ['Q1'] and value['questions'][0]['correct_option_ids'] == ['A']
    assert len(value['retrieval_plan']) == len(f.old.bank()['retrieval_plan'])
    assert not any('ID/값 중복' in e for e in validate_bank(value, ['S1'])['errors'])
    assert c.intake_projection(value)[1] == []                       # idempotent


def test_intake_leaves_a_bank_without_repeats_alone():
    bank = f.old.bank()
    value, changes = c.intake_projection(bank)
    assert not any(x['field'].endswith(('.directions', '.prerequisites', '.correct_option_ids')) or x['field'] in ('retrieval_plan', 'source_summary')
                   for x in changes)
    assert value['questions'] == [dict(q, importance=v['importance']) for q, v in zip(bank['questions'], value['questions'])]


def test_two_different_plans_for_one_concept_still_stop():
    from studyez_contracts.bank.validate import validate_bank
    bank = f.old.bank()
    other = copy.deepcopy(bank['retrieval_plan'][0])
    other['repetition_budget'] = other['repetition_budget'] + 1
    bank['retrieval_plan'].append(other)
    value, _ = c.intake_projection(bank)
    assert len(value['retrieval_plan']) == 2
    assert any(e.startswith('retrieval_plan: ID/값 중복') for e in validate_bank(value, ['S1'])['errors'])
