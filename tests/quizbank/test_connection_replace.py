"""unplaced-only/1 (docs/changes/2026-11-15-unplaced-replace): a published review-relations/1 run whose question Q2
no goal took is placed again, through the synthetic /4 model of test_map_relation_guard."""
import copy
import json

import pytest

from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import packet_hash, validate_result as consume
from tests.quizbank.test_map_relation_guard import LateModel, DuplicateLateModel
from tests.quizbank.test_place_by_review import run_v1
from tests.quizbank.test_root_generation_v4 import tasks

LATE = ['v4-supplement-late', 'v4-supplement-normalize-late', 'v4-coverage-supplement-late', 'v4-map-check-late']


def published(tmp_path, model=None):
    old_packet, _, old = run_v1(tmp_path / 'old', model or LateModel())
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, unplacedOnly=True,
                  restartReason='못 붙은 문항 재배치')
    packet['inputHash'] = packet_hash(packet)
    return previous, old, packet


def test_an_unplaced_question_gets_a_late_goal_and_nothing_else_changes(tmp_path):
    previous, old, packet = published(tmp_path)
    assert [u['question_id'] for u in old['manifest']['unplacedQuestions']] == ['Q2'] and 'Q2' not in dict(tasks(old))
    model = LateModel()
    result = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert consume(result, packet) == result['document']
    # Only the late stages call the model; the late supplement is offered no existing point.
    assert model.calls == LATE
    assert model.inputs['v4-supplement-late']['points'] == []
    placed = dict(tasks(result))
    assert placed['Q2'].startswith('DQ') and set(tasks(old)) <= set(tasks(result))
    meta = result['manifest']
    assert meta['unplacedQuestions'] == [] and meta['placement'] == {'policy': v4.REVIEW_PLACEMENT2}
    record = meta['unplacedOnly']
    assert record['policy'] == 'unplaced-only/1' and record['previousRevision'] == old['document']['revision']
    assert (record['unplacedBefore'], record['unplacedAfter'], record['lateQuestions']) == (1, 0, ['Q2'])
    # Questions, the medical review and the item reviews are the old ones; the map only grows.
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']
    assert result['medical'] == old['medical'] and meta['itemReviews'] == old['manifest']['itemReviews']
    assert {t['target_id'] for t in old['brief']['targets']} < {t['target_id'] for t in result['brief']['targets']}
    names = [s['name'] for s in meta['stages']]
    assert names[:len(old['manifest']['stages'])] == [s['name'] for s in old['manifest']['stages']] and names[-4:] == LATE
    assert json.loads((previous / 'result.json').read_text(encoding='utf-8')) == old


def test_a_second_run_reuses_the_late_stages(tmp_path):
    previous, _, packet = published(tmp_path)
    first = g.run(packet, tmp_path / 'new', invoke=LateModel(), unplaced_of=previous)
    (tmp_path / 'new' / 'result.json').unlink()
    model = LateModel()
    again = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert model.calls == [] and again['document'] == first['document']


def test_a_question_still_off_the_map_is_reported_not_dropped(tmp_path):
    previous, old, packet = published(tmp_path)
    result = g.run(packet, tmp_path / 'new', invoke=LateModel(keep_off=True), unplaced_of=previous)
    assert consume(result, packet) == result['document']
    assert [u['question_id'] for u in result['manifest']['unplacedQuestions']] == ['Q2']
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']


def test_a_late_duplicate_of_answer_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    with pytest.raises(ValueError, match='late supplement: input.points is empty'):
        g.run(packet, tmp_path / 'new', invoke=DuplicateLateModel(), unplaced_of=previous)


def test_another_lecture_input_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    packet['title'] = 'Another lecture'
    packet['inputHash'] = packet_hash(packet)
    with pytest.raises(ValueError, match='강의 입력'):
        g.run(packet, tmp_path / 'new', invoke=LateModel(), unplaced_of=previous)


# ---------------------------------------------------------------- R4: unsupported relations are repaired
from tests.quizbank.test_root_generation_v4 import Model  # noqa: E402


class UnknownR1Model(Model):
    """The first map check leaves R1 unknown (its condition misses the subject), so neither D1 question is a task;
    the repair rewrites R1's condition and the re-check supports it. `bad_fix`: the repair also edits a goal."""

    def __init__(self, bad_fix=False, condition='Synthetic subject named'):
        self.condition = condition
        # The item reviews name no relation for Q1/Q2 (R1 is not a supported relation they may name).
        super().__init__(relations={'Q1': [], 'Q2': [], 'Q003': [('R2', 'whole')]})
        self.bad_fix = bad_fix

    def __call__(self, stage, ctx, material, model):
        if stage == 'v4-brief-fix-late':
            self.calls.append(stage)
            self.inputs[stage] = ctx
            fixed = copy.deepcopy(ctx['brief'])
            fixed['provenance']['independent_points'] = 'derived'
            next(r for r in fixed['relations'] if r['relation_id'] == 'R1')['condition'] = self.condition
            if self.bad_fix:
                t = fixed['targets'][0]
                key = next(k for k, v in t.items() if type(v) is str and k != 'target_id')
                t[key] += ' (changed goal)'
            return {'brief': fixed, 'map_change_reason': 'Synthetic relation repair'}, {}
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'v4-map-check-0':
            for r in value['relation_checks']:
                if r['relation_id'] == 'R1':
                    r.update(status='unknown', reason='Synthetic: the subject is missing')
        return value, info


def test_a_question_on_an_unknown_relation_is_placed_after_the_repair(tmp_path):
    previous, old, packet = published(tmp_path, UnknownR1Model())
    assert {'Q1', 'Q2'} & set(dict(tasks(old))) == set()
    model = UnknownR1Model()
    result = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert consume(result, packet) == result['document']
    assert model.calls == ['v4-brief-fix-late', 'v4-map-check-fix-late']
    assert [e.split(':')[0] for e in model.inputs['v4-brief-fix-late']['errors']] == ['R1']
    assert {'Q1', 'Q2'} <= set(dict(tasks(result))) and result['manifest']['unplacedQuestions'] == []
    repair = result['manifest']['unplacedOnly']['relationRepair']
    assert repair == {'relations': ['R1'], 'changed': ['R1'], 'supported': ['R1']}
    assert next(r for r in result['brief']['relations'] if r['relation_id'] == 'R1')['condition'] == 'Synthetic subject named'
    assert result['brief']['targets'] == old['brief']['targets']
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']


def test_a_repair_that_changes_a_goal_is_refused(tmp_path):
    previous, _, packet = published(tmp_path, UnknownR1Model())
    with pytest.raises(ValueError, match='관계 수선: targets'):
        g.run(packet, tmp_path / 'new', invoke=UnknownR1Model(bad_fix=True), unplaced_of=previous)


def test_a_repair_that_drops_the_korean_of_a_relation_is_refused(tmp_path):
    previous, old, packet = published(tmp_path, UnknownR1Model())
    rel = next(r for r in old['brief']['relations'] if r['relation_id'] == 'R1')
    if not any('가' <= ch <= '힣' for ch in str(rel.get('condition') or '')):
        pytest.skip('the synthetic R1 condition has no Korean')
    with pytest.raises(ValueError, match='한국어'):
        g.run(packet, tmp_path / 'new', invoke=UnknownR1Model(condition='English only'), unplaced_of=previous)


def test_korean_check():
    from quizbank.connection_replace import _check_repair
    before = {'relations': [{'relation_id': 'R1', 'from_id': 'C1', 'to_id': 'C2', 'condition': '리노바이러스 수용체'}],
              'concepts': [{'concept_id': 'C1', 'label': '수용체', 'parent_ids': []}, {'concept_id': 'C2', 'label': 'ICAM-1 이용', 'parent_ids': []}]}
    after = copy.deepcopy(before)
    after['relations'][0]['condition'] = 'Rhinovirus binds ICAM-1.'
    with pytest.raises(ValueError, match='한국어'):
        _check_repair(before, {'brief': after}, {'R1'})
    after['relations'][0]['condition'] = 'Rhinovirus의 80% 초과가 ICAM-1에 결합'
    assert _check_repair(before, {'brief': after}, {'R1'})['brief'] == after
