"""map-tree/2: front stages + an independent bank → root-generation/3 → server check (docs/changes/2026-11-10-root-generation-3, PR C).

Synthetic PDFs, a fake Codex call and a fake generation model. No model, server or DB."""
import copy
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'quizbank'))
from runner import root_front as rf
from runner import connection_generation as worker
from runner import root_choices, root_evidence
from studyez_contracts.roots import map_tree, document_hash
from studyez_contracts.roots.automation import packet_hash, validate_result
from map_tree_fixture import TITLE, pdf, fake_codex
import generation_v2_fixture as f2
import test_root_generation_v3 as t3

GID = 'b' * 32


def server_packet(tmp_path):
    sources = []
    for sid, kind, name, pages in (('S1', 'notes_current', 'notes.pdf', 2), ('S2', 'jokbo', 'jokbo.pdf', 1)):
        path = pdf(tmp_path / name, pages); body = path.read_bytes()
        sources.append({'id': sid, 'assetId': 1, 'kind': kind, 'filename': name, 'sizeBytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest(), 'originalKey': 'k/' + name, 'uploadedAt': '2026-11-10T00:00:00+00:00',
                        'snapshotKey': 'snap/' + name, 'localPath': str(path)})
    p = {'generationId': GID, 'revision': 'auto-' + GID, 'subject': 'Synthetic subject', 'runId': '261110_01', 'title': TITLE,
         'owner': 'admin', 'privatePilot': False, 'sources': sources, 'conceptMap': '', 'points': '', 'scope': '',
         'examDate': None, 'authoring': 'cli', 'inputMode': 'source', 'pipeline': map_tree.PIPELINE2,
         'sourceAssessmentFormat': map_tree.FORMAT2}
    p['inputHash'] = packet_hash(p)
    return p


def bank_value():
    bank = f2.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
        q['point_ids'] = []
    return {'bank': bank, 'visual_stimuli': [], 'clinical_conflicts': []}


def front_codex(calls, **kwargs):
    run = fake_codex(calls, **kwargs)

    def call(task, *, cwd, label, **rest):
        if Path(cwd).name != 'bank':
            return run(task, cwd=cwd, label=label, **rest)
        calls.append(('bank', task))
        path = Path(cwd) / 'bank.json'
        path.write_text(json.dumps(bank_value(), ensure_ascii=False), encoding='utf-8')
        return {'text': json.dumps({'path': 'bank.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}),
                'session_id': 'session-bank', 'duration_ms': 3, 'usage': {'input_tokens': 1}}
    return call


class Model(t3.Model):
    """The /3 synthetic model on a derived map-tree packet: the brief's point is the extracted point."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'normalize':
            value['points'][0]['point_id'] = json.loads(self.points)['points'][0]['point_id']
        return value, info


def test_front_runs_map_point_and_bank_and_derives_a_v3_packet(tmp_path):
    p = server_packet(tmp_path); calls = []
    derived = rf.Front(p, tmp_path / 'front', invoke=front_codex(calls)).run()
    # The audit follows the points at once, beside the Map and the bank (2026-11-11-pipeline-resilience).
    names = [s for s, _ in calls]
    assert sorted(names) == ['audit', 'bank', 'map', 'point'] and names.index('point') < names.index('audit')
    assert derived['generationPolicy'] == 'root-generation/3' and derived['intakeBank'] == bank_value()
    front = derived['frontStages']
    assert list(front['stages']) == ['map', 'point', 'bank', 'audit'] and front['bankHash'] == document_hash(bank_value())
    assert front['openPoints'] == [] and 'parallel/bank.md' in front['prompts']
    bank_task = next(t for s, t in calls if s == 'bank')
    assert bank_task.startswith(rf.asset_text('parallel/bank.md')) and 'image_id를 쓰지 않고' in bank_task
    assert '출제포인트' in bank_task and 'exam-points' not in bank_task   # the bank never sees the points output
    # A changed bank no longer matches the recorded stage.
    with pytest.raises(ValueError, match='independent bank'):
        map_tree.derive_packet(p, derived['conceptMap'], derived['points'], front, {**bank_value(), 'clinical_conflicts': [{'conflict_id': 'X', 'facts': 'x'}]})
    with pytest.raises(ValueError, match='independent bank is missing'):
        map_tree.derive_packet(p, derived['conceptMap'], derived['points'], front, None)


def test_a_map_tree_1_request_is_unchanged(tmp_path):
    p = server_packet(tmp_path)
    p.update(pipeline=map_tree.PIPELINE, sourceAssessmentFormat=map_tree.FORMAT)
    p['inputHash'] = packet_hash(p)
    calls = []
    derived = rf.Front(p, tmp_path / 'front', invoke=front_codex(calls)).run()
    assert [s for s, _ in calls] == ['map', 'point', 'audit'] and 'generationPolicy' not in derived and 'intakeBank' not in derived


def test_open_audit_points_travel_to_the_result(tmp_path):
    p = server_packet(tmp_path); calls = []
    run = front_codex(calls, issues=True)

    def keep_issue(task, *, cwd, label, **rest):
        info = run(task, cwd=cwd, label=label, **rest)
        path = Path(cwd) / 'audit.json'
        if Path(cwd).name == 'final-audit':
            value = json.loads(path.read_text(encoding='utf-8'))
            first = json.loads((Path(cwd).parent / 'audit' / 'audit.json').read_text(encoding='utf-8'))
            value.update(verdict='needs_revision', issues=first['issues'][:1])
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            info['text'] = json.dumps({'path': 'audit.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return info
    derived = rf.Front(p, tmp_path / 'front', invoke=keep_issue).run()
    assert derived['frontStages']['openPoints'] and set(derived['frontStages']['openPoints']) <= {
        x['point_id'] for x in json.loads(derived['points'])['points']}


class Client:
    base = 'http://local.example'

    def __init__(self, packet):
        self.packet = {k: v for k, v in packet.items()}
        self.packet['sources'] = [{k: v for k, v in s.items() if k != 'localPath'} for s in packet['sources']]
        self.bodies = {s['id']: Path(s['localPath']).read_bytes() for s in packet['sources']}
        self.calls = []

    def call(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == 'GET':
            return {'published': False, 'packet': {**self.packet, 'sources': [{**s, 'downloadUrl': '/signed/' + s['id']} for s in self.packet['sources']]}}
        return {'status': 'ready'}


def test_runner_runs_front_then_v3_and_the_server_can_re_derive_and_check(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir(); p = server_packet(tmp_path / 'src')
    client = Client(p); commands = []; front_calls = []
    monkeypatch.setattr(root_evidence, 'build', lambda *a, **k: None)
    monkeypatch.setattr(root_choices, 'build', lambda *a, **k: None)
    monkeypatch.setattr(worker.urllib.request, 'urlopen', lambda req, **k: io.BytesIO(client.bodies[req.full_url.rsplit('/', 1)[1]]))

    def child(args, **kwargs):
        commands.append(args)
        packet = json.loads(Path(args[args.index('--packet') + 1]).read_text(encoding='utf-8'))
        out = Path(args[args.index('--out') + 1])
        if args[2] == 'runner.root_front':
            rf.Front(packet, out, invoke=front_codex(front_calls)).run()
        else:
            from quizbank import connection_generate as g
            model = Model()
            model.points = packet['points']
            g.run(packet, out, invoke=model)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker, 'run_forwarded', child)
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 0
    assert [c[2] for c in commands] == ['runner.root_front', 'runner.root_native_json']
    payload = next(c for c in client.calls if c[0] == 'PUT')[2]
    assert payload['manifest']['pipelineVersion'] == 'root-generation/3'
    doc = validate_result(json.loads(json.dumps(payload)), client.packet)
    assert doc['revision'] == p['revision'] and doc['tasks']
    bad = copy.deepcopy(payload)
    bad['manifest']['derivedPacket']['intakeBank']['bank']['questions'][0]['answer'] = 'Synthetic other'
    with pytest.raises(ValueError):
        validate_result(bad, client.packet)


def test_a_resume_sets_aside_a_stored_result_the_current_checks_refuse(tmp_path, monkeypatch):
    """261102_02 (2026-11-10): after a fix, 「이어서 만들기」 re-validated the stored result (refused by the server
    with 0 tasks) and stopped before the generator could apply the fix."""
    (tmp_path / 'src').mkdir(); p = server_packet(tmp_path / 'src')
    client = Client(p); commands = []
    monkeypatch.setattr(root_evidence, 'build', lambda *a, **k: None)
    monkeypatch.setattr(root_choices, 'build', lambda *a, **k: None)
    monkeypatch.setattr(worker.urllib.request, 'urlopen', lambda req, **k: io.BytesIO(client.bodies[req.full_url.rsplit('/', 1)[1]]))

    def child(args, **kwargs):
        commands.append(args)
        packet = json.loads(Path(args[args.index('--packet') + 1]).read_text(encoding='utf-8'))
        out = Path(args[args.index('--out') + 1])
        if args[2] == 'runner.root_front':
            rf.Front(packet, out, invoke=front_codex([])).run()
        else:
            from quizbank import connection_generate as g
            model = Model()
            model.points = packet['points']
            g.run(packet, out, invoke=model, resume=args[args.index('--resume') + 1] if '--resume' in args else None)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker, 'run_forwarded', child)
    runs = tmp_path / 'runs'
    assert worker.run_generation(client, p['subject'], p['runId'], runs, GID) == 0
    gen = runs / '_root-generation' / GID / 'generation'
    stored = json.loads((gen / 'result.json').read_text(encoding='utf-8'))
    stale = copy.deepcopy(stored)
    stale['manifest']['clinicalContext']['unrecorded'] = ['Synthetic stale']
    (gen / 'result.json').write_text(json.dumps(stale, ensure_ascii=False), encoding='utf-8')
    # Without a reason the stored result is still what the runner checks: it stops, nothing is moved.
    with pytest.raises(ValueError):
        worker.run_generation(client, p['subject'], p['runId'], runs, GID)
    assert (gen / 'result.json').exists() and not list(gen.glob('.rejected-result-*'))
    commands.clear()
    assert worker.run_generation(client, p['subject'], p['runId'], runs, GID, resume='Synthetic fix applied') == 0
    assert [c[2] for c in commands] == ['runner.root_native_json']   # the front stays; the generator runs again
    kept = json.loads((gen / '.rejected-result-0' / 'result.json').read_text(encoding='utf-8'))
    assert kept == stale
    reason = json.loads((gen / '.rejected-result-0' / 'reason.json').read_text(encoding='utf-8'))
    assert reason['resume'] == 'Synthetic fix applied' and reason['error'].startswith('result3:')
    assert json.loads((gen / 'result.json').read_text(encoding='utf-8'))['manifest']['clinicalContext']['unrecorded'] == []
    # A stored result that passes is reused even with a reason.
    commands.clear()
    assert worker.run_generation(client, p['subject'], p['runId'], runs, GID, resume='Again') == 0
    assert commands == [] and len(list(gen.glob('.rejected-result-*'))) == 1
