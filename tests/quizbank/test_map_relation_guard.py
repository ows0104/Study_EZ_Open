"""review-relations/2 through the /4 generator with a synthetic model (docs/changes/2026-11-14-map-relation-guard).

A: a map goal with no content relation of its own goes to the brief fix, and the run stops if it stays so.
B: a question its item review ties to no goal is placed by the relations its coverage evidence names.
C: one still off the map goes to the supplement once more after the review.
D: an ok question left off the map stops the run before the medical review."""
import copy
import json

import pytest

from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import validate_result as consume
from tests.quizbank.test_root_generation_v4 import Model, NoRelationModel, run, tasks

NO_REVIEW_RELATION = {'Q1': [('R1', 'whole')], 'Q2': [], 'Q003': [('R2', 'whole')]}
LATE = ('v4-supplement-late', 'v4-supplement-normalize-late')


class LateModel(NoRelationModel):
    """Neither Q2's review nor its D1 coverage row names a relation: only the late supplement can place it."""

    def __init__(self, keep_off=False):
        super().__init__(relations=NO_REVIEW_RELATION)
        self.keep_off = keep_off   # D: the new goal's coverage judgment does not find Q2 there either

    def __call__(self, stage, ctx, material, model):
        if stage in LATE:
            self.calls.append(stage)
            value, info = super().__call__(stage[:-len('-late')], ctx, material, model)
            self.calls.pop()
            return value, info
        value, info = super().__call__(stage, ctx, material, model)
        if self.keep_off and stage == 'v4-coverage-supplement-late':
            for row in value['rows']:
                row.update(evidence=[], status='missing')
        return value, info


class HierarchyModel(Model):
    """normalize writes R2 as a hierarchy edge, so D2 has no content relation; the brief fix restores it or not."""

    def __init__(self, repair=True):
        super().__init__()
        self.repair = repair

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model) if stage != 'v4-brief-fix' else (None, {})
        if stage == 'normalize':
            next(r for r in value['relations'] if r['relation_id'] == 'R2')['kind'] = 'classification'
        if stage == 'v4-brief-fix':
            self.calls.append(stage)
            self.inputs[stage] = ctx
            fixed = copy.deepcopy(ctx['brief'])
            fixed['provenance']['independent_points'] = 'derived'
            if self.repair:
                next(r for r in fixed['relations'] if r['relation_id'] == 'R2')['kind'] = 'association'
            else:
                fixed['provenance']['notes'] = 'Synthetic: relations left as they were'
            return {'brief': fixed, 'map_change_reason': 'Synthetic map fix'}, {}
        return value, info


def test_a_new_run_names_review_relations_2():
    assert v4.REVIEW_PLACEMENT2 == 'review-relations/2' and 'review-coverage' in v4.PLACEMENTS


def test_b_a_question_its_review_ties_to_nothing_is_placed_by_its_coverage_evidence(tmp_path):
    p, model, result = run(tmp_path, Model(relations=NO_REVIEW_RELATION))
    assert consume(result, p) == result['document']
    assert result['manifest']['placement'] == {'policy': v4.REVIEW_PLACEMENT2}
    assert dict(tasks(result))['Q2'] == 'D1'
    assert result['manifest']['coverageFallback'] == [{'question_id': 'Q2', 'direction_id': 'D1'}]
    assert result['manifest']['unplacedQuestions'] == [] and not any(c in model.calls for c in LATE)


def test_c_a_question_off_the_map_after_the_review_gets_a_late_supplement_goal(tmp_path):
    p, model, result = run(tmp_path, LateModel())
    assert consume(result, p) == result['document']
    assert 'v4-supplement' not in model.calls and [c for c in model.calls if c in LATE] == list(LATE)
    assert [(d['question_id'], d['decision']) for d in result['manifest']['supplement']] == [('Q2', 'point')]
    placed = dict(tasks(result))
    assert placed['Q2'].startswith('DQ')
    assert result['manifest']['coverageFallback'] == [{'question_id': 'Q2', 'direction_id': placed['Q2']}]
    assert result['manifest']['unplacedQuestions'] == []


def test_d_an_ok_question_left_off_the_map_stops_before_the_medical_review(tmp_path):
    model = LateModel(keep_off=True)
    with pytest.raises(ValueError, match='지도에 못 붙은 문항 1개'):
        run(tmp_path, model)
    assert 'medical-0' not in model.calls
    ready = json.loads((tmp_path / 'out' / 'readiness.json').read_text(encoding='utf-8'))
    assert [u['question_id'] for u in ready['unplacedQuestions']] == ['Q2']


def test_a_a_goal_without_a_content_relation_goes_to_the_brief_fix(tmp_path):
    p, model, result = run(tmp_path, HierarchyModel())
    assert consume(result, p) == result['document']
    assert any(e.startswith('D2: 계층(classification) 관계만 있다') for e in model.inputs['v4-brief-fix']['errors'])
    assert v4.relation_findings(result['brief']) == []


def test_a_a_map_still_without_content_relations_stops_before_the_coverage_judgment(tmp_path):
    model = HierarchyModel(repair=False)
    with pytest.raises(ValueError, match='지도 관계 검사'):
        run(tmp_path, model)
    assert 'v4-brief-fix' in model.calls and not any(c.startswith('v4-coverage') for c in model.calls)
