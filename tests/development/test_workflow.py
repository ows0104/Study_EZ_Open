import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import development as dev
import maintenance


@pytest.fixture
def change(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, 'ROOT', tmp_path)
    templates = tmp_path / 'docs/development/templates'
    templates.mkdir(parents=True)
    for name in ('intent', 'spec', 'plan', 'release'):
        (templates / f'{name}.md').write_text('{{title}}\nReady', encoding='utf-8')
    folder = dev.create('test-change', 'Test', 'site', ['unit'])
    dev.main(['approve', 'test-change', '--phase', 'build', '--evidence', 'Actual user message', '--scope', 'local'])
    return folder


def test_changed_design_or_required_checks_invalidates_build_approval(change):
    folder, state = dev.load('test-change')
    assert not dev.gate(folder, state, 'build')
    (folder / 'spec.md').write_text('Different behavior', encoding='utf-8')
    assert dev.gate(folder, state, 'build')
    dev.main(['approve', 'test-change', '--phase', 'build', '--evidence', 'Reapproved', '--scope', 'local'])
    folder, state = dev.load('test-change')
    state['required_checks'] = []
    dev.save(folder, state)
    assert dev.gate(folder, state, 'build')


def test_failed_latest_check_and_code_change_block_release(change):
    assert dev.main(['verify', 'test-change', '--check', 'unit', '--', sys.executable, '-c', 'pass']) == 0
    dev.main(['review', 'test-change', '--summary', 'Reviewed code'])
    folder, state = dev.load('test-change')
    assert not dev.gate(folder, state, 'release')
    assert dev.gate(folder, state, 'deploy')
    with pytest.raises(ValueError, match='candidate'):
        dev.main(['approve', 'test-change', '--phase', 'deploy', '--evidence', 'User deploy approval', '--scope', 'staging'])
    assert dev.main(['verify', 'test-change', '--check', 'unit', '--', sys.executable, '-c', 'raise SystemExit(3)']) == 3
    folder, state = dev.load('test-change')
    assert dev.gate(folder, state, 'release')
    (dev.ROOT / 'web').mkdir()
    (dev.ROOT / 'web/file.ts').write_text('changed', encoding='utf-8')
    assert dev.gate(folder, state, 'deploy')


def test_missing_command_records_failure(change):
    assert dev.main(['verify', 'test-change', '--check', 'unit', '--', 'nonexistent-studyez-command']) == 127
    _, state = dev.load('test-change')
    assert state['checks'][-1]['exit_code'] == 127


def test_changed_release_plan_invalidates_deployment_approval(change):
    dev.main(['verify', 'test-change', '--check', 'unit', '--', sys.executable, '-c', 'pass'])
    dev.main(['review', 'test-change', '--summary', 'Reviewed'])
    folder, state = dev.load('test-change')
    # A release without a concrete artifact may be reviewed, but cannot be deployed.
    assert dev.gate(folder, state, 'deploy')
    (folder / 'release.md').write_text('Different deployment target', encoding='utf-8')
    assert dev.gate(folder, state, 'deploy')


def test_concurrent_verifications_preserve_all_records(change):
    from concurrent.futures import ThreadPoolExecutor
    folder, state = dev.load('test-change')
    state['required_checks'] = ['unit', 'other']
    dev.save(folder, state)
    dev.main(['approve', 'test-change', '--phase', 'build', '--evidence', 'User', '--scope', 'local'])
    def verify(name):
        return dev.main(['verify', 'test-change', '--check', name, '--', sys.executable,
                         '-c', 'import time; time.sleep(0.1)'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(verify, ['unit', 'other'])) == [0, 0]
    _, state = dev.load('test-change')
    assert {row['name'] for row in state['checks']} == {'unit', 'other'}
    assert len({row['log'] for row in state['checks']}) == 2


def test_new_change_cannot_escape_root_or_overwrite(change):
    with pytest.raises(ValueError):
        dev.change_dir('../outside')
    with pytest.raises(FileExistsError):
        dev.create('test-change', 'Replace', 'site', ['unit'])


def test_monitor_deduplicates_and_distinguishes_observation_failure():
    created = []
    def create(*args):
        created.append(args)
        return f'incident-{len(created)}'
    state = {}
    probe = {'id': 'api'}
    unknown = {'status': 'unknown', 'reason': 'observation_failed'}
    healthy = {'status': 'healthy', 'reason': 'ok'}
    update = lambda result: maintenance.reconcile(state, probe, result, '2026-10-26T00:00:00Z', 2, create)
    assert update(unknown) == []
    assert update(unknown)[0]['status'] == 'unknown'
    assert update(unknown) == []
    assert len(created) == 1
    assert update(healthy)[0]['type'] == 'recovered'
    assert update(healthy) == []
    update(unknown)
    assert update(unknown)[0]['change'] == 'incident-2'


def test_monitor_unexpected_body_is_not_healthy(monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'<html>proxy page</html>'
    monkeypatch.setattr(maintenance.urllib.request, 'urlopen', lambda *a, **k: Response())
    assert maintenance.observe({'url': 'https://example.invalid/health', 'kind': 'api'})['status'] == 'failed'
