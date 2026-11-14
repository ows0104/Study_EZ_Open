"""Main-Quiz 강의별 Claude 출제(docs/changes/2026-11-14-root-claude-provider): 지정 파일·러너 명령·공급자별 거절 표식."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from runner import agent, model_overrides, root_native_json as n
from studyez_llm import claude
from test_root_content_restriction import restricted  # noqa: F401  (Codex가 거절한 판)
from test_root_native_json import provider

GID = 'd4b5c7e61ce04cff97feb77c89175728'
CLAUDE = 'claude-opus-5-5'


def write_overrides(runs, generations):
    (runs / model_overrides.FILENAME).write_text(json.dumps({'version': 1, 'generations': generations}), encoding='utf-8')


def row(model=CLAUDE, **more):
    return {'model': model, 'reason': 'OpenAI 콘텐츠 제한 3회', 'approval': '「응 구현 시작해줘」', 'at': '2026-11-14T16:00:00+09:00', **more}


def test_지정이_없으면_명령이_그대로다(tmp_path):
    worker = agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path, announce=lambda *_: None)
    job = agent.Job(id=1, subject='감염과 면역', run_id='261109_02', kind=agent.BANK, root_generation_id=GID)
    argv = worker.make_argv(job)
    assert '--model' not in argv and argv[argv.index('--root-generation') + 1] == GID
    write_overrides(tmp_path, {'0' * 32: row()})
    assert worker.make_argv(job) == argv


def test_지정한_요청에만_모델을_붙인다(tmp_path):
    worker = agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path, announce=lambda *_: None)
    write_overrides(tmp_path, {GID: row()})
    job = agent.Job(id=1, subject='감염과 면역', run_id='261109_02', kind=agent.BANK, root_generation_id=GID)
    argv = worker.make_argv(job)
    assert argv[argv.index('--model') + 1] == CLAUDE
    other = agent.Job(id=2, subject='감염과 면역', run_id='261113_02', kind=agent.BANK, root_generation_id='f' * 32)
    assert '--model' not in worker.make_argv(other)
    plain = agent.Job(id=3, subject='감염과 면역', run_id='261109_02', kind=agent.BANK)
    assert '--model' not in worker.make_argv(plain)


@pytest.mark.parametrize('content', [
    'not json',
    json.dumps({'generations': {}}),
    json.dumps({'version': 1, 'generations': {'short': row()}}),
    json.dumps({'version': 1, 'generations': {GID: row(model='opus')}}),
    json.dumps({'version': 1, 'generations': {GID: row(approval='')}}),
])
def test_형식이_틀린_지정은_보류_사유다(tmp_path, content):
    (tmp_path / model_overrides.FILENAME).write_text(content, encoding='utf-8')
    with pytest.raises(model_overrides.OverrideError):
        model_overrides.model_for(tmp_path, GID)


def test_파일이_없으면_지정도_없다(tmp_path):
    assert model_overrides.model_for(tmp_path, GID) is None


def test_codex_거절_표식은_claude_실행을_막지_않는다(restricted, monkeypatch):
    out, packet, calls = restricted
    with pytest.raises(n.ContentRestricted):
        n.require_unblocked(out, model='gpt-6.1-sol')
    with pytest.raises(n.ContentRestricted):
        n.require_unblocked(out)   # 모델을 모르면 지금처럼 막는다
    n.require_unblocked(out, model=CLAUDE)
    # CLI: Claude 모델이면 생성기까지 간다(재개 이유가 실패 단계와 표식을 .resume-<k>/로 옮긴다).
    reached = []
    monkeypatch.setattr(sys, 'argv', ['root_native_json', '--packet', str(out / 'packet.json'), '--out', str(out),
                                      '--model', CLAUDE, '--resume', 'Claude로 전환'])
    monkeypatch.setattr(g, 'run', lambda *a, **k: reached.append(k['model']) or (_ for _ in ()).throw(RuntimeError('stop')))
    assert n.main() == 1 and reached == [CLAUDE]


@pytest.fixture
def claude_restricted(tmp_path):
    out = tmp_path / 'out'; out.mkdir(); packet = f.packet(tmp_path / 'source.txt'); g.write(out / 'packet.json', packet)

    def invoke(prompt, **kwargs):
        if kwargs['cwd'].parent.name == 'generate':
            raise g.codex.SessionError(claude.REFUSAL_MARKER + ' Claude가 안전상 이유로 응답을 거절했다')
        return provider(out)(prompt, **kwargs)
    with pytest.raises(g.codex.SessionError):
        g.run(packet, out, invoke=n.NativeJson(out, invoke=invoke))
    return out


def test_claude_거절은_claude만_막고_이름을_밝힌다(claude_restricted):
    out = claude_restricted
    proof = n.read(out / '.native/generate/content-block.json')['proof']
    assert proof['provider'] == 'claude' and proof['classification']['kind'] == 'model_content_restricted'
    assert 'Claude' in proof['classification']['message']
    with pytest.raises(n.ContentRestricted) as error:
        n.require_unblocked(out, model=CLAUDE)
    assert 'Claude' in str(error.value) and n.classify_error(error.value)['message'] == n.CLAUDE_RESTRICTED_MESSAGE
    n.require_unblocked(out, model='gpt-6.1-sol')


def test_codex_거절_표식의_모양은_그대로다(restricted):
    out, packet, calls = restricted
    assert 'provider' not in n.read(out / '.native/generate/content-block.json')['proof']


def test_재개할_때_다른_모델로_완료된_단계는_다시_돈다(tmp_path):
    from quizbank import connection_generate_v3 as v3gen
    out = tmp_path / 'generation'; out.mkdir()
    ledger = {'pipelineVersion': v3gen.POLICY, 'inputHash': 'p' * 64, 'identity': 'old', 'stages': {
        'normalize': {'status': 'completed', 'inputHash': 'a'}, 'v4-brief-fix': {'status': 'completed', 'inputHash': 'b'},
        'v4-coverage-0-0': {'status': 'failed', 'inputHash': 'c'}}}
    g.write(out / 'ledger.json', ledger)
    for name, model in (('normalize', CLAUDE), ('v4-brief-fix', 'claude-opus-5')):
        g.write(out / (name + '.usage.json'), {'fileReceipt': {'proof': {'model': model}}})
        g.write(out / (name + '.json'), {'stage': name})
    stages = v3gen.Stages({'inputHash': 'p' * 64}, out, 'claude-opus-5', invoke=None, resume='Opus 5로 이어 가기')
    kept = stages.ledger['stages']
    assert 'normalize' not in kept and kept['v4-brief-fix']['status'] == 'completed'
    assert [row['name'] for row in stages.resume_row['superseded']] == ['normalize']
    archived = [p for p in out.glob('.resume-*/normalize.json')]
    assert len(archived) == 1 and not (out / 'normalize.json').exists()
