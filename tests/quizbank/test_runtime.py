import hashlib
import json

from quizbank import runtime


def setup_source(tmp_path, monkeypatch):
    root = tmp_path / 'deployed-copy'
    prompt = root / 'content/prompts/bank/bankPrompt.md'
    prompt.parent.mkdir(parents=True)
    prompt.write_text('<!--\nVersion: 1.66\n-->\n문항 품질 원칙\n원본 기준', encoding='utf-8')
    code = root / 'quizbank/run.py'
    code.parent.mkdir()
    code.write_text('actual deployed code', encoding='utf-8')
    monkeypatch.setattr(runtime, 'ROOT', root)
    return root, prompt, code


def test_records_deployed_source_instead_of_callers_working_directory(tmp_path, monkeypatch):
    root, prompt, code = setup_source(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / 'output'
    runtime.record(out, 'started')
    r = json.loads((out / 'runtime.json').read_text(encoding='utf-8'))['started']
    assert r['sourceRoot'] == str(root)
    assert r['commonPromptVersion'] == '1.66'
    assert r['commonPromptSha256'] == hashlib.sha256(prompt.read_bytes()).hexdigest()
    assert r['codeSha256']['quizbank/run.py'] == hashlib.sha256(code.read_bytes()).hexdigest()


def test_detects_common_rules_changed_without_a_version_change(tmp_path, monkeypatch):
    _, prompt, _ = setup_source(tmp_path, monkeypatch)
    out = tmp_path / 'output'
    runtime.record(out, 'started')
    prompt.write_text(prompt.read_text(encoding='utf-8') + '\n추가 규칙', encoding='utf-8')
    runtime.record(out, 'finished')
    r = json.loads((out / 'runtime.json').read_text(encoding='utf-8'))
    assert r['started']['commonPromptVersion'] == r['finished']['commonPromptVersion']
    assert r['contractUnchanged'] is False


def test_failed_run_retains_start_and_new_invocation_clears_old_completion(tmp_path, monkeypatch):
    setup_source(tmp_path, monkeypatch)
    out = tmp_path / 'output'
    runtime.record(out, 'started')
    runtime.record(out, 'failed')
    r = json.loads((out / 'runtime.json').read_text(encoding='utf-8'))
    assert r['contractUnchanged'] is True and 'started' in r and 'failed' in r
    runtime.record(out, 'started')
    assert set(json.loads((out / 'runtime.json').read_text(encoding='utf-8'))) == {'started'}
