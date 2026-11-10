"""root-generation/4 end to end with a synthetic model (docs/changes/2026-11-10-importance-at-authoring/spec.md)."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import packet_hash, validate_result as consume


def basis(kind, quote=''):
    return [{'kind': kind, 'refs': [{'source_id': 'S1', 'pages': [1]}], 'quote': quote, 'reason': 'Synthetic', 'year': None}]


POINTS = {'schema_version': 'exam-point-extract/4', 'title': 'Synthetic lecture', 'notes': [],
          'notebook_profile': {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'},
          'points': [{'point_id': 'P1', 'point': 'Synthetic A/B point', 'source_refs': [{'source_id': 'S1', 'pages': [], 'locator': 'synthetic paragraph'}]}]}
INTAKE_BASIS = {'Q1': basis('exam_forecast', '꼭 나온다'), 'Q2': []}


def packet(tmp_path):
    p = f.old.packet(tmp_path / 'synthetic.txt')
    bank = f.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
        q['point_ids'] = []
    p.update(points=json.dumps(POINTS, ensure_ascii=False), generationPolicy=v4.POLICY,
             intakeBank={'bank': bank, 'visual_stimuli': [], 'clinical_conflicts': [],
                         'question_importance': [{'question_id': k, 'importance_basis': v} for k, v in INTAKE_BASIS.items()]})
    p['inputHash'] = packet_hash(p)
    return p


def authored(q):
    return {k: copy.deepcopy(v) for k, v in q.items() if k != 'stimuli'}


class Model:
    """D1 is asked by both Q1 and Q2 (one asks it whole, one too); D2 has no question until an add stage writes Q003.
    `duplicate`: the coverage judgment calls Q1 and Q2 the same recall in other words."""

    def __init__(self, duplicate=False, design_doubt=('Q1',)):
        self.calls, self.inputs = [], {}
        self.duplicate, self.design_doubt = duplicate, set(design_doubt)

    def __call__(self, stage, ctx, material, model):
        self.calls.append(stage)
        ctx = {k: v for k, v in ctx.items() if k != '_check'}
        self.inputs[stage] = ctx
        if stage == 'normalize':
            b = f.brief(ctx['sources'])
            b['lecture_id'] = ctx['lecture_id']
            b['points'][0]['point_id'] = 'P1'
            return b, {}
        assert not stage.startswith('v3-'), stage
        if stage.startswith('v4-coverage'):
            qids = {q['question_id'] for q in ctx['questions']}
            asks = {'D1': [('Q1', 'R1'), ('Q2', 'R1')], 'D2': [('Q003', 'R2')]}
            rows = []
            for goal in ctx['goals']:
                ev = [{'question_id': q, 'tested_relation_ids': [rid],
                       'components': [{'component_id': c['component_id'], 'location': 'answer', 'answer_unit_indices': [0], 'reason': 'x'}
                                      for c in goal['components']], 'visual_verdict': 'not_applicable', 'reason': 'Synthetic'}
                      for q, rid in asks.get(goal['direction_id'], []) if q in qids]
                dup = ([{'question_ids': ['Q1', 'Q2'], 'reason': 'Same recall'}]
                       if self.duplicate and goal['direction_id'] == 'D1' and {'Q1', 'Q2'} <= {e['question_id'] for e in ev} else [])
                rows.append({'direction_id': goal['direction_id'], 'status': 'covered' if ev else 'missing', 'evidence': ev,
                             'duplicates': dup, 'reason': 'Synthetic'})
            return {'rows': rows}, {}
        if stage.startswith('v4-map-check'):
            assert all('importance_basis' not in t for t in ctx['targets'])
            return {'relation_checks': [{'relation_id': r['relation_id'], 'status': 'supported', 'reason': 'x'} for r in ctx['relations']],
                    'target_checks': [{'target_id': t['target_id'], 'status': 'consistent', 'reason': 'x'} for t in ctx['targets']],
                    'direction_checks': [{'direction_id': gl['direction_id'], 'scope_status': 'consistent', 'reason': 'x'}
                                         for t in ctx['targets'] for gl in t['goals']], 'issues': []}, {}
        if stage.startswith('v4-add'):
            assert all(g_['missing_component_ids'] for g_ in ctx['goals'])
            q = authored(f.old.bank()['questions'][0])
            q.update(question_id=ctx['allowed_question_ids'][0], question='Synthetic added question', point_ids=ctx['goals'][0]['point_ids'])
            return {'questions': [q], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': [],
                    'question_importance': [{'question_id': q['question_id'], 'importance_basis': basis('learning_objective')}]}, {}
        if stage.startswith('v4-review'):
            first = stage.endswith('-0')
            assert {r['question_id'] for r in ctx['question_importance']} == {q['question_id'] for q in ctx['questions']}
            return {'reviews': [{'question_id': q['question_id'], 'verdict': 'ok',
                                 'design': 'doubt' if first and q['question_id'] in self.design_doubt else 'ok',
                                 'note': '', 'suggested_answer': '', 'fix': '', 'importance_note': '',
                                 'prerequisite_checks': [{'prerequisite_id': p, 'status': 'supported', 'reason': 'x'}
                                                         for p in q.get('prerequisites', [])]}
                                for q in ctx['questions']]}, {}
        if stage.startswith('v4-fix'):
            qs = []
            for q in ctx['questions']:
                fixed = authored(q)
                fixed['explanation'] = 'Synthetic clearer explanation'
                qs.append(fixed)
            return {'questions': qs, 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': [],
                    'question_importance': copy.deepcopy(ctx['question_importance'])}, {}
        if stage.startswith('v4-context'):
            return {'conflicts': [{'conflict_id': c['conflict_id'], 'status': 'consistent', 'reason': 'Synthetic'} for c in ctx['conflicts']],
                    'questions': [], 'unrecorded': []}, {}
        if stage.startswith('medical-'):
            return f.old.checks(ctx['bank']), {}
        raise AssertionError(stage)


def run(tmp_path, model=None):
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path)
    model = model or Model()
    return p, model, g.run(p, tmp_path / 'out', invoke=model)


def tasks(result):
    return sorted((t['question_id'], t['direction_id']) for t in result['document']['tasks'])


def test_every_ok_question_is_a_task_and_one_goal_takes_several(tmp_path):
    p, model, result = run(tmp_path)
    assert consume(result, p) == result['document']
    meta = result['manifest']
    assert meta['pipelineVersion'] == 'root-generation/4' and result['document']['generation_policy'] == 'root-generation/4'
    assert tasks(result) == [('Q003', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]
    assert meta['addRounds'] == 1 and meta['mergedDuplicates'] == [] and meta['unplacedQuestions'] == []
    assert model.calls[0] == 'normalize' and model.calls[-1] == 'medical-0' and all(c in ('normalize', 'medical-0') or c.startswith('v4-')
                                                                                      for c in model.calls)
    assert [x['question_id'] for x in meta['fixes']] == ['Q1']


def test_tiers_come_from_each_question_basis(tmp_path):
    p, model, result = run(tmp_path)
    tiers = {q['question_id']: q['tier'] for q in result['document']['bank_snapshot']['questions']}
    assert tiers == {'Q1': 'Essential', 'Q2': 'Optional', 'Q003': 'Core'}
    assert result['manifest']['questionImportance']['Q003'][0]['kind'] == 'learning_objective'
    # The fix copied Q1's basis; it is kept.
    assert result['manifest']['questionImportance']['Q1'] == INTAKE_BASIS['Q1']


def test_true_duplicates_merge_into_one_task(tmp_path):
    p, model, result = run(tmp_path, Model(duplicate=True))
    assert consume(result, p) == result['document']
    assert tasks(result) == [('Q003', 'D2'), ('Q1', 'D1')]
    assert [(m['question_id'], m['kept']) for m in result['manifest']['mergedDuplicates']] == [('Q2', 'Q1')]


def test_an_authoring_output_without_basis_stops_that_stage(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path)
    p['intakeBank']['question_importance'] = p['intakeBank']['question_importance'][:1]
    p['inputHash'] = packet_hash(p)
    with pytest.raises(ValueError, match='missing for Q2'):
        g.run(p, tmp_path / 'out', invoke=Model())


def test_the_runner_accepts_a_completed_v4_result(tmp_path):
    """A finished /4 run has add rounds, not repair rounds (review 2026-11-11: every /4 result was refused)."""
    from runner.connection_generation import completed_result
    p, model, result = run(tmp_path)
    assert completed_result(tmp_path / 'out', p) == result


def test_an_unfixed_intake_basis_cannot_be_swapped(tmp_path):
    p, model, result = run(tmp_path)
    result['manifest']['questionImportance']['Q2'] = basis('clinical')
    with pytest.raises(ValueError, match='Q2 importance basis differs from the intake bank|projections differ'):
        consume(result, p)
