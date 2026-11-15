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
