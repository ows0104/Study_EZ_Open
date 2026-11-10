"""Review/fix batches side by side (docs/changes/2026-11-11-root-batch-parallel/spec.md).

The synthetic /4 lecture of test_root_generation_v4 with one question per batch: Q1, Q2 and the added Q003
are three batches, so the batches really run beside each other."""
import copy
import json
import random
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_root_generation_v4 as t4
from quizbank import connection_batches as batches
from quizbank import connection_generate as g
from quizbank import connection_generate_v3 as g3
from quizbank import connection_generate_v4 as g4
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots.automation import packet_hash, validate_result as consume


@pytest.fixture(autouse=True)
def one_question_per_batch(monkeypatch):
    monkeypatch.setattr(g4, 'REVIEW_BATCH', 1)
    monkeypatch.setattr(g3, 'MEDICAL_BATCH', 1)


class Timed(t4.Model):
    """The synthetic model with a delay per call, a record of how many calls ran at once, and optional
    failures and conflicts written by fixes."""

    def __init__(self, seed=None, fail=(), new_conflict=None, **kw):
        super().__init__(**kw)
        self.rng = random.Random(seed)
        self.lock, self.running, self.most = threading.Lock(), 0, 0
        self.batch_running = self.batch_most = 0
        self.fail, self.new_conflict = set(fail), new_conflict

    def __call__(self, stage, ctx, material, model):
        batch = stage.startswith(('v4-review', 'v4-fix', 'v4-coverage-fix'))
        with self.lock:
            self.running += 1
            self.most = max(self.most, self.running)
            self.batch_running += batch
            self.batch_most = max(self.batch_most, self.batch_running)
            delay = self.rng.uniform(0, 0.05) if self.rng else 0
        try:
            time.sleep(delay)
            if stage in self.fail:
                self.fail.discard(stage)
                raise RuntimeError('synthetic transport failure: ' + stage)
            value, info = super().__call__(stage, ctx, material, model)
            if stage.startswith('v4-fix') and self.new_conflict:
                value = self.new_conflict(stage, ctx, value)
            return value, info
        finally:
            with self.lock:
                self.running -= 1
                self.batch_running -= batch


def run(tmp_path, model, resume=None, packet=None):
    tmp_path.mkdir(exist_ok=True)
    p = packet or t4.packet(tmp_path)
    return p, g.run(p, tmp_path / 'out', invoke=model, resume=resume)


def ledger(tmp_path):
    return json.loads((tmp_path / 'out' / 'ledger.json').read_text(encoding='utf-8'))


def comparable(result):
    value = copy.deepcopy(result)
    value['manifest'].pop('batchPhases', None)
    value['validation'].pop('checked_at', None)
    value['medical'].pop('reviewed_at', None)   # the time of the medical review
    return value


def sequential(monkeypatch):
    monkeypatch.setattr(g3.Stages, 'parallel', property(lambda self: False))


def test_batches_run_side_by_side_and_give_the_one_after_another_result(tmp_path, monkeypatch):
    model = Timed(seed=1, design_doubt=('Q1', 'Q2', 'Q003'))
    p, result = run(tmp_path / 'a', model)
    assert consume(result, p) == result['document']
    assert model.batch_most >= 2
    phases = {r['phase']: r for r in result['manifest']['batchPhases']}
    assert phases['item-review'] == {'phase': 'item-review', 'mode': 'parallel', 'batches': 3, 'reasons': []}
    assert [f['question_id'] for f in result['manifest']['fixes']] == ['Q1', 'Q2', 'Q003']
    # every fix input names its batch's prefix
    scopes = {s: c['conflict_scope']['new_conflict_id_prefix'] for s, c in model.inputs.items() if s.startswith('v4-fix')}
    assert scopes == {'v4-fix-0-0': 'CF-B1-', 'v4-fix-1-0': 'CF-B2-', 'v4-fix-2-0': 'CF-B3-'}

    sequential(monkeypatch)
    one = Timed(seed=1, design_doubt=('Q1', 'Q2', 'Q003'))
    _, before = run(tmp_path / 'b', one)
    assert 'batchPhases' not in before['manifest']
    assert not any('conflict_scope' in c for s, c in one.inputs.items() if s.startswith('v4-fix'))
    # Stage records differ only by the fix inputs' conflict scope (and the medical review's time); the result is the same.
    differs = [s['name'] for s, t in zip(result['manifest']['stages'], before['manifest']['stages']) if s != t]
    assert differs == ['v4-fix-0-0', 'v4-fix-1-0', 'v4-fix-2-0', 'medical-0']
    a, b = comparable(result), comparable(before)
    for m in (a['manifest'], b['manifest']):
        m['stages'] = [s['name'] for s in m['stages']]
        m.pop('runtimeHash')
    assert a == b


def test_the_finishing_order_does_not_change_the_result_or_the_ledger(tmp_path):
    results, orders = [], []
    for seed in (2, 3, 4):
        model = Timed(seed=seed, design_doubt=('Q1', 'Q2', 'Q003'))
        _, result = run(tmp_path / str(seed), model)
        results.append(comparable(result))
        orders.append(list(ledger(tmp_path / str(seed))['stages']))
    assert orders[0] == orders[1] == orders[2]
    assert orders[0].index('v4-review-0-0') < orders[0].index('v4-review-1-0') < orders[0].index('v4-review-2-0')
    assert results[0]['document'] == results[1]['document'] == results[2]['document']
    assert results[0]['manifest']['verdictLedger'] == results[1]['manifest']['verdictLedger'] == results[2]['manifest']['verdictLedger']


def test_a_failed_batch_lets_the_others_finish_and_a_resume_reuses_them(tmp_path):
    model = Timed(seed=5, design_doubt=('Q1', 'Q2', 'Q003'), fail={'v4-fix-1-0'})
    with pytest.raises(RuntimeError, match='v4-fix-1-0'):
        run(tmp_path, model)
    stages = ledger(tmp_path)['stages']
    assert stages['v4-fix-1-0']['status'] == 'failed'
    assert all(stages[n]['status'] == 'completed' for n in ('v4-fix-0-0', 'v4-coverage-fix-0-0', 'v4-fix-2-0', 'v4-coverage-fix-2-0'))
    again = Timed(seed=6, design_doubt=('Q1', 'Q2', 'Q003'))
    p = json.loads((tmp_path / 'out' / 'packet.json').read_text(encoding='utf-8')) if (tmp_path / 'out' / 'packet.json').exists() else None
    _, result = run(tmp_path, again, resume='synthetic transport failure', packet=p or t4.packet(tmp_path))
    assert consume(result, p or t4.packet(tmp_path)) == result['document']
    asked = set(again.calls)
    assert not asked & {'v4-review-0-0', 'v4-fix-0-0', 'v4-fix-2-0', 'v4-coverage-fix-0-0', 'normalize'}
    assert 'v4-fix-1-0' in asked
    assert [f['question_id'] for f in result['manifest']['fixes']] == ['Q1', 'Q2', 'Q003']


def test_batches_joined_by_a_prerequisite_run_one_after_another(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    p = t4.packet(tmp_path)
    p['intakeBank']['bank']['questions'][1]['prerequisites'] = ['Q1']
    p['inputHash'] = packet_hash(p)
    model = Timed(seed=None, design_doubt=('Q1', 'Q2'))
    model.rng = None
    _, result = run(tmp_path, model, packet=p)
    phase = {r['phase']: r for r in result['manifest']['batchPhases']}['item-review']
    assert phase['mode'] == 'sequential' and phase['reasons'] == ['묶음을 넘는 선행 연결: Q2→Q1']
    assert not any('conflict_scope' in c for s, c in model.inputs.items() if s.startswith('v4-fix'))
    assert model.batch_most == 1


def test_a_duplicate_partner_changed_in_another_batch_is_judged_again(tmp_path):
    model = Timed(seed=7, duplicate=True, design_doubt=('Q1', 'Q2'))
    p, result = run(tmp_path, model)
    assert consume(result, p) == result['document']
    assert 'v4-coverage-merge-0' in model.calls
    judged = {q['question_id'] for q in model.inputs['v4-coverage-merge-0']['questions']}
    assert judged == {'Q1', 'Q2'}
    assert t4.tasks(result) == [('Q003', 'D2'), ('Q1', 'D1')]


def test_each_batch_writes_new_conflicts_under_its_own_prefix(tmp_path):
    def conflict(stage, ctx, value):
        scope = ctx['conflict_scope']
        cid = scope['new_conflict_id_prefix'] + '01'
        q = value['questions'][0]
        q['conflict_id'] = cid
        value['source_conflicts'] = [{'conflict_id': cid, 'description': 'Synthetic lecture vs current answer',
                                      'source_refs': [{'source_id': 'S1', 'locator': 'synthetic paragraph'}], 'unresolved': False}]
        value['clinical_conflicts'] = [{'conflict_id': cid, 'facts': 'Synthetic facts ' + stage}]
        return value
    model = Timed(seed=8, design_doubt=('Q1', 'Q2'), new_conflict=conflict)
    p, result = run(tmp_path, model)
    assert consume(result, p) == result['document']
    ids = [c['conflict_id'] for c in result['manifest']['clinicalConflicts']]
    assert ids == ['CF-B1-01', 'CF-B2-01']


def test_the_conflict_scope_check():
    scope = {'new_conflict_id_prefix': 'CF-B2-', 'own_conflict_ids': ['CF01'], 'known_conflict_ids': ['CF01', 'CF02']}
    q = {'question_id': 'Q2', 'conflict_id': 'CF-B2-01'}
    ok = {'questions': [q], 'source_conflicts': [{'conflict_id': 'CF-B2-01'}], 'clinical_conflicts': [{'conflict_id': 'CF-B2-01'}]}
    v3.check_conflict_scope(ok, scope)
    with pytest.raises(ValueError, match='starts with CF-B2-'):
        v3.check_conflict_scope({**ok, 'source_conflicts': [{'conflict_id': 'CF03'}]}, scope)
    other = {'questions': [{'question_id': 'Q2', 'conflict_id': 'CF02'}], 'source_conflicts': [], 'clinical_conflicts': [{'conflict_id': 'CF02'}]}
    with pytest.raises(ValueError, match='CF02 belongs to another batch'):
        v3.check_conflict_scope(other, scope)
    own = {'questions': [{'question_id': 'Q2', 'conflict_id': 'CF01'}], 'source_conflicts': [], 'clinical_conflicts': [{'conflict_id': 'CF01'}]}
    v3.check_conflict_scope(own, scope)
    # citing another batch's conflict without writing its facts is allowed
    v3.check_conflict_scope({**other, 'clinical_conflicts': []}, scope)


def test_a_ledger_from_before_runs_its_batches_one_after_another(tmp_path):
    model = Timed(seed=9, design_doubt=('Q1', 'Q2'), fail={'normalize'})
    with pytest.raises(RuntimeError):
        run(tmp_path, model)
    path = tmp_path / 'out' / 'ledger.json'
    old = json.loads(path.read_text(encoding='utf-8'))
    old.pop('batchMode')
    path.write_text(json.dumps(old, ensure_ascii=False), encoding='utf-8')
    again = Timed(seed=10, design_doubt=('Q1', 'Q2'))
    p, result = run(tmp_path, again, resume='before the batch change')
    assert consume(result, p) == result['document']
    assert 'batchPhases' not in result['manifest'] and 'batchMode' not in ledger(tmp_path)
    assert not any('conflict_scope' in c for s, c in again.inputs.items() if s.startswith('v4-fix'))
    assert again.most == 1


def test_parallel_calls_run_everything_and_raise_the_first_failure_in_order():
    done = []

    def ok(n):
        time.sleep(0.01 * (3 - n))
        done.append(n)
        return n

    def bad(n):
        raise RuntimeError(str(n))
    assert batches.parallel_calls([lambda n=n: ok(n) for n in range(3)]) == [0, 1, 2]
    done.clear()
    with pytest.raises(RuntimeError, match='1'):
        batches.parallel_calls([lambda: ok(0), lambda: bad(1), lambda: bad(2), lambda: ok(2)], workers=4)
    assert sorted(done) == [0, 2]
