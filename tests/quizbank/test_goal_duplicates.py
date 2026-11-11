"""goal-duplicates/1 through the /4 generator with a synthetic model (docs/changes/2026-11-12-goal-dedupe).

261111_02: one goal's only component carried a caveat no question can answer. The coverage judgment called every
question for it partial, two add rounds each wrote the same question again, and the re-check after each round read
only that round's questions, so the three were never compared and all became tasks.
"""
import copy

import pytest

from quizbank import connection_generate as g
from quizbank import connection_generate_v4 as gen
from quizbank.connection_generate_v3 import Stages
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import validate_result as consume
from tests.quizbank.test_root_generation_v4 import Model, authored, basis, packet, tasks
import generation_v2_fixture as f

RELATIONS = {'Q1': [('R1', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')], 'Q004': [('R2', 'whole')]}


class Caveat(Model):
    """D2's component can never be answered whole: every question written for it is judged partial (missing).
    `silent`: the add stage sees that and writes nothing."""

    def __init__(self, silent=False):
        super().__init__(design_doubt=(), relations=RELATIONS)
        self.silent = silent

    def __call__(self, stage, ctx, material, model):
        if stage.startswith('v4-coverage'):
            self.calls.append(stage)
            self.inputs[stage] = {k: v for k, v in ctx.items() if k != '_check'}
            qids = [q['question_id'] for q in ctx['questions']]
            rows = []
            for goal in ctx['goals']:
                if goal['direction_id'] == 'D1':
                    ev = [self.evidence(goal, q, 'R1', 'answer', stage) for q in ('Q1', 'Q2') if q in qids]
                    rows.append({'direction_id': 'D1', 'status': 'covered' if ev else 'missing', 'evidence': ev, 'duplicates': [],
                                 'reason': 'Synthetic'})
                    continue
                ev = [self.evidence(goal, q, 'R2', 'missing', stage) for q in qids if q in ('Q003', 'Q004')]
                dup = [{'question_ids': ['Q003', 'Q004'], 'reason': 'Same answer asked the same way'}] if len(ev) == 2 else []
                rows.append({'direction_id': goal['direction_id'], 'status': 'missing', 'evidence': ev, 'duplicates': dup,
                             'reason': 'The caveat is not asked'})
            return {'rows': rows}, {}
        if stage.startswith('v4-add'):
            self.calls.append(stage)
            self.inputs[stage] = {k: v for k, v in ctx.items() if k != '_check'}
            if self.silent:
                return {k: [] for k in v4.ADD_OUTPUT['properties']}, {}
            q = authored(f.old.bank()['questions'][0])
            qid = ctx['allowed_question_ids'][0]
            q.update(question_id=qid, question='Synthetic question written for the gap ' + qid, point_ids=ctx['goals'][0]['point_ids'])
            return {'questions': [q], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [],
                    'clinical_conflicts': [], 'question_importance': [{'question_id': qid, 'importance_basis': basis('learning_objective')}]}, {}
        return super().__call__(stage, ctx, material, model)

    @staticmethod
    def evidence(goal, qid, relation, location, stage):
        return {'question_id': qid, 'tested_relation_ids': [relation],
                'components': [{'component_id': c['component_id'], 'location': location,
                                'answer_unit_indices': [0] if location == 'answer' else [], 'reason': 'judged in ' + stage}
                               for c in goal['components']],
                'visual_verdict': 'not_applicable', 'reason': 'judged in ' + stage}


def run(tmp_path, model, legacy=False):
    """`legacy`: a ledger made before goal-duplicates/1 (no goalDuplicates key)."""
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path)
    if not legacy:
        return p, g.run(p, tmp_path / 'out', invoke=model)

    class Legacy(Stages):
        def __init__(self, *a, fresh=None, **kw):
            super().__init__(*a, fresh={k: v for k, v in (fresh or {}).items() if k != 'goalDuplicates'}, **kw)
    current, gen.Stages = gen.Stages, Legacy
    try:
        return p, g.run(p, tmp_path / 'out', invoke=model)
    finally:
        gen.Stages = current


def asked_in(model, stage):
    return [q['question_id'] for q in model.inputs[stage]['questions']]


def test_a_question_written_again_for_a_goal_is_merged_into_the_first(tmp_path):
    model = Caveat()
    p, result = run(tmp_path, model)
    assert consume(result, p) == result['document']
    # The second add round is told which question already asks the goal and what the judgment found missing.
    assert 'asked' in model.inputs['v4-add-0']['goals'][0] and model.inputs['v4-add-0']['goals'][0]['asked'] == []
    asked = model.inputs['v4-add-1']['goals'][0]['asked']
    assert [a['question_id'] for a in asked] == ['Q003']
    assert asked[0]['components'][0]['location'] == 'missing' and asked[0]['components'][0]['reason'] == 'judged in v4-coverage-1-0'
    # The re-check after the second round reads the first round's question beside the new one.
    assert asked_in(model, 'v4-coverage-1-0') == ['Q003'] and asked_in(model, 'v4-coverage-2-0') == ['Q003', 'Q004']
    row = next(r for r in result['manifest']['coverage'] if r['direction_id'] == 'D2')
    assert [e['question_id'] for e in row['evidence']] == ['Q003', 'Q004']
    # A question judged before keeps its first evidence; the group of two partial questions is kept.
    assert row['evidence'][0]['reason'] == 'judged in v4-coverage-1-0'
    assert [d['question_ids'] for d in row['duplicates']] == [['Q003', 'Q004']]
    assert [(m['question_id'], m['kept'], m['direction_id']) for m in result['manifest']['mergedDuplicates']] == [('Q004', 'Q003', 'D2')]
    assert tasks(result) == [('Q003', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]
    # The merged question stays in the bank; only its task is gone.
    assert 'Q004' in {q['question_id'] for q in result['document']['bank_snapshot']['questions']}
    assert 'goalDuplicates' not in result['manifest']


def test_a_ledger_made_before_keeps_its_inputs_and_both_tasks(tmp_path):
    model = Caveat()
    p, result = run(tmp_path, model, legacy=True)
    assert consume(result, p) == result['document']
    assert all('asked' not in goal for stage in ('v4-add-0', 'v4-add-1') for goal in model.inputs[stage]['goals'])
    assert asked_in(model, 'v4-coverage-1-0') == ['Q003'] and asked_in(model, 'v4-coverage-2-0') == ['Q004']
    assert result['manifest']['mergedDuplicates'] == []
    assert tasks(result) == [('Q003', 'D2'), ('Q004', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]


def test_an_add_stage_that_writes_nothing_ends_the_add_rounds(tmp_path):
    model = Caveat(silent=True)
    p, result = run(tmp_path, model)
    assert consume(result, p) == result['document']
    assert [c for c in model.calls if c.startswith('v4-add')] == ['v4-add-0']
    assert not any(c.startswith('v4-coverage-1') for c in model.calls)
    assert result['manifest']['addRounds'] == 1
    assert tasks(result) == [('Q1', 'D1'), ('Q2', 'D1')]
    assert {r['direction_id']: r['reason'] for r in result['manifest']['notReady']} == {'D2': 'no-question'}


def test_an_empty_add_output_carries_nothing_else():
    empty = {k: [] for k in v4.ADD_OUTPUT['properties']}
    assert v4.check_added(copy.deepcopy(empty), {}) == empty
    with pytest.raises(ValueError, match='without questions carries nothing else'):
        v4.check_added({**empty, 'visual_stimuli': [{'question_id': 'Q9'}]}, {})


def test_a_group_of_partial_questions_survives_the_merge_only_under_the_policy():
    goal = {'components': [{'component_id': 'C1'}], 'requires_visual': False}
    partial = lambda q: {'question_id': q, 'tested_relation_ids': ['R1'], 'visual_verdict': 'not_applicable', 'reason': 'x',
                         'components': [{'component_id': 'C1', 'location': 'missing', 'answer_unit_indices': [], 'reason': 'x'}]}
    old = {'direction_id': 'D', 'status': 'missing', 'evidence': [partial('A')], 'duplicates': [], 'reason': 'x'}
    new = {'direction_id': 'D', 'status': 'missing', 'evidence': [partial('A'), partial('B')],
           'duplicates': [{'question_ids': ['A', 'B'], 'reason': 'same'}], 'reason': 'y'}
    trimmed = gen._first_evidence(old, new)
    assert [e['question_id'] for e in trimmed['evidence']] == ['B']
    assert gen._merge_row(old, trimmed, goal, by_evidence=True)['duplicates'] == [{'question_ids': ['A', 'B'], 'reason': 'same'}]
    assert gen._merge_row(old, trimmed, goal)['duplicates'] == []
