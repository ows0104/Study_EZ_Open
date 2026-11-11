"""review-relations/1 through the /4 generator with a synthetic model (docs/changes/2026-11-11-place-by-review)."""
import pytest

from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import validate_result as consume
from tests.quizbank.test_root_generation_v4 import Model, run, tasks


def test_a_new_run_reviews_with_the_supported_map_relations_and_places_by_them(tmp_path):
    p, model, result = run(tmp_path)
    reviews = [ctx for stage, ctx in model.inputs.items() if stage.startswith('v4-review')]
    assert reviews and all([r['relation_id'] for r in ctx['map_relations']] == ['R1', 'R2'] for ctx in reviews)
    assert result['manifest']['placement'] == {'policy': v4.REVIEW_PLACEMENT}
    assert all('relations' in r for r in result['manifest']['itemReviews'])
    assert consume(result, p) == result['document']
    assert tasks(result) == [('Q003', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]


def test_the_review_not_the_coverage_judgment_decides_the_goal(tmp_path):
    """The coverage judgment names R1 for Q2; the review says Q2 recalls part of R2, so Q2 goes to D2."""
    relations = {'Q1': [('R1', 'whole')], 'Q2': [('R2', 'partial')], 'Q003': [('R2', 'whole')]}
    p, model, result = run(tmp_path, Model(relations=relations))
    assert consume(result, p) == result['document']
    assert dict(tasks(result))['Q2'] == 'D2'


def test_a_question_the_review_finds_no_relation_for_stays_off_the_map(tmp_path):
    p, model, result = run(tmp_path, Model(relations={'Q1': [('R1', 'whole')], 'Q2': [], 'Q003': [('R2', 'whole')]}))
    assert consume(result, p) == result['document']
    assert [u['question_id'] for u in result['manifest']['unplacedQuestions']] == ['Q2']
    assert result['manifest']['unplacedQuestions'][0]['reason'].startswith('no-relation')


def test_an_unknown_relation_stops_the_review_stage(tmp_path):
    with pytest.raises(ValueError, match='not a supported map relation'):
        run(tmp_path, Model(relations={'Q1': [('R9', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')]}))


def test_a_question_judged_without_a_relation_waits_for_its_review_not_the_supplement(tmp_path):
    """Review 2026-11-11: under the evidence rule Q2 (judged for D1 without a relation) became a supplement goal before
    any review; under review-relations/1 it is reviewed and placed by the relation its review names."""
    from tests.quizbank.test_root_generation_v4 import NoRelationModel
    p, model, result = run(tmp_path, NoRelationModel())
    assert consume(result, p) == result['document']
    assert 'v4-supplement' not in model.calls and result['manifest']['supplement'] == []
    assert dict(tasks(result))['Q2'] == 'D1'
