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
