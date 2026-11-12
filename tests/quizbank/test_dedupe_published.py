"""duplicates-only/1 (docs/changes/2026-11-12-dedupe-published): a published /4 run made before goal-duplicates/1
judged again for duplicates only, through the synthetic /4 model of test_goal_duplicates."""
import copy
import json

import pytest

from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import packet_hash, validate_result as consume
from tests.quizbank.test_goal_duplicates import Caveat, run as legacy_run
from tests.quizbank.test_root_generation_v4 import tasks


def published(tmp_path):
    """The legacy run (Q003 and Q004 both tasks of D2) and a new request packet of the same lecture input."""
    old_packet, old = legacy_run(tmp_path / 'old', Caveat(), legacy=True)
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, duplicatesOnly=True)
    packet['inputHash'] = packet_hash(packet)
    return previous, old_packet, old, packet


def test_only_the_duplicate_groups_change_and_the_result_is_a_valid_revision(tmp_path):
    previous, old_packet, old, packet = published(tmp_path)
    assert tasks(old) == [('Q003', 'D2'), ('Q004', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]
    model = Caveat()
    result = g.run(packet, tmp_path / 'new', invoke=model, duplicates_of=previous)
    assert consume(result, packet) == result['document']
    # One judgment of the goals whose evidence names two questions or more; no earlier stage runs again.
    assert model.calls == ['v4-coverage-dup-0']
    assert [goal['direction_id'] for goal in model.inputs['v4-coverage-dup-0']['goals']] == ['D1', 'D2']
    assert [q['question_id'] for q in model.inputs['v4-coverage-dup-0']['questions']] == ['Q1', 'Q2', 'Q003', 'Q004']
    assert tasks(result) == [('Q003', 'D2'), ('Q1', 'D1'), ('Q2', 'D1')]
    assert [(m['question_id'], m['kept']) for m in result['manifest']['mergedDuplicates']] == [('Q004', 'Q003')]
    # Evidence, status and reason stay the first judgment's; questions and the medical review are the old ones.
    old_rows = {r['direction_id']: r for r in old['manifest']['coverage']}
    for r in result['manifest']['coverage']:
        assert {k: v for k, v in r.items() if k != 'duplicates'} == {k: v for k, v in old_rows[r['direction_id']].items() if k != 'duplicates'}
    assert result['document']['bank_snapshot'] == old['document']['bank_snapshot']
    assert result['medical'] == old['medical'] and result['brief'] == old['brief']
    assert result['document']['revision'] == 'auto-new'
    record = result['manifest']['duplicatesOnly']
    assert record['policy'] == 'duplicates-only/1' and record['previousRevision'] == old['document']['revision']
    assert (record['tasksBefore'], record['tasksAfter'], record['judgedGoals']) == (4, 3, ['D1', 'D2'])
    # The old run's stages are carried as they were, the new one after them.
    names = [s['name'] for s in result['manifest']['stages']]
    assert names[:-1] == [s['name'] for s in old['manifest']['stages']] and names[-1] == 'v4-coverage-dup-0'
    # The previous run is untouched.
    assert json.loads((previous / 'result.json').read_text(encoding='utf-8')) == old


def test_a_second_run_reuses_the_judgment(tmp_path):
    previous, _, _, packet = published(tmp_path)
    first = g.run(packet, tmp_path / 'new', invoke=Caveat(), duplicates_of=previous)
    (tmp_path / 'new' / 'result.json').unlink()
    model = Caveat()
    again = g.run(packet, tmp_path / 'new', invoke=model, duplicates_of=previous)
    assert model.calls == [] and again == first


def test_another_lecture_input_is_refused(tmp_path):
    previous, _, _, packet = published(tmp_path)
    packet['title'] = 'Another lecture'
    packet['inputHash'] = packet_hash(packet)
    with pytest.raises(ValueError, match='강의 입력'):
        g.run(packet, tmp_path / 'new', invoke=Caveat(), duplicates_of=previous)


def test_the_same_revision_is_refused(tmp_path):
    previous, old_packet, _, packet = published(tmp_path)
    packet['revision'] = old_packet['revision']
    packet['inputHash'] = packet_hash(packet)
    with pytest.raises(ValueError, match='판 이름'):
        g.run(packet, tmp_path / 'new', invoke=Caveat(), duplicates_of=previous)



class OtherGoal(Caveat):
    """The re-judgment of D1 also names Q003 (evidence only for D2) a duplicate of Q1."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-coverage-dup'):
            for r in value['rows']:
                if r['direction_id'] == 'D1':
                    r['duplicates'] = [{'question_ids': ['Q1', 'Q003'], 'reason': 'Synthetic'}]
                    r['evidence'].append(self.evidence(next(g for g in ctx['goals'] if g['direction_id'] == 'D1'), 'Q003', 'R1', 'answer', stage))
        return value, info


def test_a_group_keeps_only_questions_the_goal_already_had(tmp_path):
    previous, _, old, packet = published(tmp_path)
    result = g.run(packet, tmp_path / 'new', invoke=OtherGoal(), duplicates_of=previous)
    row = next(r for r in result['manifest']['coverage'] if r['direction_id'] == 'D1')
    assert row['duplicates'] == [] and 'Q003' not in [e['question_id'] for e in row['evidence']]
    assert ('Q1', 'D1') in tasks(result) and ('Q003', 'D2') in tasks(result)


def test_another_model_is_refused_before_any_call(tmp_path):
    previous, _, _, packet = published(tmp_path)
    model = Caveat()
    with pytest.raises(ValueError, match='모델'):
        g.run(packet, tmp_path / 'new', model='gpt-other-model', invoke=model, duplicates_of=previous)
    assert model.calls == [] and not (tmp_path / 'new' / 'ledger.json').exists()


def test_an_interrupted_seed_is_linked_again_without_touching_the_previous_run(tmp_path):
    previous, _, old, packet = published(tmp_path)
    out = tmp_path / 'new'
    out.mkdir()
    (out / '.seeding').write_text(str(previous), encoding='utf-8')
    stage = next(p for p in previous.glob('v4-*.json'))
    (out / stage.name).write_text('partial', encoding='utf-8')   # a half-written entry from the crash
    before = stage.read_bytes()
    result = g.run(packet, out, invoke=Caveat(), duplicates_of=previous)
    assert consume(result, packet) == result['document'] and not (out / '.seeding').exists()
    assert stage.read_bytes() == before and (out / stage.name).read_bytes() == before
