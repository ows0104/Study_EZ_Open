"""answer-level/1 (docs/changes/2026-11-26-answer-holds-the-link): the question that asks a link is at least as important
as the questions whose stems give it (R3), and an exam year whose question asked something coarser than this question's
answer does not count for it (R2).

Shape of 피부근염 261124_02: 「근염 특이 항체 3가지」 was Optional while the Must-Know question on anti-synthetase stood
on it, and four exam years on 「MRI helps to tell relapse from steroid myopathy」 sat on a question that gave that
judgment in its stem and asked which imaging."""
import copy

import pytest
from studyez_contracts.bank import importance as imp
from studyez_contracts.roots import generation_v4 as c
from studyez_contracts.roots.validate import document_hash

from test_generation_v4 import PROFILE, basis, consume, full_result, result, review, rows, scenario, v4_packet

EXAM = basis('current_exam', year=2025, reason='2025 #1') + basis('current_exam', year=2022, reason='2022 #25')    # 4.0: Must-Know


def tiers(table):
    return {q: r['tier'] for q, r in table['questions'].items()}


# ---------------------------------------------------------------- the table
def test_without_the_two_arguments_the_table_is_the_earlier_policy_exactly():
    found = {'Q1': EXAM, 'Q2': [], 'Q3': basis('learning_objective')}
    assert imp.question_table(found, PROFILE) == imp.question_table(found, PROFILE, None, None, None)
    assert imp.question_table(found, PROFILE)['policy'] == imp.POLICY
    assert imp.question_table(found, PROFILE, ['Q2'])['policy'] == imp.POLICY2


def test_a_trunk_takes_the_highest_tier_of_the_questions_standing_on_it():
    found = {'Q1': EXAM, 'Q2': [], 'Q3': basis('learning_objective')}
    table = imp.question_table(found, PROFILE, None, {'Q2': ['Q3', 'Q1']})
    assert table['policy'] == imp.POLICY3 and tiers(table) == {'Q1': 'Essential', 'Q2': 'Essential', 'Q3': 'Core'}
    assert table['questions']['Q2']['rule'] == 'carries' and table['questions']['Q1']['rule'] == 'sum'
    assert table['carries'] == {'Q2': ['Q3', 'Q1']} and 'marked' not in table


def test_a_chain_is_followed_to_its_end_and_nothing_is_lowered():
    found = {'Q1': EXAM, 'Q2': [], 'Q3': []}
    # Q3 asks what Q2's stem gives, Q2 asks what Q1's stem gives; listed leaf-last on purpose
    table = imp.question_table(found, PROFILE, None, {'Q3': ['Q2'], 'Q2': ['Q1']})
    assert tiers(table) == {'Q1': 'Essential', 'Q2': 'Essential', 'Q3': 'Essential'}
    table = imp.question_table(found, PROFILE, None, {'Q1': ['Q2']})       # a lower leaf changes nothing
    assert tiers(table) == {'Q1': 'Essential', 'Q2': 'Optional', 'Q3': 'Optional'}
    assert table['questions']['Q1']['rule'] == 'sum'


def test_an_exclusion_is_neither_raised_nor_raises():
    out = basis('exam_exclusion', quote='안 낸다')
    table = imp.question_table({'Q1': EXAM, 'Q2': out, 'Q3': []}, PROFILE, None, {'Q2': ['Q1'], 'Q3': ['Q2']})
    assert tiers(table) == {'Q1': 'Essential', 'Q2': 'Optional', 'Q3': 'Optional'}
    assert table['questions']['Q2']['rule'] == 'exclusion'


def test_the_marked_floor_and_the_carried_floor_live_in_one_table():
    table = imp.question_table({'Q1': [], 'Q2': [], 'Q3': []}, PROFILE, ['Q1'], {'Q2': ['Q1']})
    assert tiers(table) == {'Q1': 'Core', 'Q2': 'Core', 'Q3': 'Optional'} and table['marked'] == ['Q1']
    warnings = c.importance_warnings(table)
    assert warnings['markedFloor'] == ['Q1'] and warnings['carriedFloor'] == ['Q2'] and warnings['offLevelExam'] == {}


def test_off_level_exam_years_do_not_count_but_stay_in_the_basis():
    found = {'Q1': EXAM + basis('clinical'), 'Q2': EXAM, 'Q3': []}
    table = imp.question_table(found, PROFILE, None, None, {'Q1': [2025, 2022], 'Q2': [2022]})
    assert tiers(table) == {'Q1': 'Important', 'Q2': 'Core', 'Q3': 'Optional'}       # 1.0 clinical / 2.0 one year
    assert table['questions']['Q1']['basis'] == found['Q1'] and table['questions']['Q1']['offLevelExamYears'] == [2022, 2025]
    assert table['offLevel'] == {'Q1': [2022, 2025], 'Q2': [2022]}
    # a forecast is the professor's own word about this content: it stays Must-Know
    table = imp.question_table({'Q1': EXAM + basis('exam_forecast', quote='MRI로 알 수 있다'), 'Q2': [], 'Q3': []},
                               PROFILE, None, None, {'Q1': [2025, 2022]})
    assert tiers(table)['Q1'] == 'Essential'


@pytest.mark.parametrize('carries, off, message', [
    ({'Q9': ['Q1']}, None, 'carries must map'),
    ({'Q1': ['Q1']}, None, 'carries must map'),
    ({'Q1': []}, None, 'carries must map'),
    (None, {'Q1': [1999]}, 'does not cite'),
    (None, {'Q1': []}, 'non-empty'),
    (None, {'Q9': [2025]}, 'must name questions'),
])
def test_malformed_arguments_are_refused(carries, off, message):
    with pytest.raises(imp.ImportanceError, match=message):
        imp.question_table({'Q1': EXAM, 'Q2': [], 'Q3': []}, PROFILE, None, carries, off)


# ---------------------------------------------------------------- who stands on whom
def link(qid, by=(), point=None):
    return {'question_id': qid, 'a': 'A', 'b': 'B', 'link': 'A에 B가 있다.', 'recalled_by': list(by), 'point_id': point}


def test_carried_by_reads_the_recalling_questions_and_the_whole_answers_of_existence_goals():
    b, bank = scenario()
    assert c.carried_by(b, bank, rows(), None) == {}
    assert c.carried_by(b, bank, rows(), [link('Q3', ['Q2']), link('Q1', ['Q2'])]) == {'Q2': ['Q1', 'Q3']}
    # a link nobody recalled got point P1 → goals D1 and D2; only Q2 answers a whole goal (D2)
    assert c.carried_by(b, bank, rows(), [link('Q1', point='P1')]) == {'Q2': ['Q1']}
    # a question does not stand on itself, and a question that left the bank is dropped
    assert c.carried_by(b, bank, rows(), [link('Q2', point='P1'), link('Q9', ['Q2']), link('Q1', ['Q9'])]) == {}


# ---------------------------------------------------------------- the item review
def test_the_review_names_off_level_years_only_when_asked_and_only_cited_ones():
    ctx = {'questions': [{'question_id': 'Q1', 'prerequisites': []}], 'exam_level': True,
           'question_importance': [{'question_id': 'Q1', 'importance_basis': EXAM}]}
    schema = c.review_schema(ctx)['properties']['reviews']['items']
    assert c.OFF_LEVEL in schema['required'] and 'relations' not in schema['required']
    assert c.OFF_LEVEL not in c.review_schema({})['properties']['reviews']['items']['properties']
    value = {'reviews': [{**review('Q1'), c.OFF_LEVEL: [2025]}]}
    assert c.check_review_input(value, ctx) == value
    value['reviews'][0][c.OFF_LEVEL] = [2019]
    with pytest.raises(ValueError, match='off-level exam year'):
        c.check_review_input(value, ctx)
    value['reviews'][0][c.OFF_LEVEL] = [2025, 2025]
    with pytest.raises(ValueError, match='duplicate'):
        c.check_review_input(value, ctx)
    with pytest.raises(ValueError):
        c.check_review_input({'reviews': [review('Q1')]}, ctx)                 # asked, not answered


def test_off_level_years_follow_the_basis_a_fix_left():
    reviews = [{'question_id': 'Q1', c.OFF_LEVEL: [2025, 2022]}, {'question_id': 'Q2', c.OFF_LEVEL: []}, {'question_id': 'Q3'}]
    assert c.off_level_years(reviews, {'Q1': EXAM, 'Q2': EXAM, 'Q3': []}) == {'Q1': [2022, 2025]}
    assert c.off_level_years(reviews, {'Q1': basis('current_exam', year=2025), 'Q2': [], 'Q3': []}) == {'Q1': [2025]}
    assert c.off_level_years(reviews, {'Q1': [], 'Q2': [], 'Q3': []}) == {}


# ---------------------------------------------------------------- assembly and the consumer
def leveled(found, off, presuppositions):
    """A result made with answer-level/1: the same judgments, the policy in the manifest, the years on the reviews."""
    b, bank = scenario()
    p = v4_packet(bank)
    value = result(p, b, bank, rows(), found)
    meta = value['manifest']
    for r in meta['itemReviews']:
        r[c.OFF_LEVEL] = off.get(r['question_id'], [])
    for e in meta['verdictLedger']:
        e['value'][c.OFF_LEVEL] = off.get(e['key'], [])
    meta.update(verdictLedgerHash=document_hash(meta['verdictLedger']), answerLevel={'policy': c.ANSWER_LEVEL},
                presuppositions=presuppositions)
    doc, placed, proofs = c.assemble(b, bank, value['sourceAudit'], rows(), found, PROFILE, revision=p['revision'], title=p['title'],
                                     exam_date=p['examDate'], presuppositions=presuppositions, item_reviews=meta['itemReviews'],
                                     answer_level=True)
    value['document'] = doc
    meta.update(bankHash=document_hash(doc['bank_snapshot']), importanceProjection=proofs['importanceProjection'],
                readiness=c.readiness(b, rows(), doc), **placed)
    return p, value


def test_assembly_applies_both_and_the_consumer_rebuilds_the_same_document():
    found = {'Q1': EXAM, 'Q2': [], 'Q3': EXAM}
    p, value = leveled(found, {'Q3': [2025, 2022]}, [link('Q1', ['Q2'])])
    got = {q['question_id']: q['tier'] for q in value['document']['bank_snapshot']['questions']}
    assert got == {'Q1': 'Essential', 'Q2': 'Essential', 'Q3': 'Optional'}
    proof = value['manifest']['importanceProjection']
    assert proof['policy'] == imp.POLICY3 and proof['table']['carries'] == {'Q2': ['Q1']}
    assert consume(value, p) == value['document']
    # the consumer recomputes from the recorded judgments: dropping the policy changes the projection
    del value['manifest']['answerLevel']
    with pytest.raises(ValueError, match='off-level exam years without the answer-level policy'):
        consume(value, p)


def test_a_raised_trunk_without_a_task_is_reported():
    """2026-11-26 피부근염 2회: 「MSA 세 계열」 was carried to Must-Know but sat on a relation the map check called a
    conflict, so no goal took it. The warning names it; nothing is blocked."""
    from test_generation_v4 import map_ok, JUDGMENT
    from studyez_contracts.roots import generation_v2 as v2, generation_v3 as v3
    b, bank = scenario()
    coverage = rows()
    coverage[1] = {**coverage[1], 'status': 'missing', 'evidence': []}           # nobody places Q2 on D2
    reviews = [review(q['question_id']) for q in bank['questions']]
    raw = c.assessment_raw(b, bank, coverage, map_ok(b), reviews, v3.context_summary(JUDGMENT), 'Synthetic', 'evidence')
    audit = c.compile_assessment(b, bank, v2.envelope(b, bank, raw), 'evidence')
    p = v4_packet(bank)
    args = (b, bank, audit, coverage, {'Q1': EXAM, 'Q2': [], 'Q3': []}, PROFILE)
    kw = dict(revision=p['revision'], title=p['title'], exam_date=p['examDate'], presuppositions=[link('Q1', ['Q2'])],
              item_reviews=[{**r, c.OFF_LEVEL: []} for r in reviews])
    doc, placed, proofs = c.assemble(*args, **kw, answer_level=True)
    assert 'Q2' not in {t['question_id'] for t in doc['tasks']} and [u['question_id'] for u in placed['unplacedQuestions']] == ['Q2']
    assert proofs['importanceWarnings']['carriedFloor'] == ['Q2'] and proofs['importanceWarnings']['carriedUnplaced'] == ['Q2']
    assert 'carriedUnplaced' not in c.assemble(*args, **kw)[2]['importanceWarnings']


def test_a_result_made_before_the_policy_is_assembled_as_before():
    p, value = full_result()
    assert 'answerLevel' not in value['manifest'] and consume(value, p) == value['document']
    assert value['manifest']['importanceProjection']['policy'] == imp.POLICY


def test_the_policy_needs_the_years_on_every_review():
    p, value = leveled({'Q1': EXAM, 'Q2': [], 'Q3': []}, {}, None)
    assert consume(value, p) == value['document']
    broken = copy.deepcopy(value)
    del broken['manifest']['itemReviews'][0][c.OFF_LEVEL]
    with pytest.raises(ValueError):
        consume(broken, p)
    broken = copy.deepcopy(value)
    broken['manifest']['answerLevel'] = {'policy': 'answer-level/9'}
    with pytest.raises(ValueError, match='unknown answer-level policy'):
        consume(broken, p)
