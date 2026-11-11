"""No model calls: overlap guards, process trees and failure telemetry."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from studyez_llm import codex
from studyez_llm.execution import AlreadyRunning, exclusive, run_process


def test_overlap_is_blocked_but_lock_releases_after_failure(monkeypatch, tmp_path):
    monkeypatch.setenv('STUDYEZ_CODEX_USAGE_DIR', str(tmp_path))
    request={'request': 'same'}
    with exclusive(request):
        with pytest.raises(AlreadyRunning):
            with exclusive(request):
                raise AssertionError('must not execute')
        with exclusive({'request': 'different'}):
            pass
    with exclusive(request):
        pass


def test_call_failure_is_logged_without_prompt_or_reply(monkeypatch, tmp_path):
    monkeypatch.setenv('STUDYEZ_CODEX_USAGE_DIR', str(tmp_path/'usage'))
    monkeypatch.setenv('STUDYEZ_CODEX_BIN', 'not-invoked')
    def fail(*args, **kwargs):
        raise codex.SessionError('failure details must not enter telemetry')
    monkeypatch.setattr(codex, '_run', fail)
    with pytest.raises(codex.SessionError):
        codex.run('private prompt', blind=True)
    rows=list((tmp_path/'usage').glob('*/*.json'))
    assert len(rows)==1
    body=rows[0].read_text(encoding='utf-8');row=json.loads(body)
    assert row['status']=='failed' and row['partialUsageUnknown'] and row['usage'] is None
    assert 'private prompt' not in body and 'failure details' not in body


def test_timeout_terminates_child_too(tmp_path):
    # The grandchild would write this after the caller has timed out if orphaned.
    marker=tmp_path/'orphan.txt'
    child="import time; from pathlib import Path; time.sleep(2); Path("+repr(str(marker))+").write_text('orphan')"
    parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"+repr(child)+"]); time.sleep(30)"
    with pytest.raises(subprocess.TimeoutExpired):
        run_process([sys.executable,'-c',parent],input='',cwd=tmp_path,timeout=0.8)
    time.sleep(2.2)
    assert not marker.exists(), 'A child survived the timeout and continued work'


def test_normal_process_keeps_unicode_and_exit_status(tmp_path):
    result=run_process([sys.executable,'-c',"import sys; print(sys.stdin.read()); sys.exit(3)"],
                       input='검증',cwd=tmp_path,timeout=10)
    assert result.returncode==3 and result.stdout.strip()=='검증'


# ------------------------------------------------------------------ machine-wide session slots, network drops
# docs/changes/2026-11-11-pipeline-resilience

def test_session_slots_cap_the_machine_and_come_back(monkeypatch, tmp_path):
    from studyez_llm.execution import slot, slot_limit
    monkeypatch.setenv('STUDYEZ_CODEX_USAGE_DIR', str(tmp_path))
    monkeypatch.delenv('STUDYEZ_CODEX_SLOTS', raising=False)
    assert slot_limit() == 8
    monkeypatch.setenv('STUDYEZ_CODEX_SLOTS', '2'); assert slot_limit() == 2
    monkeypatch.setenv('STUDYEZ_CODEX_SLOTS', 'x'); assert slot_limit() == 8

    class Full(Exception):
        pass

    def no_wait(seconds):
        raise Full()
    told = []
    with slot(2) as first, slot(2) as second:
        assert {first, second} == {0, 1}
        with pytest.raises(Full):   # a third session waits; here the wait is the signal
            with slot(2, sleep=no_wait, waiting=lambda: told.append(1)):
                raise AssertionError('must not run')
        assert told == [1]
    with slot(2) as again:           # both came back
        assert again == 0
    with pytest.raises(RuntimeError):
        with slot(1):
            raise RuntimeError('the call failed')
    with slot(1) as after_failure:   # a failed call gives its slot back
        assert after_failure == 0


def test_a_waiting_session_starts_when_a_slot_is_free(monkeypatch, tmp_path):
    import threading
    from studyez_llm.execution import slot
    monkeypatch.setenv('STUDYEZ_CODEX_USAGE_DIR', str(tmp_path))
    release, order = threading.Event(), []

    def holder():
        with slot(1):
            order.append('first in')
            release.wait(20)
            order.append('first out')
    thread = threading.Thread(target=holder); thread.start()
    while not order:
        time.sleep(0.01)

    def waiting():
        order.append('second waits')
        release.set()
    with slot(1, poll=0.01, waiting=waiting):
        order.append('second in')
    thread.join()
    assert order == ['first in', 'second waits', 'first out', 'second in']


def test_codex_run_holds_a_slot_for_the_call(monkeypatch, tmp_path):
    from studyez_llm import execution
    monkeypatch.setenv('STUDYEZ_CODEX_USAGE_DIR', str(tmp_path / 'usage'))
    monkeypatch.setenv('STUDYEZ_CODEX_SLOTS', '1')
    seen = []

    def inside(*args, **kwargs):
        with pytest.raises(ZeroDivisionError):   # the only slot is held while the call runs
            with execution.slot(sleep=lambda s: 1 / 0):
                raise AssertionError('must not run')
        seen.append('ran')
        return {'usage': {}, 'session_id': 's', 'text': '{}'}
    monkeypatch.setattr(codex, '_run', inside)
    codex.run('prompt', blind=False, cwd=tmp_path)
    with execution.slot() as free:
        assert seen == ['ran'] and free == 0


def test_network_drops_are_told_from_other_failures():
    drop = codex.SessionError('x: Reconnecting... 5/5 (stream disconnected before completion: No such host is known. (os error 11001))')
    assert codex.network_failure(drop)
    assert codex.network_failure(codex.SessionError('x: codex가 1로 끝났다\nerror sending request for url (https://chatgpt.com/…)'))
    try:
        try:
            raise drop
        except codex.SessionError as cause:
            raise ValueError('stage failed') from cause
    except ValueError as wrapped:
        assert codex.network_failure(wrapped)   # found anywhere in the cause chain
    assert not codex.network_failure(ValueError('stream disconnected in a contract message'))   # not a CLI session
    assert not codex.network_failure(codex.SessionError('x: 2400초 안에 끝나지 않았다'))
    assert not codex.network_failure(codex.SessionError('x: codex 세션 완료 이벤트가 없다 (출력 중단)'))
    assert not codex.network_failure(codex.SessionError('stream disconnected: limited access to this content for safety reasons'))
    assert not codex.network_failure(codex.SessionError('stream disconnected: you have hit your usage limit'))
    try:
        try:
            raise subprocess.TimeoutExpired('codex', 5)
        except subprocess.TimeoutExpired as cause:
            raise codex.SessionError('x: connection reset') from cause
    except codex.SessionError as timed_out:
        assert not codex.network_failure(timed_out)


def test_waiting_for_the_network_ends_when_a_host_resolves_or_the_limit_passes():
    now, slept, asked = [0.0], [], []

    def clock():
        return now[0]

    def sleep(seconds):
        slept.append(seconds); now[0] += seconds

    def down(host, port):
        asked.append(host)
        raise OSError(11001, 'getaddrinfo failed')

    def back_after_two(host, port):
        asked.append(host)
        if len(slept) < 2:
            raise OSError(11001, 'getaddrinfo failed')
        return [('ok',)]
    assert codex.wait_for_network(resolve=back_after_two, sleep=sleep, clock=clock, step=15, limit=900) is True
    assert slept == [15, 15]
    slept.clear(); asked.clear(); now[0] = 0.0
    assert codex.wait_for_network(resolve=down, sleep=sleep, clock=clock, step=15, limit=60) is False
    assert sum(slept) == 60 and set(asked) == set(codex.NETWORK_HOSTS)
