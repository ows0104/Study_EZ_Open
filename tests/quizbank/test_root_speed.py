"""Opt-in speed path (speedStages): context check first, source ‖ medical, medical review reuse."""
import copy
import json
import sys
import threading
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash


def speed_packet(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); p['speedStages'] = True; p['inputHash'] = packet_hash(p)
    return p


def recorder(status='consistent', wrong_once=False, change_q2=False, problem=None):
    calls, medical_questions, lock = [], {}, threading.Lock()
    def invoke(stage, ctx, *args):
        with lock:
            calls.append(stage)
        if stage.startswith('context-'):
            assert 'brief' not in ctx and 'clinical_conflicts' in ctx and 'bank' in ctx
            kind = problem or ('contamination' if status == 'conflict' else 'none')
            return {'clinical_context_status': status, 'clinical_context_problem': kind, 'clinical_context_reason': 'synthetic ' + status}, {}
        if stage.startswith('medical-'):
            medical_questions[stage] = [q['question_id'] for q in ctx['bank']['questions']]
        value, info = f.model(stage, ctx, *args)
        if stage == 'source-0' and wrong_once:
            value['question_reviews'][0]['verdict'] = 'wrong'; value['question_reviews'][0]['note'] = 'synthetic wrong'
        if stage == 'repair-1' and change_q2:
            q = next(q for q in value['bank']['questions'] if q['question_id'] == 'Q2'); q['explanation'] = 'Synthetic changed explanation'
        return value, info
    return invoke, calls, medical_questions


def test_context_check_runs_first_and_source_and_medical_share_the_round(tmp_path):
    p = speed_packet(tmp_path); invoke, calls, _ = recorder()
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert calls[:3] == ['normalize', 'generate', 'context-0'] and set(calls[3:]) == {'source-0', 'medical-0'}
    assert result['manifest']['contextStages'] is True and result['manifest']['clinicalContext']['clinical_context_status'] == 'consistent'
    c.validate_result(result, p)
    bad = copy.deepcopy(result); bad['manifest']['clinicalContext']['clinical_context_status'] = 'unknown'
    with pytest.raises(ValueError):
        c.validate_result(bad, p)
    plain = f.packet(tmp_path / 'plain.txt')
    assert 'context-0' not in [s for s in g.run(plain, tmp_path / 'plain', invoke=recorder()[0])['manifest'].get('stages', [])]


def test_an_unverified_context_never_reaches_the_blind_medical_model(tmp_path):
    p = speed_packet(tmp_path); invoke, calls, _ = recorder(status='conflict')
    with pytest.raises(ValueError):
        g.run(p, tmp_path / 'out', invoke=invoke)
    assert not any(s.startswith('medical-') for s in calls) and 'repair-1' in calls


def test_unchanged_questions_reuse_the_earlier_medical_review(tmp_path):
    p = speed_packet(tmp_path); invoke, calls, medical = recorder(wrong_once=True, change_q2=True)
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert result['manifest']['repairRounds'] >= 1
    assert medical['medical-0'] == ['Q1', 'Q2'] and medical['medical-1'] == ['Q2']  # Q1 unchanged → reused
    rows = result['manifest']['medicalReuse']
    assert rows[0]['stage'] == 'medical-1' and [r['question_id'] for r in rows[0]['reused']] == ['Q1']
    c.validate_result(result, p)
    bad = copy.deepcopy(result); bad['manifest']['medicalReuse'][0]['reused'][0]['questionHash'] = '0' * 64
    if result['manifest']['repairRounds'] == 1:
        with pytest.raises(ValueError):
            c.validate_result(bad, p)


# clinical-context/2 (2026-11-09 사용자 「오염만 막기」)
def test_an_incomplete_conflict_record_still_gets_the_medical_review_and_goes_to_repair(tmp_path):
    p = speed_packet(tmp_path); invoke, calls, _ = recorder(status='conflict', problem='incomplete')
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    stages = {s['name']: s['status'] for s in result['manifest']['stages']}
    assert all(stages[f'medical-{n}'] == 'completed' for n in range(4))  # every round was medically reviewed, none withheld
    decision = json.loads((tmp_path / 'out' / 'repair-decision-0.json').read_text(encoding='utf-8'))
    assert any(r['text'].startswith('임상 충돌 정리 보완(정답 검수는 진행)') for r in decision['reasons'])
    assert result['manifest']['repairRounds'] == 3 and result['manifest']['clinicalContext']['clinical_context_problem'] == 'incomplete'
    c.validate_result(result, p)


def test_unknown_context_no_longer_withholds_the_medical_review_and_is_not_a_repair_reason(tmp_path):
    p = speed_packet(tmp_path); invoke, calls, _ = recorder(status='unknown')
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert 'medical-0' in calls and result['manifest']['repairRounds'] == 0
    c.validate_result(result, p)


def test_context_status_and_problem_must_agree_and_legacy_records_keep_the_old_rule():
    ok = {'clinical_context_status': 'conflict', 'clinical_context_problem': 'incomplete', 'clinical_context_reason': 'x'}
    assert c.validate_context(ok) and not c.context_blocks_medical(ok) and c.context_repair_note(ok)
    for status, problem in (('conflict', 'none'), ('consistent', 'incomplete'), ('unknown', 'contamination')):
        with pytest.raises(ValueError):
            c.validate_context({**ok, 'clinical_context_status': status, 'clinical_context_problem': problem})
    assert c.context_blocks_medical({**ok, 'clinical_context_problem': 'contamination'})
    for status, blocks in (('consistent', False), ('unknown', True), ('conflict', True)):  # written before /2
        legacy = {'clinical_context_status': status, 'clinical_context_reason': 'x'}
        assert c.validate_context(legacy) and c.context_blocks_medical(legacy) is blocks and not c.context_repair_note(legacy)
