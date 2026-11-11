"""map-tree/1 front stages in the runner (docs/changes/2026-11-09-main-quiz-runner-pipeline R2·R3·R6).

The prompts reproduce the 사슬알균 pilot's task.md byte for byte (tests/fixtures/map_tree_26110901, copied from
runs/_e2e/26110901); the rest runs on synthetic PDFs with a fake Codex call. No model, server or DB."""
import copy
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
from runner import root_front as rf
from runner import connection_generation as worker
from runner import root_evidence
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import packet_hash, validate_result
from map_tree_fixture import TITLE, pdf, concept_map, points, fake_codex, generation_model

GOLD = Path(__file__).resolve().parents[1] / 'fixtures' / 'map_tree_26110901'
GID = 'a' * 32


def gold(name):
    return (GOLD / name).read_text(encoding='utf-8').replace('\r\n', '\n')


# ------------------------------------------------------------------ the pilots' prompts, verbatim

def test_templates_reproduce_the_pilot_tasks_byte_for_byte():
    title, pages = '사슬알균', {'S1': 38, 'S2': 8}
    for kind in ('map', 'point'):
        schema, request, filename, first = rf.ASSET[kind]
        task = rf.asset_text(request) + '\n\n' + rf.template('map-tree/extract-task.md', title=title, first_id=first, filename=filename)
        assert task == gold(kind + '.task.md')
    audit = rf.template('map-tree/point-audit.md', pages=map_tree.pages_phrase(pages), title=title).rstrip('\n')
    assert audit == gold('audit.task.md') == gold('final-audit.task.md')
    repair = rf.asset_text(rf.ASSET['point'][1]) + '\n' + rf.template('map-tree/point-repair.md', title=title).rstrip('\n')
    assert repair == gold('point-repair.task.md')
    assert rf.audit_schema() == json.loads(gold('audit.schema.json'))


# ------------------------------------------------------------------ synthetic request

def server_packet(tmp_path, jokbo=True, scope=''):
    sources = []
    for sid, kind, name, pages in (('S1', 'notes_current', 'notes.pdf', 2), ('S2', 'jokbo', 'jokbo.pdf', 1))[:2 if jokbo else 1]:
        path = pdf(tmp_path / name, pages); body = path.read_bytes()
        sources.append({'id': sid, 'assetId': 1, 'kind': kind, 'filename': name, 'sizeBytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest(), 'originalKey': 'k/' + name, 'uploadedAt': '2026-11-09T00:00:00+00:00',
                        'snapshotKey': 'snap/' + name, 'localPath': str(path)})
    p = {'generationId': GID, 'revision': 'auto-' + GID, 'subject': 'Synthetic subject', 'runId': '261109_01', 'title': TITLE,
         'owner': 'admin', 'privatePilot': False, 'sources': sources, 'conceptMap': '', 'points': '', 'scope': scope,
         'examDate': None, 'authoring': 'cli', 'inputMode': 'source', 'pipeline': map_tree.PIPELINE,
         'sourceAssessmentFormat': map_tree.FORMAT}
    p['inputHash'] = packet_hash(p)
    return p


def stages(calls):
    return [s for s, _ in calls]


# ------------------------------------------------------------------ front stages

def test_ready_audit_runs_three_calls_and_derives_the_pilot_packet_shape(tmp_path):
    p = server_packet(tmp_path, scope='Admin note'); calls = []
    derived = rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls)).run()
    assert stages(calls) == ['map', 'point', 'audit']
    assert derived['inputMode'] == 'provided' and derived['sourceAssessmentFormat'] == 'source-assessment/2' and derived['speedStages'] is True
    assert 'pipeline' not in derived and derived['derivedFrom'] == p['inputHash'] and derived['revision'] == p['revision']
    assert derived['scope'].startswith('올해 필기 S1 전체(2쪽, 「Synthetic lecture」)가 이 강의 범위다. S2는 이 강의 족보(1쪽)다.')
    assert '관리자 범위 메모: Admin note' in derived['scope'] and derived['scope'].endswith(map_tree.SCOPE_SUFFIX)
    assert json.loads(derived['conceptMap']) == concept_map() and json.loads(derived['points']) == points()
    front = derived['frontStages']
    assert front['pointsFrom'] == 'point' and [a['verdict'] for a in front['audits']] == ['ready'] and front['pageCounts'] == {'S1': 2, 'S2': 1}
    assert derived['inputHash'] == packet_hash(derived)
    assert json.loads((tmp_path / 'front' / 'derived-packet.json').read_text(encoding='utf-8')) == derived
    # The extraction task is the pilot template with this lecture's title; the audit covers every frozen page.
    assert '실제 대상은 「Synthetic lecture」이다' in calls[0][1] and 'S1 1~2쪽과 S2 1~1쪽의 모든 물리쪽' in calls[2][1]
    assert sorted(p.name for p in (tmp_path / 'front' / 'material').iterdir()) == ['S1-0001.png', 'S1-0002.png', 'S1.md', 'S1.pdf', 'S2-0001.png', 'S2.md', 'S2.pdf']
    # Completed stages are reused, never called again.
    assert rf.Front(p, tmp_path / 'front', invoke=lambda *a, **k: pytest.fail('no repeat')).run() == derived


def test_audit_issues_get_one_point_repair_and_a_final_audit(tmp_path):
    p = server_packet(tmp_path); calls = []
    derived = rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls, issues=True)).run()
    assert stages(calls) == ['map', 'point', 'audit', 'point-repair', 'final-audit']
    assert json.loads(derived['points']) == points(extra=True) and derived['frontStages']['pointsFrom'] == 'point-repair'
    assert [a['verdict'] for a in derived['frontStages']['audits']] == ['needs_revision', 'ready']
    assert 'previous-exam-points.json' in calls[3][1] and calls[3][1].startswith(rf.asset_text('point-extract-v3.md'))


def test_notes_only_request_has_no_jokbo_sentence(tmp_path):
    p = server_packet(tmp_path, jokbo=False); calls = []
    run = fake_codex(calls)
    def notes_only(task, *, cwd, label, **kwargs):
        info = run(task, cwd=cwd, label=label, **kwargs)
        path = Path(cwd) / 'audit.json'
        if path.exists():
            value = json.loads(path.read_text(encoding='utf-8')); value['page_review'] = value['page_review'][:1]
            path.write_text(json.dumps(value), encoding='utf-8')
            info['text'] = json.dumps({'path': 'audit.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return info
    derived = rf.Front(p, tmp_path / 'front', invoke=notes_only).run()
    assert '족보' not in derived['scope'] and derived['frontStages']['pageCounts'] == {'S1': 2}


def test_interrupted_stage_is_never_retried_automatically_and_resumes_only_with_a_reason(tmp_path):
    p = server_packet(tmp_path); calls = []
    with pytest.raises(RuntimeError):
        rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls, fail=['point'])).run()
    with pytest.raises(ValueError, match='자동 재실행하지 않습니다'):
        rf.Front(p, tmp_path / 'front', invoke=lambda *a, **k: pytest.fail('no automatic retry')).run()
    derived = rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls), resume='admin: retry after a network drop').run()
    assert stages(calls) == ['map', 'point', 'point', 'audit']  # the map is kept
    assert (tmp_path / 'front' / '.resume-1' / 'point' / 'failure.json').exists()
    assert derived['frontStages']['resumes'] == [{'reason': 'admin: retry after a network drop', 'stages': ['point']}]


def test_a_rerun_stage_reruns_every_later_stage(tmp_path):
    p = server_packet(tmp_path); calls = []
    with pytest.raises(RuntimeError):
        rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls, fail=['audit'])).run()
    (tmp_path / 'front' / 'point' / 'state.json').write_text(json.dumps({'status': 'failed', 'inputHashes': {}}), encoding='utf-8')
    rf.Front(p, tmp_path / 'front', invoke=fake_codex(calls), resume='admin: point output was cut').run()
    assert stages(calls) == ['map', 'point', 'audit', 'point', 'audit']
    assert sorted(x.name for x in (tmp_path / 'front' / '.resume-1').iterdir()) == ['audit', 'point']


def test_a_model_that_changes_its_input_fails_the_stage(tmp_path):
    p = server_packet(tmp_path)
    with pytest.raises(ValueError, match='Model modified input'):
        rf.Front(p, tmp_path / 'front', invoke=fake_codex([], tamper='map')).run()
    assert json.loads((tmp_path / 'front' / 'map' / 'state.json').read_text(encoding='utf-8'))['status'] == 'failed'


def retitled(calls, rename):
    """fake_codex whose Map/points outputs carry another title (agent.261104_03: 'Different title')."""
    run = fake_codex(calls)
    def call(task, *, cwd, label, **kwargs):
        info = run(task, cwd=cwd, label=label, **kwargs)
        stage = Path(cwd).name
        if stage in rename:
            name = json.loads(info['text'])['path']; path = Path(cwd) / name
            value = json.loads(path.read_text(encoding='utf-8')); value['title'] = rename[stage]
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            info['text'] = json.dumps({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return info
    return call


def test_a_model_written_title_is_replaced_by_the_request_title_and_kept(tmp_path):
    p = server_packet(tmp_path); calls = []
    rename = {'map': TITLE + ' (강의록)', 'point': ' ' + TITLE, 'point-repair': '다른 강의'}
    derived = rf.Front(p, tmp_path / 'front', invoke=retitled(calls, rename)).run()
    assert stages(calls) == ['map', 'point', 'audit']
    assert json.loads(derived['conceptMap']) == concept_map() and json.loads(derived['points']) == points()
    for stage, name in (('map', 'concept-map.json'), ('point', 'exam-points.json')):
        work = tmp_path / 'front' / stage
        assert json.loads((work / ('model-' + name)).read_text(encoding='utf-8'))['title'] == rename[stage]
        assert json.loads((work / 'state.json').read_text(encoding='utf-8'))['modelTitle'] == rename[stage]
    # The repaired points are retitled the same way.
    (tmp_path / 'r').mkdir(); p2 = server_packet(tmp_path / 'r'); with_issues = fake_codex([], issues=True)
    def repaired(task, *, cwd, label, **kwargs):
        model = with_issues if Path(cwd).name == 'audit' else retitled([], rename)
        return model(task, cwd=cwd, label=label, **kwargs)
    derived = rf.Front(p2, tmp_path / 'front2', invoke=repaired).run()
    assert derived['frontStages']['pointsFrom'] == 'point-repair' and json.loads(derived['points'])['title'] == TITLE
    assert json.loads((tmp_path / 'front2' / 'point-repair' / 'state.json').read_text(encoding='utf-8'))['modelTitle'] == '다른 강의'


def test_a_result_that_fails_its_checks_is_recorded_as_failed(tmp_path):
    p = server_packet(tmp_path); run = fake_codex([])
    def duplicated(task, *, cwd, label, **kwargs):
        info = run(task, cwd=cwd, label=label, **kwargs)
        if Path(cwd).name == 'map':
            path = Path(cwd) / 'concept-map.json'; value = json.loads(path.read_text(encoding='utf-8'))
            value['concepts'].append(value['concepts'][0]); path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            info['text'] = json.dumps({'path': 'concept-map.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return info
    with pytest.raises(ValueError, match='duplicate ID'):
        rf.Front(p, tmp_path / 'front', invoke=duplicated).run()
    work = tmp_path / 'front' / 'map'
    assert json.loads((work / 'state.json').read_text(encoding='utf-8'))['status'] == 'failed' and (work / 'failure.json').exists()


def test_changed_source_bytes_stop_before_any_model_call(tmp_path):
    p = server_packet(tmp_path)
    Path(p['sources'][0]['localPath']).write_bytes(b'%PDF-changed')
    with pytest.raises(ValueError, match='Source changed'):
        rf.Front(p, tmp_path / 'front', invoke=lambda *a, **k: pytest.fail('no model call')).run()


# ------------------------------------------------------------------ runner: request → front → generation → publication

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


def wire(monkeypatch, client, commands, front_calls):
    monkeypatch.setattr(root_evidence, 'build', lambda *a, **k: None)
    monkeypatch.setattr(worker.urllib.request, 'urlopen', lambda req, **k: io.BytesIO(client.bodies[req.full_url.rsplit('/', 1)[1]]))

    def child(args, **kwargs):
        commands.append(args)
        packet = json.loads(Path(args[args.index('--packet') + 1]).read_text(encoding='utf-8'))
        out = Path(args[args.index('--out') + 1])
        resume = args[args.index('--resume') + 1] if '--resume' in args else None
        if args[2] == 'runner.root_front':
            rf.Front(packet, out, invoke=fake_codex(front_calls), resume=resume).run()
        else:
            from quizbank import connection_generate as g
            g.run(packet, out, invoke=generation_model, resume=resume)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker, 'run_forwarded', child)


def test_runner_runs_front_then_generation_and_the_server_can_re_derive_the_packet(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir(); p = server_packet(tmp_path / 'src')
    client = Client(p); commands = []; front_calls = []
    wire(monkeypatch, client, commands, front_calls)
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 0
    assert [c[2] for c in commands] == ['runner.root_front', 'runner.root_native_json']
    out = tmp_path / 'runs' / '_root-generation' / GID
    assert commands[1][commands[1].index('--out') + 1] == str((out / 'generation').resolve())
    put = next(c for c in client.calls if c[0] == 'PUT')
    payload = put[2]
    # What the server holds: the request without any local path. It re-derives the generation packet.
    doc = validate_result(json.loads(json.dumps(payload)), client.packet)
    assert doc['revision'] == p['revision'] and doc['tasks']
    assert payload['manifest']['derivedPacket']['derivedFrom'] == p['inputHash'] and payload['manifest']['runPolicies']
    for change in ('conceptMap', 'scope', 'front', 'request'):
        bad, server = copy.deepcopy(payload), copy.deepcopy(client.packet)
        if change == 'conceptMap': bad['manifest']['derivedPacket']['conceptMap'] = json.dumps({**concept_map(), 'overview': 'other'})
        elif change == 'scope': bad['manifest']['derivedPacket']['scope'] += ' extra'
        elif change == 'front': bad['manifest']['derivedPacket']['frontStages']['audits'][0]['issues'] = 1
        else: server['title'] = 'Another lecture'; server['inputHash'] = packet_hash(server)
        with pytest.raises(ValueError): validate_result(bad, server)
    # A rerun reuses everything: no model call, same publication payload.
    commands.clear()
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 0 and commands == []


def test_runner_passes_the_administrators_resume_reason(tmp_path, monkeypatch):
    p = server_packet(tmp_path); client = Client(p); commands = []; front_calls = []
    wire(monkeypatch, client, commands, front_calls)
    original = worker.run_forwarded
    def failing(args, **kwargs):
        if args[2] == 'runner.root_front' and '--resume' not in args:
            commands.append(args); return SimpleNamespace(returncode=1)
        return original(args, **kwargs)
    monkeypatch.setattr(worker, 'run_forwarded', failing)
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 1
    assert not any(c[0] == 'PUT' for c in client.calls)
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID, resume='admin: network was down') == 0
    assert commands[-2][commands[-2].index('--resume') + 1] == 'admin: network was down'


def test_a_map_tree_request_never_reaches_the_earlier_generator_paths(tmp_path):
    """Before this change a runner sent the request to quizbank.connection_generate, which refuses the format."""
    from quizbank import connection_generate as g
    p = server_packet(tmp_path)
    with pytest.raises(ValueError, match='지원하지 않는 원본 검수 형식'):
        g.run(p, tmp_path / 'out', invoke=lambda *a: pytest.fail('no model call'))


# ------------------------------------------------------------------ local replay of the 사슬알균 pilot (skipped without its archive)

PILOT = Path(__file__).resolve().parents[2] / 'runs' / '_e2e' / '26110901'
if not PILOT.exists():  # a worktree reads the main checkout's runs/
    PILOT = next((p / 'runs' / '_e2e' / '26110901' for p in Path(__file__).resolve().parents if (p / 'runs' / '_e2e' / '26110901').exists()), PILOT)


@pytest.mark.skipif(not (PILOT / 'final-audit' / 'audit.json').exists(), reason='pilot archive runs/_e2e/26110901 is local only')
def test_replaying_the_sasl_pilot_answers_reproduces_its_front_outputs(tmp_path):
    files = {'map': 'concept-map.json', 'point': 'exam-points.json', 'audit': 'audit.json', 'point-repair': 'exam-points.json', 'final-audit': 'audit.json'}
    sources = []
    for sid, kind in (('S1', 'notes_current'), ('S2', 'jokbo')):
        body = (PILOT / 'material' / (sid + '.pdf')).read_bytes(); local = tmp_path / (sid + '.pdf'); local.write_bytes(body)
        sources.append({'id': sid, 'kind': kind, 'filename': sid + '.pdf', 'sizeBytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest(), 'localPath': str(local)})
    p = {'generationId': GID, 'revision': 'auto-' + GID, 'subject': '감염과 면역', 'runId': '261105_01', 'title': '사슬알균', 'owner': 'admin',
         'privatePilot': False, 'sources': sources, 'conceptMap': '', 'points': '', 'scope': '', 'examDate': None, 'authoring': 'cli',
         'inputMode': 'source', 'pipeline': map_tree.PIPELINE, 'sourceAssessmentFormat': map_tree.FORMAT}
    p['inputHash'] = packet_hash(p)
    sent = {}

    def replay(task, *, cwd, label, **kwargs):
        stage = Path(cwd).name; sent[stage] = task
        body = (PILOT / stage / files[stage]).read_bytes(); (Path(cwd) / files[stage]).write_bytes(body)
        old = json.loads((PILOT / stage / 'model-response.json').read_text(encoding='utf-8'))
        return {**old, 'text': json.dumps({'path': files[stage], 'sha256': hashlib.sha256(body).hexdigest()})}
    derived = rf.Front(p, tmp_path / 'front', invoke=replay).run()
    assert list(sent) == ['map', 'point', 'audit', 'point-repair', 'final-audit']
    for stage in ('map', 'point', 'audit', 'point-repair', 'final-audit'):
        # The same instructions the pilot sent: task.md is byte-identical, and the first message is that text
        # followed only by the contents of the stage's input files (docs/changes/2026-11-11-pipeline-overlap).
        assert (tmp_path / 'front' / stage / 'task.md').read_bytes().decode('utf-8') == gold(stage + '.task.md')
        head, _, tail = sent[stage].partition('\n\n---\nThe complete contents of these input files')
        assert head == gold(stage + '.task.md') and '===== BEGIN input.json =====' in tail
    assert json.loads(derived['conceptMap']) == json.loads((PILOT / 'map/concept-map.json').read_text(encoding='utf-8-sig'))
    assert json.loads(derived['points']) == json.loads((PILOT / 'point-repair/exam-points.json').read_text(encoding='utf-8-sig'))
    pilot_packet = json.loads((PILOT / 'generation/packet.json').read_text(encoding='utf-8'))
    assert json.loads(derived['points']) == json.loads(pilot_packet['points']) and json.loads(derived['conceptMap']) == json.loads(pilot_packet['conceptMap'])
    assert [(a['verdict'], a['issues']) for a in derived['frontStages']['audits']] == [('needs_revision', 10), ('needs_revision', 6)]


def test_the_server_stored_reason_is_used_once_for_the_next_run(tmp_path, monkeypatch):
    """The admin screen stores the reason in the request (operatorResumes, outside its fingerprint)."""
    p = server_packet(tmp_path); client = Client(p); commands = []; front_calls = []
    wire(monkeypatch, client, commands, front_calls)
    original = worker.run_forwarded
    def first_fails(args, **kwargs):
        if args[2] == 'runner.root_front' and not any(a[2] == 'runner.root_front' for a in commands):
            commands.append(args); return SimpleNamespace(returncode=1)
        return original(args, **kwargs)
    monkeypatch.setattr(worker, 'run_forwarded', first_fails)
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 1
    client.packet['operatorResumes'] = [{'reason': 'admin: runner laptop slept', 'at': '2026-11-09T12:00:00+00:00', 'by': 'admin'}]
    assert packet_hash(client.packet) == client.packet['inputHash']  # the reason is not part of the request identity
    assert worker.run_generation(client, p['subject'], p['runId'], tmp_path / 'runs', GID) == 0
    front_args = [a for a in commands if a[2] == 'runner.root_front']
    assert '--resume' not in front_args[0] and front_args[1][front_args[1].index('--resume') + 1] == 'admin: runner laptop slept'
    assert json.loads((tmp_path / 'runs' / '_root-generation' / GID / 'operator-resumes.json').read_text()) == {'used': 1}
    put = next(c for c in client.calls if c[0] == 'PUT')
    validate_result(json.loads(json.dumps(put[2])), client.packet)  # the server's stored packet, with the reason
