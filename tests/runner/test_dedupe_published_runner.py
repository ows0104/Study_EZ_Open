"""duplicates-only/1 in the runner (docs/changes/2026-11-12-dedupe-published): the published run a request replaces
is found by `restartOf`, its derived packet is re-derived without the front stages, the generator is called with
`--duplicates-of`, and the previous evidence is uploaded under the new revision. Fakes only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import connection_generation as worker
from runner import root_evidence
from studyez_contracts.roots import map_tree

OLD, NEW = 'a' * 32, 'b' * 32


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def previous_run(runs, revision='auto-' + OLD, posted=None):
    root = runs / '_root-generation' / OLD
    write(root / 'published.json', posted or {'status': 'ready', 'revision': revision})
    write(root / 'generation' / 'result.json', {'document': {'revision': revision}})
    write(root / 'front' / 'derived-packet.json', {'conceptMap': 'map', 'points': 'points', 'frontStages': {'f': 1}, 'intakeBank': {'b': 1}})
    write(root / 'generation' / 'evidence' / 'evidence.json', {'schema': 'root-evidence/1', 'revision': revision, 'sources': {'S1': 'x'}})
    return root


def request(**extra):
    return {'generationId': NEW, 'revision': 'auto-' + NEW, 'subject': 'S', 'runId': 'R', 'restartOf': OLD,
            'duplicatesOnly': True, 'pipeline': map_tree.PIPELINE3, **extra}


@pytest.fixture
def derive(monkeypatch):
    seen = []

    def fake(server, concept_map, points, front, bank=None):
        seen.append((server['generationId'], concept_map, points, front, bank))
        return {'derivedFrom': server['generationId'], 'conceptMap': concept_map, 'sources': []}
    monkeypatch.setattr(map_tree, 'derive_packet', fake)
    return seen


def test_the_previous_derived_packet_is_re_derived_from_this_request(tmp_path, derive):
    runs = tmp_path / 'runs'
    root = previous_run(runs)
    out = runs / '_root-generation' / NEW
    assert worker.duplicates_front(request(), out) == root / 'generation'
    assert derive == [(NEW, 'map', 'points', {'f': 1}, {'b': 1})]
    assert json.loads((out / 'front' / 'derived-packet.json').read_text(encoding='utf-8'))['derivedFrom'] == NEW
    # Again (a restarted runner): the same packet is kept.
    assert worker.duplicates_front(request(), out) == root / 'generation'


def test_a_run_not_published_here_is_refused(tmp_path, derive):
    runs = tmp_path / 'runs'
    previous_run(runs, posted={'status': 'ready', 'revision': 'auto-other'})
    with pytest.raises(ValueError, match='게시된 결과'):
        worker.duplicates_front(request(), runs / '_root-generation' / NEW)


def test_the_generator_is_called_with_the_previous_run_and_the_old_evidence_is_reused(tmp_path, derive, monkeypatch):
    runs = tmp_path / 'runs'
    root = previous_run(runs)
    out = runs / '_root-generation' / NEW
    out.mkdir(parents=True)
    commands, uploads = [], []
    gen_packet = {'generationPolicy': 'root-generation/4', 'sourceAssessmentFormat': 'source-assessment/2'}  # as map-tree derives it

    def front(packet, out_, **kw):
        (out_ / 'generation').mkdir(exist_ok=True)
        write(out_ / 'generation' / 'packet.json', gen_packet)
        return gen_packet

    def child(args, **kw):
        commands.append(args)
        write(Path(args[args.index('--out') + 1]) / 'result.json', {'document': {'revision': 'auto-' + NEW}, 'manifest': {}})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker, 'map_tree_front', front)
    monkeypatch.setattr(worker, 'run_forwarded', child)
    monkeypatch.setattr(worker, 'validate_result', lambda payload, packet: payload['document'])
    monkeypatch.setattr(worker, 'validate_continuations', lambda out_, payload: None)
    monkeypatch.setattr(worker, 'completed_result', lambda out_, packet: json.loads((out_ / 'result.json').read_text(encoding='utf-8')))
    monkeypatch.setattr(root_evidence, 'upload', lambda client, subject, run_id, path: uploads.append(path))
    monkeypatch.setattr(root_evidence, 'build', lambda *a, **k: pytest.fail('the evidence is not built again'))
    client = SimpleNamespace(call=lambda method, path, payload=None: {'status': 'ready', 'revision': 'auto-' + NEW})
    packet = request()
    assert worker._generate(client, 'S', 'R', '/api/x', packet, out / 'packet.json', out) == 0
    args = commands[0]
    assert args[2] == 'runner.root_native_json'   # the native transport, whose main takes the flag
    assert Path(args[args.index('--duplicates-of') + 1]) == (root / 'generation').resolve() and '--resume' not in args
    assert [p.name for p in uploads] == ['auto-' + NEW + '.json']
    assert json.loads(uploads[0].read_text(encoding='utf-8')) == {'schema': 'root-evidence/1', 'revision': 'auto-' + NEW, 'sources': {'S1': 'x'}}
    # The previous run is untouched.
    assert json.loads((root / 'generation' / 'evidence' / 'evidence.json').read_text(encoding='utf-8'))['revision'] == 'auto-' + OLD


def test_a_request_without_the_flag_runs_as_before(tmp_path, monkeypatch):
    out = tmp_path / 'runs' / '_root-generation' / NEW
    out.mkdir(parents=True)
    commands = []
    monkeypatch.setattr(worker, 'map_tree_front', lambda packet, out_, **kw: None)  # the front stops here
    monkeypatch.setattr(worker, 'duplicates_front', lambda *a: pytest.fail('not a duplicates-only request'))
    assert worker._generate(None, 'S', 'R', '/api/x', request(duplicatesOnly=False), out / 'packet.json', out) == 1


def test_the_native_transport_takes_the_flag_to_the_generator(tmp_path, monkeypatch):
    from runner import root_native_json as native
    seen = {}
    monkeypatch.setattr(native.g, 'run', lambda packet, out, **kw: seen.update(kw) or {'manifest': {}})
    monkeypatch.setattr(native, 'validate_all', lambda out, result: None)
    (tmp_path / 'packet.json').write_text(json.dumps({'generationPolicy': 'root-generation/4', 'sourceAssessmentFormat': 'source-assessment/2'}), encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['x', '--packet', str(tmp_path / 'packet.json'), '--out', str(tmp_path / 'o'), '--duplicates-of', str(tmp_path / 'prev')])
    assert native.main() == 0
    assert seen['duplicates_of'] == tmp_path / 'prev' and isinstance(seen['invoke'], native.NativeJson)
