"""root-generation/4 contracts (docs/changes/2026-11-10-importance-at-authoring/spec.md). Pure functions, synthetic data.

The shape follows 261102_02 (2026-11-10): one goal asked by two questions on different parts (Q001 host
factors, Q003 environment factors), a target blocked only by an importance label, a good question without
the figure its goal asks for.
"""
import copy

import pytest
import generation_v2_fixture as f
from studyez_contracts.bank import importance as imp
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import generation_v4 as c
from studyez_contracts.roots.validate import validate_document

CONTEXT = {'clinical_context_status': 'consistent', 'clinical_context_reason': 'Synthetic', 'clinical_context_problem': 'none'}


def part(cid, location):
    return {'component_id': cid, 'location': location, 'answer_unit_indices': [0] if location == 'answer' else [], 'reason': 'Synthetic'}


def ev(qid, rid, parts, visual='not_applicable'):
    return {'question_id': qid, 'tested_relation_ids': [rid], 'components': parts, 'visual_verdict': visual, 'reason': 'Synthetic'}


def scenario():
    """D1 has two components (host, env); Q1 answers host, Q3 answers env. D2 is answered whole by Q2."""
    b, bank = f.brief(), f.old.bank()
    d1 = b['targets'][0]['directions'][0]
    d1['components'] = [{'component_id': 'host', 'text': 'Synthetic host factors'}, {'component_id': 'env', 'text': 'Synthetic environment factors'}]
    for q in bank['questions']:
        q.pop('stimuli', None)
    q3 = copy.deepcopy(bank['questions'][0])
    q3.update(question_id='Q3', question='Synthetic question 3?', answer='Secret answer 3', answer_units=['Secret answer 3'])
    bank['questions'].append(q3)
    return b, bank


def rows(status1='covered', dup=()):
    d1 = {'direction_id': 'D1', 'status': status1, 'reason': 'Synthetic coverage', 'duplicates': [],
          'evidence': [ev('Q1', 'R1', [part('host', 'answer'), part('env', 'missing')]),
                       ev('Q3', 'R1', [part('host', 'missing'), part('env', 'answer')])]}
    if dup:
        d1['duplicates'] = [{'question_ids': list(dup), 'reason': 'Same recall, other wording'}]
    d2 = {'direction_id': 'D2', 'status': 'covered', 'reason': 'Synthetic coverage', 'duplicates': [],
          'evidence': [ev('Q2', 'R2', [part('fact', 'answer')])]}
    return [d1, d2]


def map_ok(b):
    return {'relation_checks': [{'relation_id': r['relation_id'], 'status': 'supported', 'reason': 'Synthetic'} for r in b['relations']],
            'target_checks': [{'target_id': t['target_id'], 'status': 'consistent', 'reason': 'Synthetic'} for t in b['targets']],
            'direction_checks': [{'direction_id': d['direction_id'], 'scope_status': 'consistent', 'reason': 'Synthetic'}
                                 for t in b['targets'] for d in t['directions']], 'issues': []}


def review(qid, verdict='ok'):
    return {'question_id': qid, 'verdict': verdict, 'design': 'ok', 'note': '' if verdict == 'ok' else 'Synthetic note',
            'suggested_answer': '', 'fix': '', 'prerequisite_checks': [], 'importance_note': ''}


def build(b, bank, coverage, mapcheck=None, reviews=None):
    reviews = reviews or [review(q['question_id']) for q in bank['questions']]
    raw = c.assessment_raw(b, bank, coverage, mapcheck or map_ok(b), reviews, CONTEXT, 'Synthetic /4 judgments')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw))
    return c.make_document(b, bank, audit, coverage, revision='test', title='Synthetic', exam_date=None)


def tasks(doc):
    return sorted((t['question_id'], t['direction_id']) for t in doc['tasks'])


# ---------------------------------------------------------------- R5 coverage
def test_a_goal_is_covered_by_the_union_of_answered_components():
    b, bank = scenario()
    ctx = v3.coverage_input(b, bank)
    c.check_coverage({'rows': rows()}, ctx['goals'], ctx['questions'])
    one = rows()
    one[0]['evidence'] = one[0]['evidence'][:1]                       # nobody asks env
    with pytest.raises(ValueError, match='D1 is missing'):
        c.check_coverage({'rows': one}, ctx['goals'], ctx['questions'])
    one[0]['status'] = 'missing'
    c.check_coverage({'rows': one}, ctx['goals'], ctx['questions'])
    goal = next(g for g in ctx['goals'] if g['direction_id'] == 'D1')
    assert c.missing_components(one[0], goal) == ['env']


def test_the_add_stage_gets_only_the_unasked_components():
    b, bank = scenario()
    value = c.add_input(b, bank, {'D1': ['env']}, ['Q9'])
    goal = value['goals'][0]
    assert [x['component_id'] for x in goal['components']] == ['env'] and goal['missing_component_ids'] == ['env']


def test_a_visual_goal_needs_an_image_question_but_keeps_the_others():
    b, bank = scenario()
    b['targets'][0]['directions'][1]['requires_visual'] = True
    ctx = v3.coverage_input(b, bank)
    with pytest.raises(ValueError, match='D2 is missing'):
        c.check_coverage({'rows': rows()}, ctx['goals'], ctx['questions'])
    r = rows()
    r[1]['status'] = 'missing'
    c.check_coverage({'rows': r}, ctx['goals'], ctx['questions'])
    assert c.not_ready(b, r, [review(q['question_id']) for q in bank['questions']]) == [{'direction_id': 'D2', 'reason': 'visual'}]


def test_duplicate_groups_name_only_questions_that_answer_the_goal():
    b, bank = scenario()
    ctx = v3.coverage_input(b, bank)
    r = rows(dup=('Q1', 'Q2'))
    with pytest.raises(ValueError, match='does not answer this goal'):
        c.check_coverage({'rows': r}, ctx['goals'], ctx['questions'])


# ---------------------------------------------------------------- R6 tasks
def test_every_ok_question_is_a_task_and_a_goal_can_have_several():
    b, bank = scenario()
    doc, placed = build(b, bank, rows())
    assert tasks(doc) == [('Q1', 'D1'), ('Q2', 'D2'), ('Q3', 'D1')]
    assert doc['generation_policy'] == c.POLICY and placed == {'mergedDuplicates': [], 'unplacedQuestions': []}
    # The /3 assembly of the same bank keeps at most one question per goal and needs one that answers it whole.
    raw3 = v3.assessment_raw(b, bank, [{k: v for k, v in r.items() if k != 'duplicates'} for r in rows()], map_ok(b),
                             [{k: v for k, v in review(q['question_id']).items() if k != 'importance_note'} for q in bank['questions']],
                             CONTEXT, 'x')
    doc3 = v2.make_document(b, bank, v2.compile_assessment(b, bank, v2.envelope(b, bank, raw3)), revision='t', title='S', exam_date=None)
    assert tasks(doc3) == [('Q2', 'D2')]


def test_only_true_duplicates_merge():
    b, bank = scenario()
    doc, placed = build(b, bank, rows(dup=('Q1', 'Q3')))
    assert tasks(doc) == [('Q1', 'D1'), ('Q2', 'D2')]
    assert placed['mergedDuplicates'] == [{'question_id': 'Q3', 'kept': 'Q1', 'direction_id': 'D1', 'reason': 'Same recall, other wording'}]


def test_the_kept_duplicate_is_the_more_important_one():
    b, bank = scenario()
    snapshot = copy.deepcopy(bank)
    next(q for q in snapshot['questions'] if q['question_id'] == 'Q3').update(tier='Core', importance=4)
    raw = c.assessment_raw(b, bank, rows(dup=('Q1', 'Q3')), map_ok(b), [review(q['question_id']) for q in bank['questions']], CONTEXT, 'x')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw))
    doc, placed = c.make_document(b, bank, audit, rows(dup=('Q1', 'Q3')), revision='t', title='S', exam_date=None,
                                  snapshot=snapshot, importance={})
    assert placed['mergedDuplicates'][0]['kept'] == 'Q3' and tasks(doc) == [('Q2', 'D2'), ('Q3', 'D1')]


def test_a_question_not_ok_is_not_a_task():
    b, bank = scenario()
    doc, _ = build(b, bank, rows(), reviews=[review('Q1'), review('Q2'), review('Q3', 'doubt')])
    assert tasks(doc) == [('Q1', 'D1'), ('Q2', 'D2')]


# ---------------------------------------------------------------- R3/R7 judgments never decide a task
def test_map_target_scope_and_visual_judgments_do_not_remove_tasks():
    b, bank = scenario()
    base, _ = build(b, bank, rows())
    m = map_ok(b)
    m['target_checks'][0].update(status='conflict', reason='P026: exam_forecast should be professor_remark')
    m['direction_checks'][0].update(scope_status='conflict', reason='Synthetic scope doubt')
    r = rows()
    r[0]['evidence'][0]['visual_verdict'] = 'doubt'
    doc, _ = build(b, bank, r, mapcheck=m)
    assert tasks(doc) == tasks(base)


def test_an_unreviewed_relation_still_cannot_be_tested():
    b, bank = scenario()
    m = map_ok(b)
    m['relation_checks'][1]['status'] = 'unknown'
    doc, placed = build(b, bank, rows(), mapcheck=m)
    assert ('Q2', 'D2') not in tasks(doc)
    assert [u['question_id'] for u in placed['unplacedQuestions']] == ['Q2']


def test_the_document_validator_keeps_the_whole_goal_rule_for_older_policies():
    b, bank = scenario()
    b['targets'][0]['directions'][0]['relation_ids'] = ['R1', 'R2']   # D1 spans two relations; each question tests one
    r = rows()
    r[0]['evidence'][1]['tested_relation_ids'] = ['R2']
    doc, _ = build(b, bank, r)
    assert ('Q3', 'D1') in tasks(doc)
    validate_document(doc)
    old = copy.deepcopy(doc)
    old['generation_policy'] = 'root-generation/2'
    with pytest.raises(ValueError, match='entire direction'):
        validate_document(old)


def test_one_question_is_one_task():
    b, bank = scenario()
    doc, _ = build(b, bank, rows())
    twice = copy.deepcopy(doc)
    extra = dict(twice['tasks'][0], task_id='task-extra', direction_id='D2')
    twice['tasks'].append(extra)
    with pytest.raises(ValueError):
        validate_document(twice)


# ---------------------------------------------------------------- R1/R2 importance per question
def basis(kind='slide_emphasis', **kw):
    row = {'kind': kind, 'refs': [{'source_id': 'S1', 'pages': [3]}], 'quote': '', 'reason': 'Synthetic', 'year': None}
    row.update(kw)
    return [row]


def test_points_carry_no_importance_and_the_map_check_sees_none():
    assert 'importance_basis' not in c.POINT['properties'] and 'importance_basis' not in c.POINT['required']
    b, _ = scenario()
    value = c.map_check_input(b)
    assert all('importance_basis' not in t for t in value['targets'])


def test_authored_questions_must_name_their_basis():
    rows = [{'question_id': 'Q1', 'importance_basis': basis('exam_forecast', quote='꼭 나온다')},
            {'question_id': 'Q2', 'importance_basis': []}]
    found = c.collect_basis(rows, ['Q1', 'Q2'])
    assert found['Q1'][0]['kind'] == 'exam_forecast' and found['Q2'] == []
    with pytest.raises(ValueError, match='missing for Q3'):
        c.collect_basis(rows, ['Q1', 'Q2', 'Q3'])
    with pytest.raises(ValueError, match='did not write'):
        c.collect_basis(rows, ['Q1'])
    rows[1]['importance_basis'] = basis('exam_forecast')            # a forecast needs the original wording
    with pytest.raises(ValueError, match='Q2'):
        c.collect_basis(rows, ['Q1', 'Q2'])


def test_authoring_outputs_carry_basis_beside_the_questions():
    for schema in (c.INTAKE_OUTPUT, c.ADD_OUTPUT, c.FIX_OUTPUT):
        assert 'question_importance' in schema['required']
    q = c.ADD_OUTPUT['properties']['questions']['items']
    assert 'importance_basis' not in q['properties']                # bank 3.3 questions are unchanged
    assert 'importance_note' in c.ITEM_REVIEW_OUTPUT['properties']['reviews']['items']['required']
    assert 'duplicates' in c.COVERAGE_OUTPUT['properties']['rows']['items']['required']


def test_supplement_points_have_no_basis():
    doc = {'schema_version': 'exam-point-extract/4', 'title': 'S', 'notebook_profile': PROFILE,
           'points': [{'point_id': 'P001', 'point': 'Existing', 'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}]}]}
    c.check_points(doc)
    out = {'rows': [{'question_id': 'Q7', 'decision': 'point', 'duplicate_of': None, 'reason': 'Synthetic',
                     'point': {'point': 'New', 'source_refs': [{'source_id': 'S1', 'pages': [2], 'locator': None}]}}]}
    value, decisions = c.attach_points(doc, out, ['Q7'], {'S1': 5})
    assert [p['point_id'] for p in value['points']] == ['P001', 'P002'] and all('importance_basis' not in p for p in value['points'])
    assert decisions[0]['point_id'] == 'P002'
    out['rows'][0]['point']['importance_basis'] = []
    with pytest.raises(ValueError, match='no importance'):
        c.attach_points(doc, out, ['Q7'], {'S1': 5})


def test_tier_is_computed_from_the_question_basis():
    b, bank = scenario()
    profile = {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'}
    found = {'Q1': basis('exam_forecast', quote='꼭 나온다'), 'Q2': [], 'Q3': basis('learning_objective')}
    table = c.question_table(found, profile, bank)
    snapshot, proof = c.project_importance(bank, table)
    tiers = {q['question_id']: (q['tier'], q['importance']) for q in snapshot['questions']}
    assert tiers == {'Q1': ('Essential', 5), 'Q2': ('Optional', 2), 'Q3': ('Core', 4)}
    assert v2.restore_importance(snapshot, proof) == bank
    with pytest.raises(ValueError, match='exactly one basis'):
        c.question_table({'Q1': []}, profile, bank)


def test_target_axes_come_from_its_questions():
    b, bank = scenario()
    profile = {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'}
    table = c.question_table({'Q1': basis('clinical'), 'Q2': [], 'Q3': basis('exam_exclusion', quote='안 낸다')}, profile, bank)
    doc, _ = build(b, bank, rows())
    axes = c.target_importance(b, doc['review'], bank, table)['T1']
    assert axes['clinical']['status'] == 'supported' and axes['exam']['status'] == 'insufficient'
    # One excluded question does not mark a target whose other questions ask other parts.
    table = c.question_table({'Q1': basis('slide_emphasis'), 'Q2': [], 'Q3': basis('exam_exclusion', quote='안 낸다')}, profile, bank)
    assert c.target_importance(b, doc['review'], bank, table)['T1']['exam']['status'] == 'supported'


def test_the_point_table_reads_as_before():
    profile = {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'}
    table = imp.point_table([{'point_id': 'P1', 'importance_basis': basis('exam_exclusion', quote='안 낸다')},
                             {'point_id': 'P2', 'importance_basis': basis('slide_emphasis')}], profile)
    axes = imp.target_axes(table, ['P1', 'P2'])
    assert axes['exam'] == {'status': 'insufficient', 'reason': '출제 제외: P1', 'evidence': []}
    assert imp.target_axes(table, ['P2'])['exam']['reason'] == 'importance-basis/1 포인트 근거에서 계산'


def test_importance_doubts_are_notes_not_verdicts():
    reviews = [review('Q1'), dict(review('Q2'), importance_note='22쪽에는 스탬프가 없다')]
    assert c.importance_notes(reviews) == [{'question_id': 'Q2', 'note': '22쪽에는 스탬프가 없다'}]
    b, bank = scenario()
    doc, _ = build(b, bank, rows(), reviews=[review('Q1'), dict(review('Q2'), importance_note='x'), review('Q3')])
    assert ('Q2', 'D2') in tasks(doc)


# ---------------------------------------------------------------- result (consumer check)
import json
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result as consume

JUDGMENT = {'conflicts': [], 'questions': [], 'unrecorded': []}
PROFILE = {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'}


def v4_packet(bank):
    p = f.packet()
    p['generationPolicy'] = c.POLICY
    p['intakeBank'] = {'bank': copy.deepcopy(bank), 'visual_stimuli': [], 'clinical_conflicts': []}
    p['points'] = json.dumps({'schema_version': 'exam-point-extract/4', 'title': 'Synthetic', 'notebook_profile': PROFILE,
                              'points': [{'point_id': 'P1', 'point': 'Synthetic', 'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}]}]})
    return p


def result(p, b, bank, coverage, basis):
    b['lecture_id'] = p['subject'] + '/' + p['runId']
    reviews = [review(q['question_id']) for q in bank['questions']]
    raw = c.assessment_raw(b, bank, coverage, map_ok(b), reviews, v3.context_summary(JUDGMENT), 'Synthetic /4 judgments')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw))
    doc, placed, proofs = c.assemble(b, bank, audit, coverage, basis, PROFILE, revision=p['revision'], title=p['title'], exam_date=p['examDate'])
    ledger = [v3.ledger_entry('item', q['question_id'], v3.item_hash(q, bank, []), review(q['question_id']), 'review-1') for q in bank['questions']]
    medical = f.old.checks(bank)
    med_input = {'title': p['title'], 'bank': bank, 'clinicalInput': v2.medical_input(bank, []), 'medicalFinal': True, '_pipeline_version': c.POLICY}
    stage = lambda name, inp, out: {'name': name, 'status': 'completed', 'inputHash': document_hash(inp), 'outputHash': document_hash(out)}
    stages = [stage('normalize', {}, b), stage('v4-add-0', {}, {}), stage('v4-context-0', {}, JUDGMENT), stage('medical-0', med_input, medical)]
    meta = {'pipelineVersion': c.POLICY, 'inputHash': p['inputHash'], 'briefHash': document_hash(b), 'bankHash': document_hash(doc['bank_snapshot']),
            'model': 'synthetic', 'runtimeHash': '0' * 64, 'stages': stages, 'verdictLedger': ledger, 'verdictLedgerHash': document_hash(ledger),
            'addRounds': 1, 'notReady': c.not_ready(b, coverage, reviews), 'offGoalQuestions': [], 'rejectedAtIntake': [], 'supplement': [],
            'initialBrief': b, 'supplementPoints': None, 'intakeProjection': v3.intake_projection(p['intakeBank']['bank'])[1],
            'initialBank': copy.deepcopy(bank), 'coverage': coverage, 'mapCheck': map_ok(b),
            'itemReviews': reviews, 'clinicalContext': JUDGMENT, 'contextJudgments': [JUDGMENT], 'medicalUnreviewed': [],
            'readiness': c.readiness(b, coverage, doc), 'clinicalConflicts': [], 'medicalFinal': True,
            'sourceAssessment': raw, 'fixes': [], 'questionImportance': basis, 'importanceNotes': c.importance_notes(reviews),
            **placed, **{k: v for k, v in proofs.items() if k != 'importanceWarnings' and (k != 'bankProjection' or v)}}
    return {'brief': b, 'document': doc, 'sourceAudit': audit, 'medical': medical, 'validation': {}, 'manifest': meta}


def full_result():
    b, bank = scenario()
    p = v4_packet(bank)
    found = {'Q1': basis('exam_forecast', quote='꼭 나온다'), 'Q2': [], 'Q3': basis('learning_objective')}
    return p, result(p, b, bank, rows(), found)


def test_a_v4_result_is_checked_by_the_v4_contract():
    p, value = full_result()
    doc = consume(value, p)
    assert doc == value['document'] and tasks(doc) == [('Q1', 'D1'), ('Q2', 'D2'), ('Q3', 'D1')]
    tiers = {q['question_id']: q['tier'] for q in doc['bank_snapshot']['questions']}
    assert tiers == {'Q1': 'Essential', 'Q2': 'Optional', 'Q3': 'Core'}


@pytest.mark.parametrize('tamper,message', [
    (lambda v: v['manifest']['questionImportance'].update(Q2=basis('exam_forecast', quote='x')), 'projections differ'),
    (lambda v: v['manifest'].update(mergedDuplicates=[{'question_id': 'Q3', 'kept': 'Q1', 'direction_id': 'D1', 'reason': 'x'}]),
     'merged duplicates'),
    (lambda v: v['manifest'].update(importanceNotes=[{'question_id': 'Q1', 'note': 'x'}]), 'importance notes'),
    (lambda v: v['manifest'].update(notReady=[{'direction_id': 'D1', 'reason': 'partial'}]), 'not-ready goals differ'),
    (lambda v: v['manifest']['coverage'][0].update(duplicates=[{'question_ids': ['Q1', 'Q3'], 'reason': 'x'}]), 'assessment|document|differ'),
])
def test_tampered_v4_results_are_rejected(tamper, message):
    p, value = full_result()
    tamper(value)
    with pytest.raises(ValueError, match=message):
        consume(value, p)


def test_a_v3_packet_never_accepts_a_v4_result():
    p, value = full_result()
    p3 = dict(p, generationPolicy=v3.POLICY)
    with pytest.raises(Exception):
        consume(value, p3)


def test_v4_exam_points_carry_no_importance():
    p, value = full_result()
    points = json.loads(p['points'])
    points['points'][0]['importance_basis'] = []
    p['points'] = json.dumps(points)
    with pytest.raises(ValueError, match='carry no importance'):
        consume(value, p)


def test_a_keeper_is_never_merged_away_in_a_later_group():
    """Review 2026-11-11: Q2~Q1 in one goal, Q1~Q3 in another, Q3 more important → Q1 stays (it keeps Q2's goal)."""
    b, bank = scenario()
    weighed = copy.deepcopy(bank)
    next(q for q in weighed['questions'] if q['question_id'] == 'Q3').update(importance=5)
    groups = [{'direction_id': 'D1', 'status': 'covered', 'duplicates': [{'question_ids': ['Q1', 'Q2'], 'reason': 'a'}]},
              {'direction_id': 'D2', 'status': 'covered', 'duplicates': [{'question_ids': ['Q1', 'Q3'], 'reason': 'b'}]}]
    merged = c.merged_duplicates(groups, weighed, {'Q1': 'ok', 'Q2': 'ok', 'Q3': 'ok'})
    assert [(m['question_id'], m['kept']) for m in merged] == [('Q2', 'Q1'), ('Q3', 'Q1')]
    # A question that cannot be placed is never the keeper.
    merged = c.merged_duplicates(groups[:1], weighed, {'Q1': 'ok', 'Q2': 'ok', 'Q3': 'ok'}, placeable={'Q2', 'Q3'})
    assert merged == []


def test_the_carry_over_fingerprint_is_the_question_content():
    from studyez_contracts.roots.validate import task_fingerprints
    b, bank = scenario()
    doc, _ = build(b, bank, rows())
    before = task_fingerprints(doc)
    other = copy.deepcopy(doc)
    other['bank_snapshot']['concepts'][0]['title'] = 'Renamed concept'          # bank context only
    next(q for q in other['bank_snapshot']['questions'] if q['question_id'] == 'Q1').update(tier='Core', importance=4)
    assert task_fingerprints(other) == before
    next(q for q in other['bank_snapshot']['questions'] if q['question_id'] == 'Q1')['answer'] = 'Changed answer'
    changed = task_fingerprints(other)
    assert [t for t in before if before[t] != changed[t]] == [t['task_id'] for t in doc['tasks'] if t['question_id'] == 'Q1']


# ---------------------------------------------------------------- placement by evidence (2026-11-11-place-by-evidence)
def partial_rows(rid='R1'):
    """D1's only component is too big for Q3 to answer whole: Q3's row says missing, but the judgment reviewed it
    for D1 (261102_02 /4 trial: Q001 host factors, Q003 environment factors on D001)."""
    r = rows()
    r[0]['evidence'][1] = ev('Q3', rid, [part('host', 'missing'), part('env', 'missing')]) if rid else \
        {**ev('Q3', 'R1', [part('host', 'missing'), part('env', 'missing')]), 'tested_relation_ids': []}
    r[0]['status'] = 'missing'                      # env is now asked by nobody
    return r


def test_a_question_reviewed_for_a_goal_is_placed_there_even_if_it_answers_no_whole_part():
    b, bank = scenario()
    doc, placed = build(b, bank, partial_rows())
    assert ('Q3', 'D1') in tasks(doc) and placed['unplacedQuestions'] == []
    # Completeness still follows the answered parts: D1 is not covered and stays an add-stage gap.
    goal = next(g for g in v3.coverage_input(b, bank)['goals'] if g['direction_id'] == 'D1')
    assert not c.full(partial_rows()[0], goal) and c.missing_components(partial_rows()[0], goal) == ['env']
    assert c.not_ready(b, partial_rows(), [review(q['question_id']) for q in bank['questions']]) == [{'direction_id': 'D1', 'reason': 'partial'}]


def test_a_reviewed_question_without_any_tested_relation_stays_unplaced():
    b, bank = scenario()
    doc, placed = build(b, bank, partial_rows(rid=None))
    assert ('Q3', 'D1') not in tasks(doc)
    assert [u['question_id'] for u in placed['unplacedQuestions']] == ['Q3']


def test_duplicates_may_group_questions_reviewed_for_the_goal():
    b, bank = scenario()
    ctx = v3.coverage_input(b, bank)
    r = partial_rows()
    r[0]['duplicates'] = [{'question_ids': ['Q1', 'Q3'], 'reason': 'Same recall'}]
    c.check_coverage({'rows': r}, ctx['goals'], ctx['questions'])


def test_a_question_with_rows_but_no_tested_relation_goes_to_the_supplement():
    """261102_02 /4 trial: 10 questions had evidence rows without relations, so neither placed nor supplemented."""
    b, bank = scenario()
    assert c.off_goal(bank, rows()) == []
    assert c.off_goal(bank, partial_rows(rid=None)) == ['Q3']
    unknown = rows()
    unknown[1]['status'] = 'unknown'
    assert c.off_goal(bank, unknown) == ['Q2']
