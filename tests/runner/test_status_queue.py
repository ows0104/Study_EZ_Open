import subprocess

from runner.status_queue import QueueReader, queue_text, read_server


def row(run_id, title, state="queued"):
    return dict(runId=run_id, title=title, kind="bank", subject="약리학", state=state,
                stage="출제", stageIndex=2, stageTotal=8, elapsedSeconds=120, etaSeconds=300)


def test_queue_preserves_server_order_and_names():
    value = dict(waiting=[row("second", "두번째"), row("first", "첫번째")], running=[], held=[], jobs=[])
    content = queue_text(value, 1000)
    assert content.index("1. 두번째") < content.index("2. 첫번째")
    assert "대기 2" in content


def test_transient_failure_retains_last_snapshot_and_backs_off(tmp_path, monkeypatch):
    calls = []
    def fetch(root):
        calls.append(root)
        if len(calls) > 1:
            raise subprocess.TimeoutExpired("server", 20)
        return {"jobs": [row("one", "강의")]}
    now = [0]
    monkeypatch.setattr("runner.status_queue.time.monotonic", lambda: now[0])
    monkeypatch.setattr("runner.status_queue.read_server", fetch)
    reader = QueueReader(tmp_path)
    value, checked, error = reader.read()
    assert not error
    now[0] = 10
    assert reader.read() == (value, checked, "")
    assert len(calls) == 1
    now[0] = 31
    stale, stamp, error = reader.read()
    assert stale == value and stamp == checked and "조회 실패" in error
    now[0] = 32
    reader.read()
    assert len(calls) == 2


def test_server_runtime_does_not_inherit_uv_interpreter_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONHOME", "uv-home")
    monkeypatch.setenv("UV_INTERNAL__PYTHONHOME", "uv-home")
    def run(command, **kwargs):
        assert "PYTHONHOME" not in kwargs['env']
        assert "UV_INTERNAL__PYTHONHOME" not in kwargs['env']
        assert kwargs['timeout'] == 20
        return subprocess.CompletedProcess(command, 0, stdout='{"jobs": []}')
    monkeypatch.setattr("runner.status_queue.subprocess.run", run)
    assert read_server(tmp_path) == {'jobs': []}
