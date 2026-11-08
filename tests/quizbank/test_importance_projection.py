"""exam-point-extract/3 points: tiers are computed from the point basis and projected at assembly."""
import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash


def v3_packet(tmp_path, basis):
    p = f.packet(tmp_path / 'source.txt')
    p['points'] = json.dumps({'schema_version': 'exam-point-extract/3', 'title': 'Synthetic', 'notes': [],
                              'notebook_profile': {'legend': '', 'emphasis_style': 'slide', 'reason': 'synthetic'},
                              'points': [{'point_id': 'P1', 'point': 'Synthetic A/B point',
                                          'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}],
                                          'importance_basis': basis}]}, ensure_ascii=False)
    p['inputHash'] = packet_hash(p)
    return p


BASIS = [{'kind': 'current_exam', 'year': 2023, 'quote': '', 'reason': 'synthetic exam', 'refs': [{'source_id': 'S1', 'pages': [1]}]},
         {'kind': 'slide_emphasis', 'year': None, 'quote': '', 'reason': 'synthetic box', 'refs': [{'source_id': 'S1', 'pages': [1]}]}]


def with_point_ids(stage, ctx, *args):
    value, info = f.model(stage, ctx, *args)
    if stage == 'generate' or stage.startswith('repair-'):
        for q in value['bank']['questions']:
            q['point_ids'] = ['P1']
    return value, info


def test_points_basis_decides_tier_and_target_axes_without_an_importance_stage(tmp_path):
    p = v3_packet(tmp_path, BASIS); calls = []
    def invoke(stage, *args):
        calls.append(stage); return with_point_ids(stage, *args)
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert calls == ['normalize', 'generate', 'source-0', 'medical-0']
    bank = result['document']['bank_snapshot']
    assert bank['build_meta']['schema_version'] == '3.3'
    assert {(q['tier'], q['importance']) for q in bank['questions']} == {('Core', 4)}  # 2 + 1 = 3 → Core
    axes = result['document']['review']['targets'][0]['importance']
    assert axes['exam']['status'] == 'supported' and axes['clinical']['status'] == 'insufficient'
    assert result['manifest']['importanceProjection']['fallback'] == []
    c.validate_result(result, p)
    tampered = copy.deepcopy(result)
    tampered['document']['bank_snapshot']['questions'][0]['tier'] = 'Essential'
    with pytest.raises(ValueError):
        c.validate_result(tampered, p)


def test_missing_point_ids_are_a_repair_reason_and_fall_back_to_the_concept_targets(tmp_path):
    p = v3_packet(tmp_path, [{**BASIS[0], 'kind': 'exam_forecast', 'quote': '시험에 낼 겁니다', 'year': None}])
    calls = []
    def invoke(stage, *args):
        calls.append(stage); return f.model(stage, *args)
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert 'repair-1' in calls  # the missing point_ids were sent back to authoring
    proof = result['manifest']['importanceProjection']
    assert sorted(proof['fallback']) == ['Q1', 'Q2']
    assert {q['tier'] for q in result['document']['bank_snapshot']['questions']} == {'Essential'}
    c.validate_result(result, p)


def test_older_point_formats_keep_the_authored_tiers(tmp_path):
    p = f.packet(tmp_path / 'source.txt')
    result = g.run(p, tmp_path / 'out', invoke=f.model)
    assert 'importanceProjection' not in result['manifest']
    assert result['document']['bank_snapshot']['build_meta']['schema_version'] == '3.2'


def test_model_written_target_axes_are_replaced_by_the_assembly_placeholder(tmp_path):
    """261104_02 26110803: normalisation copied point evidence into target axes (clinical under exam)."""
    p = v3_packet(tmp_path, BASIS); seen = []
    def invoke(stage, ctx, *args):
        seen.append((stage, 'importanceTable' in ctx))
        value, info = with_point_ids(stage, ctx, *args)
        if stage == 'normalize':
            value['targets'][0]['importance']['exam'] = {'status': 'supported', 'reason': 'model copy', 'evidence': [
                {'kind': 'clinical_rationale', 'reason': 'wrong axis', 'refs': [{'source_id': 'S1', 'locator': 'p1', 'pages': []}]}]}
        return value, info
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert dict(seen)['normalize'] is False and dict(seen)['generate'] is True
    assert all(a == c.IMPORTANCE_PLACEHOLDER for t in result['manifest']['initialBrief']['targets'] for a in t['importance'].values())
    assert result['manifest']['repairRounds'] == 0
    c.validate_result(result, p)
