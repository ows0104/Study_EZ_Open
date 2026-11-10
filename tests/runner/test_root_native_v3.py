"""root-generation/3 stages in the native JSON adapter (docs/changes/2026-11-10-root-generation-3)."""
import pytest
from runner import root_native_json as n
from studyez_contracts.roots import generation_v3 as v3


@pytest.mark.parametrize('stage,schema', [
    ('v3-coverage-0-0', v3.COVERAGE_OUTPUT), ('v3-coverage-fix-1-0', v3.COVERAGE_OUTPUT), ('v3-map-check-0', v3.MAP_CHECK_OUTPUT),
    ('v3-supplement', v3.SUPPLEMENT_OUTPUT), ('v3-supplement-normalize', v3.SUPPLEMENT_NORMALIZE_OUTPUT), ('v3-add-1', v3.ADD_OUTPUT),
    ('v3-review-2-0', v3.ITEM_REVIEW_OUTPUT), ('v3-fix-2-1', v3.FIX_OUTPUT), ('v3-brief-fix', v3.BRIEF_FIX_OUTPUT),
])
def test_v3_stage_names_select_their_schema_and_prompt(stage, schema):
    assert n.schema_for(stage, {}) == schema
    task = n.task_for(stage)
    assert task.startswith('root-generation/3 단계다') and 'EXECUTION TRANSPORT ONLY' in task
    assert n.decode_for(stage, {'x': None}, schema) == ({'x': None}, None)


def test_unknown_v3_stage_is_refused():
    with pytest.raises(ValueError):
        n.schema_for('v3-anything', {})


def test_v2_stage_names_are_unchanged():
    from studyez_contracts.roots import generation_v2 as c
    assert n.schema_for('normalize', {}) == c.BRIEF
    assert n.task_for('source-1').startswith(n.g.PROMPTS.joinpath('source-v2.md').read_text(encoding='utf-8')[:40])


def test_v3_attaches_only_cited_pages_and_its_question_stimuli(tmp_path):
    material = tmp_path / 'material'
    material.mkdir()
    for name in ('S1-0001.png', 'S1-0002.png', 'S1-0003.png', 'S2-0001.png', 'stimulus-aa.png', 'stimulus-bb.png'):
        (material / name).write_bytes(b'png')
    ctx = {'pages': [['S1', 2], ['S2', 1]], 'questions': [{'question_id': 'Q1', 'stimuli': ['bb']}]}
    assert [p.name for p in n.review_images('v3-review-0-0', tmp_path, ctx)] == ['S1-0002.png', 'S2-0001.png', 'stimulus-bb.png']
    assert [p.name for p in n.review_images('v3-coverage-0-0', tmp_path, {'goals': [], 'questions': []})] == []


def test_the_host_check_state_is_written_beside_the_input_and_used_by_check_file(tmp_path, monkeypatch):
    """P6: `_check` leaves the stage input (and its hash); check_file runs the generator's check_stage with it."""
    import json
    from pathlib import Path
    seen = {}

    def fake_check_stage(kind, value, ctx, state, scratch):
        seen.update(kind=kind, state=state, scratch=Path(scratch).name)
        raise ValueError('synthetic merge error')
    import quizbank.connection_generate_v3 as g3
    monkeypatch.setattr(g3, 'check_stage', fake_check_stage)
    work = tmp_path / 'work'
    work.mkdir()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
    import generation_v2_fixture as f
    q = f.old.bank()['questions'][0]
    q.pop('stimuli', None)
    ctx = {'questions': [q], '_pipeline_version': v3.POLICY}
    (work / 'input.json').write_text(json.dumps(ctx), encoding='utf-8')
    (work / 'acceptance.schema.json').write_text(json.dumps(n.schema_for('v3-fix-0-0', ctx)), encoding='utf-8')
    (work / 'result.json').write_text(json.dumps({'questions': [q], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}), encoding='utf-8')
    (work / 'host-check.json').write_text(json.dumps({'bank': {'x': 1}}), encoding='utf-8')
    with pytest.raises(ValueError, match='synthetic merge error'):
        n.check_file('v3-fix-0-0', work)
    assert seen == {'kind': 'fix', 'state': {'bank': {'x': 1}}, 'scratch': '.check-render'}
