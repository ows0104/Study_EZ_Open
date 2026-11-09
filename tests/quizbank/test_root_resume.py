"""stage-resume/1 (2026-11-09 사용자 「중간 성공한 부분까지는 저장되게 해서 안된 부분부터 하자」)."""
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

REASON = 'test: resume after a fixed engine defect'


def speed_packet(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); p['speedStages'] = True; p['inputHash'] = packet_hash(p)
    return p


def model(calls, fail=(), wrong_once=False, legacy_context=False):
    def invoke(stage, ctx, *args):
        calls.append(stage)
        if stage in fail:
            raise RuntimeError('synthetic crash in ' + stage)
        if stage.startswith('context-'):
            value = {'clinical_context_status': 'consistent', 'clinical_context_reason': 'synthetic'}
            if not legacy_context:
                value['clinical_context_problem'] = 'none'
            return value, {}
        value, info = f.model(stage, ctx, *args)
        if stage == 'source-0' and wrong_once:
            value['question_reviews'][0]['verdict'] = 'wrong'; value['question_reviews'][0]['note'] = 'synthetic wrong'
        return value, info
    return invoke


def ledger(out):
    return json.loads((out / 'ledger.json').read_text(encoding='utf-8'))


def test_a_failed_stage_is_rerun_alone_and_the_completed_ones_are_kept(tmp_path):
    p = speed_packet(tmp_path); out = tmp_path / 'out'
    with pytest.raises(RuntimeError):
        g.run(p, out, invoke=model([], fail={'repair-1'}, wrong_once=True))
    assert ledger(out)['stages']['repair-1']['status'] == 'failed'
    with pytest.raises(ValueError, match='자동 재실행하지 않습니다'):  # without the operator's reason nothing reruns
        g.run(p, out, invoke=model([], wrong_once=True))
    second = []
    result = g.run(p, out, invoke=model(second, wrong_once=True), resume=REASON)
    assert second[0] == 'repair-1' and not {'normalize', 'generate', 'context-0', 'source-0', 'medical-0'} & set(second)
    rows = result['manifest']['stageResumes']
    assert [s['name'] for s in rows[0]['superseded']] == ['repair-1'] and rows[0]['reason'] == REASON
    assert (out / '.resume-1' / 'ledger-before.json').exists() and (out / '.resume-1' / 'repair-1.input.json').exists()
    assert result['manifest']['repairRounds'] == 1  # the same round 1, not a new one
    c.validate_result(result, p)
    bad = copy.deepcopy(result); bad['manifest']['stageResumes'][0]['superseded'][0]['entry']['status'] = 'completed'
    with pytest.raises(ValueError):
        c.validate_result(bad, p)


def test_after_a_code_change_kept_stages_are_reused_without_model_calls(tmp_path, monkeypatch):
    p = speed_packet(tmp_path); out = tmp_path / 'out'
    with pytest.raises(RuntimeError):
        g.run(p, out, invoke=model([], fail={'medical-0'}))
    monkeypatch.setattr(g, 'identity', lambda packet, m: 'f' * 64)  # a new runtime
    with pytest.raises(ValueError, match='--resume'):
        g.run(p, out, invoke=model([]))
    calls = []
    result = g.run(p, out, invoke=model(calls), resume=REASON)
    assert calls == ['medical-0'] and result['manifest']['runtimeHash'] == 'f' * 64
    assert result['manifest']['stageResumes'][0]['priorLedger']['identity'] != 'f' * 64
    c.validate_result(result, p)


def test_a_kept_stage_the_current_acceptance_rejects_is_rerun(tmp_path, monkeypatch):
    """26110901 generation-4: context stages written before clinical-context/2 lack the problem kind."""
    p = speed_packet(tmp_path); out = tmp_path / 'out'
    with monkeypatch.context() as old:  # the acceptance before clinical-context/2
        old.setattr(c, 'CONTEXT_OUTPUT', c.CONTEXT); old.setattr(c, 'validate_context', lambda v: v)
        with pytest.raises(RuntimeError):
            g.run(p, out, invoke=model([], fail={'medical-0'}, legacy_context=True))
    calls = []
    result = g.run(p, out, invoke=model(calls), resume=REASON)
    assert calls[0] == 'context-0' and 'source-0' not in calls and 'generate' not in calls
    assert {s['name'] for s in result['manifest']['stageResumes'][0]['superseded']} == {'context-0', 'medical-0'}
    c.validate_result(result, p)


def test_resume_refuses_finished_runs_and_runs_with_other_recoveries(tmp_path):
    p = speed_packet(tmp_path); out = tmp_path / 'out'
    g.run(p, out, invoke=model([]))
    with pytest.raises(ValueError, match='완료된 실행'):
        g.run(p, out, invoke=model([]), resume=REASON)
    calls = []  # a finished run reopens only for a named stage; its result is archived, not deleted
    again = g.run(p, out, invoke=model(calls), resume=REASON, rerun=('source-0',))
    assert sorted(calls) == ['source-0'] and (out / '.resume-1' / 'result.json').exists()
    c.validate_result(again, p)
    other = tmp_path / 'other'
    with pytest.raises(RuntimeError):
        g.run(p, other, invoke=model([], fail={'source-0'}))
    value = ledger(other); value['renderRecoveries'] = [{'proof': {}}]
    (other / 'ledger.json').write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='다른 복구 기록'):
        g.run(p, other, invoke=model([]), resume=REASON)


def test_a_named_completed_review_is_rerun_and_unchanged_stages_stay(tmp_path):
    """26110901: the final source review is run again after its instructions changed (연결 목표 중요도)."""
    p = speed_packet(tmp_path); out = tmp_path / 'out'
    with pytest.raises(RuntimeError):
        g.run(p, out, invoke=model([], fail={'medical-0'}))
    with pytest.raises(ValueError, match='완료된 단계'):
        g.run(p, out, invoke=model([]), resume=REASON, rerun=('repair-1',))
    calls = []
    result = g.run(p, out, invoke=model(calls), resume=REASON, rerun=('source-0',))
    assert sorted(calls) == ['medical-0', 'source-0']  # nothing else is called again
    assert {s['name'] for s in result['manifest']['stageResumes'][-1]['superseded']} == {'source-0', 'medical-0'}
    c.validate_result(result, p)
