"""New-run policies (2026-11-09 사용자 설계 결정, docs/changes/2026-11-09-main-quiz-runner-pipeline).

initial-correction-separate/1 (「따로 세기」): fixing the initial map during the first authoring is not a repair
round; the three repairs are always for repairs. review-retry/1 (「새 세션 1회 자동」): a source review that
judged nothing, or a final source review that left the clinical projection unknown, runs once more in a
fresh session; the abandoned stage is archived, never deleted, and the repair budget does not change.
Ledgers recorded before these policies keep the old rules, also when resumed."""
import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from quizbank import connection_generate_v2 as g2
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash

REASON = 'test: resume after an interrupted call'


def invalid_map(value):
    value['prerequisites'] = [{'before_target': 'missing', 'after_target': 'T1', 'relation_id': 'R1'}]
    return value


def corrected(value):
    value['brief']['prerequisites'] = []; value['brief']['provenance']['independent_points'] = 'derived'
    value['map_change_reason'] = 'Synthetic invalid prerequisite corrected; original source scope preserved'
    return value


def unperformed(value):
    """26110901 source-2: every verdict doubt, every check unknown, no direction evidence."""
    for r in value['question_reviews']: r.update(verdict='doubt', suggested_answer='')
    for key in ('direction_checks', 'relation_checks', 'target_checks'):
        for r in value[key]: r['status'] = 'unknown'
    value['direction_evidence'] = []
    return value


def speed_packet(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); p['speedStages'] = True; p['inputHash'] = packet_hash(p)
    return p


def model(calls, *, initial_error=False, always_wrong=False, empty=(), unknown=(), crash=()):
    """empty/unknown: stage names (with repeats) whose next answers are unperformed / clinical unknown."""
    empty = list(empty); unknown = list(unknown)

    def invoke(stage, ctx, *args):
        calls.append(stage)
        if stage in crash:
            crash.remove(stage) if isinstance(crash, list) else None
            raise RuntimeError('synthetic crash in ' + stage)
        if stage.startswith('context-'):
            return {'clinical_context_status': 'consistent', 'clinical_context_reason': 'synthetic',
                    'clinical_context_problem': 'none'}, {}
        value, info = f.model(stage, ctx, *args)
        if stage == 'normalize' and initial_error: invalid_map(value)
        if stage == 'generate' and initial_error: corrected(value)
        if stage.startswith('medical-') and always_wrong: value['reviews'][0]['verdict'] = 'wrong'
        if stage in empty: empty.remove(stage); unperformed(value)
        if stage in unknown:
            unknown.remove(stage)
            value.update(clinical_context_status='unknown', clinical_context_reason='No direct evidence that every PNG was compared')
        return value, info
    return invoke


def ledger(out):
    return json.loads((out / 'ledger.json').read_text(encoding='utf-8'))


# --- initial-correction-separate/1 -------------------------------------------------------------

def test_new_runs_record_both_policies():
    assert g2.RUN_POLICIES == ['initial-correction-separate/1', 'review-retry/1'] == list(c.RUN_POLICIES)


def test_initial_correction_no_longer_consumes_a_repair_round(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); calls = []
    r = g.run(p, tmp_path / 'out', invoke=model(calls, initial_error=True, always_wrong=True))
    assert [s for s in calls if s.startswith('repair-')] == ['repair-1', 'repair-2', 'repair-3']
    m = r['manifest']
    assert m['repairRounds'] == 3 and m['runPolicies'] == c.RUN_POLICIES
    assert m['initialMapCorrection'] == {'errors': c.brief_findings(m['initialBrief']), 'consumedRounds': 0} and m['initialMapCorrection']['errors']
    c.validate_result(json.loads(json.dumps(r)), p)


def test_policy_and_charge_must_agree(tmp_path):
    p = f.packet(tmp_path / 'source.txt')
    r = g.run(p, tmp_path / 'out', invoke=model([], initial_error=True))
    assert r['manifest']['repairRounds'] == 0
    charged = copy.deepcopy(r); charged['manifest']['initialMapCorrection']['consumedRounds'] = 1
    with pytest.raises(ValueError): c.validate_result(charged, p)
    legacy = copy.deepcopy(r); del legacy['manifest']['runPolicies']
    with pytest.raises(ValueError): c.validate_result(legacy, p)
    other = copy.deepcopy(r); other['manifest']['runPolicies'] = ['review-retry/1']
    with pytest.raises(ValueError): c.validate_result(other, p)


def test_recorded_legacy_ledger_keeps_the_shared_budget_when_resumed(tmp_path, monkeypatch):
    p = f.packet(tmp_path / 'source.txt'); out = tmp_path / 'out'; calls = []
    monkeypatch.setattr(g2, 'RUN_POLICIES', [])  # a ledger written before the policies
    with pytest.raises(RuntimeError):
        g.run(p, out, invoke=model(calls, initial_error=True, always_wrong=True, crash=['repair-1']))
    assert 'runPolicies' not in ledger(out) and ledger(out)['repairRounds'] == 2
    monkeypatch.undo()
    r = g.run(p, out, invoke=model(calls, initial_error=True, always_wrong=True), resume=REASON)
    assert 'repair-3' not in calls and r['manifest']['repairRounds'] == 3 and 'runPolicies' not in r['manifest']
    assert r['manifest']['initialMapCorrection']['consumedRounds'] == 1
    c.validate_result(json.loads(json.dumps(r)), p)


# --- review-retry/1 ----------------------------------------------------------------------------

def test_a_review_that_judged_nothing_runs_once_more_in_a_fresh_session(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); out = tmp_path / 'out'; calls = []
    r = g.run(p, out, invoke=model(calls, empty=['source-0']))
    assert calls.count('source-0') == 2 and r['manifest']['repairRounds'] == 0
    [row] = r['manifest']['reviewRetries']
    assert row['stage'] == 'source-0' and row['kind'] == 'empty-judgment' and row['abandoned']['status'] == 'failed'
    archive = out / '.retry-source-0'
    assert (archive / 'source-0.raw.json').exists() and set(row['files']) <= {p.name for p in archive.iterdir()}
    assert json.loads((archive / 'source-0.raw.json').read_text(encoding='utf-8'))['assessment']['direction_evidence'] == []
    c.validate_result(json.loads(json.dumps(r)), p)
    assert g.run(p, out, invoke=lambda *a: pytest.fail('no replay')) == r


def test_a_second_empty_review_stops_and_is_not_retried_again(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); out = tmp_path / 'out'; calls = []
    with pytest.raises(ValueError, match='judged nothing'):
        g.run(p, out, invoke=model(calls, empty=['source-0', 'source-0']))
    assert calls.count('source-0') == 2 and 'medical-0' not in calls  # without context stages source runs first
    assert ledger(out)['stages']['source-0']['status'] == 'failed' and len(ledger(out)['reviewRetries']) == 1
    with pytest.raises(ValueError, match='중단/실패'):
        g.run(p, out, invoke=lambda *a: pytest.fail('no automatic third attempt'))


def test_a_final_clinical_unknown_runs_the_final_source_review_once_more(tmp_path):
    p = speed_packet(tmp_path); out = tmp_path / 'out'; calls = []
    r = g.run(p, out, invoke=model(calls, unknown=['source-0']))
    assert calls.count('source-0') == 2 and calls.count('medical-0') == 1
    [row] = r['manifest']['reviewRetries']
    assert row['kind'] == 'final-context-unknown' and row['abandoned']['status'] == 'completed'
    assert (out / '.retry-source-0' / 'source-0.json').exists()
    c.validate_result(json.loads(json.dumps(r)), p)


def test_a_second_final_clinical_unknown_stops_with_a_clear_reason(tmp_path):
    p = speed_packet(tmp_path); out = tmp_path / 'out'; calls = []
    with pytest.raises(ValueError, match='두 번'):
        g.run(p, out, invoke=model(calls, unknown=['source-0', 'source-0']))
    assert calls.count('source-0') == 2 and not (out / 'result.json').exists()


def test_retry_history_combines_with_a_later_operator_resume(tmp_path):
    p = speed_packet(tmp_path); out = tmp_path / 'out'; calls = []
    with pytest.raises(RuntimeError):
        g.run(p, out, invoke=model(calls, empty=['source-0'], crash=['medical-0']))
    assert len(ledger(out)['reviewRetries']) == 1
    r = g.run(p, out, invoke=model(calls), resume=REASON)
    assert calls.count('source-0') == 2 and r['manifest']['stageResumes'] and r['manifest']['reviewRetries']
    c.validate_result(json.loads(json.dumps(r)), p)


@pytest.mark.parametrize('change', ['twice', 'unpolicied', 'kind', 'input', 'same-raw'])
def test_retry_history_is_checked(tmp_path, change):
    p = f.packet(tmp_path / 'source.txt')
    r = g.run(p, tmp_path / 'out', invoke=model([], empty=['source-0']))
    bad = copy.deepcopy(r); rows = bad['manifest']['reviewRetries']
    stage = next(s for s in bad['manifest']['stages'] if s['name'] == 'source-0')
    if change == 'twice': rows.append(copy.deepcopy(rows[0]))
    elif change == 'unpolicied': bad['manifest']['runPolicies'] = ['initial-correction-separate/1']
    elif change == 'kind': rows[0]['kind'] = 'more-doubts'
    elif change == 'input': rows[0]['abandoned']['inputHash'] = '1' * 64
    else: rows[0]['abandoned']['rawOutputHash'] = stage['rawOutputHash']
    with pytest.raises(ValueError): c.validate_result(bad, p)


def test_new_policy_runs_do_not_take_manual_recovery_histories(tmp_path):
    p = f.packet(tmp_path / 'source.txt')
    r = g.run(p, tmp_path / 'out', invoke=model([]))
    for key in ('medicalRetries', 'formatRecoveries', 'runtimeRevalidations', 'normalizationRecoveries'):
        bad = copy.deepcopy(r); bad['manifest'][key] = [{'proof': {}, 'proofHash': '0' * 64}]
        with pytest.raises(ValueError): c.validate_result(bad, p)


def test_manual_recovery_tools_refuse_new_policy_ledgers(tmp_path):
    p = f.packet(tmp_path / 'source.txt'); out = tmp_path / 'out'
    g.run(p, out, invoke=model([]))
    with pytest.raises(ValueError, match='review-retry/1|initial-correction-separate/1'):
        c.require_legacy_ledger(ledger(out))
    c.require_legacy_ledger({'repairRounds': 1, 'stages': {}})
