"""Generation stages: a call the network dropped runs once more, more calls side by side
(docs/changes/2026-11-11-pipeline-resilience). The synthetic /4 model of test_root_generation_v4; no model, server or DB."""
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quizbank import connection_batches as batches
from quizbank import connection_generate_v4 as gen4
from studyez_llm import codex
import test_root_generation_v4 as t4

DROP = ('연결 파일 실행 v4-add-0: codex가 1로 끝났다\n{"type":"error","message":"stream disconnected before completion: '
        'error sending request for url (https://chatgpt.com/backend-api/codex/responses)"}')


class Dropping(t4.Model):
    """The synthetic model whose `stage` call is dropped by the network `times` times, leaving its seat behind."""

    def __init__(self, out, stage, times=1, error=DROP):
        super().__init__()
        self.out, self.stage, self.left, self.error, self.dropped = Path(out), stage, times, error, 0

    def __call__(self, stage, ctx, material, model):
        if stage == self.stage and self.left:
            self.left -= 1
            self.dropped += 1
            seat = self.out / '.native' / stage
            seat.mkdir(parents=True)   # as runner.root_native_json: one seat per call, never reused
            (seat / 'failure.json').write_text('{"errorType": "SessionError"}', encoding='utf-8')
            raise codex.SessionError(self.error)
        return super().__call__(stage, ctx, material, model)


def ledger(tmp_path):
    return json.loads((tmp_path / 'out' / 'ledger.json').read_text(encoding='utf-8'))


@pytest.fixture
def network(monkeypatch):
    waits = []
    monkeypatch.setattr(codex, 'wait_for_network', lambda: waits.append(1) or True)
    return waits


def test_a_dropped_stage_call_waits_and_runs_once_more(tmp_path, network):
    _, plain, expected = t4.run(tmp_path / 'plain')
    model = Dropping(tmp_path / 'again' / 'out', 'v4-add-0')
    _, _, result = t4.run(tmp_path / 'again', model)
    assert model.dropped == 1 and network == [1] and model.calls.count('v4-add-0') == 1
    assert result['document'] == expected['document']   # the same lecture as an undisturbed run
    row = ledger(tmp_path / 'again')
    assert row['transportRetries'] == [{'policy': 'transport-retry/1', 'stage': 'v4-add-0', 'error': DROP[-600:], 'kept': '.native/v4-add-0.net'}]
    assert row['stages']['v4-add-0']['status'] == 'completed' and row['addRounds'] == 1 and row['fixAttempts'] == {'Q1': 1}
    # The dropped call's diagnostics are kept beside the stage, and the result carries no new manifest key.
    assert (tmp_path / 'again' / 'out' / '.native' / 'v4-add-0.net' / 'failure.json').exists()
    assert set(result['manifest']) == set(expected['manifest'])
    assert [s['name'] for s in result['manifest']['stages']] == [s['name'] for s in expected['manifest']['stages']]


def test_a_stage_dropped_twice_stops_as_before(tmp_path, network):
    model = Dropping(tmp_path / 'out', 'v4-add-0', times=2)
    with pytest.raises(codex.SessionError):
        t4.run(tmp_path, model)
    row = ledger(tmp_path)
    assert model.dropped == 2 and len(row['transportRetries']) == 1 and row['stages']['v4-add-0']['status'] == 'failed'
    # Like any failed stage it continues only with the administrator's reason, and is not retried by itself then.
    with pytest.raises(ValueError, match='--resume'):
        t4.run(tmp_path, t4.Model())


def test_a_network_that_stays_down_stops_the_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(codex, 'wait_for_network', lambda: False)
    model = Dropping(tmp_path / 'out', 'v4-add-0')
    with pytest.raises(codex.SessionError):
        t4.run(tmp_path, model)
    assert model.calls.count('v4-add-0') == 0 and ledger(tmp_path)['stages']['v4-add-0']['status'] == 'failed'


@pytest.mark.parametrize('error', [
    'v4-add-0: 2400초 안에 끝나지 않았다',
    'v4-add-0: codex가 1로 끝났다\nYour account has limited access to this content for safety reasons',
    'v4-add-0: codex가 1로 끝났다\nYou have hit your usage limit. stream disconnected',
    'v4-add-0: codex 최종 응답이 비어 있다',
])
def test_a_time_limit_a_refusal_and_a_usage_limit_are_not_network_drops(tmp_path, network, error):
    model = Dropping(tmp_path / 'out', 'v4-add-0', error=error)
    with pytest.raises(codex.SessionError):
        t4.run(tmp_path, model)
    assert model.dropped == 1 and network == [] and 'transportRetries' not in ledger(tmp_path)


def test_a_check_failure_is_not_a_network_drop(tmp_path, network):
    class Wrong(t4.Model):
        def __call__(self, stage, ctx, material, model):
            if stage == 'v4-add-0':
                raise ValueError('stream disconnected is only text in a contract error')
            return super().__call__(stage, ctx, material, model)
    with pytest.raises(ValueError):
        t4.run(tmp_path, Wrong())
    assert network == [] and 'transportRetries' not in ledger(tmp_path)


# ------------------------------------------------------------------ side by side

def test_coverage_after_an_add_round_goes_through_the_side_by_side_judgments(tmp_path, monkeypatch):
    seen, real = [], batches.judgments

    def judgments(st, calls):
        seen.append([c[0] for c in calls])
        return real(st, calls)
    monkeypatch.setattr(batches, 'judgments', judgments)
    _, _, result = t4.run(tmp_path)
    assert ['v4-coverage-1-0'] in seen   # the add round's coverage chunks, with their unchanged names
    assert [s['name'] for s in result['manifest']['stages']][:5] == ['normalize', 'v4-coverage-0-0', 'v4-map-check-0', 'v4-add-0', 'v4-coverage-1-0']


def test_six_calls_run_side_by_side_and_the_ceiling_is_configurable(monkeypatch):
    import threading
    assert batches.BATCH_WORKERS == 6 and gen4.batches is batches
    monkeypatch.setenv(batches.WORKERS_ENV, '4'); assert batches._workers() == 4
    monkeypatch.setenv(batches.WORKERS_ENV, '99'); assert batches._workers() == 12
    monkeypatch.setenv(batches.WORKERS_ENV, '0'); assert batches._workers() == 1
    monkeypatch.setenv(batches.WORKERS_ENV, 'many'); assert batches._workers() == 6
    gate, lock, running, peak = threading.Barrier(6, timeout=20), threading.Lock(), [0], [0]

    def call(i):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        gate.wait()   # passes only when all six are inside at once
        with lock:
            running[0] -= 1
        return i
    assert batches.parallel_calls([lambda i=i: call(i) for i in range(6)]) == list(range(6)) and peak[0] == 6
