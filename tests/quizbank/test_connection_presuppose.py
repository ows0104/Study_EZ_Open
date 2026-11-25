"""presuppose-only/1 (docs/changes/2026-11-15-tree-edge-goals R6): a lecture published before presuppose/1 gets its
existence goals without being generated again. Q2's stem gives 「A has C」 and nobody asks it."""
import copy
import json

import pytest

from quizbank import connection_generate as g
from quizbank import connection_generate_v4 as gen4
from quizbank.connection_generate_v3 import Stages
from studyez_contracts.roots import presuppose as pre
from studyez_contracts.roots.automation import packet_hash, validate_result as consume
from tests.quizbank import test_root_generation_v4 as t4
from tests.quizbank.test_presuppose import Presupposing
from tests.quizbank.test_connection_replace import carry_sources

# discriminate/1 judges beside the stem judgment: one backfill request makes existence goals and reverse goals.
BACKFILL = ['v4-presuppose-0', 'v4-discriminate-0', 'v4-supplement-normalize-presuppose', 'v4-coverage-presuppose',
            'v4-map-check-presuppose',
            'v4-add-presuppose-0', 'v4-coverage-presuppose-1-DQ001', 'v4-review-presuppose-0', 'medical-presuppose']


class Legacy(Stages):
    """A ledger made before presuppose/1 (and so before discriminate/1, which came after it)."""
    def __init__(self, *a, fresh=None, **kw):
        super().__init__(*a, fresh={k: v for k, v in (fresh or {}).items() if k not in ('presuppositions', 'discriminations')},
                         **kw)


def published(tmp_path):
    real = gen4.Stages
    gen4.Stages = Legacy
    try:
        old_packet, _, old = t4.run(tmp_path / 'old', t4.Model())
    finally:
        gen4.Stages = real
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, presupposeOnly=True,
                  restartReason='존재 목표 보강', carrySources=carry_sources(old))
    packet['inputHash'] = packet_hash(packet)
    return previous, old, packet


def test_an_unasked_presupposed_link_gets_an_existence_goal_and_nothing_published_changes(tmp_path):
    previous, old, packet = published(tmp_path)
    assert 'presuppositions' not in old['manifest'] and old['document']['prerequisites'] == []
    model = Presupposing()
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert consume(result, packet) == result['document']
    assert model.calls == BACKFILL
    assert [gl['direction_id'] for gl in model.inputs['v4-add-presuppose-0']['goals'] if gl.get('existence')] == ['DQ001']
    doc, meta = result['document'], result['manifest']
    # Every published question, task, item review and medical verdict stays; one existence question is added.
    old_q = {q['question_id']: q for q in old['document']['bank_snapshot']['questions']}
    new_q = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    assert {k: new_q[k] for k in old_q} == old_q and set(new_q) - set(old_q) == {'Q004'}
    assert {t['task_id'] for t in old['document']['tasks']} <= {t['task_id'] for t in doc['tasks']}
    old_reviews = {r['question_id']: r for r in old['manifest']['itemReviews']}
    assert {r['question_id']: r for r in meta['itemReviews'] if r['question_id'] in old_reviews} == old_reviews
    old_medical = {r['question_id']: r for r in old['medical']['reviews']}
    assert {r['question_id']: r for r in result['medical']['reviews'] if r['question_id'] in old_medical} == old_medical
    # The existence goal is studied first.
    [edge] = doc['prerequisites']
    assert (edge['before_target'], edge['after_target']) == ('TQ001', 'T1')
    order = [t['question_id'] for t in doc['tasks']]
    assert order.index('Q004') < order.index('Q2')
    record = meta['presupposeOnly']
    assert record['policy'] == 'presuppose-only/1' and record['previousRevision'] == old['document']['revision']
    assert (record['addedQuestions'], record['existenceGoals'], record['counts']['existenceGoal'], record['counts']['open']) == (['Q004'], ['DQ001'], 1, 0)
    assert record['previousMedical'] == old['medical']
    # Every published task keeps its goal, so learners' records carry over (replace-carry-records).
    old_tasks = {(t['question_id'], t['direction_id']) for t in old['document']['tasks']}
    assert old_tasks <= {(t['question_id'], t['direction_id']) for t in doc['tasks']}
    carried = next(c for c in record['carry'] if c['revision'] == old['document']['revision'])
    assert carried['tasks'] == len(old['document']['tasks']) and doc['equivalences']
    # ... and the run hands the assembly the published places, which the consumer reads back from the record
    # (2026-11-17: the pin of PR #206 was never passed, so two lectures were refused for one question each).
    assert record['settledPlaces'] == {t['question_id']: t['direction_id'] for t in old['document']['tasks']}
    assert json.loads((previous / 'result.json').read_text(encoding='utf-8')) == old


def test_nothing_presupposed_adds_nothing_and_keeps_the_medical_review(tmp_path):
    previous, old, packet = published(tmp_path)
    model = t4.Model()
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert consume(result, packet) == result['document']
    assert model.calls == ['v4-presuppose-0', 'v4-discriminate-0']
    assert result['medical'] == old['medical'] and result['document']['bank_snapshot'] == old['document']['bank_snapshot']
    assert result['manifest']['presupposeOnly']['addedMedical'] is None


def test_a_second_run_reuses_every_stage(tmp_path):
    previous, _, packet = published(tmp_path)
    first = g.run(packet, tmp_path / 'new', invoke=Presupposing(), presuppose_of=previous)
    (tmp_path / 'new' / 'result.json').unlink()
    model = Presupposing()
    again = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert model.calls == [] and again['document'] == first['document']


def test_a_tampered_medical_review_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    result = g.run(packet, tmp_path / 'new', invoke=Presupposing(), presuppose_of=previous)
    bad = copy.deepcopy(result)
    bad['medical']['reviews'][0]['note'] = 'changed'
    with pytest.raises(ValueError, match='published review plus the added one'):
        consume(bad, packet)
    bad = copy.deepcopy(result)
    bad['manifest']['presupposeOnly']['previousMedical']['summary'] = 'other'
    with pytest.raises(ValueError, match='carried medical review'):
        consume(bad, packet)


def test_an_already_presuppose_run_and_other_flags_are_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    with pytest.raises(ValueError, match='재배치 없음'):
        g.run(packet, tmp_path / 'x', invoke=t4.Model(), presuppose_of=previous, unplaced_of=previous)
    # A lecture first made with presuppose/1 already has its existence goals.
    newer = tmp_path / 'newer'
    new_packet, _, _ = t4.run(newer, t4.Model())
    (newer / 'out' / 'packet.json').write_text(json.dumps(new_packet, ensure_ascii=False), encoding='utf-8')
    again = copy.deepcopy(new_packet)
    again.update(revision='auto-again', generationId='again', restartOf='newer', replacePublished=True, presupposeOnly=True,
                 restartReason='존재 목표 보강', carrySources=[{'revision': 'auto-older', 'tasks': []}])
    again['inputHash'] = packet_hash(again)
    with pytest.raises(ValueError, match='이미 presuppose/1'):
        g.run(again, tmp_path / 'again', invoke=t4.Model(), presuppose_of=newer / 'out')


def test_new_questions_may_not_add_clinical_conflicts(tmp_path):
    previous, _, packet = published(tmp_path)

    class Conflicting(Presupposing):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage.startswith('v4-add-presuppose'):
                value = copy.deepcopy(value)
                value['questions'][0]['conflict_id'] = 'CF-NEW'
                value['source_conflicts'] = [{'conflict_id': 'CF-NEW', 'description': 'Synthetic lecture vs current answer',
                                              'source_refs': [{'source_id': 'S1', 'locator': 'synthetic paragraph'}], 'unresolved': False}]
                value['clinical_conflicts'] = [{'conflict_id': 'CF-NEW', 'facts': 'Synthetic facts'}]
            return value, info
    with pytest.raises(ValueError, match='임상 충돌 기록을 더하지 않습니다'):
        g.run(packet, tmp_path / 'new', invoke=Conflicting(), presuppose_of=previous)


def test_a_new_question_the_review_doubts_is_fixed_and_reviewed_again(tmp_path):
    previous, old, packet = published(tmp_path)
    model = Presupposing(design_doubt=('Q004',))
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert consume(result, packet) == result['document']
    assert ['v4-fix-presuppose-0', 'v4-review-presuppose-1', 'v4-coverage-fix-presuppose-0'] ==         [c for c in model.calls if c in ('v4-fix-presuppose-0', 'v4-review-presuppose-1', 'v4-coverage-fix-presuppose-0')]
    fixes = result['manifest']['fixes']
    assert fixes[len(old['manifest']['fixes']):] == [{'question_id': 'Q004', 'attempt': 1, 'stage': 'v4-fix-presuppose-0', 'reverted': False}]
    q = next(q for q in result['document']['bank_snapshot']['questions'] if q['question_id'] == 'Q004')
    assert q['explanation'] == 'Synthetic clearer explanation'


def test_a_round_whose_every_fix_is_worse_is_undone_as_a_whole(tmp_path):
    """2026-11-17 job 670 / 261112_03: both fixes of the round were judged worse, and merging the empty rest again
    stopped the lecture with 「v3 fix output.questions: too few entries」. The first run undoes such a round whole."""
    previous, old, packet = published(tmp_path)

    class Worse(Presupposing):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage in ('v4-review-presuppose-1', 'v4-review-presuppose-2'):
                value = copy.deepcopy(value)
                for r in value['reviews']:
                    r.update(verdict='wrong', note='Synthetic worse')
            return value, info
    model = Worse(design_doubt=('Q004',))
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous)
    assert consume(result, packet) == result['document']
    fixes = result['manifest']['fixes'][len(old['manifest']['fixes']):]
    assert fixes and all(f['question_id'] == 'Q004' and f['reverted'] for f in fixes)
    # the question ends as it was added, with the doubt of its first review
    added = next(q for q in model.inputs['v4-fix-presuppose-0']['questions'] if q['question_id'] == 'Q004')
    q = next(q for q in result['document']['bank_snapshot']['questions'] if q['question_id'] == 'Q004')
    assert q['explanation'] == added['explanation'] != 'Synthetic clearer explanation'


def test_without_carry_sources_it_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    del packet['carrySources']
    packet['inputHash'] = packet_hash(packet)
    with pytest.raises(ValueError, match='carrySources'):
        g.run(packet, tmp_path / 'new', invoke=Presupposing(), presuppose_of=previous)


def test_runner_and_server_names():
    from runner import root_native_json as native
    import re
    assert native.v3_kind('v4-add-presuppose-0') == 'add' and native.v3_kind('v4-review-presuppose-1') == 'review'
    assert native.v3_kind('v4-fix-presuppose-0') == 'fix'
    assert pre.PRESUPPOSE == 'presuppose/1'


def test_the_backfill_passes_the_published_places_to_the_assembly(tmp_path, monkeypatch):
    """The pin is only as good as its caller: the assembly must get the published map, whatever the placement says."""
    from studyez_contracts.roots import generation_v4 as v4
    previous, old, packet = published(tmp_path)
    seen = {}
    real = v4.assemble

    def assemble(*a, **kw):
        seen.update(settled_places=kw.get('settled_places'))
        return real(*a, **kw)
    monkeypatch.setattr(v4, 'assemble', assemble)
    g.run(packet, tmp_path / 'new', invoke=Presupposing(), presuppose_of=previous)
    assert seen['settled_places'] == {t['question_id']: t['direction_id'] for t in old['document']['tasks']}


def test_a_published_task_is_not_merged_away_as_a_duplicate():
    """2026-11-17 job 655 / 261105_03: the new goal DQ017 judged published Q025 and Q075 duplicates, Q075 lost its
    task and the backfill was refused (「이전 판의 과제가 빠졌습니다」)."""
    from studyez_contracts.roots import generation_v4 as v4
    bank = {'questions': [{'question_id': q, 'importance': i} for q, i in (('Q025', 5), ('Q075', 4), ('Q300', 5))]}
    ok = {q['question_id']: 'ok' for q in bank['questions']}
    row = lambda *qs: {'direction_id': 'DQ017', 'status': 'covered', 'duplicates': [{'question_ids': list(qs), 'reason': 'same'}]}
    merged = lambda rows, held=frozenset(): [(m['question_id'], m['kept']) for m in v4.merged_duplicates(rows, bank, ok, held=held)]
    # a first run merges as before
    assert merged([row('Q025', 'Q075')]) == [('Q075', 'Q025')]
    # two published tasks both stay
    assert merged([row('Q025', 'Q075')], {'Q025', 'Q075'}) == []
    # a published task and an added question of the same importance or more: the added one goes
    assert merged([row('Q075', 'Q300')], {'Q075'}) == [('Q300', 'Q075')]
    assert merged([row('Q025', 'Q075', 'Q300')], {'Q025', 'Q075'}) == [('Q300', 'Q025')]
    # a published question the published revision had already merged away is not held, and goes as before
    assert merged([row('Q025', 'Q075')], {'Q025'}) == [('Q075', 'Q025')]


def test_a_revision_with_replaced_notes_is_continued(tmp_path, monkeypatch):
    """notes-update/1 then presuppose-only/1 (2026-11-17 job 670 / 261112_03): the published revision named corrected
    notes; the backfill names them too, as the consumer derives from the record the manifest inherits."""
    from tests.quizbank import test_connection_replace as rep
    with monkeypatch.context() as legacy:          # published before presuppose/1, as published() above
        legacy.setattr('quizbank.connection_generate_v3.Stages', Legacy)   # run_v1 subclasses this one
        previous, old, packet = rep.published_pdf(tmp_path, monkeypatch)
    packet = rep.corrected(tmp_path, packet, ['Synthetic notes page 1', 'Synthetic notes page 2 (corrected)', 'Synthetic notes page 3'])
    updated = g.run(packet, tmp_path / 'new', invoke=rep.PdfLateModel(), unplaced_of=previous)
    assert updated['document']['replaced_sources']
    (tmp_path / 'new' / 'packet.json').write_text(json.dumps(packet, ensure_ascii=False), encoding='utf-8')
    again = copy.deepcopy(packet)
    del again['unplacedOnly']
    again.update(revision='auto-newer', generationId='newer', restartOf='new', replacePublished=True, presupposeOnly=True,
                 restartReason='존재 목표 보강', carrySources=carry_sources(updated))
    again['inputHash'] = packet_hash(again)
    result = g.run(again, tmp_path / 'newer', invoke=rep.PdfLateModel(), presuppose_of=tmp_path / 'new')
    assert consume(result, again) == result['document']
    doc = result['document']
    assert doc['replaced_sources'] == updated['document']['replaced_sources']
    assert doc['review']['sources'] == updated['document']['review']['sources']
    assert result['brief']['sources'] == old['brief']['sources']
    assert doc['bank_snapshot']['questions'] == updated['document']['bank_snapshot']['questions']


def test_published_figures_of_replaced_notes_are_kept_and_new_ones_refused(tmp_path):
    """The five published figures of 261112_03 were cropped from the earlier notes; rendering them again from the
    corrected file changed the questions and failed the source check of the assembly."""
    from quizbank import connection_presuppose as backfill
    figure = {'source_id': 'S1', 'source_sha256': 'a' * 64, 'page': 2, 'crop': [0, 0, 1, 1], 'sha256': 'b' * 64,
              'width': 1, 'height': 1, 'png_base64': ''}
    as_published = {'Q1': {'question_id': 'Q1', 'stimuli': [figure]}, 'Q2': {'question_id': 'Q2'}}
    bank = {'questions': [{'question_id': 'Q1', 'stimuli': [{**figure, 'source_sha256': 'c' * 64}]}, {'question_id': 'Q2'},
                          {'question_id': 'Q9'}]}
    spec = {'question_id': 'Q1', 'source_id': 'S1', 'page': 2, 'crop': [0, 0, 1, 1]}
    seen = {}

    def render(value, specs, packet, material):
        seen['specs'] = specs
        value = copy.deepcopy(value)
        for q in value['questions']:
            q.pop('stimuli', None)
        return value
    real = backfill.visual.render
    backfill.visual.render = render
    try:
        value = backfill._render_keeping(bank, [spec], {'sources': []}, tmp_path, as_published, {'S1'})
        assert seen['specs'] == [] and value['questions'][0]['stimuli'] == [figure]
        assert 'stimuli' not in value['questions'][1] and 'stimuli' not in value['questions'][2]
        with pytest.raises(ValueError, match='새 문항'):
            backfill._render_keeping(bank, [spec, {**spec, 'question_id': 'Q9'}], {'sources': []}, tmp_path, as_published, {'S1'})
    finally:
        backfill.visual.render = real


# ---------------------------------------------------------------- fill mode (docs/changes/2026-11-17-fill-recovery)
class NoAdd(t4.Model):
    """The first run writes nothing for the empty goal D2: it stays open in the published revision."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-add'):
            value = {**value, 'questions': [], 'question_importance': []}
        return value, info


def judged(tmp_path):
    """A revision first made with presuppose/1 and discriminate/1 whose goal D2 has no question."""
    old_packet, _, old = t4.run(tmp_path / 'old', NoAdd())
    assert 'presuppositions' in old['manifest'] and 'discriminations' in old['manifest']
    assert t4.tasks(old) == [('Q1', 'D1'), ('Q2', 'D1')]
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, presupposeOnly=True,
                  restartReason='채우기', carrySources=carry_sources(old))
    packet['inputHash'] = packet_hash(packet)
    return previous, old, packet


def fill_record(old, goals=(), rewrite=()):
    return {'previousRevision': old['document']['revision'], 'goals': list(goals), 'rewrite': list(rewrite),
            'reason': 'Synthetic recovery', 'approval': 'Synthetic approval', 'at': '2026-11-17T09:30:00+09:00'}


def test_fill_writes_only_for_the_listed_goal_and_judges_nothing_again(tmp_path):
    previous, old, packet = judged(tmp_path)
    model = t4.Model()
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous, fill=fill_record(old, ['D2']))
    assert consume(result, packet) == result['document']
    # no judgment, no goal made: the add round, its coverage, the review of the new question and its medical review
    assert model.calls == ['v4-add-presuppose-0', 'v4-coverage-presuppose-1-D2', 'v4-review-presuppose-0', 'medical-presuppose']
    assert [gl['direction_id'] for gl in model.inputs['v4-add-presuppose-0']['goals']] == ['D2']
    assert t4.tasks(result) == [('Q003', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]
    old_q = {q['question_id']: q for q in old['document']['bank_snapshot']['questions']}
    new_q = {q['question_id']: q for q in result['document']['bank_snapshot']['questions']}
    assert {k: new_q[k] for k in old_q} == old_q and set(new_q) - set(old_q) == {'Q003'}
    meta = result['manifest']
    record = meta['presupposeOnly']
    assert record['fill']['goals'] == ['D2'] and record['addedQuestions'] == ['Q003'] and 'rewrittenQuestions' not in record
    assert (record['existenceGoals'], record['reverseGoals']) == ([], [])
    carried = next(c for c in record['carry'] if c['revision'] == old['document']['revision'])
    assert carried['tasks'] == carried['of'] == len(old['document']['tasks'])
    # the published judgments and points are the published ones
    assert meta['presuppositions'] == old['manifest']['presuppositions'] and meta['discriminations'] == old['manifest']['discriminations']
    assert meta['supplementPoints'] == old['manifest']['supplementPoints']


def test_fill_of_a_goal_that_lacks_nothing_calls_no_model(tmp_path):
    previous, old, packet = judged(tmp_path)
    model = t4.Model()
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous, fill=fill_record(old, ['D1']))
    assert consume(result, packet) == result['document']
    assert model.calls == [] and result['document']['bank_snapshot'] == old['document']['bank_snapshot']
    assert result['medical'] == old['medical'] and result['manifest']['presupposeOnly']['addedMedical'] is None


def test_fill_rewrites_a_published_question_from_the_operators_finding_and_only_its_history_restarts(tmp_path):
    previous, old, packet = judged(tmp_path)
    model = t4.Model()
    rewrite = [{'question_id': 'Q2', 'note': 'The stem hands over the link the goal asks.', 'fix': 'Ask the link itself.'}]
    result = g.run(packet, tmp_path / 'new', invoke=model, presuppose_of=previous, fill=fill_record(old, [], rewrite))
    assert consume(result, packet) == result['document']
    assert model.calls == ['v4-fix-presuppose-0', 'v4-review-presuppose-1', 'v4-coverage-fix-presuppose-0', 'medical-presuppose']
    # the fix stage is given the operator's finding, not the published review
    [finding] = model.inputs['v4-fix-presuppose-0']['findings']
    assert (finding['question_id'], finding['design'], finding['note'], finding['fix']) == \
        ('Q2', 'wrong', 'The stem hands over the link the goal asks.', 'Ask the link itself.')
    new_q = {q['question_id']: q for q in result['document']['bank_snapshot']['questions']}
    old_q = {q['question_id']: q for q in old['document']['bank_snapshot']['questions']}
    assert new_q['Q2']['explanation'] == 'Synthetic clearer explanation' and new_q['Q1'] == old_q['Q1']
    assert t4.tasks(result) == t4.tasks(old)                       # it stays on its goal
    record = result['manifest']['presupposeOnly']
    assert record['rewrittenQuestions'] == ['Q2'] and record['addedQuestions'] == []
    assert result['manifest']['fixes'][len(old['manifest']['fixes']):] == \
        [{'question_id': 'Q2', 'attempt': 1, 'stage': 'v4-fix-presuppose-0', 'reverted': False}]
    # every other task continues its history; the rewritten one starts over
    carried = next(c for c in record['carry'] if c['revision'] == old['document']['revision'])
    assert (carried['tasks'], carried['of']) == (len(old['document']['tasks']) - 1, len(old['document']['tasks']))
    # its medical verdict is the new review's, the others' the published one's
    assert [r['question_id'] for r in record['addedMedical']['reviews']] == ['Q2']
    assert [r['question_id'] for r in result['medical']['reviews']] == [q['question_id'] for q in result['document']['bank_snapshot']['questions']]
    # the consumer refuses a rewritten question the run did not fix
    bad = copy.deepcopy(result)
    bad['manifest']['presupposeOnly']['rewrittenQuestions'] = ['Q1']
    with pytest.raises(ValueError, match='rewritten questions'):
        consume(bad, packet)


def test_a_fill_record_must_fit_the_revision(tmp_path):
    previous, old, packet = judged(tmp_path)
    for record, message in [
            ({**fill_record(old, ['D2']), 'previousRevision': 'auto-other'}, '다른 판'),
            (fill_record(old, ['D9']), '지도에 없습니다'),
            (fill_record(old, [], [{'question_id': 'Q9', 'note': 'n', 'fix': 'f'}]), '다시 쓸 문항'),
            (fill_record(old), '목표도 다시 쓸 문항도'),
            ({k: v for k, v in fill_record(old, ['D2']).items() if k != 'approval'}, '형식')]:
        with pytest.raises(ValueError, match=message):
            g.run(packet, tmp_path / 'x', invoke=t4.Model(), presuppose_of=previous, fill=record)
    # a revision that was never judged is backfilled, not filled
    (tmp_path / 'plain').mkdir()
    plain_previous, plain_old, plain_packet = published(tmp_path / 'plain')
    with pytest.raises(ValueError, match='이미 거친 판만'):
        g.run(plain_packet, tmp_path / 'y', invoke=t4.Model(), presuppose_of=plain_previous, fill=fill_record(plain_old, ['D2']))


class DoubtAfterRewrite(t4.Model):
    """The re-review of the rewritten Q2 finds a new design doubt (2026-11-25 job 746 / 261123_06: Q072·Q100)."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'v4-review-presuppose-1':
            value = copy.deepcopy(value)
            for r in value['reviews']:
                if r['question_id'] == 'Q2':
                    r.update(design='doubt', note='The new answer frame is not in the source.')
        return value, info


def test_a_rewrite_the_re_review_finds_worse_in_design_is_undone_and_the_lecture_still_publishes(tmp_path):
    """Job 746 (2026-11-25): the published Q072 and Q100 were reviewed ok; rewritten, their re-review said design
    doubt with no fix budget left. Only a worse content verdict undid an operator's rewrite, so the two stayed doubtful,
    dropped out of the tasks, and the whole lecture was refused 「이전 판의 과제가 빠졌습니다」. Now the published
    question comes back, and the rest of the fill goes on."""
    previous, old, packet = judged(tmp_path)
    rewrite = [{'question_id': 'Q2', 'note': 'The answer is a long unordered list.', 'fix': 'Lay the answer out.'}]
    result = g.run(packet, tmp_path / 'new', invoke=DoubtAfterRewrite(), presuppose_of=previous,
                   fill=fill_record(old, [], rewrite))
    assert consume(result, packet) == result['document']
    old_q = {q['question_id']: q for q in old['document']['bank_snapshot']['questions']}
    new_q = {q['question_id']: q for q in result['document']['bank_snapshot']['questions']}
    assert new_q['Q2'] == old_q['Q2'] and t4.tasks(result) == t4.tasks(old)
    assert result['manifest']['fixes'][len(old['manifest']['fixes']):] == \
        [{'question_id': 'Q2', 'attempt': 1, 'stage': 'v4-fix-presuppose-0', 'reverted': True}]
    record = result['manifest']['presupposeOnly']
    assert not record.get('rewrittenQuestions')
    carried = next(c for c in record['carry'] if c['revision'] == old['document']['revision'])
    assert carried['tasks'] == carried['of'] == len(old['document']['tasks'])
