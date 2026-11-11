"""early-call/1: a stage whose input is already decided is called before its turn (docs/changes/2026-11-11-pipeline-overlap).

The synthetic /4 model of test_root_generation_v4; no model, server or DB."""
import json
import sys
import threading
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quizbank import connection_generate_v3 as gen3
from quizbank import connection_generate_v4 as gen4
from quizbank.connection_generate_v3 import Stages, early_path, write_early
import test_root_generation_v4 as t4


def ledger(tmp_path):
    return json.loads((tmp_path / 'out' / 'ledger.json').read_text(encoding='utf-8'))


def baseline(tmp_path):
    """An undisturbed run: its result and the normalize stage's input fingerprint, raw answer and usage."""
    _, _, result = t4.run(tmp_path)
    out = tmp_path / 'out'
    return result, ledger(tmp_path)['stages']['normalize']['inputHash'], json.loads((out / 'normalize.raw.json').read_text(encoding='utf-8')), \
        json.loads((out / 'normalize.usage.json').read_text(encoding='utf-8'))


# ------------------------------------------------------------------ an answer that came before the stage's turn

def test_an_early_answer_is_taken_at_the_stages_turn(tmp_path):
    expected, input_hash, raw, info = baseline(tmp_path / 'plain')
    out = tmp_path / 'early' / 'out'
    write_early(out, 'normalize', input_hash, raw, info)   # as the front stages leave it (Front.early_normalize)
    _, model, result = t4.run(tmp_path / 'early')
    assert 'normalize' not in model.calls and model.calls[0] != 'normalize'   # the model is not asked again
    assert result['document'] == expected['document'] and set(result['manifest']) == set(expected['manifest'])
    assert [s['name'] for s in result['manifest']['stages']] == [s['name'] for s in expected['manifest']['stages']]
    row = ledger(tmp_path / 'early')
    assert row['stages']['normalize'] == ledger(tmp_path / 'plain')['stages']['normalize']   # the same record as a call at its turn
    assert row['earlyCalls'] == [{'policy': 'early-call/1', 'stage': 'normalize', 'used': True}]
    assert not early_path(out, 'normalize').exists()


def test_an_early_answer_for_another_input_is_not_used(tmp_path):
    expected, input_hash, raw, info = baseline(tmp_path / 'plain')
    out = tmp_path / 'other' / 'out'
    write_early(out, 'normalize', 'f' * 64, {**raw, 'summary': 'an answer to other points'}, info)
    (out / '.native' / 'normalize').mkdir(parents=True)
    (out / '.native' / 'normalize' / 'receipt.json').write_text('{}', encoding='utf-8')
    _, model, result = t4.run(tmp_path / 'other')
    assert model.calls[0] == 'normalize' and result['document'] == expected['document']
    assert ledger(tmp_path / 'other')['earlyCalls'] == [{'policy': 'early-call/1', 'stage': 'normalize', 'used': False, 'kept': '.native/normalize.early'}]
    assert (out / '.native' / 'normalize.early' / 'receipt.json').exists() and not early_path(out, 'normalize').exists()


def test_an_early_call_that_failed_fails_the_stage_at_its_turn_and_is_not_repeated_by_itself(tmp_path):
    _, input_hash, _, _ = baseline(tmp_path / 'plain')
    out = tmp_path / 'failed' / 'out'
    write_early(out, 'normalize', input_hash, error=ValueError('연결 파일 실행 normalize: 2400초 안에 끝나지 않았다'))
    model = t4.Model()
    with pytest.raises(ValueError, match='2400초 안에 끝나지 않았다'):
        t4.run(tmp_path / 'failed', model)
    assert model.calls == [] and ledger(tmp_path / 'failed')['stages']['normalize']['status'] == 'failed'
    with pytest.raises(ValueError, match='--resume'):   # like any failed stage: only with the administrator's reason
        t4.run(tmp_path / 'failed', t4.Model())


def test_a_seat_left_by_an_early_call_that_never_finished_is_moved_out_of_the_way(tmp_path):
    out = tmp_path / 'out'
    (out / '.native' / 'normalize' / 'work').mkdir(parents=True)
    _, model, _ = t4.run(tmp_path)
    assert model.calls[0] == 'normalize' and (out / '.native' / 'normalize.early' / 'work').is_dir()
    assert ledger(tmp_path)['earlyCalls'] == [{'policy': 'early-call/1', 'stage': 'normalize', 'used': False, 'kept': '.native/normalize.early'}]


# ------------------------------------------------------------------ first reviews beside the add rounds

class Watching(t4.Model):
    """The synthetic model; the add stage does not return before the first review of batch 0 has begun."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.review_began, self.overlap = threading.Event(), None

    def __call__(self, stage, ctx, material, model):
        if stage == 'v4-review-0-0':
            self.materials = Path(material)
            self.review_began.set()
        if stage == 'v4-add-0':
            self.overlap = self.review_began.wait(20)
        return super().__call__(stage, ctx, material, model)


def test_the_first_review_of_a_full_intake_batch_runs_beside_the_add_round(tmp_path, monkeypatch):
    monkeypatch.setattr(gen4, 'REVIEW_BATCH', 2)   # the two intake questions fill batch 0; the added one is batch 1
    monkeypatch.setattr(Stages, 'start_early', lambda *a, **k: False)
    _, plain, expected = t4.run(tmp_path / 'plain')
    monkeypatch.undo()
    monkeypatch.setattr(gen4, 'REVIEW_BATCH', 2)
    model = Watching()
    _, _, result = t4.run(tmp_path / 'early', model)
    assert model.overlap is True                                    # the review had begun before the add stage returned
    assert model.calls.count('v4-review-0-0') == 1 and sorted(model.calls) == sorted(plain.calls)   # the same calls, once each
    assert result['document'] == expected['document']
    assert [s['name'] for s in result['manifest']['stages']] == [s['name'] for s in expected['manifest']['stages']]
    assert {k: v for k, v in result['manifest'].items() if k not in ('stages', 'runtimeHash')} == \
        {k: v for k, v in expected['manifest'].items() if k not in ('stages', 'runtimeHash')}
    row = ledger(tmp_path / 'early')
    assert {'policy': 'early-call/1', 'stage': 'v4-review-0-0', 'used': True} in row['earlyCalls']
    # The early call read its own copy of material/ (an add round writes new images into the shared folder), gone at the end.
    assert model.materials == tmp_path / 'early' / 'out' / '.early' / 'm0' and not model.materials.exists()
    assert not list((tmp_path / 'early' / 'out' / '.early').glob('*.json'))


def test_a_batch_an_add_round_fills_starts_right_after_that_round(tmp_path, monkeypatch):
    # Real runs get about half of their questions from the add rounds, nearly all from the first one.
    monkeypatch.setattr(gen4, 'REVIEW_BATCH', 3)   # two intake questions and the added one fill batch 0
    began, seen = threading.Event(), {}

    class Model(t4.Model):
        def __call__(self, stage, ctx, material, model):
            if stage == 'v4-review-0-0':
                assert [q['question_id'] for q in ctx['questions']] == ['Q1', 'Q2', 'Q003']
                began.set()
            if stage == 'v4-add-0':
                seen['before the add round'] = began.is_set()
            if stage == 'v4-coverage-1-0':   # the add round's own coverage judgment
                seen['beside the coverage judgment'] = began.wait(20)
            return super().__call__(stage, ctx, material, model)
    model = Model()
    t4.run(tmp_path, model)
    assert seen == {'before the add round': False, 'beside the coverage judgment': True}
    assert model.calls.count('v4-review-0-0') == 1
    assert {'policy': 'early-call/1', 'stage': 'v4-review-0-0', 'used': True} in ledger(tmp_path)['earlyCalls']


def test_a_partly_filled_batch_and_an_old_ledger_start_nothing_early(tmp_path, monkeypatch):
    started = []
    real = Stages.start_early
    monkeypatch.setattr(Stages, 'start_early', lambda self, name, *a, **k: started.append(name) or real(self, name, *a, **k))
    t4.run(tmp_path / 'small')                      # two intake questions, batches of 40: the add round may fill the batch
    assert started == []
    monkeypatch.setattr(gen4, 'REVIEW_BATCH', 2)
    # A ledger made without batchMode keeps the one-after-another order, and starts nothing ahead of its turn.
    monkeypatch.setattr(gen3.Stages, 'parallel', property(lambda self: False))
    t4.run(tmp_path / 'old')
    assert started == []


def test_the_context_judgment_runs_beside_the_coverage_recheck_after_the_merge(tmp_path, monkeypatch):
    # One question per batch, both fixed, and the coverage judgment calls them duplicates: the merged bank needs
    # one more coverage judgment (coverage-merge-0). The context judgment does not read its rows.
    monkeypatch.setattr(gen4, 'REVIEW_BATCH', 1)
    began, seen = threading.Event(), {}

    class Model(t4.Model):
        def __call__(self, stage, ctx, material, model):
            if stage == 'v4-context-0':
                began.set()
            if stage == 'v4-coverage-merge-0':
                seen['context began before the re-check returned'] = began.wait(20)
            return super().__call__(stage, ctx, material, model)
    model = Model(duplicate=True, design_doubt=('Q1', 'Q2'))
    _, _, result = t4.run(tmp_path, model)
    assert seen == {'context began before the re-check returned': True} and model.calls.count('v4-context-0') == 1
    assert {'policy': 'early-call/1', 'stage': 'v4-context-0', 'used': True} in ledger(tmp_path)['earlyCalls']
    names = [s['name'] for s in result['manifest']['stages']]
    assert names.index('v4-coverage-merge-0') < names.index('v4-context-0')   # the record keeps the stages' order


# ------------------------------------------------------------------ the mechanism itself

def stages(tmp_path, invoke):
    p = t4.packet(tmp_path)
    return Stages(p, tmp_path / 'out', None, invoke, policy=gen4.POLICY, prompts=('v3', 'v4'))


def test_start_early_never_calls_a_stage_twice_and_unused_calls_are_settled(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    calls = []

    def invoke(stage, ctx, material, model):
        calls.append(stage)
        return {'answer': stage}, {'usage': {}}
    st = stages(tmp_path, invoke)
    assert st.start_early('x-0', {'a': 1}) is True and st.start_early('x-0', {'a': 1}) is False
    assert st.run('x-0', {'a': 1}, lambda raw: raw) == {'answer': 'x-0'} and calls == ['x-0']
    assert st.start_early('x-0', {'a': 1}) is False            # the ledger has it
    assert st.start_early('never-taken', {'b': 2}) is True
    st.settle_early()
    assert calls == ['x-0', 'never-taken'] and not list((tmp_path / 'out' / '.early').glob('*.json'))
    assert st.ledger['earlyCalls'] == [{'policy': 'early-call/1', 'stage': 'never-taken', 'used': False},
                                       {'policy': 'early-call/1', 'stage': 'x-0', 'used': True}]   # by stage name, not by timing
    assert 'never-taken' not in st.ledger['stages']


def test_an_early_failure_is_raised_as_the_same_error_at_the_turn(tmp_path):
    tmp_path.mkdir(exist_ok=True)

    class Refused(RuntimeError):
        pass

    def invoke(stage, ctx, material, model):
        raise Refused('the provider refused')
    st = stages(tmp_path, invoke)
    st.start_early('x-0', {'a': 1})
    with pytest.raises(Refused):
        st.run('x-0', {'a': 1}, lambda raw: raw)
    assert st.ledger['stages']['x-0']['status'] == 'failed'
