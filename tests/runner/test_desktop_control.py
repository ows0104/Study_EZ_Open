import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from runner import agent, desktop_control as control


def test_auto_start_boundary_and_once_only():
    timer = control.AutoStart(100)
    assert not timer.due(159.999)
    assert timer.due(160)
    assert not timer.due(500)


def test_cancel_never_rearms_even_after_long_wait():
    timer = control.AutoStart(100)
    timer.cancel()
    assert not timer.due(10000)


def test_individual_choices_are_isolated_by_subject_run_and_kind(tmp_path):
    key = control.job_key('과목', '261102_01', 'pre')
    with control.locked(tmp_path):
        control.write(tmp_path, dict(paused=True, jobs={key: 'stopped'}))
    assert control.decision(tmp_path, '과목', '261102_01', 'pre') == 'stopped'
    assert control.decision(tmp_path, '과목', '261102_01', 'bank') == 'paused'
    assert control.decision(tmp_path, '다른 과목', '261102_01', 'pre') == 'paused'
    with control.locked(tmp_path):
        value = control.read(tmp_path)
        value['paused'] = False
        control.write(tmp_path, value)
    assert control.decision(tmp_path, '과목', '261102_01', 'pre') == 'stopped'
    assert control.decision(tmp_path, '과목', '261102_01', 'bank') == ''


def test_corrupted_choices_fail_closed(tmp_path):
    (tmp_path / control.CONTROL).write_text('{broken', encoding='utf-8')
    assert control.decision(tmp_path) == 'paused'


def test_simultaneous_windows_do_not_lose_choices(tmp_path):
    def change(n):
        with control.locked(tmp_path):
            value = control.read(tmp_path)
            value['jobs'][str(n)] = 'stopped'
            time.sleep(.01)
            control.write(tmp_path, value)
    threads = [threading.Thread(target=change, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert len(control.read(tmp_path)['jobs']) == 6


class Client:
    base, token = 'http://test.invalid', 'test'

    def __init__(self):
        self.puts = []

    def call(self, method, path, body=None):
        assert method == 'PUT'
        self.puts.append(body)
        return {'job': {'cancelRequested': False}, 'applied': True}


def test_pause_prevents_claim_and_sweep(tmp_path):
    worker = agent.Agent(None, tmp_path, tmp_path)
    with control.locked(tmp_path):
        control.write(tmp_path, dict(paused=True, jobs={}))
    worker.claim = lambda *args: pytest.fail('must not claim')
    worker.sweep_subjects = lambda: pytest.fail('must not sweep')
    assert worker.tick() is False
    worker.sweep()


def test_pause_interrupts_real_child_and_preserves_output(tmp_path, monkeypatch):
    client = Client()
    worker = agent.Agent(client, tmp_path, tmp_path, announce=lambda *_: None)
    job = agent.Job(1, '과목', '261102_01', kind='pre')
    child = "from pathlib import Path; import time; Path('checkpoint.txt').write_text('saved'); time.sleep(120)"
    def pause():
        deadline = time.monotonic() + 10
        while not (tmp_path / 'checkpoint.txt').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        with control.locked(tmp_path):
            control.write(tmp_path, dict(paused=True, jobs={}))
    thread = threading.Thread(target=pause)
    thread.start()
    code, _ = worker._run([sys.executable, '-c', child], tmp_path / 'child.log', job)
    thread.join(timeout=5)
    assert code == agent.HELD_BY_DESKTOP
    assert (tmp_path / 'checkpoint.txt').read_text() == 'saved'
    worker.hold_for_desktop(job)
    assert client.puts[-1]['state'] == 'held'
    assert client.puts[-1]['stage'] == control.GLOBAL_STAGE


def test_resume_racing_with_stop_acknowledgement_requeues(tmp_path):
    client = Client()
    worker = agent.Agent(client, tmp_path, tmp_path)
    worker.hold_for_desktop(agent.Job(1, '과목', '261102_01'))
    assert [row['state'] for row in client.puts] == ['held', 'queued']


def test_cancel_wins_over_global_pause_without_touching_other_kind(tmp_path):
    client = Client()
    worker = agent.Agent(client, tmp_path, tmp_path)
    with control.locked(tmp_path):
        control.write(tmp_path, dict(paused=True, jobs={control.job_key('과목', '261102_01', 'pre'): 'canceled'}))
    worker.hold_for_desktop(agent.Job(1, '과목', '261102_01'))
    assert client.puts[-1]['state'] == 'canceled'


def test_existing_agent_is_connected_without_launch(tmp_path, monkeypatch):
    from runner import desktop
    runs = tmp_path / 'runs'
    runs.mkdir()
    (runs / 'agent.lock').write_text('pid 123')
    monkeypatch.setattr(desktop, 'process_list', lambda: [dict(ProcessId=123, ParentProcessId=0, CommandLine='python -m runner agent')])
    monkeypatch.setattr(desktop, 'launch', lambda *a, **k: pytest.fail('must not duplicate runner'))
    desktop.ensure_agent(tmp_path)


def test_process_query_failure_does_not_launch(tmp_path, monkeypatch):
    from runner import desktop
    def fail():
        raise OSError('CIM unavailable')
    monkeypatch.setattr(desktop, 'process_list', fail)
    monkeypatch.setattr(desktop, 'launch', lambda *a, **k: pytest.fail('must not guess idle'))
    with pytest.raises(OSError):
        desktop.ensure_agent(tmp_path)


def test_sweep_holds_only_the_stopped_kind_and_keeps_notes(tmp_path):
    from runner import publish
    plan = publish.LecturePlan(subject='과목', run_id='261102_01', item=None)
    for kind in ('notes_current', 'pre_apkg', 'main_apkg'):
        path = tmp_path / (kind + '.bin')
        path.write_bytes(b'preserve')
        plan.uploads.append(publish.Upload(kind, path))
    plan.pre_items = tmp_path / 'pre_items.json'
    plan.main_items = tmp_path / 'main_items.json'
    with control.locked(tmp_path):
        control.write(tmp_path, dict(paused=False, jobs={control.job_key('과목', '261102_01', 'pre'): 'stopped'}))
    publish.hold_desktop(plan, tmp_path)
    assert [u.kind for u in plan.uploads] == ['notes_current', 'main_apkg']
    assert plan.pre_items is None and plan.main_items is not None
    assert (tmp_path / 'pre_apkg.bin').read_bytes() == b'preserve'


@pytest.mark.skipif(os.name != 'nt', reason='Windows desktop shortcut')
def test_shortcut_installer_supports_korean_filename_in_windows_powershell(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(root / 'scripts/install-runner-desktop.ps1'), '-Destination', str(tmp_path)],
                   capture_output=True, timeout=20,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0, (result.stdout + result.stderr).decode('utf-8', errors='replace')
    assert (tmp_path / 'Study EZ 러너.lnk').is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ['Study EZ 러너.lnk']
