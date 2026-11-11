"""Stage inputs in the first message, and the generator's normalize call started by the front stages
(docs/changes/2026-11-11-pipeline-overlap). Synthetic PDFs and fake Codex calls. No model, server or DB."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'quizbank'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from quizbank import connection_generate_v4 as gen4
from quizbank.connection_generate_v3 import early_path
from runner import connection_generation as worker
from runner import root_front as rf
from runner import root_native_json as n
from studyez_contracts.roots import document_hash, map_tree
from studyez_contracts.roots.automation import packet_hash
from studyez_llm import codex
from map_tree_fixture import concept_map
import test_root_front_v3 as t
import test_root_generation_v4 as t4


# ------------------------------------------------------------------ generation stages: the three files come with the message

def normalize_call(tmp_path):
    p = t4.packet(tmp_path)
    out = tmp_path / 'out'
    sources = g.prepare(p, out / 'material')
    return out, {**gen4.normalize_input(p, sources), '_pipeline_version': gen4.POLICY}


def brief_writer(prompts, fail=None):
    def run(prompt, **kwargs):
        work = kwargs['cwd']
        prompts.append(prompt)
        if fail is not None:
            raise fail
        ctx = n.read(work / 'input.json')
        value = f.brief(ctx['sources'])
        value['lecture_id'] = ctx['lecture_id']
        path = work / 'result.json'
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return {'text': json.dumps({'path': 'result.json', 'sha256': n.sha(path)}), 'turns': 1, 'session_id': 'synthetic-native',
                'usage': {'input_tokens': 100, 'output_tokens': 20}, 'models': {kwargs['model']: 20}, 'cost_usd': None, 'duration_ms': 5}
    return run


def test_a_stage_gets_its_task_schema_and_input_in_the_first_message(tmp_path):
    out, ctx = normalize_call(tmp_path)
    prompts = []
    n.NativeJson(out, invoke=brief_writer(prompts))('normalize', ctx, out / 'material', None)
    prompt, work = prompts[0], out / '.native' / 'normalize' / 'work'
    assert prompt.startswith('Read task.md, input.json and acceptance.schema.json from THIS MESSAGE')
    assert 'Do not print or re-read those three files with shell commands' in prompt and sys.executable in prompt
    for name in ('task.md', 'acceptance.schema.json', 'input.json'):
        assert f'===== BEGIN {name} =====' in prompt and f'===== END {name} =====' in prompt
    assert (work / 'task.md').read_text(encoding='utf-8') in prompt                               # the instructions, whole
    assert json.dumps(n.read(work / 'input.json'), ensure_ascii=False, separators=(',', ':')) in prompt   # the same data
    assert json.dumps(n.read(work / 'acceptance.schema.json'), ensure_ascii=False, separators=(',', ':')) in prompt
    # The files stay where the model's local code and the host check read them.
    assert n.read(work / 'input.json') == n.clean(ctx) and (work / 'check_result.py').is_file()


def test_a_stage_too_large_for_the_message_reads_its_files_as_before(tmp_path, monkeypatch):
    out, ctx = normalize_call(tmp_path)
    monkeypatch.setattr(n, 'INLINE_LIMIT', 100)
    prompts = []
    n.NativeJson(out, invoke=brief_writer(prompts))('normalize', ctx, out / 'material', None)
    assert prompts[0].startswith('Read task.md, input.json and acceptance.schema.json. Complete the original task') and 'BEGIN' not in prompts[0]


def test_images_and_inputs_share_the_first_message():
    text = n.first_message([Path('S1-0001.png')], '\n\n===== BEGIN task.md =====\nx\n===== END task.md =====', 'py.exe')
    assert 'Attached to this message, in this order, are the 1 images' in text and text.endswith('===== END task.md =====') and 'py.exe' in text
    assert n.first_message([]) == n.first_message([], '', None) and 'BEGIN' not in n.first_message([])


# ------------------------------------------------------------------ front stages: the inputs follow the task

def test_a_front_stage_gets_its_input_files_after_its_unchanged_task(tmp_path):
    p = t.server_packet(tmp_path); calls = []
    rf.Front(p, tmp_path / 'front', invoke=t.front_codex(calls, issues=True)).run()
    sent = {}
    for stage, prompt in calls:
        sent[stage] = prompt
    for stage, prompt in sent.items():
        work = tmp_path / 'front' / stage
        task = (work / 'task.md').read_text(encoding='utf-8')
        assert prompt.startswith(task) and '===== BEGIN' not in task          # task.md is the stage's own text
        assert '===== BEGIN input.json =====' in prompt and '===== BEGIN material/S1.md =====' in prompt
        assert (work / 'input.json').read_text(encoding='utf-8') in prompt
    assert '===== BEGIN exam-points.json =====' in sent['audit']
    assert '===== BEGIN previous-exam-points.json =====' in sent['point-repair'] and '===== BEGIN source-audit.json =====' in sent['point-repair']
    assert 'exam-points' not in sent['bank']                                   # the bank still never sees the points


def test_front_inputs_that_do_not_fit_are_read_from_the_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, 'INLINE_LIMIT', 10)
    p = t.server_packet(tmp_path); calls = []
    rf.Front(p, tmp_path / 'front', invoke=t.front_codex(calls)).run()
    for stage, prompt in calls:
        assert prompt == (tmp_path / 'front' / stage / 'task.md').read_text(encoding='utf-8')


# ------------------------------------------------------------------ normalize beside the final audit and the bank

def test_the_normalize_input_is_known_before_the_bank_and_the_audits(tmp_path):
    p = t.server_packet(tmp_path)
    derived = rf.Front(p, tmp_path / 'front', invoke=t.front_codex([])).run()
    early = map_tree.provisional_packet(p, derived['conceptMap'], derived['points'], derived['frontStages']['pageCounts'])
    assert early == {k: v for k, v in derived.items() if k not in ('frontStages', 'generationPolicy', 'intakeBank', 'inputHash')}
    sources = [{'source_id': 'S1'}]
    assert gen4.normalize_input(early, sources) == gen4.normalize_input(derived, sources)


def test_the_points_being_final_starts_the_early_call_once(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(rf.Front, 'early_normalize', lambda self, points_from, map_job=None: seen.append(points_from))
    (tmp_path / 'a').mkdir(); (tmp_path / 'b').mkdir()
    rf.Front(t.server_packet(tmp_path / 'a'), tmp_path / 'a' / 'front', invoke=t.front_codex([])).run()
    assert seen == ['point']                                          # an audit without issues: the first points stand
    rf.Front(t.server_packet(tmp_path / 'b'), tmp_path / 'b' / 'front', invoke=t.front_codex([], issues=True)).run()
    assert seen == ['point', 'point-repair']                          # after the repair, before the final audit ends


def v4_front(tmp_path, invoke, **kwargs):
    """A map-tree/3 front whose Map and points are already written (the stages themselves are tested elsewhere)."""
    p = t.server_packet(tmp_path)
    p.update(pipeline=map_tree.PIPELINE3, sourceAssessmentFormat=map_tree.FORMAT3)
    p['inputHash'] = packet_hash(p)
    front = rf.Front(p, tmp_path / 'front', invoke=invoke, generation=tmp_path / 'generation', **kwargs)
    (tmp_path / 'front').mkdir()
    front.prepare()
    for stage, name, value in (('map', 'concept-map.json', concept_map()), ('point', 'exam-points.json', t4.POINTS)):
        (tmp_path / 'front' / stage).mkdir()
        (tmp_path / 'front' / stage / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return p, front


def test_the_front_leaves_the_generators_normalize_answer_for_its_turn(tmp_path):
    prompts = []
    p, front = v4_front(tmp_path, brief_writer(prompts))
    front.early_normalize('point')
    gen = tmp_path / 'generation'
    row = json.loads(early_path(gen, 'normalize').read_text(encoding='utf-8'))
    # The fingerprint is the one the generator will compute for this stage from the derived packet.
    packet = map_tree.provisional_packet(p, rf.text_of(tmp_path / 'front/map/concept-map.json'),
                                         rf.text_of(tmp_path / 'front/point/exam-points.json'), front.pages())
    sources = g.prepare(packet, tmp_path / 'again')
    ctx = {**gen4.normalize_input(packet, sources), '_pipeline_version': 'root-generation/4'}
    assert row['policy'] == 'early-call/1' and row['inputHash'] == document_hash(ctx)
    assert row['raw']['lecture_id'] == ctx['lecture_id'] and row['info']['fileReceipt']['proof']['inputHash'] == row['inputHash']
    # The call's seat is where the generator's own call would have left it; no ledger and no packet were written.
    assert (gen / '.native' / 'normalize' / 'receipt.json').is_file() and n.read(gen / '.native' / 'normalize' / 'work' / 'input.json') == ctx
    assert not (gen / 'ledger.json').exists() and not list(gen.glob('*.json'))
    assert len(prompts) == 1
    front.early_normalize('point')            # a resumed front finds the answer and asks nothing
    assert len(prompts) == 1


def test_a_failed_early_normalize_never_fails_the_front(tmp_path):
    for name, error, kept in (('dropped', codex.SessionError('normalize: stream disconnected before completion: No such host is known.'), False),
                              ('failed', codex.SessionError('normalize: 2400초 안에 끝나지 않았다'), True)):
        (tmp_path / name).mkdir()
        _, front = v4_front(tmp_path / name, brief_writer([], fail=error))
        front.early_normalize('point')        # does not raise
        gen = tmp_path / name / 'generation'
        if kept:   # the stage fails at its turn with this error, as the same call there would have
            row = json.loads(early_path(gen, 'normalize').read_text(encoding='utf-8'))
            assert '2400초 안에 끝나지 않았다' in row['error'] and 'raw' not in row and (gen / '.native' / 'normalize').is_dir()
        else:      # a network drop: nothing is kept against the stage, which runs at its turn with its own retry
            assert not early_path(gen, 'normalize').exists() and not (gen / '.native' / 'normalize').exists()
            assert (gen / '.native' / 'normalize.early').is_dir()


def test_the_early_call_touches_nothing_without_a_generator_folder_or_once_the_generator_started(tmp_path):
    (tmp_path / 'a').mkdir(); (tmp_path / 'b').mkdir(); (tmp_path / 'c').mkdir()
    _, front = v4_front(tmp_path / 'a', lambda *a, **k: pytest.fail('no call'))
    front.generation = None
    front.early_normalize('point')
    assert not (tmp_path / 'a' / 'generation').exists()
    _, front = v4_front(tmp_path / 'b', lambda *a, **k: pytest.fail('no call'))
    (tmp_path / 'b' / 'generation').mkdir()
    (tmp_path / 'b' / 'generation' / 'ledger.json').write_text('{}', encoding='utf-8')
    front.early_normalize('point')
    assert not (tmp_path / 'b' / 'generation' / 'material').exists()
    # map-tree/2 (root-generation/3) is not started early.
    p = t.server_packet(tmp_path / 'c')
    front = rf.Front(p, tmp_path / 'c' / 'front', invoke=lambda *a, **k: pytest.fail('no call'), generation=tmp_path / 'c' / 'generation')
    front.early_normalize('point')
    assert not (tmp_path / 'c' / 'generation').exists()


def test_the_runner_names_the_generator_folder_to_the_front(tmp_path):
    seen = []

    def run(args, cwd):
        seen.append(args)
        return SimpleNamespace(returncode=1)
    out = tmp_path / 'run'
    out.mkdir()
    assert worker.map_tree_front({'pipeline': map_tree.PIPELINE3}, out, run=run) is None
    assert seen[0][seen[0].index('--generation') + 1] == str((out / 'generation').resolve())
    assert seen[0][seen[0].index('--out') + 1] == str((out / 'front').resolve())


def test_the_generator_takes_the_early_answer_and_its_receipt_still_validates(tmp_path):
    """The whole hand-over on one /4 packet: the call made before the ledger exists, then the generator's run and
    the runner's receipt validation (seat, archived inputs, material fingerprints) of that stage."""
    from quizbank.connection_generate_v3 import write_early
    p = t4.packet(tmp_path)
    out = tmp_path / 'out'
    sources = g.prepare(p, out / 'material')
    ctx = {**gen4.normalize_input(p, sources), '_pipeline_version': gen4.POLICY}

    def native(prompt, **kwargs):          # the synthetic model's normalize answer, written as a real stage file
        work = kwargs['cwd']
        value, _ = t4.Model()('normalize', n.read(work / 'input.json'), work / 'material', None)
        path = work / 'result.json'
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return {'text': json.dumps({'path': 'result.json', 'sha256': n.sha(path)}), 'turns': 1, 'session_id': 'synthetic-native',
                'usage': {'input_tokens': 100, 'output_tokens': 20}, 'models': {kwargs['model']: 20}, 'cost_usd': None, 'duration_ms': 5}
    raw, info = n.NativeJson(out, invoke=native)('normalize', ctx, out / 'material', None)
    write_early(out, 'normalize', document_hash(ctx), raw, info)

    model = t4.Model()
    result = g.run(p, out, invoke=model)
    assert 'normalize' not in model.calls
    entry = next(s for s in result['manifest']['stages'] if s['name'] == 'normalize')
    assert entry['status'] == 'completed' and entry['inputHash'] == document_hash(ctx)
    n.validate_all(out, result)            # the early call's seat is this stage's receipt
    _, _, expected = t4.run(tmp_path / 'plain')
    assert result['document'] == expected['document']
