"""medical-final/1: one medical review after the last repair round; it never repairs or withholds."""
import copy
import sys
import threading
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from quizbank import connection_generate_v2 as g2
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash


@pytest.fixture(autouse=True)
def final_medical(monkeypatch):
    monkeypatch.setattr(g2, 'MEDICAL_FINAL', True)


def packet(tmp_path, speed=True):
    p = f.packet(tmp_path / 'source.txt')
    if speed:
        p['speedStages'] = True; p['inputHash'] = packet_hash(p)
    return p


def recorder(source_wrong_once=False, medical_wrong=False):
    calls, contexts, lock = [], {}, threading.Lock()
    def invoke(stage, ctx, *args):
        with lock:
            calls.append(stage); contexts[stage] = ctx
        if stage.startswith('context-'):
            return {'clinical_context_status': 'consistent', 'clinical_context_problem': 'none', 'clinical_context_reason': 'synthetic'}, {}
        value, info = f.model(stage, ctx, *args)
        if stage == 'source-0' and source_wrong_once:
            value['question_reviews'][0]['verdict'] = 'wrong'; value['question_reviews'][0]['note'] = 'synthetic wrong'
        if stage.startswith('medical-') and medical_wrong:
            value = copy.deepcopy(value)
            for r in value['reviews']:
                r['verdict'] = 'wrong'; r['note'] = '현재 의학: synthetic difference'
        return value, info
    return invoke, calls, contexts


@pytest.mark.parametrize('speed', [True, False])
def test_rounds_review_the_source_only_and_the_medical_review_runs_once_at_the_end(tmp_path, speed):
    p = packet(tmp_path, speed); invoke, calls, contexts = recorder(source_wrong_once=True)
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert result['manifest']['repairRounds'] == 1 and result['manifest']['medicalFinal'] == c.MEDICAL_FINAL_POLICY
    assert [s for s in calls if s.startswith('medical-')] == ['medical-1']
    assert calls.index('medical-1') > calls.index('source-1') and calls[-1] == 'medical-1'
    assert contexts['medical-1']['medicalFinal'] is True
    c.validate_result(result, p)


def test_a_medical_finding_neither_repairs_nor_withholds_the_question(tmp_path):
    p = packet(tmp_path)
    plain = g.run(p, tmp_path / 'ok', invoke=recorder()[0])
    invoke, calls, _ = recorder(medical_wrong=True)
    flagged = g.run(p, tmp_path / 'wrong', invoke=invoke)
    assert flagged['manifest']['repairRounds'] == 0 and 'repair-1' not in calls
    assert all(r['verdict'] == 'wrong' for r in flagged['medical']['reviews'])
    assert flagged['document']['tasks'] == plain['document']['tasks'] and flagged['document']['tasks']
    c.validate_result(flagged, p)


def test_the_result_must_keep_its_medical_policy(tmp_path):
    p = packet(tmp_path); result = g.run(p, tmp_path / 'out', invoke=recorder(medical_wrong=True)[0])
    dropped = copy.deepcopy(result); del dropped['manifest']['medicalFinal']
    with pytest.raises(ValueError):
        c.validate_result(dropped, p)
    unknown = copy.deepcopy(result); unknown['manifest']['medicalFinal'] = 'medical-final/2'
    with pytest.raises(ValueError):
        c.validate_result(unknown, p)


def test_earlier_ledgers_keep_the_per_round_review(tmp_path, monkeypatch):
    monkeypatch.setattr(g2, 'MEDICAL_FINAL', False)
    p = packet(tmp_path); invoke, calls, _ = recorder(source_wrong_once=True)
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    stages = {s['name'] for s in result['manifest']['stages']}
    assert 'medicalFinal' not in result['manifest'] and 'medical-0' in calls and {'medical-0', 'medical-1'} <= stages
    c.validate_result(result, p)


def test_the_final_prompt_keeps_the_lecture_answer_and_writes_student_notes():
    text = g2.MEDICAL_FINAL_PROMPT
    assert '강의 자료가 기준' in text and '「판정: 」' in text and '「현재 의학: 」' in text and '학생에게 그대로 보인다' in text


def test_only_a_differing_source_conflict_judgment_becomes_an_answer_fix():
    bank = {'questions': [{'question_id': 'Q1', 'conflict_id': 'CF1'}, {'question_id': 'Q2', 'conflict_id': ''}, {'question_id': 'Q3', 'conflict_id': 'CF2'}]}
    medical = {'reviews': [
        {'question_id': 'Q1', 'verdict': 'wrong', 'note': '판정: 본문이 맞다.', 'suggested_answer': '23가 다당백신'},
        {'question_id': 'Q2', 'verdict': 'wrong', 'note': '현재 의학: 다르다.', 'suggested_answer': 'x'},
        {'question_id': 'Q3', 'verdict': 'doubt', 'note': '판정: 확정 불가.', 'suggested_answer': 'y'}]}
    fixes = c.judgment_fixes(bank, medical)
    assert [f['question_ids'] for f in fixes] == [['Q1']] and '23가 다당백신' in fixes[0]['text']


def test_a_judgment_fix_repairs_once_then_reviews_again(tmp_path, monkeypatch):
    p = packet(tmp_path); invoke, calls, contexts = recorder()
    real = c.judgment_fixes
    def once(bank, medical):
        if medical is contexts.get('_seen'):
            return []
        contexts['_seen'] = medical
        return [{'kind': 'question_fix', 'question_ids': [bank['questions'][0]['question_id']], 'direction_ids': [], 'text': '의학 판정: synthetic'}]
    monkeypatch.setattr(c, 'judgment_fixes', lambda bank, medical: once(bank, medical) if 'repair-1' not in calls else real(bank, medical))
    result = g.run(p, tmp_path / 'out', invoke=invoke)
    assert result['manifest']['repairRounds'] == 1
    assert [s for s in calls if s.startswith(('medical-', 'repair-', 'source-'))] == ['source-0', 'medical-0', 'repair-1', 'source-1', 'medical-1']
    assert contexts['repair-1']['repairReasons'][0]['text'] == '의학 판정: synthetic'
    c.validate_result(result, p)
