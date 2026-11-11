"""scripts/ci_scope.py: 문서·기록만 바뀌면 전체 검사를, 러너 쪽이 안 바뀌면 Windows 검사를 건너뛴다."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import ci_scope  # noqa: E402


def test_docs_and_runs_only_skip_everything():
    assert ci_scope.classify(['docs/changes/x/README.md', 'runs/_pairs/a.json', 'etc/a.html',
                              'CLAUDE.md', 'web/CLAUDE.md', 'quizgen/README.md']) == {'tests': False, 'windows': False}


def test_docs_read_by_tests_still_run_tests():
    for path in ('docs/samples/a.json', 'docs/prompt-architecture.md', 'docs/development/templates/plan.md'):
        assert ci_scope.classify([path])['tests'] is True, path


def test_prompt_markdown_outside_root_is_code():
    assert ci_scope.classify(['web/src/bank/bankPrompt.md']) == {'tests': True, 'windows': False}
    assert ci_scope.classify(['content/prompts/a.md']) == {'tests': True, 'windows': True}


def test_site_only_change_skips_windows():
    assert ci_scope.classify(['web/src/App.tsx', 'server/app/main.py', 'server/tests/test_a.py']) == {'tests': True, 'windows': False}


def test_runner_side_change_runs_windows():
    for path in ('runner/agent.py', 'quizgen/x.py', 'studyez_contracts/a.py', 'scripts/a.ps1',
                 'server/deploy.ps1', 'requirements.txt', '.github/workflows/deploy.yml', 'bridge/a.js'):
        assert ci_scope.classify([path]) == {'tests': True, 'windows': True}, path


def test_unknown_event_or_failure_runs_everything(tmp_path, monkeypatch):
    event = tmp_path / 'event.json'; event.write_text(json.dumps({}))
    out = tmp_path / 'out'
    monkeypatch.setenv('GITHUB_REPOSITORY', 'o/r'); monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event)); monkeypatch.setenv('GITHUB_OUTPUT', str(out))
    ci_scope.main()
    assert out.read_text() == 'tests=true\nwindows=true\n'
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'push')  # payload lacks GITHUB_SHA -> error -> everything
    monkeypatch.delenv('GITHUB_SHA', raising=False)
    event.write_text(json.dumps({'before': 'a' * 40}))
    out.write_text('')
    ci_scope.main()
    assert out.read_text() == 'tests=true\nwindows=true\n'


def test_merge_with_same_tree_as_passed_pr_head_skips(monkeypatch, tmp_path):
    calls = {
        'repos/o/r/compare/b...m': {'files': [{'filename': 'web/src/a.tsx'}, {'filename': 'runner/a.py'}]},
        'repos/o/r/commits/m': {'parents': [{'sha': 'b'}, {'sha': 'h'}], 'commit': {'tree': {'sha': 'T'}}},
        'repos/o/r/commits/h': {'parents': [{'sha': 'x'}], 'commit': {'tree': {'sha': 'T'}}},
        'repos/o/r/commits/h/check-runs?per_page=100': {'check_runs': [
            {'name': 'Tests and build', 'conclusion': 'success'},
            {'name': 'Windows runner checks', 'conclusion': 'success'}]},
    }
    monkeypatch.setattr(ci_scope, '_gh', lambda *a: calls[a[-1]])
    event = tmp_path / 'e.json'; event.write_text(json.dumps({'before': 'b'}))
    env = {'GITHUB_REPOSITORY': 'o/r', 'GITHUB_EVENT_NAME': 'push', 'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': 'm'}
    assert ci_scope.decide(env)[0] == {'tests': False, 'windows': False}
    calls['repos/o/r/commits/h']['commit']['tree']['sha'] = 'OTHER'  # master moved: merge differs from PR head
    assert ci_scope.decide(env)[0] == {'tests': True, 'windows': True}
