"""presuppose/1 (docs/changes/2026-11-15-tree-edge-goals): a link a stem gives as known becomes an existence goal
that is studied first.

Q2's stem gives 「A has C」 and no question asks it. The run makes point P002 → goal TQ001 (relation RQP001 A→C),
the add stage asks it (Q004), and the document orders TQ001 before T1 with a reviewed prerequisite.
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_root_generation_v4 as t4
from studyez_contracts.roots import presuppose as pre
from studyez_contracts.roots.automation import validate_result as consume

REF = [{'source_id': 'S1', 'pages': [], 'locator': 'synthetic paragraph'}]
LINK = {'a': 'A', 'b': 'C', 'link': 'A에게 C가 있다', 'recalled_by': [],
        'point': {'point': 'A가 가진 C', 'source_refs': REF}, 'reason': 'Q2의 발문이 A의 C를 전제로 준다'}


class Presupposing(t4.Model):
    """t4.Model, plus: Q2 presupposes A→C; the existence goal DQ001 is asked by the question written for it."""

    def __init__(self, links=None, **kw):
        relations = {'Q1': [('R1', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')], 'Q004': [('RQP001', 'whole')]}
        super().__init__(presupposes={'Q2': [copy.deepcopy(LINK)]} if links is None else links, relations=relations, **kw)

    def __call__(self, stage, ctx, material, model):
        clean = {k: v for k, v in ctx.items() if k != '_check'}
        if stage == 'v4-supplement-normalize-presuppose':
            self.calls.append(stage)
            self.inputs[stage] = clean
            point = clean['points'][0]
            tid, did = clean['allowed']['target_ids'][0], clean['allowed']['direction_ids'][0]
            rid = clean['allowed_relation_ids'][0]
            target = {'target_id': tid, 'title': 'A가 가진 C는?', 'concept_ids': ['A', 'C'], 'relation_ids': [rid], 'role': 'leaf',
                      'reason': 'existence', 'evidence': [{'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}],
                      'importance': {axis: {'status': 'unreviewed', 'reason': 'x', 'evidence': []} for axis in ('structural', 'exam', 'clinical')},
                      'directions': [{'direction_id': did, 'cue': 'A가 가진 C는?', 'answer_scope': 'C', 'requirement': 'required',
                                      'relation_ids': [rid], 'components': [{'component_id': 'member', 'text': 'C'}], 'requires_visual': False}]}
            relation = {'relation_id': rid, 'from_id': 'A', 'to_id': 'C', 'kind': 'association', 'condition': 'A는 C를 가진다',
                        'evidence': [{'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}],
                        'review_status': 'unreviewed', 'reason': 'existence'}
            brief_point = {'point_id': point['point_id'], 'text': point['point'],
                           'evidence': [{'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}],
                           'target_ids': [tid], 'scope_status': 'included', 'reason': 'existence'}
            return {'targets': [target], 'points': [brief_point], 'relations': [relation]}, {}
        if stage.startswith('v4-coverage') and any(gl['direction_id'] == 'DQ001' for gl in clean['goals']):
            self.calls.append(stage)
            self.inputs[stage] = clean
            rows = []
            for gl in clean['goals']:
                if gl['direction_id'] != 'DQ001':
                    rows += super().__call__(stage + '-base', {**clean, 'goals': [gl]}, material, model)[0]['rows']
                    self.calls.pop()
                    continue
                ev = [{'question_id': q['question_id'], 'tested_relation_ids': ['RQP001'],
                       'components': [{'component_id': 'member', 'location': 'answer', 'answer_unit_indices': [0], 'reason': 'x'}],
                       'visual_verdict': 'not_applicable', 'reason': 'Synthetic'}
                      for q in clean['questions'] if q['question'] == 'Existence question']
                rows.append({'direction_id': 'DQ001', 'status': 'covered' if ev else 'missing', 'evidence': ev, 'duplicates': [], 'reason': 'x'})
            return {'rows': rows}, {}
        if stage.startswith('v4-add') and any(gl['direction_id'] == 'DQ001' for gl in clean['goals']):
            self.calls.append(stage)
            self.inputs[stage] = clean
            qs = []
            for qid, gl in zip(clean['allowed_question_ids'], clean['goals']):
                q = t4.authored(t4.f.old.bank()['questions'][0])
                q.update(question_id=qid, point_ids=gl['point_ids'],
                         question='Existence question' if gl['direction_id'] == 'DQ001' else 'Synthetic added question')
                qs.append(q)
            return {'questions': qs, 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': [],
                    'question_importance': [{'question_id': q['question_id'], 'importance_basis': t4.basis('learning_objective')} for q in qs]}, {}
        return super().__call__(stage, ctx, material, model)


def test_a_presupposed_link_nobody_asks_becomes_an_existence_goal_studied_first(tmp_path):
    packet, model, result = t4.run(tmp_path, Presupposing())
    consume(result, packet)
    meta, doc, brief = result['manifest'], result['document'], result['brief']
    assert meta['presuppositions'] == [{'question_id': 'Q2', 'a': 'A', 'b': 'C', 'link': 'A에게 C가 있다', 'recalled_by': [], 'point_id': 'P002'}]
    assert [p['point_id'] for p in meta['supplementPoints']['points'] if p.get('origin') == pre.ORIGIN] == ['P002']
    assert 'TQ001' in {t['target_id'] for t in brief['targets']} and 'RQP001' in {r['relation_id'] for r in brief['relations']}
    assert model.calls.index('v4-presuppose-0') < model.calls.index('v4-supplement-normalize-presuppose') < model.calls.index('v4-add-0')
    # The add stage is told which goal is an existence goal and which stems presuppose it.
    goals = {gl['direction_id']: gl for gl in model.inputs['v4-add-0']['goals']}
    assert goals['DQ001']['existence'] == {'presupposed_by': [{'question_id': 'Q2', 'question': goals['DQ001']['existence']['presupposed_by'][0]['question']}]}
    assert 'existence' not in goals.get('D2', {})
    # The existence goal's question is a task, and its goal comes before the goal of the question that presupposed it.
    owners = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    task_of = {t['question_id']: owners[t['direction_id']] for t in doc['tasks']}
    assert task_of['Q004'] == 'TQ001' and task_of['Q2'] == 'T1'
    [edge] = doc['prerequisites']
    assert (edge['before_target'], edge['after_target']) == ('TQ001', 'T1')
    relation = next(r for r in doc['review']['relations'] if r['relation_id'] == edge['relation_id'])
    assert relation['kind'] == 'prerequisite' and relation['review_status'] == 'reviewed' and (relation['from_id'], relation['to_id']) == ('C', 'B')
    order = [t['question_id'] for t in doc['tasks']]
    assert order.index('Q004') < order.index('Q2')
    counts = pre.report(meta['presuppositions'], doc)
    assert (counts['presupposed'], counts['existenceGoal'], counts['open'], counts['prerequisites']) == (1, 1, [], 1)


def test_a_link_another_question_already_asks_orders_that_goal_first_and_makes_no_goal(tmp_path):
    # Q003 (D2, goal T1) recalls the link; Q2 is on T1 too, so there is no new goal and no edge within one goal.
    link = {**copy.deepcopy(LINK), 'recalled_by': ['Q1'], 'point': None}
    packet, model, result = t4.run(tmp_path, t4.Model(presupposes={'Q2': [link]}))
    consume(result, packet)
    assert 'v4-supplement-normalize-presuppose' not in model.calls
    assert result['manifest']['presuppositions'][0]['point_id'] is None and result['document']['prerequisites'] == []
    assert result['manifest']['supplementPoints'] is None


def test_an_older_ledger_runs_without_the_stem_judgment(tmp_path):
    from quizbank import connection_generate_v4 as gen
    from quizbank.connection_generate_v3 import Stages
    real = gen.Stages

    class Legacy(Stages):
        def __init__(self, *a, fresh=None, **kw):
            super().__init__(*a, fresh={k: v for k, v in (fresh or {}).items() if k != 'presuppositions'}, **kw)
    gen.Stages = Legacy
    try:
        packet, model, result = t4.run(tmp_path, t4.Model())
    finally:
        gen.Stages = real
    assert not any(s.startswith('v4-presuppose') for s in model.calls)
    assert 'presuppositions' not in result['manifest']
    consume(result, packet)


def test_stage_output_checks():
    ctx = {'questions': [{'question_id': 'Q2'}], 'all_questions': [{'question_id': 'Q1'}, {'question_id': 'Q2'}], 'page_counts': {'S1': 3}}
    ok = {'rows': [{'question_id': 'Q2', 'presupposes': [copy.deepcopy(LINK)]}]}
    assert pre.check(ok, ctx) == ok
    for broken, message in [
        ({'rows': []}, 'every judged question'),
        ({'rows': [{'question_id': 'Q2', 'presupposes': [{**LINK, 'recalled_by': ['Q2'], 'point': None}]}]}, 'own stem'),
        ({'rows': [{'question_id': 'Q2', 'presupposes': [{**LINK, 'recalled_by': ['Q9'], 'point': None}]}]}, 'unknown'),
        ({'rows': [{'question_id': 'Q2', 'presupposes': [{**LINK, 'recalled_by': ['Q1']}]}]}, 'carries no point'),
        ({'rows': [{'question_id': 'Q2', 'presupposes': [{**LINK, 'point': None}]}]}, 'needs its point'),
        ({'rows': [{'question_id': 'Q2', 'presupposes': [{**LINK, 'point': {'point': 'x', 'source_refs': [
            {'source_id': 'S1', 'pages': [9], 'locator': None}]}}]}]}, 'outside the sources')]:
        with pytest.raises(ValueError, match=message):
            pre.check(broken, ctx)


def _brief(*targets):
    return {'targets': [{'target_id': tid, 'concept_ids': cids, 'evidence': [{'source_id': 'S1', 'pages': [1]}],
                         'directions': [{'direction_id': 'D' + tid}]} for tid, cids in targets],
            'points': [{'point_id': 'P9', 'target_ids': ['TE']}]}


def test_order_edges_skip_cycles_shared_concepts_and_goals_without_tasks():
    brief = _brief(('TE', ['A', 'C']), ('T1', ['A', 'B']), ('T2', ['A']))
    tasks = [{'question_id': 'QE', 'direction_id': 'DTE'}, {'question_id': 'Q1', 'direction_id': 'DT1'},
             {'question_id': 'Q2', 'direction_id': 'DT2'}]
    rec = lambda qid, point=None, by=(): {'question_id': qid, 'a': 'A', 'b': 'C', 'link': 'x', 'recalled_by': list(by), 'point_id': point}
    relations, edges = pre.order_edges(brief, tasks, [rec('Q1', 'P9'), rec('Q1', 'P9')], [], [])
    assert [(e['before_target'], e['after_target']) for e in edges] == [('TE', 'T1')]       # one edge per goal pair
    assert relations[0]['from_id'] == 'C' and relations[0]['to_id'] == 'B'
    # T2's concepts are all in TE: no concept to point at, so no edge.
    assert pre.order_edges(brief, tasks, [rec('Q2', 'P9')], [], [])[1] == []
    # An edge back against an existing one would close a cycle.
    existing = [{'before_target': 'T1', 'after_target': 'TE', 'relation_id': 'R'}]
    assert pre.order_edges(brief, tasks, [rec('Q1', 'P9')], [], existing)[1] == []
    # A goal without tasks takes no part.
    assert pre.order_edges(brief, tasks[1:], [rec('Q1', 'P9')], [], [])[1] == []
    # Recalled by a question of another goal: that goal comes first.
    assert [(e['before_target'], e['after_target']) for e in pre.order_edges(brief, tasks, [rec('Q1', by=['QE'])], [], [])[1]] == [('TE', 'T1')]


def test_normalize_may_add_only_new_content_relations_between_existing_concepts():
    brief = t4.f.brief([{'source_id': 'S1'}])
    ctx = {'concepts': [{'concept_id': c['concept_id']} for c in brief['concepts']], 'allowed_relation_ids': ['RQP001'],
           'relations': [{'relation_id': r['relation_id']} for r in brief['relations']]}
    rel = {'relation_id': 'RQP001', 'from_id': 'A', 'to_id': 'C', 'kind': 'association', 'condition': 'x',
           'evidence': [{'source_id': 'S1', 'locator': 'p', 'pages': []}], 'review_status': 'unreviewed', 'reason': 'x'}
    pre._relations({'relations': [rel]}, ctx)
    for broken, message in [({**rel, 'relation_id': 'R1'}, 'outside the allowed'), ({**rel, 'to_id': 'Z'}, 'existing concepts'),
                            ({**rel, 'kind': 'classification'}, 'association'), ({**rel, 'review_status': 'reviewed'}, 'association')]:
        with pytest.raises(ValueError, match=message):
            pre._relations({'relations': [broken]}, ctx)


def test_runner_maps_the_new_stages():
    from runner import root_native_json as native
    assert native.v3_kind('v4-presuppose-0') == 'presuppose'
    assert native.v3_kind('v4-supplement-normalize-presuppose') == 'presuppose-normalize'
    assert native.v3_kind('v4-supplement-normalize-late') == 'supplement-normalize'
    assert native.v3_schema('v4-presuppose-0') is pre.OUTPUT
    assert native.v3_schema('v4-supplement-normalize-presuppose') is pre.NORMALIZE_OUTPUT
    assert 'presuppose/1' in native.task_for('v4-presuppose-0') and 'presuppose/1' in native.task_for('v4-supplement-normalize-presuppose')


def test_report_counts_records_or_falls_back_to_the_baseline(tmp_path, capsys):
    from quizbank import presuppose_report as rep
    packet, _, result = t4.run(tmp_path / 'new', Presupposing())
    row = rep.report(result)
    assert (row['policy'], row['presupposed'], row['existenceGoal'], row['prerequisites'], row['existencePoints']) == (pre.PRESUPPOSE, 1, 1, 1, ['P002'])
    old = copy.deepcopy(result)
    del old['manifest']['presuppositions']
    assert rep.report(old)['policy'] is None and 'neverAnswered' in rep.report(old)['baseline']
    assert rep.main([str(tmp_path / 'new' / 'out')]) == 0 and '존재 목표 1' in capsys.readouterr().out


def test_links_with_the_same_point_text_make_one_existence_point():
    bank = {'questions': [{'question_id': q} for q in ('Q1', 'Q2', 'Q3')]}
    points = {'points': [{'point_id': 'P1'}]}
    same = {'point': 'A의 보조 인자: C, D', 'source_refs': REF}
    out = [{'rows': [
        {'question_id': 'Q1', 'presupposes': [{**LINK, 'b': 'C', 'point': same}, {**LINK, 'b': 'D', 'point': {**same, 'point': ' A의 보조  인자: C, D'}}]},
        {'question_id': 'Q2', 'presupposes': [{**LINK, 'b': 'C', 'point': {'point': '다른 말로 쓴 A의 C', 'source_refs': REF}}]},
        {'question_id': 'Q3', 'presupposes': [{**LINK, 'b': 'E', 'point': {'point': 'A의 E', 'source_refs': REF}}]}]}]
    doc, recs, made = pre.records(out, bank, points)
    assert [p['point_id'] for p in made] == ['P002', 'P003'] and [p['origin_question_id'] for p in made] == ['Q1', 'Q3']
    assert [r['point_id'] for r in recs] == ['P002', 'P002', 'P002', 'P003']   # same text, same (A, B), a new one
    assert [p['point_id'] for p in doc['points']] == ['P1', 'P002', 'P003']
