"""Add/fix stages write importance only; code fills the tier, and quality advice reaches a question's first fix only
(docs/changes/2026-11-11-tier-from-importance). Pure functions, synthetic data."""
import copy

import pytest
import generation_v2_fixture as f
from studyez_contracts.learning_links.validate import validate_shape
from studyez_contracts.roots import generation_v3 as c

EMPTY_ADD = {'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}
EMPTY_FIX = {'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}


def bank():
    value = f.old.bank()
    for q in value['questions']:
        q.pop('stimuli', None)
    return value


def authored(base, qid, importance):
    q = copy.deepcopy(base)
    q.pop('stimuli', None)
    q.pop('tier', None)
    q.update(question_id=qid, question='Synthetic new question ' + qid, importance=importance)
    return q


def test_the_stage_schemas_ask_for_importance_only():
    for schema in (c.AUTHORED_QUESTION, c.AUTHORED_CONCEPT):
        assert 'tier' not in schema['properties'] and 'tier' not in schema['required']
        assert schema['properties']['importance']['enum'] == [2, 3, 4, 5]
    b = bank()
    q = authored(b['questions'][0], 'Q003', 4)
    validate_shape({'questions': [q], **EMPTY_ADD}, c.ADD_OUTPUT, 'add')
    with pytest.raises(Exception):
        validate_shape({'questions': [{**q, 'tier': 'Core'}], **EMPTY_ADD}, c.ADD_OUTPUT, 'add')
    with pytest.raises(Exception):
        validate_shape({'questions': [{**q, 'importance': 1}], **EMPTY_ADD}, c.ADD_OUTPUT, 'add')


@pytest.mark.parametrize('importance,tier', [(5, 'Essential'), (4, 'Core'), (3, 'Important'), (2, 'Optional')])
def test_an_added_question_takes_the_tier_its_importance_names(importance, tier):
    b = bank()
    ids = c.next_question_ids(b, 1)
    merged, _ = c.merge_added(b, [], {'questions': [authored(b['questions'][0], ids[0], importance)], **EMPTY_ADD}, ids)
    new = merged['questions'][-1]
    assert (new['importance'], new['tier']) == (importance, tier)
    assert merged['questions'][:-1] == b['questions']


def test_a_fixed_question_takes_its_tier_from_importance_and_an_old_output_tier_is_ignored():
    b = bank()
    fixed = copy.deepcopy(b['questions'][0])
    fixed.update(tier='Optional', importance=4)   # a cached stage output of an earlier run, out of step
    merged, _, changed = c.merge_fixes(b, [], {'questions': [fixed], **EMPTY_FIX}, ['Q1'])
    assert changed == ['Q1']
    assert (merged['questions'][0]['importance'], merged['questions'][0]['tier']) == (4, 'Core')
    assert merged['questions'][1] == b['questions'][1]


def test_quality_advice_reaches_only_the_first_fix(monkeypatch):
    import quizbank.connection_generate_v3 as g
    monkeypatch.setattr(g, 'validate_bank', lambda bank, sources: {'errors': ['Q2: synthetic format error']})
    monkeypatch.setattr(g.v2, 'quality_reasons', lambda bank: [
        {'kind': 'question_fix', 'text': '문항 품질: Q1: 회상 부담이 크다', 'question_ids': ['Q1'], 'direction_ids': []},
        {'kind': 'question_fix', 'text': '문항 품질: Q2: 회상 부담이 크다', 'question_ids': ['Q2'], 'direction_ids': []}])
    monkeypatch.setattr(g.v3, 'history_marked', lambda bank: [])
    first = g._bank_findings({}, [])
    assert set(first) == {'Q1', 'Q2'} and len(first['Q2']) == 2
    later = g._bank_findings({}, [], {'Q1': 1, 'Q2': 1})
    assert 'Q1' not in later                                  # advice only: the question is not sent back
    assert later['Q2'] == ['Q2: synthetic format error']      # a format error still is
