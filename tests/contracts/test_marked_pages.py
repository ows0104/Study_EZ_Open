"""Pages the professor marked for the exam are at least Core (docs/changes/2026-11-25-professor-marked-pages).

Shape of 전신경화증 261124_01: the notes quote the professor ("시험은 햇살 슬라이드만"), the sun pages are the
lecture's own pages, and every question answering a goal from those pages is raised to Core; nothing else moves."""
import copy

import pytest
from studyez_contracts.bank import importance as imp
from studyez_contracts.roots import generation_v4 as c
from studyez_contracts.learning_links.validate import LinkValidationError as ContractError

from test_generation_v4 import (PROFILE, basis, full_result, consume, result, rows, scenario, v4_packet)

MARKED = {'instruction': {'quote': '시험은 오른쪽 위에 햇살 그림이 있는 슬라이드만 열심히 보고 외워두면 된다',
                          'refs': [{'source_id': 'S2', 'pages': [1]}], 'year': 2026, 'source': 'notes'},
          'marker': '강의록 원래의 해 모양 아이콘', 'pages': [{'source_id': 'S1', 'pages': [8]}]}


def marked_profile(**instruction):
    value = copy.deepcopy(MARKED)
    value['instruction'].update(instruction)
    return {**PROFILE, 'marked_pages': value}


def split():
    """T1 (D1: Q1 host, Q3 env) from P1 on page 8; T2 (D2: Q2) from P2 on page 3."""
    b, bank = scenario()
    t1 = b['targets'][0]
    t2 = copy.deepcopy(t1)
    t2.update(target_id='T2', directions=[t1['directions'][1]])
    t1['directions'] = [t1['directions'][0]]
    for t in (t1, t2):
        t['relation_ids'] = sorted({r for d in t['directions'] for r in d['relation_ids']})
    b['targets'].append(t2)
    p1 = b['points'][0]
    p1['evidence'] = [{'source_id': 'S1', 'locator': 'p8', 'pages': [8]}]
    p2 = copy.deepcopy(p1)
    p2.update(point_id='P2', evidence=[{'source_id': 'S1', 'locator': 'p3', 'pages': [3]}], target_ids=['T2'])
    b['points'].append(p2)
    for source in b['sources']:
        source['page_count'] = 40
    return b, bank


# ---------------------------------------------------------------- the floor itself
@pytest.mark.parametrize('rows_, expected', [
    ([], 'Core'),                                                    # Optional → Core
    (basis('slide_emphasis'), 'Core'),                               # Important → Core
    (basis('learning_objective'), 'Core'),                           # Core stays
    (basis('exam_forecast', quote='꼭 낸다'), 'Essential'),           # Must-Know stays
    (basis('exam_exclusion', quote='안 낸다'), 'Optional'),            # the professor's exclusion outranks the page
])
def test_a_marked_question_is_at_least_core(rows_, expected):
    assert imp.score(rows_, 'slide', marked=True)['tier'] == expected


def test_the_rule_names_the_floor_and_unmarked_is_unchanged():
    assert imp.score([], 'slide', marked=True)['rule'] == 'marked_page'
    assert imp.score(basis('learning_objective'), 'slide', marked=True)['rule'] == 'sum'
    for rows_ in ([], basis('slide_emphasis'), basis('writer_mark')):
        assert imp.score(rows_, 'slide', marked=False) == imp.score(rows_, 'slide')


def test_without_marked_pages_the_table_is_policy_one_exactly():
    table = imp.question_table({'Q1': [], 'Q2': basis('slide_emphasis')}, PROFILE)
    assert table['policy'] == imp.POLICY and 'marked' not in table
    two = imp.question_table({'Q1': [], 'Q2': basis('slide_emphasis')}, PROFILE, {'Q1'})
    assert two['policy'] == imp.POLICY2 and two['marked'] == ['Q1']
    assert two['questions']['Q1']['tier'] == 'Core' and two['questions']['Q2'] == table['questions']['Q2']
    with pytest.raises(ValueError, match='questions of the table'):
        imp.question_table({'Q1': []}, PROFILE, {'Q9'})


# ---------------------------------------------------------------- the record
@pytest.mark.parametrize('tamper, message', [
    (lambda m: m['instruction'].update(quote=' '), "professor's words"),
    (lambda m: m['instruction'].update(source='writer'), 'year and source'),
    (lambda m: m['instruction'].pop('year'), 'year and source'),
    (lambda m: m['instruction'].update(refs=[]), 'instruction refs'),
    (lambda m: m.update(pages=[{'source_id': 'S1', 'pages': [0]}]), 'pages need'),
    (lambda m: m.update(pages=[{'source_id': 'S1', 'pages': [8]}, {'source_id': 'S1', 'pages': [9]}]), 'each source once'),
    (lambda m: m.update(marker=None), 'marker'),
])
def test_marked_pages_shape(tamper, message):
    value = copy.deepcopy(MARKED)
    tamper(value)
    doc = {'schema_version': 'exam-point-extract/4', 'title': 'S', 'notebook_profile': {**PROFILE, 'marked_pages': value},
           'points': [{'point_id': 'P1', 'point': 'x', 'source_refs': []}]}
    with pytest.raises(ContractError, match=message):
        c.check_points(doc)


def test_an_admin_record_needs_no_note_reference():
    value = copy.deepcopy(MARKED)
    value['instruction'].update(source='admin', refs=[])
    assert c.check_marked_pages(value) is value


def test_words_from_an_earlier_year_are_not_applied_unless_the_admin_records_them():
    assert c.marked_pages(marked_profile(), '2026-11-27') == {'S1': {8}}
    assert c.marked_pages(marked_profile(year=2023), '2026-11-27') is None
    assert c.marked_pages(marked_profile(year=2023), None) is None
    assert c.marked_pages(marked_profile(year=2023, source='admin'), '2026-11-27') == {'S1': {8}}
    assert c.marked_pages(PROFILE, '2026-11-27') is None


# ---------------------------------------------------------------- which questions
def test_marked_questions_are_the_answers_of_goals_from_marked_pages():
    b, _ = split()
    assert c.marked_points(b, {'S1': {8}}) == ['P1']
    assert c.marked_questions(b, rows(), {'S1': {8}}) == ['Q1', 'Q3']
    assert c.marked_questions(b, rows(), {'S1': {3}}) == ['Q2']
    assert c.marked_questions(b, rows(), {'S2': {8}}) == []


def test_a_question_that_only_mentions_the_goal_does_not_count():
    b, _ = split()
    coverage = rows()
    for e in coverage[0]['evidence']:
        if e['question_id'] == 'Q3':
            for p in e['components']:
                p.update(location='stem', answer_unit_indices=[])
    assert c.marked_questions(b, coverage, {'S1': {8}}) == ['Q1']


# ---------------------------------------------------------------- assembly and the consumer
def test_assembly_raises_marked_answers_and_leaves_the_rest():
    b, bank = split()
    p = v4_packet(bank)
    found = {'Q1': [], 'Q2': [], 'Q3': basis('slide_emphasis')}
    p['examDate'] = '2026-11-27'
    value = result(p, b, bank, rows(), found)
    plain = {q['question_id']: q['tier'] for q in value['document']['bank_snapshot']['questions']}
    assert plain == {'Q1': 'Optional', 'Q2': 'Optional', 'Q3': 'Important'}

    import json
    points = json.loads(p['points'])
    points['notebook_profile'] = marked_profile()
    p['points'] = json.dumps(points, ensure_ascii=False)
    import test_generation_v4 as t
    original, t.PROFILE = t.PROFILE, marked_profile()
    try:
        value = result(p, b, bank, rows(), found)
    finally:
        t.PROFILE = original
    tiers = {q['question_id']: q['tier'] for q in value['document']['bank_snapshot']['questions']}
    assert tiers == {'Q1': 'Core', 'Q2': 'Optional', 'Q3': 'Core'}
    proof = value['manifest']['importanceProjection']
    assert proof['policy'] == imp.POLICY2 and proof['table']['marked'] == ['Q1', 'Q3']
    assert consume(value, p) == value['document']
    # The consumer recomputes the floor from the packet's profile: dropping the record changes the projection.
    points['notebook_profile'] = PROFILE
    p['points'] = json.dumps(points, ensure_ascii=False)
    with pytest.raises(ValueError, match='projections differ'):
        consume(value, p)


def test_the_report_counts_goals_and_core_questions_per_page():
    b, bank = split()
    found = {'Q1': [], 'Q2': [], 'Q3': []}
    table = c.question_table(found, marked_profile(), bank, c.marked_questions(b, rows(), {'S1': {8}}))
    report = c.marked_report(b, rows(), {'S1': {8, 9}}, table)
    assert report == [{'source_id': 'S1', 'page': 8, 'points': 1, 'goals': 1, 'covered': 1, 'coreOrAbove': 2},
                      {'source_id': 'S1', 'page': 9, 'points': 0, 'goals': 0, 'covered': 0, 'coreOrAbove': 0}]
    assert c.importance_warnings(table)['markedFloor'] == ['Q1', 'Q3']


def test_a_result_without_marked_pages_still_validates():
    p, value = full_result()
    assert consume(value, p) == value['document']
    assert value['manifest']['importanceProjection']['policy'] == imp.POLICY


# ---------------------------------------------------------------- supplement may add the admin's pages
def test_a_supplement_may_add_only_the_admins_marked_pages():
    admin = copy.deepcopy(MARKED)
    admin['instruction'].update(source='admin', refs=[])
    assert c.added_profile(PROFILE, PROFILE)
    assert c.added_profile(PROFILE, {**PROFILE, 'marked_pages': admin})
    assert not c.added_profile(PROFILE, {**PROFILE, 'marked_pages': MARKED})       # the notes' words need a new extraction
    assert not c.added_profile(PROFILE, {**PROFILE, 'legend': 'changed', 'marked_pages': admin})
    assert not c.added_profile({**PROFILE, 'marked_pages': MARKED}, {**PROFILE, 'marked_pages': admin})


def test_with_review_evidence_the_answer_page_decides():
    """review-evidence/1: the page the item review checked the answer on, not the goal's other pages."""
    b, _ = split()
    reviews = [{'question_id': 'Q1', 'evidence': {'mode': 'single', 'reason': 'x', 'slides': [{'page': 9, 'evidence': 'x'}]}},
               {'question_id': 'Q2', 'evidence': {'mode': 'single', 'reason': 'x', 'slides': [{'page': 8, 'evidence': 'x'}]}},
               {'question_id': 'Q3', 'evidence': {'mode': 'unresolved', 'reason': 'x', 'slides': []}}]
    assert c.marked_questions(b, rows(), {'S1': {8}}, reviews, 'S1') == ['Q2']
    assert c.marked_questions(b, rows(), {'S1': {8}}, reviews, 'S2') == []
    assert c.marked_goals(b, {'S1': {8}}) == ['D1']
