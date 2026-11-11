"""Front stages that no longer stop a lecture for what one call can put right (docs/changes/2026-11-11-pipeline-resilience).

Synthetic PDFs and a fake Codex call (tests/contracts/map_tree_fixture, test_root_front_v3). No model, server or DB."""
import hashlib
import json
import sys
import threading
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'quizbank'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import root_front as rf
from studyez_llm import codex
from map_tree_fixture import concept_map
import test_root_front_v3 as t

DROP = 'Synthetic lecture point extraction: Reconnecting... 5/5 (stream disconnected before completion: No such host is known. (os error 11001))'


def receipt(path):
    return json.dumps({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})


def front(tmp_path, call, **kwargs):
    tmp_path.mkdir(exist_ok=True)
    f = rf.Front(t.server_packet(tmp_path), tmp_path / 'front', invoke=call, **kwargs)
    f.followups = True
    f.wait_network = lambda: True
    return f


def state(tmp_path, stage):
    return json.loads((tmp_path / 'front' / stage / 'state.json').read_text(encoding='utf-8'))


# ------------------------------------------------------------------ a refused result goes back into the same session

def refusing(calls, stage, spoil, mend=True, session=None):
    """front_codex whose `stage` result fails its host check; the follow-up in the same session writes a good one."""
    run = t.front_codex(calls)

    def call(task, *, cwd, label, **rest):
        work = Path(cwd)
        if work.name != stage:
            return run(task, cwd=cwd, label=label, **rest)
        if 'resume' in rest:
            calls.append((stage + ':followup', task))
            assert rest['resume'] == 'session-' + stage and rest['previous_usage'] == {'input_tokens': 1}
            name = spoil(work, undo=mend)
            return {'text': receipt(work / name), 'session_id': session or 'session-' + stage, 'duration_ms': 5, 'usage': {'input_tokens': 2}}
        info = run(task, cwd=cwd, label=label, **rest)
        name = spoil(work)
        return {**info, 'text': receipt(work / name)}
    return call


def spoil_map(work, undo=False):
    value = concept_map()
    if not undo:
        value['concepts'].append(value['concepts'][0])
    (work / 'concept-map.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return 'concept-map.json'


def spoil_bank(work, undo=False):
    value = t.bank_value()
    if not undo:   # an error of no single question: the generator's intake stops the whole lecture on it
        value['bank']['concepts'].append(dict(value['bank']['concepts'][0]))
    (work / 'bank.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return 'bank.json'


def test_a_refused_map_is_corrected_in_the_same_session(tmp_path):
    calls = []
    derived = front(tmp_path, refusing(calls, 'map', spoil_map)).run()
    names = [s for s, _ in calls]
    assert names.count('map') == 1 and names.count('map:followup') == 1
    followup = next(task for s, task in calls if s == 'map:followup')
    assert 'duplicate ID' in followup and 'concept-map.json' in followup
    assert json.loads(derived['conceptMap']) == concept_map()
    row = state(tmp_path, 'map')
    assert row['status'] == 'completed' and 'duplicate ID' in row['followup']['error']
    assert row['usage'] == {'input_tokens': 3} and row['duration_ms'] == 8   # both calls of the one session
    work = tmp_path / 'front' / 'map'
    refused = json.loads((work / 'refused-concept-map.json').read_text(encoding='utf-8'))
    assert len(refused['concepts']) == len(concept_map()['concepts']) + 1   # the refused bytes are kept
    assert hashlib.sha256((work / 'refused-concept-map.json').read_bytes()).hexdigest() == row['followup']['refusedSha256']
    # The server sees a normal completed stage: the derived packet's stage row has no new key.
    assert set(derived['frontStages']['stages']['map']) == {'inputHash', 'outputSha256', 'sessionId', 'model', 'durationMs'}


def test_a_second_refusal_is_recorded_as_failed(tmp_path):
    calls = []
    with pytest.raises(ValueError, match='duplicate ID'):
        front(tmp_path, refusing(calls, 'map', spoil_map, mend=False)).run()
    assert [s for s, _ in calls].count('map:followup') == 1   # once, not a loop
    assert state(tmp_path, 'map')['status'] == 'failed' and (tmp_path / 'front' / 'map' / 'failure.json').exists()


def test_a_followup_must_continue_the_same_session(tmp_path):
    with pytest.raises(ValueError, match='same session'):
        front(tmp_path, refusing([], 'map', spoil_map, session='another-session')).run()
    assert state(tmp_path, 'map')['status'] == 'failed'


def test_a_bank_the_intake_would_stop_on_is_corrected_by_its_author(tmp_path):
    calls = []
    derived = front(tmp_path, refusing(calls, 'bank', spoil_bank)).run()
    followup = next(task for s, task in calls if s == 'bank:followup')
    assert '문제은행 형식 오류가 특정 문항에 속하지 않습니다' in followup and 'concepts: ID/값 중복' in followup
    assert derived['intakeBank'] == t.bank_value() and 'followup' in state(tmp_path, 'bank')


def test_without_followups_a_bank_level_error_stops_at_the_front_not_twenty_minutes_later(tmp_path):
    f = front(tmp_path, refusing([], 'bank', spoil_bank))
    f.followups = False
    with pytest.raises(ValueError, match='concepts: ID/값 중복'):
        f.run()
    assert state(tmp_path, 'bank')['status'] == 'failed'


# ------------------------------------------------------------------ a call the network dropped runs once more

def dropping(calls, stage, times=1):
    run = t.front_codex(calls)
    left = [times]

    def call(task, *, cwd, label, **rest):
        if Path(cwd).name == stage and left[0]:
            left[0] -= 1
            calls.append((stage + ':dropped', task))
            (Path(cwd) / 'draft-points.txt').write_text('half written', encoding='utf-8')
            raise codex.SessionError(DROP)
        return run(task, cwd=cwd, label=label, **rest)
    return call


def test_a_dropped_call_waits_for_the_network_and_runs_once_more(tmp_path):
    calls, waited = [], []
    f = front(tmp_path, dropping(calls, 'point'))
    f.wait_network = lambda: waited.append(1) or True
    derived = f.run()
    names = [s for s, _ in calls]
    assert names.count('point:dropped') == 1 and names.count('point') == 1 and waited == [1]
    row = state(tmp_path, 'point')
    assert row['status'] == 'completed' and row['transportRetries'][0]['policy'] == 'transport-retry/1'
    kept = tmp_path / 'front' / row['transportRetries'][0]['kept']
    assert (kept / 'draft-points.txt').read_text(encoding='utf-8') == 'half written' and 'No such host' in (kept / 'error.txt').read_text(encoding='utf-8')
    assert not (tmp_path / 'front' / 'point' / 'draft-points.txt').exists()   # the second call starts from the inputs alone
    assert derived['frontStages']['resumes'] == []                             # not an operator resume


def test_a_second_drop_or_a_network_that_stays_down_stops_as_before(tmp_path):
    with pytest.raises(codex.SessionError):
        front(tmp_path / 'twice', dropping([], 'point', times=2)).run()
    assert state(tmp_path / 'twice', 'point')['status'] == 'failed'
    calls = []
    f = front(tmp_path / 'down', dropping(calls, 'point'))
    f.wait_network = lambda: False
    with pytest.raises(codex.SessionError):
        f.run()
    assert [s for s, _ in calls].count('point') == 0 and state(tmp_path / 'down', 'point')['status'] == 'failed'


def test_other_failures_are_still_never_run_again(tmp_path):
    calls = []
    run = t.front_codex(calls)

    def call(task, *, cwd, label, **rest):
        if Path(cwd).name == 'point':
            calls.append(('point:failed', task))
            raise codex.SessionError('point: 2400초 안에 끝나지 않았다')
        return run(task, cwd=cwd, label=label, **rest)
    with pytest.raises(codex.SessionError):
        front(tmp_path, call).run()
    assert [s for s, _ in calls].count('point:failed') == 1 and state(tmp_path, 'point')['status'] == 'failed'


# ------------------------------------------------------------------ the audit no longer waits for the bank

def test_the_audit_runs_beside_the_bank(tmp_path):
    calls, audit_started = [], threading.Event()
    run = t.front_codex(calls)
    seen = {}

    def call(task, *, cwd, label, **rest):
        stage = Path(cwd).name
        if stage == 'audit':
            audit_started.set()
        if stage == 'bank':
            seen['audit_before_bank_ended'] = audit_started.wait(20)
        return run(task, cwd=cwd, label=label, **rest)
    derived = front(tmp_path, call).run()
    assert seen['audit_before_bank_ended'] is True
    assert list(derived['frontStages']['stages']) == ['map', 'point', 'bank', 'audit']   # the record keeps its order


def bank_cut(calls):
    run = t.front_codex(calls)

    def call(task, *, cwd, label, **rest):
        if Path(cwd).name == 'bank':
            calls.append(('bank', task))
            raise RuntimeError('synthetic interrupted bank call')
        return run(task, cwd=cwd, label=label, **rest)
    return call


def test_a_failed_bank_leaves_the_point_chain_completed_for_the_resume(tmp_path):
    p, calls = t.server_packet(tmp_path), []
    with pytest.raises(RuntimeError):
        rf.Front(p, tmp_path / 'front', invoke=bank_cut(calls)).run()
    assert state(tmp_path, 'audit')['status'] == 'completed' and state(tmp_path, 'map')['status'] == 'completed'
    again = []
    derived = rf.Front(p, tmp_path / 'front', invoke=t.front_codex(again), resume='admin: bank call was cut').run()
    assert [s for s, _ in again] == ['bank']   # only the bank runs again
    assert derived['frontStages']['resumes'] == [{'reason': 'admin: bank call was cut', 'stages': ['bank']}]


def test_a_rerun_point_stage_still_reruns_its_audit(tmp_path):
    p, calls = t.server_packet(tmp_path), []
    with pytest.raises(RuntimeError):
        rf.Front(p, tmp_path / 'front', invoke=bank_cut(calls)).run()
    (tmp_path / 'front' / 'point' / 'state.json').write_text(json.dumps({'status': 'failed', 'inputHashes': {}}), encoding='utf-8')
    again = []
    rf.Front(p, tmp_path / 'front', invoke=t.front_codex(again), resume='admin: point output was cut').run()
    assert sorted(s for s, _ in again) == ['audit', 'bank', 'point']   # the Map is kept
    assert sorted(x.name for x in (tmp_path / 'front' / '.resume-1').iterdir()) == ['audit', 'bank', 'point']
