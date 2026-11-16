"""discriminate/1 (docs/changes/2026-11-16-reverse-discriminating): a named element whose siblings sit under another
owner becomes a reverse goal, asked by the cue alone.

The map gets two owners (B and C), each with a category of the same kind holding one named element. No question asks
「the element with this action」 without naming its owner, so the run makes point P002 → goal TQ001 (relation RQD001),
the add stage writes that question, and the document orders the forward question's goal before it.
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_root_generation_v4 as t4
from studyez_contracts.roots import discriminate as dis
from studyez_contracts.roots.automation import validate_result as consume

REF = [{'source_id': 'S1', 'pages': [], 'locator': 'synthetic paragraph'}]
ELEMENT = {'element': 'Toxa', 'cue': '단서: 표적 X를 끊는다', 'siblings': ['Toxb'], 'asked_by': [], 'forward_by': ['Q1'],
           'point': {'point': '표적 X를 끊는 인자는?', 'source_refs': REF}, 'reason': '다른 주체에 형제가 있다'}


def _extended(brief):
    """The synthetic map with a category under each of two owners: B/BC/Toxa and C/CC/Toxb."""
    brief = copy.deepcopy(brief)
    for c in brief['concepts']:
        if c['concept_id'] in ('B', 'C'):
            c['label'] = {'B': 'Pseudomonas', 'C': 'Campylobacter'}[c['concept_id']]
    brief['concepts'] += [{'concept_id': 'BC', 'label': '손상 인자', 'parent_ids': ['B']},
                          {'concept_id': 'BE', 'label': 'Toxa', 'parent_ids': ['BC']},
                          {'concept_id': 'CC', 'label': '손상 효소', 'parent_ids': ['C']},
                          {'concept_id': 'CE', 'label': 'Toxb', 'parent_ids': ['CC']}]
    return brief


class Discriminating(t4.Model):
    """t4.Model with the deeper map, Toxa judged discriminable, and the question written for its reverse goal."""

    def __init__(self, elements=None, **kw):
        relations = {'Q1': [('R1', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')],
                     'Q004': [('RQD001', 'whole')]}
        super().__init__(relations=relations, **kw)
        self.elements = [copy.deepcopy(ELEMENT)] if elements is None else elements

    def __call__(self, stage, ctx, material, model):
        clean = {k: v for k, v in ctx.items() if k != '_check'}
        if stage == 'normalize':
            return _extended(super().__call__(stage, ctx, material, model)[0]), {}
        if stage.startswith('v4-discriminate'):
            self.calls.append(stage)
            self.inputs[stage] = clean
            rows = []
            for cat in clean['categories']:
                mine = self.elements if cat['concept_id'] == 'BC' else []
                peers = [c['concept_id'] for c in clean['all_categories']
                         if c['owner_id'] != cat['owner_id'] and c['concept_id'] != cat['concept_id']]
                rows.append({'concept_id': cat['concept_id'], 'peer_concept_ids': peers if mine else [],
                             'elements': copy.deepcopy(mine), 'reason': 'Synthetic'})
            return {'rows': rows}, {}
        if stage == 'v4-supplement-normalize-discriminate':
            self.calls.append(stage)
            self.inputs[stage] = clean
            point = clean['points'][0]
            tid, did = clean['allowed']['target_ids'][0], clean['allowed']['direction_ids'][0]
            rid = clean['allowed_relation_ids'][0]
            where = [{'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}]
            target = {'target_id': tid, 'title': '표적 X를 끊는 인자는?', 'concept_ids': ['BC', 'BE'], 'relation_ids': [rid],
                      'role': 'leaf', 'reason': 'reverse', 'evidence': where,
                      'importance': {axis: {'status': 'unreviewed', 'reason': 'x', 'evidence': []}
                                     for axis in ('structural', 'exam', 'clinical')},
                      'directions': [{'direction_id': did, 'cue': '표적 X를 끊는 인자는?', 'answer_scope': 'Toxa',
                                      'requirement': 'required', 'relation_ids': [rid],
                                      'components': [{'component_id': 'member', 'text': 'Toxa'}], 'requires_visual': False}]}
            relation = {'relation_id': rid, 'from_id': 'BC', 'to_id': 'BE', 'kind': 'association',
                        'condition': '손상 인자에 Toxa가 있다', 'evidence': where, 'review_status': 'unreviewed',
                        'reason': 'reverse'}
            brief_point = {'point_id': point['point_id'], 'text': point['point'], 'evidence': where,
                           'target_ids': [tid], 'scope_status': 'included', 'reason': 'reverse'}
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
                # Judged only after the add round (spec R4): Q004 is the reverse question.
                ev = [{'question_id': q['question_id'], 'tested_relation_ids': ['RQD001'],
                       'components': [{'component_id': 'member', 'location': 'answer', 'answer_unit_indices': [0],
                                       'reason': 'x'}], 'visual_verdict': 'not_applicable', 'reason': 'Synthetic'}
                      for q in clean['questions'] if q['question_id'] == 'Q004']
                rows.append({'direction_id': 'DQ001', 'status': 'covered' if ev else 'missing', 'evidence': ev,
                             'duplicates': [], 'reason': 'x'})
            return {'rows': rows}, {}
        if stage.startswith('v4-add') and any(gl['direction_id'] == 'DQ001' for gl in clean['goals']):
            self.calls.append(stage)
            self.inputs[stage] = clean
            qs = []
            for qid, gl in zip(clean['allowed_question_ids'], clean['goals']):
                q = t4.authored(t4.f.old.bank()['questions'][0])
                q.update(question_id=qid, point_ids=gl['point_ids'],
                         question='표적 X를 끊는 인자는?' if gl['direction_id'] == 'DQ001' else 'Synthetic added question')
                qs.append(q)
            return {'questions': qs, 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [],
                    'clinical_conflicts': [],
                    'question_importance': [{'question_id': q['question_id'], 'importance_basis': t4.basis('learning_objective')}
                                            for q in qs]}, {}
        return super().__call__(stage, ctx, material, model)


def test_a_discriminable_element_nobody_asks_by_the_cue_becomes_a_reverse_goal(tmp_path):
    packet, model, result = t4.run(tmp_path, Discriminating())
    consume(result, packet)
    meta, doc, brief = result['manifest'], result['document'], result['brief']
    assert meta['discriminations'] == [{'concept_id': 'BC', 'owner': 'Pseudomonas', 'element': 'Toxa',
                                        'cue': '단서: 표적 X를 끊는다', 'siblings': ['Toxb'], 'asked_by': [],
                                        'forward_by': ['Q1'], 'point_id': 'P002'}]
    assert [p['point_id'] for p in meta['supplementPoints']['points'] if p.get('origin') == dis.ORIGIN] == ['P002']
    assert 'RQD001' in {r['relation_id'] for r in brief['relations']}
    assert model.calls.index('v4-discriminate-0') < model.calls.index('v4-supplement-normalize-discriminate') \
        < model.calls.index('v4-add-0')
    # The add stage is told the cue, the element and the forward stems it must not copy.
    goals = {gl['direction_id']: gl for gl in model.inputs['v4-add-0']['goals']}
    [told] = goals['DQ001']['discrimination']
    assert (told['owner'], told['element'], told['cue'], told['siblings']) == ('Pseudomonas', 'Toxa', '단서: 표적 X를 끊는다', ['Toxb'])
    assert [f['question_id'] for f in told['forward_by']] == ['Q1']
    assert 'discrimination' not in goals.get('D2', {})
    # Its question is a task, and the forward question's goal comes first.
    owners = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    task_of = {t['question_id']: owners[t['direction_id']] for t in doc['tasks']}
    assert task_of['Q004'] == 'TQ001' and task_of['Q1'] == 'T1'
    [edge] = [e for e in doc['prerequisites'] if dis.is_reverse_edge(e)]
    assert (edge['before_target'], edge['after_target']) == ('T1', 'TQ001')
    relation = next(r for r in doc['review']['relations'] if r['relation_id'] == edge['relation_id'])
    assert relation['kind'] == 'prerequisite' and relation['review_status'] == 'reviewed'
    order = [t['question_id'] for t in doc['tasks']]
    assert order.index('Q1') < order.index('Q004')
    counts = dis.report(meta['discriminations'], doc, doc['bank_snapshot'])
    assert (counts['discriminable'], counts['reverseGoal'], counts['open']) == (1, 1, [])
    assert counts['ownerInStem'] == []


def test_an_element_already_asked_by_the_cue_makes_no_goal(tmp_path):
    element = {**copy.deepcopy(ELEMENT), 'asked_by': ['Q2'], 'point': None}
    packet, model, result = t4.run(tmp_path, Discriminating(elements=[element]))
    consume(result, packet)
    assert 'v4-supplement-normalize-discriminate' not in model.calls
    assert result['manifest']['discriminations'][0]['point_id'] is None
    assert not any(dis.is_reverse_edge(e) for e in result['document']['prerequisites'])


def test_a_stem_that_names_the_owner_is_counted_not_blocked(tmp_path):
    """R9: the one rule this policy asks for is measured, so one bad stem never holds a lecture."""
    class Named(Discriminating):
        def __call__(self, stage, ctx, material, model):
            value, rest = super().__call__(stage, ctx, material, model)
            if stage.startswith('v4-add'):
                for q in value['questions']:
                    if q['question'].startswith('표적'):
                        q['question'] = 'Pseudomonas에서 표적 X를 끊는 인자는?'
            return value, rest
    packet, _, result = t4.run(tmp_path, Named())
    consume(result, packet)
    counts = dis.report(result['manifest']['discriminations'], result['document'], result['document']['bank_snapshot'])
    assert [r['question_id'] for r in counts['ownerInStem']] == ['Q004']
    assert counts['reverseGoal'] == 1       # published all the same


def test_an_older_ledger_runs_without_the_element_judgment(tmp_path):
    from quizbank import connection_generate_v4 as gen
    from quizbank.connection_generate_v3 import Stages
    real = gen.Stages

    class Legacy(Stages):
        def __init__(self, *a, fresh=None, **kw):
            super().__init__(*a, fresh={k: v for k, v in (fresh or {}).items() if k != 'discriminations'}, **kw)
    gen.Stages = Legacy
    try:
        packet, model, result = t4.run(tmp_path, Discriminating())
    finally:
        gen.Stages = real
    assert not any(s.startswith('v4-discriminate') for s in model.calls)
    assert 'discriminations' not in result['manifest']
    consume(result, packet)


# ---------------------------------------------------------------- pure functions
def test_categories_only_names_owner_subtrees_with_named_elements():
    brief = _extended({'concepts': [{'concept_id': 'A', 'label': 'A', 'parent_ids': []},
                                    {'concept_id': 'B', 'label': 'B', 'parent_ids': ['A']},
                                    {'concept_id': 'C', 'label': 'C', 'parent_ids': ['A']},
                                    {'concept_id': 'D', 'label': '설명만 있는 묶음', 'parent_ids': ['A']},
                                    {'concept_id': 'DE', 'label': '중간 단계 하나', 'parent_ids': ['D']}]})
    assert dis.categories(brief) == ['BC', 'CC']        # D holds no named element; B and C are owners, not categories
    assert dis.owners(brief)['BE'] == 'B' and dis.owners(brief)['CE'] == 'C'
    assert dis.named('LasB–zinc metalloprotease') == ['LasB', 'zinc', 'metalloprotease']
    assert dis.named('짧고 굽은 막대균') == []


def test_stage_output_checks():
    ctx = {'categories': [{'concept_id': 'BC', 'owner_id': 'B', 'elements': ['Toxa']}],
           'all_categories': [{'concept_id': 'BC', 'owner_id': 'B', 'elements': ['Toxa']},
                              {'concept_id': 'CC', 'owner_id': 'C', 'elements': ['Toxb']}],
           'all_questions': [{'question_id': 'Q1'}, {'question_id': 'Q2'}], 'page_counts': {'S1': 3}}
    ok = {'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['CC'], 'elements': [copy.deepcopy(ELEMENT)], 'reason': 'x'}]}
    assert dis.check(ok, ctx) == ok
    row = lambda **kw: {'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['CC'], 'reason': 'x',
                                 'elements': [{**copy.deepcopy(ELEMENT), **kw}]}]}
    for broken, message in [
        ({'rows': []}, 'every judged category'),
        ({'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['BC'], 'elements': [], 'reason': 'x'}]}, 'other categories'),
        ({'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['ZZ'], 'elements': [], 'reason': 'x'}]}, 'other categories'),
        ({'rows': [{'concept_id': 'BC', 'peer_concept_ids': [], 'elements': [copy.deepcopy(ELEMENT)], 'reason': 'x'}]},
         'without a peer category'),
        (row(element='Nope'), 'not a named element'),
        (row(asked_by=['Q9'], point=None), 'unknown questions'),
        (row(forward_by=['Q9']), 'unknown questions'),
        (row(asked_by=['Q1']), 'already asked carries no point'),
        (row(point=None), 'nobody asks needs its point'),
        (row(point={'point': 'x', 'source_refs': [{'source_id': 'S1', 'pages': [9], 'locator': None}]}),
         'outside the sources')]:
        with pytest.raises(ValueError, match=message):
            dis.check(broken, ctx)
    # one row per element
    twice = {'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['CC'], 'reason': 'x',
                       'elements': [copy.deepcopy(ELEMENT), {**copy.deepcopy(ELEMENT), 'cue': '다른 단서'}]}]}
    with pytest.raises(ValueError, match='one row per element'):
        dis.check(twice, ctx)


def _brief(*targets):
    return {'targets': [{'target_id': tid, 'concept_ids': cids, 'evidence': [{'source_id': 'S1', 'pages': [1]}],
                         'directions': [{'direction_id': 'D' + tid,
                                         'components': [{'component_id': 'm', 'text': 'Toxa'}]}]}
                        for tid, cids in targets],
            'points': [{'point_id': 'P9', 'target_ids': ['TR']}]}


def rec(point_id='P9', forward=('Q1',)):
    return {'concept_id': 'BC', 'owner': 'B', 'element': 'Toxa', 'cue': 'c', 'siblings': ['Toxb'],
            'asked_by': [], 'forward_by': list(forward), 'point_id': point_id}


def test_gaps_keep_a_reverse_goal_open_until_a_question_carries_its_point():
    brief = _brief(('T1', ['A', 'B']), ('TR', ['BC', 'BE']))
    bank = {'questions': [{'question_id': 'Q1', 'point_ids': ['P1']}]}
    assert dis.gaps(brief, [rec()], bank) == {'DTR': ['m']}
    assert dis.written_for(bank, brief, [rec()]) == set()
    asked = {'questions': [{'question_id': 'Q1', 'point_ids': ['P1']}, {'question_id': 'Q4', 'point_ids': ['P9']}]}
    assert dis.written_for(asked, brief, [rec()]) == {'DTR'}
    assert dis.gaps(brief, [rec()], asked) == {}
    assert dis.gaps(brief, [rec(point_id=None)], bank) == {}


def test_order_edges_put_the_forward_goal_first_and_skip_cycles():
    brief = _brief(('T1', ['A', 'B']), ('TR', ['BC', 'BE']))
    tasks = [{'question_id': 'Q1', 'direction_id': 'DT1'}, {'question_id': 'Q4', 'direction_id': 'DTR'}]
    relations, edges = dis.order_edges(brief, tasks, [rec(), rec()], [], [])
    assert [(e['before_target'], e['after_target']) for e in edges] == [('T1', 'TR')]
    assert len(relations) == 1 and relations[0]['kind'] == 'prerequisite'
    assert dis.is_reverse_edge(edges[0]) and not dis.is_reverse_edge({'relation_id': 'R1'})
    # the forward question is not a task, so there is nothing to order
    assert dis.order_edges(brief, tasks[1:], [rec()], [], [])[1] == []
    # an edge that already exists, and one that would close a cycle, are left out
    existing = [{'before_target': 'T1', 'after_target': 'TR', 'relation_id': 'R9'}]
    assert dis.order_edges(brief, tasks, [rec()], [], existing)[1] == []
    cycle = [{'before_target': 'TR', 'after_target': 'T1', 'relation_id': 'R9'}]
    assert dis.order_edges(brief, tasks, [rec()], [], cycle)[1] == []


def test_records_make_one_point_per_owner_element_and_drop_questions_that_left():
    outputs = [{'rows': [{'concept_id': 'BC', 'peer_concept_ids': ['CC'], 'reason': 'x',
                          'elements': [copy.deepcopy(ELEMENT), {**copy.deepcopy(ELEMENT), 'element': 'Toxa '}]}]}]
    bank = {'questions': [{'question_id': 'Q2'}]}
    brief = {'concepts': [{'concept_id': 'A', 'label': 'A', 'parent_ids': []},
                          {'concept_id': 'B', 'label': 'Pseudomonas', 'parent_ids': ['A']},
                          {'concept_id': 'BC', 'label': '손상 인자', 'parent_ids': ['B']}]}
    points, got, new = dis.records(outputs, bank, {'points': [{'point_id': 'P001'}]}, brief)
    assert [p['point_id'] for p in new] == ['P002']
    assert [r['point_id'] for r in got] == ['P002', 'P002']
    assert got[0]['forward_by'] == []      # Q1 is not in this bank any more
    assert new[0]['origin'] == dis.ORIGIN and new[0]['origin_concept_id'] == 'BC'
    assert [p['point_id'] for p in points['points']] == ['P001', 'P002']


def test_the_backfill_adds_reverse_goals_beside_existence_goals_and_keeps_every_published_task(tmp_path):
    """presuppose-only/1 is the path the 25 published lectures take (사용자 「역방향 넣고 한 번에」)."""
    import json
    from quizbank import connection_generate as g
    from quizbank import connection_generate_v4 as gen4
    from studyez_contracts.roots.automation import packet_hash
    from tests.quizbank.test_connection_presuppose import Legacy
    from tests.quizbank.test_connection_replace import carry_sources
    real = gen4.Stages
    gen4.Stages = Legacy
    try:
        old_packet, _, old = t4.run(tmp_path / 'old', Discriminating())
    finally:
        gen4.Stages = real
    assert 'discriminations' not in old['manifest']
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, presupposeOnly=True,
                  restartReason='존재 목표 보강', carrySources=carry_sources(old))
    packet['inputHash'] = packet_hash(packet)
    model = Discriminating()
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert consume(result, packet) == result['document']
    assert model.calls.index('v4-discriminate-0') < model.calls.index('v4-supplement-normalize-discriminate') \
        < model.calls.index('v4-add-presuppose-0')
    meta, doc = result['manifest'], result['document']
    assert [r['point_id'] for r in meta['discriminations']] == ['P002']
    assert meta['presupposeOnly']['addedQuestions'] == ['Q004']
    assert meta['presupposeOnly']['reverseCounts']['reverseGoal'] == 1
    assert {t['question_id'] for t in old['document']['tasks']} <= {t['question_id'] for t in doc['tasks']}
    assert any(dis.is_reverse_edge(e) for e in doc['prerequisites'])
