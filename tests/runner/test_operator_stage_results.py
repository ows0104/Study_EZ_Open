"""operator-stage-result/1: a normalize answer a person brought from outside (docs/changes/2026-11-19-operator-normalize-import)."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generation_v2_fixture as f
from quizbank import connection_generate as g, connection_generate_v2 as producer
from runner import root_native_json as n, connection_generation as worker, operator_stage_results as ops
from test_root_native_json import provider


def reference(tmp_path, monkeypatch):
    """A run where the model wrote every stage; its normalize file is what the person brings."""
    monkeypatch.setattr(producer, 'call_model', f.model)
    packet = f.packet(tmp_path / 'source.txt')
    out = tmp_path / 'ref' / 'generation'
    g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out)))
    return packet, (out / '.native' / 'normalize' / 'output.json').read_bytes()


def record(folder, body, **change):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'operator-normalize.json').write_bytes(body)
    row = {'file': 'operator-normalize.json', 'sha256': hashlib.sha256(body).hexdigest(), 'producer': 'ChatGPT 웹(운영자 제공)',
           'reason': '모델 normalize가 거절되어 웹 결과를 쓴다', 'approval': '「이걸로 돌려줘」', 'at': '2026-11-19T10:00:00+09:00', **change}
    doc = {'version': 1, 'stages': {'normalize': row}}
    (folder / ops.FILENAME).write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return doc


def test_the_operators_normalize_takes_the_models_place_and_stays_verifiable(tmp_path, monkeypatch):
    packet, body = reference(tmp_path, monkeypatch)
    out = tmp_path / 'run' / 'generation'
    record(out.parent, body)
    calls = []
    result = g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out, calls)))
    assert calls == ['generate', 'source-0']   # normalize did not reach a model
    receipt = n.read(out / '.native' / 'normalize' / 'receipt.json')
    imported = receipt['proof']['operatorImport']
    assert imported['policy'] == ops.POLICY and imported['entry']['producer'] == 'ChatGPT 웹(운영자 제공)'
    assert not (out / '.native' / 'normalize' / 'provider.json').exists()
    assert (out / '.native' / 'normalize' / 'output.json').read_bytes() == body
    usage = n.read(out / 'normalize.usage.json')
    assert {k: usage[k] for k in n.IMPORTED_USAGE} == n.IMPORTED_USAGE and usage['operatorImport'] == imported
    n.validate_all(out, result)
    assert worker.completed_result(out, packet) == result


@pytest.mark.parametrize('change', ['record', 'file', 'removed'])
def test_a_changed_record_or_file_blocks_the_completed_result(tmp_path, monkeypatch, change):
    packet, body = reference(tmp_path, monkeypatch)
    out = tmp_path / 'run' / 'generation'
    doc = record(out.parent, body)
    result = g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out)))
    if change == 'record':
        doc['stages']['normalize']['approval'] = '다른 승인'
        (out.parent / ops.FILENAME).write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    if change == 'file':
        (out.parent / 'operator-normalize.json').write_bytes(body + b' ')
    if change == 'removed':
        (out.parent / ops.FILENAME).unlink()
    with pytest.raises(ValueError):
        n.validate_all(out, result)


def test_an_operator_file_that_fails_the_checks_fails_the_stage_without_a_model(tmp_path, monkeypatch):
    packet, body = reference(tmp_path, monkeypatch)
    value = json.loads(body)
    value['lecture_id'] = 'other/lecture'
    bad = json.dumps(value, ensure_ascii=False).encode('utf-8')
    out = tmp_path / 'run' / 'generation'
    record(out.parent, bad)
    calls = []
    with pytest.raises(ValueError):
        g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out, calls)))
    assert calls == [] and n.read(out / '.native' / 'normalize' / 'journal.json')['status'] == 'failed'
    assert n.read(out / 'ledger.json')['stages']['normalize']['status'] == 'failed'


def test_garbled_korean_in_the_operators_file_is_refused(tmp_path, monkeypatch):
    packet, body = reference(tmp_path, monkeypatch)
    value = json.loads(body)
    value['points'][0]['text'] = '?? ???? ?? ?'
    out = tmp_path / 'run' / 'generation'
    record(out.parent, json.dumps(value, ensure_ascii=False).encode('utf-8'))
    with pytest.raises(ValueError):
        g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out, [])))


@pytest.mark.parametrize('problem', ['stage', 'sha', 'path', 'field', 'missing'])
def test_a_malformed_record_holds_the_stage(tmp_path, problem):
    out = tmp_path / 'gen' / 'generation'
    body = b'{}'
    doc = record(out.parent, body)
    row = doc['stages']['normalize']
    if problem == 'stage':
        doc['stages'] = {'generate': row}
    if problem == 'sha':
        row['sha256'] = '0' * 64
    if problem == 'path':
        row['file'] = '../x.json'
    if problem == 'field':
        row['approval'] = ' '
    if problem == 'missing':
        (out.parent / 'operator-normalize.json').unlink()
    (out.parent / ops.FILENAME).write_text(json.dumps(doc), encoding='utf-8')
    stage = 'generate' if problem == 'stage' else 'normalize'
    with pytest.raises(ops.OperatorStageError):
        ops.entry(out, stage)


def test_without_a_record_the_model_runs_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(producer, 'call_model', f.model)
    packet = f.packet(tmp_path / 'source.txt')
    out = tmp_path / 'run' / 'generation'
    calls = []
    g.run(packet, out, invoke=n.NativeJson(out, invoke=provider(out, calls)))
    assert calls[0] == 'normalize' and ops.entry(out, 'normalize') is None
    assert 'operatorImport' not in n.read(out / '.native' / 'normalize' / 'receipt.json')['proof']
