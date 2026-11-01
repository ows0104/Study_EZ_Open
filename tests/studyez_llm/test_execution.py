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
