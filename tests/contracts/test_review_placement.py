"""review-relations/1: a question is placed by the map relations its item review names; the goal coverage judgment
only finds what is not asked yet (docs/changes/2026-11-11-place-by-review)."""
import copy

import pytest

from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import generation_v4 as c
from studyez_contracts.roots.automation import validate_result as consume
from tests.contracts.test_generation_v4 import (CONTEXT, JUDGMENT, PROFILE, ev, map_ok, part, partial_rows, recall_scenario,
                                                review, rows, scenario, tasks, v4_packet)


def reviewed(relations):
    """Item reviews with the relations each question recalls: {qid: [(relation_id, part)]}."""
    out = []
    for qid, claims in relations.items():
        r = review(qid)
        r['relations'] = [{'relation_id': rid, 'part': p, 'reason': 'Synthetic'} for rid, p in claims]
        out.append(r)
    return out


def assemble(b, bank, coverage, relations):
    reviews = reviewed(relations)
    raw = c.assessment_raw(b, bank, coverage, map_ok(b), reviews, CONTEXT, 'Synthetic /4 judgments', 'review')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw), 'review')
    doc, placed = c.make_document(b, bank, audit, coverage, revision='test', title='Synthetic', exam_date=None, placement='review')
    return doc, placed, audit


ALL = {'Q1': [('R1', 'whole')], 'Q2': [('R2', 'whole')], 'Q3': [('R1', 'partial')]}


def test_a_question_asking_part_of_a_goal_is_placed_by_its_relation():
    """Rickettsia Q001 shape: the coverage row says the component is missing and names no relation."""
    b, bank = scenario()
    coverage = partial_rows(rid=None)
    doc, placed, _ = assemble(b, bank, coverage, ALL)
    assert tasks(doc) == [('Q1', 'D1'), ('Q2', 'D2'), ('Q3', 'D1')]
    assert placed['unplacedQuestions'] == []
    # The coverage judgment still decides what is missing: D1's env component is asked by nobody.
    assert c.missing_components(coverage[0], b['targets'][0]['directions'][0]) == ['env']


def test_the_older_rule_leaves_that_question_without_a_goal():
    b, bank = scenario()
    raw = c.assessment_raw(b, bank, partial_rows(rid=None), map_ok(b), [review(q['question_id']) for q in bank['questions']],
                           CONTEXT, 'x', 'evidence')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw), 'evidence')
    _, placed = c.make_document(b, bank, audit, partial_rows(rid=None), revision='t', title='t', exam_date=None)
    assert [u['question_id'] for u in placed['unplacedQuestions']] == ['Q3']


def test_a_question_with_no_relation_is_off_the_map():
    b, bank = scenario()
    _, placed, _ = assemble(b, bank, rows(), {**ALL, 'Q3': []})
    assert placed['unplacedQuestions'] == [{'question_id': 'Q3', 'reason': placed['unplacedQuestions'][0]['reason']}]
    assert placed['unplacedQuestions'][0]['reason'].startswith('no-relation')


def test_a_goal_recalled_whole_comes_before_one_recalled_in_part():
    b, bank = scenario()
    doc, _, _ = assemble(b, bank, rows(), {**ALL, 'Q3': [('R1', 'partial'), ('R2', 'whole')]})
    assert dict(tasks(doc))['Q3'] == 'D2'
    doc, _, _ = assemble(b, bank, rows(), {**ALL, 'Q3': [('R1', 'whole'), ('R2', 'partial')]})
    assert dict(tasks(doc))['Q3'] == 'D1'


def test_reverse_and_inference_questions_are_placed_by_the_relation_they_use():
    """Rickettsia Q022 (organism given, disease asked) and Q030 (a judgment using a relation): no coverage row at all."""
    b, bank = scenario()
    coverage = rows()
    coverage[0]['evidence'] = coverage[0]['evidence'][:1]          # the coverage judgment never listed Q3
    doc, placed, _ = assemble(b, bank, coverage, {**ALL, 'Q3': [('R2', 'partial')]})
    assert dict(tasks(doc))['Q3'] == 'D2' and placed['unplacedQuestions'] == []


# ---------------------------------------------------------------- recall units (R5)
def test_a_recall_unit_goal_places_the_question_on_the_unit_it_answers():
    """The PR #90 rule put Q3 (answers env only) on D1_host, the first unit; the review rule puts it on D1_env."""
    b, bank = recall_scenario()
    doc, _, audit = assemble(b, bank, rows(), {'Q1': [('R1', 'whole')], 'Q2': [('R2', 'whole')], 'Q3': [('R1', 'whole')]})
    assert tasks(doc) == [('Q1', 'D1_host'), ('Q2', 'D2'), ('Q3', 'D1_env')]
    d1 = next(g for g in audit['goal_coverage'] if g['direction_id'] == 'D1')
    assert d1['confirmed_unit_ids'] == ['D1_host', 'D1_env'] and d1['status'] == 'confirmed'


def test_an_unanswered_unit_is_not_confirmed():
    """Rickettsia U054_1: only the units a question answers count; Q3 answering nothing keeps both units as candidates."""
    b, bank = recall_scenario()
    coverage = rows()
    coverage[0]['evidence'] = [ev('Q1', 'R1', [part('host', 'answer'), part('env', 'missing')]),
                               ev('Q3', 'R1', [part('host', 'missing'), part('env', 'missing')])]
    doc, _, audit = assemble(b, bank, coverage, {'Q1': [('R1', 'whole')], 'Q2': [('R2', 'whole')], 'Q3': [('R1', 'partial')]})
    d1 = next(g for g in audit['goal_coverage'] if g['direction_id'] == 'D1')
    assert d1['confirmed_unit_ids'] == ['D1_host'] and d1['status'] == 'partial'
    # Q3 answers neither unit: both stay candidates and map order picks one.
    assert dict(tasks(doc))['Q3'] == 'D1_host'
    q3 = next(r for r in audit['assessment']['assessment']['question_reviews'] if r['question_id'] == 'Q3')
    assert q3['relations'][0]['direction_ids'] == ['D1']


# ---------------------------------------------------------------- the consumer
def review_result(relations=ALL, coverage=rows, scene=scenario, marker=True, placement='review'):
    """A /4 result made by the review rule, its item reviews recorded in the verdict ledger."""
    b, bank = scene()
    p = v4_packet(bank)
    b['lecture_id'] = p['subject'] + '/' + p['runId']
    cov = coverage()
    reviews = reviewed(relations) if placement == 'review' else [review(q['question_id']) for q in bank['questions']]
    raw = c.assessment_raw(b, bank, cov, map_ok(b), reviews, v3.context_summary(JUDGMENT), 'Synthetic /4 judgments', placement)
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw), placement)
    basis = {q['question_id']: [] for q in bank['questions']}
    doc, placed, proofs = c.assemble(b, bank, audit, cov, basis, PROFILE, revision=p['revision'], title=p['title'],
                                     exam_date=p['examDate'], placement=placement)
    ledger = [v3.ledger_entry('item', r['question_id'], v3.item_hash(next(q for q in bank['questions'] if q['question_id'] == r['question_id']), bank, []),
                              r, 'review-1') for r in reviews]
    medical = __import__('generation_v2_fixture').old.checks(bank)
    med_input = {'title': p['title'], 'bank': bank, 'clinicalInput': v2.medical_input(bank, []), 'medicalFinal': True, '_pipeline_version': c.POLICY}
    stage = lambda name, inp, out: {'name': name, 'status': 'completed', 'inputHash': document_hash(inp), 'outputHash': document_hash(out)}
    stages = [stage('normalize', {}, b), stage('v4-add-0', {}, {}), stage('v4-context-0', {}, JUDGMENT), stage('medical-0', med_input, medical)]
    meta = {'pipelineVersion': c.POLICY, 'inputHash': p['inputHash'], 'briefHash': document_hash(b), 'bankHash': document_hash(doc['bank_snapshot']),
            'model': 'synthetic', 'runtimeHash': '0' * 64, 'stages': stages, 'verdictLedger': ledger, 'verdictLedgerHash': document_hash(ledger),
            'addRounds': 1, 'notReady': c.not_ready(b, cov, reviews), 'offGoalQuestions': [], 'rejectedAtIntake': [], 'supplement': [],
            'initialBrief': b, 'supplementPoints': None, 'intakeProjection': v3.intake_projection(p['intakeBank']['bank'])[1],
            'initialBank': copy.deepcopy(bank), 'coverage': cov, 'mapCheck': map_ok(b),
            'itemReviews': reviews, 'clinicalContext': JUDGMENT, 'contextJudgments': [JUDGMENT], 'medicalUnreviewed': [],
            'readiness': c.readiness(b, cov, doc), 'clinicalConflicts': [], 'medicalFinal': True,
            'sourceAssessment': raw, 'fixes': [], 'questionImportance': basis, 'importanceNotes': c.importance_notes(reviews),
            **placed, **{k: v for k, v in proofs.items() if k != 'importanceWarnings' and (k != 'bankProjection' or v)},
            **({'placement': {'policy': c.REVIEW_PLACEMENT}} if marker else {})}
    return p, {'brief': b, 'document': doc, 'sourceAudit': audit, 'medical': medical, 'validation': {}, 'manifest': meta}


def test_the_consumer_accepts_a_review_placed_result():
    p, value = review_result(coverage=lambda: partial_rows(rid=None))
    assert consume(value, p) == value['document']
    assert tasks(value['document']) == [('Q1', 'D1'), ('Q2', 'D2'), ('Q3', 'D1')]
    p, value = review_result(scene=recall_scenario)
    assert consume(value, p) == value['document']


def tampered(edit, **kw):
    p, value = review_result(**kw)
    value = copy.deepcopy(value)
    edit(value)
    return p, value


@pytest.mark.parametrize('edit, message', [
    (lambda v: v['document']['tasks'][2].update(direction_id='D2'), 'document|task|differ'),
    (lambda v: v['manifest']['itemReviews'][2]['relations'].append({'relation_id': 'R2', 'part': 'whole', 'reason': 'x'}),
     'not a recorded judgment'),
    (lambda v: v['manifest'].pop('placement'), 'assessment is not the gathered judgments'),
    (lambda v: v['manifest'].update(placement={'policy': 'other/1'}), 'unknown placement policy'),
])
def test_the_consumer_refuses_a_placement_the_reviews_do_not_give(edit, message):
    p, value = tampered(edit)
    with pytest.raises(ValueError, match=message):
        consume(value, p)


def test_a_marked_result_must_be_placed_by_the_review_rule():
    p, value = review_result(placement='evidence', marker=True)
    with pytest.raises(ValueError, match='names no map relations'):
        consume(value, p)


def test_review_relations_must_be_supported_map_relations():
    ctx = {'questions': [{'question_id': 'Q1', 'prerequisites': []}], 'map_relations': [{'relation_id': 'R1'}]}
    value = {'reviews': [{**review('Q1'), 'relations': [{'relation_id': 'R9', 'part': 'whole', 'reason': 'x'}]}]}
    with pytest.raises(ValueError, match='not a supported map relation'):
        c.check_review_input(value, ctx)
    value['reviews'][0]['relations'] = [{'relation_id': 'R1', 'part': 'whole', 'reason': 'x'}]
    assert c.check_review_input(value, ctx) == value
    assert 'relations' in c.review_schema(ctx)['properties']['reviews']['items']['required']
    assert c.review_schema({}) is c.ITEM_REVIEW_OUTPUT


def test_only_supported_relations_reach_the_review():
    b, _ = scenario()
    checks = map_ok(b)
    checks['relation_checks'][1]['status'] = 'unsupported'
    assert [r['relation_id'] for r in c.map_relations(b, [checks])] == ['R1']


def test_a_unit_reached_by_another_relation_is_dropped_when_another_unit_is_answered():
    """Review 2026-11-11: Q3 answers env only but also claims R3, which only the host unit carries. Narrowing per claim
    kept D1_host (R3 reaches no answered unit); narrowing per goal drops it."""
    b, bank = recall_scenario()
    d1 = b['targets'][0]['directions'][0]
    r3 = copy.deepcopy(next(r for r in b['relations'] if r['relation_id'] == 'R1'))
    r3['relation_id'] = 'R3'
    b['relations'].append(r3)
    d1['relation_ids'] = d1['relation_ids'] + ['R3']
    b['targets'][0]['relation_ids'].append('R3')
    d1['recall_units'][0]['relation_ids'] = ['R1', 'R3']
    d1['recall_units'][1]['relation_ids'] = ['R1']
    doc, _, _ = assemble(b, bank, rows(), {'Q1': [('R1', 'whole')], 'Q2': [('R2', 'whole')], 'Q3': [('R1', 'partial'), ('R3', 'whole')]})
    assert dict(tasks(doc))['Q3'] == 'D1_env'
