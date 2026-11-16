"""discriminate/1 (docs/changes/2026-11-16-reverse-discriminating): a goal no question asks from the other end
becomes a reverse goal.

The judgment reads the lecture's own goals, so it is not tied to one map shape: D1 here is an ordinary goal, and
its reverse (a stem that gives only the answer side) becomes point P002 → goal TQ001 (relation RQD001). The add
stage writes that question, and the document orders D1's goal before it.
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
ROW = {'reversible': True, 'cue': '표적 X를 끊는 작용을 하는 것은?', 'answer': 'Toxa', 'competitors': ['Toxb'],
       'asked_by': [], 'forward_by': ['Q1'], 'point': {'point': '표적 X를 끊는 것은?', 'source_refs': REF},
       'reason': '강의 안에 같은 단서에 걸릴 다른 후보가 있다'}


def row(did, **kw):
    return {'direction_id': did, **copy.deepcopy(ROW), **kw}


def nothing(did):
    return {'direction_id': did, 'reversible': False, 'cue': '', 'answer': '', 'competitors': [], 'asked_by': [],
            'forward_by': [], 'point': None, 'reason': '헷갈릴 후보가 없다'}


class Discriminating(t4.Model):
    """t4.Model, plus: D1 is worth reversing, and the question written for its reverse goal."""

    def __init__(self, rows=None, **kw):
        relations = {'Q1': [('R1', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')],
                     'Q004': [('RQD001', 'whole')]}
        super().__init__(relations=relations, **kw)
        self.rows = rows

    def __call__(self, stage, ctx, material, model):
        clean = {k: v for k, v in ctx.items() if k != '_check'}
        if stage.startswith('v4-discriminate'):
            self.calls.append(stage)
            self.inputs[stage] = clean
            if self.rows is not None:
                return {'rows': [{**copy.deepcopy(r), 'direction_id': g['direction_id']}
                                 for r, g in zip(self.rows, clean['goals'])]}, {}
            return {'rows': [row(g['direction_id']) if g['direction_id'] == 'D1' else nothing(g['direction_id'])
                             for g in clean['goals']]}, {}
        if stage == 'v4-supplement-normalize-discriminate':
            self.calls.append(stage)
            self.inputs[stage] = clean
            point = clean['points'][0]
            tid, did = clean['allowed']['target_ids'][0], clean['allowed']['direction_ids'][0]
            rid = clean['allowed_relation_ids'][0]
            where = [{'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}]
            target = {'target_id': tid, 'title': '표적 X를 끊는 것은?', 'concept_ids': ['B', 'C'], 'relation_ids': [rid],
                      'role': 'leaf', 'reason': 'reverse', 'evidence': where,
                      'importance': {axis: {'status': 'unreviewed', 'reason': 'x', 'evidence': []}
                                     for axis in ('structural', 'exam', 'clinical')},
                      'directions': [{'direction_id': did, 'cue': '표적 X를 끊는 작용을 하는 것은?', 'answer_scope': 'Toxa',
                                      'requirement': 'required', 'relation_ids': [rid],
                                      'components': [{'component_id': 'member', 'text': 'Toxa'}],
                                      'requires_visual': False}]}
            relation = {'relation_id': rid, 'from_id': 'B', 'to_id': 'C', 'kind': 'association',
                        'condition': '표적 X를 끊는 것은 Toxa다', 'evidence': where, 'review_status': 'unreviewed',
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
                         question='표적 X를 끊는 작용을 하는 것은?' if gl['direction_id'] == 'DQ001'
                         else 'Synthetic added question')
                qs.append(q)
            return {'questions': qs, 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [],
                    'visual_stimuli': [], 'clinical_conflicts': [],
                    'question_importance': [{'question_id': q['question_id'],
                                             'importance_basis': t4.basis('learning_objective')} for q in qs]}, {}
        return super().__call__(stage, ctx, material, model)


def test_a_goal_nobody_asks_in_reverse_becomes_a_reverse_goal_studied_after_it(tmp_path):
    packet, model, result = t4.run(tmp_path, Discriminating())
    consume(result, packet)
    meta, doc, brief = result['manifest'], result['document'], result['brief']
    assert meta['discriminations'] == [{'direction_id': 'D1', 'cue': '표적 X를 끊는 작용을 하는 것은?', 'answer': 'Toxa',
                                        'competitors': ['Toxb'], 'asked_by': [], 'forward_by': ['Q1'],
                                        'point_id': 'P002'}]
    assert [p['point_id'] for p in meta['supplementPoints']['points'] if p.get('origin') == dis.ORIGIN] == ['P002']
    assert 'RQD001' in {r['relation_id'] for r in brief['relations']}
    assert model.calls.index('v4-discriminate-0') < model.calls.index('v4-supplement-normalize-discriminate') \
        < model.calls.index('v4-add-0')
    # The judgment is handed the lecture's goals, not a shape of the map.
    judged = model.inputs['v4-discriminate-0']
    assert [g['direction_id'] for g in judged['goals']] == ['D1', 'D2']
    assert {'cue', 'answer_scope', 'components'} <= set(judged['goals'][0])
    # The add stage is told the reverse cue, the answer, the competitors and the forward stems not to copy.
    goals = {gl['direction_id']: gl for gl in model.inputs['v4-add-0']['goals']}
    [told] = goals['DQ001']['discrimination']
    assert (told['cue'], told['answer'], told['competitors']) == ('표적 X를 끊는 작용을 하는 것은?', 'Toxa', ['Toxb'])
    assert [f['question_id'] for f in told['forward_by']] == ['Q1']
    assert 'discrimination' not in goals.get('D2', {})
    # Its question is a task, and the forward goal comes first.
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
    # three different numbers, each named for what it counts (2026-11-16)
    assert (counts['reversible'], counts['goalsMade'], counts['goalsWithTask'], counts['connectionsPlaced']) == (1, 1, 1, 1)
    assert (counts['open'], counts['answerInStem']) == ([], [])


def test_a_goal_already_asked_in_reverse_makes_no_goal(tmp_path):
    packet, model, result = t4.run(tmp_path, Discriminating(rows=[{**ROW, 'asked_by': ['Q2'], 'point': None},
                                                                  nothing('D2')]))
    consume(result, packet)
    assert 'v4-supplement-normalize-discriminate' not in model.calls
    assert result['manifest']['discriminations'][0]['point_id'] is None
    assert not any(dis.is_reverse_edge(e) for e in result['document']['prerequisites'])


def test_a_stem_that_gives_the_answer_away_is_counted_not_blocked(tmp_path):
    """R9: the one rule this policy asks for is measured, so one bad stem never holds a lecture."""
    class Named(Discriminating):
        def __call__(self, stage, ctx, material, model):
            value, rest = super().__call__(stage, ctx, material, model)
            if stage.startswith('v4-add'):
                for q in value['questions']:
                    if q['question'].startswith('표적'):
                        q['question'] = 'Toxa는 표적 X를 끊는다. 이 작용을 하는 것은?'
            return value, rest
    packet, _, result = t4.run(tmp_path, Named())
    consume(result, packet)
    counts = dis.report(result['manifest']['discriminations'], result['document'], result['document']['bank_snapshot'])
    assert [r['question_id'] for r in counts['answerInStem']] == ['Q004']
    assert counts['goalsWithTask'] == 1       # published all the same


def test_an_older_ledger_runs_without_the_reverse_judgment(tmp_path):
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


def test_the_backfill_adds_reverse_goals_beside_existence_goals_and_keeps_every_published_task(tmp_path):
    """presuppose-only/1 is the path the published lectures take (사용자 「역방향 넣고 한 번에」)."""
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
    assert meta['presupposeOnly']['reverseCounts']['goalsWithTask'] == 1
    assert {t['question_id'] for t in old['document']['tasks']} <= {t['question_id'] for t in doc['tasks']}
    assert any(dis.is_reverse_edge(e) for e in doc['prerequisites'])


# ---------------------------------------------------------------- pure functions
def test_stage_input_carries_every_goal_as_the_reference():
    brief = {'targets': [{'target_id': 'T1', 'evidence': [{'source_id': 'S1', 'pages': [1]}],
                          'directions': [{'direction_id': 'D1', 'cue': 'A가 가진 것은?', 'answer_scope': 'Toxa',
                                          'components': [{'component_id': 'm', 'text': 'Toxa'}],
                                          'requires_visual': False, 'relation_ids': []}]},
                         {'target_id': 'T2', 'evidence': [], 'directions':
                          [{'direction_id': 'D2', 'cue': 'B가 가진 것은?', 'answer_scope': 'Toxb',
                            'components': [{'component_id': 'm', 'text': 'Toxb'}], 'requires_visual': False,
                            'relation_ids': []}]}],
             'relations': [], 'points': []}
    bank = {'questions': [{'question_id': 'Q1', 'question': 'x', 'answer': 'y', 'answer_units': []}]}
    got = dis.stage_input(brief, bank, ['D1'], {'S1': 3})
    assert [g['direction_id'] for g in got['goals']] == ['D1']
    assert [g['direction_id'] for g in got['all_goals']] == ['D1', 'D2']   # competitors are looked for in all of them
    assert got['pages'] == [('S1', 1)] and [q['question_id'] for q in got['all_questions']] == ['Q1']
    assert dis.goals(brief) == ['D1', 'D2']
    with pytest.raises(ValueError, match='unknown goal'):
        dis.stage_input(brief, bank, ['D9'], {'S1': 3})


def test_stage_output_checks():
    ctx = {'goals': [{'direction_id': 'D1'}], 'all_goals': [{'direction_id': 'D1'}, {'direction_id': 'D2'}],
           'all_questions': [{'question_id': 'Q1'}, {'question_id': 'Q2'}], 'page_counts': {'S1': 3}}
    ok = {'rows': [row('D1')]}
    assert dis.check(ok, ctx) == ok
    assert dis.check({'rows': [nothing('D1')]}, ctx) == {'rows': [nothing('D1')]}
    for broken, message in [
        ({'rows': []}, 'every judged goal'),
        ({'rows': [row('D1', competitors=[])]}, 'candidates its stem rules out'),
        ({'rows': [row('D1', cue='  ')]}, 'needs a cue and an answer'),
        ({'rows': [row('D1', asked_by=['Q9'], point=None)]}, 'unknown questions'),
        ({'rows': [row('D1', forward_by=['Q9'])]}, 'unknown questions'),
        ({'rows': [row('D1', asked_by=['Q1'])]}, 'already asked carries no point'),
        ({'rows': [row('D1', point=None)]}, 'nobody asks needs its point'),
        ({'rows': [{**nothing('D1'), 'point': {'point': 'x', 'source_refs': REF}}]}, 'not worth reversing'),
        ({'rows': [row('D1', point={'point': 'x', 'source_refs': [
            {'source_id': 'S1', 'pages': [9], 'locator': None}]})]}, 'outside the sources')]:
        with pytest.raises(ValueError, match=message):
            dis.check(broken, ctx)


def _brief(*targets):
    return {'targets': [{'target_id': tid, 'concept_ids': cids, 'evidence': [{'source_id': 'S1', 'pages': [1]}],
                         'directions': [{'direction_id': 'D' + tid,
                                         'components': [{'component_id': 'm', 'text': 'Toxa'}]}]}
                        for tid, cids in targets],
            'points': [{'point_id': 'P9', 'target_ids': ['TR']}]}


def rec(point_id='P9', forward=('Q1',), did='DT1'):
    return {'direction_id': did, 'cue': 'c', 'answer': 'Toxa', 'competitors': ['Toxb'], 'asked_by': [],
            'forward_by': list(forward), 'point_id': point_id}


def test_gaps_keep_a_reverse_goal_open_until_a_question_carries_its_point():
    brief = _brief(('T1', ['A', 'B']), ('TR', ['B', 'C']))
    bank = {'questions': [{'question_id': 'Q1', 'point_ids': ['P1']}]}
    assert dis.gaps(brief, [rec()], bank) == {'DTR': ['m']}
    assert dis.written_for(bank, brief, [rec()]) == set()
    asked = {'questions': [{'question_id': 'Q1', 'point_ids': ['P1']}, {'question_id': 'Q4', 'point_ids': ['P9']}]}
    assert dis.written_for(asked, brief, [rec()]) == {'DTR'}
    assert dis.gaps(brief, [rec()], asked) == {}
    assert dis.gaps(brief, [rec(point_id=None)], bank) == {}


def test_order_edges_put_the_forward_goal_first_and_skip_cycles():
    brief = _brief(('T1', ['A', 'B']), ('TR', ['B', 'C']))
    tasks = [{'question_id': 'Q1', 'direction_id': 'DT1'}, {'question_id': 'Q4', 'direction_id': 'DTR'}]
    relations, edges = dis.order_edges(brief, tasks, [rec(), rec()], [], [])
    assert [(e['before_target'], e['after_target']) for e in edges] == [('T1', 'TR')]
    assert len(relations) == 1 and relations[0]['kind'] == 'prerequisite'
    assert dis.is_reverse_edge(edges[0]) and not dis.is_reverse_edge({'relation_id': 'R1'})
    # the judged goal itself orders the reverse even when no forward question is named
    assert [(e['before_target'], e['after_target'])
            for e in dis.order_edges(brief, tasks, [rec(forward=())], [], [])[1]] == [('T1', 'TR')]
    # neither the judged goal nor a forward question is a task: nothing to order
    assert dis.order_edges(brief, tasks[1:], [rec(forward=())], [], [])[1] == []
    existing = [{'before_target': 'T1', 'after_target': 'TR', 'relation_id': 'R9'}]
    assert dis.order_edges(brief, tasks, [rec()], [], existing)[1] == []
    cycle = [{'before_target': 'TR', 'after_target': 'T1', 'relation_id': 'R9'}]
    assert dis.order_edges(brief, tasks, [rec()], [], cycle)[1] == []


def test_records_keep_map_order_make_one_point_per_reverse_and_drop_questions_that_left():
    brief = {'targets': [{'target_id': 'T1', 'directions': [{'direction_id': 'D1'}]},
                         {'target_id': 'T2', 'directions': [{'direction_id': 'D2'}]}]}
    outputs = [{'rows': [row('D2'), row('D1'), nothing('D3')]}]
    bank = {'questions': [{'question_id': 'Q2'}]}
    points, got, new = dis.records(outputs, bank, {'points': [{'point_id': 'P001'}]}, brief)
    assert [r['direction_id'] for r in got] == ['D1', 'D2']     # map order, and the row judged false is left out
    assert [p['point_id'] for p in new] == ['P002']             # same answer and cue: one point
    assert [r['point_id'] for r in got] == ['P002', 'P002']
    assert got[0]['forward_by'] == []                           # Q1 is not in this bank any more
    assert new[0]['origin'] == dis.ORIGIN and new[0]['origin_direction_id'] == 'D1'
    assert [p['point_id'] for p in points['points']] == ['P001', 'P002']


def test_answer_in_stem_reads_only_the_questions_placed_on_a_reverse_goal():
    """`_join_points` hands the point to forward questions too; their stems are not this rule's business."""
    recs = [rec()]
    bank = {'questions': [{'question_id': 'Q4', 'point_ids': ['P9'], 'question': 'Toxa의 표적은?',
                           'answer': 'x', 'answer_units': []},
                          {'question_id': 'Q5', 'point_ids': ['P9'], 'question': '이 작용을 하는 것은?',
                           'answer': 'x', 'answer_units': []}]}
    # no document: every carrier is read, so the forward stem is flagged
    assert [r['question_id'] for r in dis.answer_in_stem(None, recs, bank)] == ['Q4']
    doc = {'review': {'points': [{'point_id': 'P9', 'target_ids': ['TR']}],
                      'targets': [{'target_id': 'T1', 'directions': [{'direction_id': 'DT1'}]},
                                  {'target_id': 'TR', 'directions': [{'direction_id': 'DTR'}]}]},
           'tasks': [{'question_id': 'Q4', 'direction_id': 'DT1'}, {'question_id': 'Q5', 'direction_id': 'DTR'}]}
    assert dis.placed_on_reverse(doc, recs) == {'Q5'}
    assert dis.answer_in_stem(doc, recs, bank) == []        # Q4 sits on its own forward goal


def test_answer_in_stem_takes_the_whole_korean_answer_not_its_category_word():
    def bank(*stems):
        return {'questions': [{'question_id': f'Q{n}', 'point_ids': ['P9'], 'question': s, 'answer': 'x',
                               'answer_units': []} for n, s in enumerate(stems)]}
    recs = [{**rec(), 'answer': '수도모나스'}]
    got = dis.answer_in_stem(None, recs, bank('수도모나스에서 이 작용을 하는 것은?', '이 작용을 하는 것은?'))
    assert [r['question_id'] for r in got] == ['Q0']
    # the words an answer shares with its own question are its category: asking needs them (2026-11-16 실측 3/17)
    recs = [{**rec(), 'answer': '획득 내성'}]
    assert dis.answer_in_stem(None, recs, bank('수평적 내성 유전자 획득으로 생기는 내성 유형은?')) == []
    recs = [{**rec(), 'answer': 'V. vulnificus 중증 감염'}]
    assert dis.answer_in_stem(None, recs, bank('이 병합을 치료 예로 쓰는 중증 감염의 원인균은?')) == []
    # a Latin name in the stem is still a give-away
    assert [r['question_id'] for r in dis.answer_in_stem(None, recs, bank('V. vulnificus에서 쓰는 병합은?'))] == ['Q0']


def test_a_published_question_keeps_its_goal_when_a_new_goal_would_take_it():
    """2026-11-16 job 646 / 261102_02: Q070 moved D061 → DQ011 (content unchanged) and the backfill was refused.
    The replay of that run with this pin finished, so the pin is what carries the history."""
    from studyez_contracts.roots import generation_v4 as v4
    where = {'Q070': 'DQ011', 'Q004': 'DQ001', 'Q1': 'D1'}
    settled = {'Q070': 'D061', 'Q1': 'D1'}                 # what the published revision placed
    assert v4.keep_published(where, settled) == {'Q070': 'D061', 'Q004': 'DQ001', 'Q1': 'D1'}
    assert v4.keep_published(where, None) == where          # a first run pins nothing
    assert v4.keep_published(where, {}) == where
    # a published question the placement dropped (merged as a duplicate) stays dropped
    assert v4.keep_published({'Q004': 'DQ001'}, settled) == {'Q004': 'DQ001'}


def test_a_forward_question_or_one_from_before_the_run_is_not_the_reverse_question_for_its_link():
    """The existence path's 2026-11-16 failure, in this path's shape: a later coverage round can give a reverse goal's
    point to the forward question, and the review would then read that question as the reverse one and have the fix
    put the answer's own side back into the stem. docs/changes/2026-11-17-existence-review-label."""
    brief = {'targets': [{'target_id': 'TR', 'directions': [{'direction_id': 'DTR', 'cue': 'c',
                                                             'relation_ids': ['RQD001'],
                                                             'components': [{'component_id': 'm', 'text': 'Toxa'}]}]}],
             'points': [{'point_id': 'P9', 'target_ids': ['TR']}]}
    bank = {'questions': [{'question_id': 'Q1', 'question': 'Toxa의 작용은?', 'point_ids': ['P9']},
                          {'question_id': 'Q4', 'question': 'c', 'point_ids': ['P9']}]}
    recs = [rec()]   # forward_by = ('Q1',)
    ctx = dis.mark_review({'questions': copy.deepcopy(bank['questions'])}, brief, recs, bank)
    assert [r['question_id'] for r in ctx['discrimination']] == ['Q4']
    assert 'discrimination' not in dis.mark_review({'questions': copy.deepcopy(bank['questions'])}, brief, recs, bank,
                                                   exclude=['Q1', 'Q4'])
