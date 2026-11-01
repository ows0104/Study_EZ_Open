import os
import subprocess

from runner.status import collect, option, tail


def processes():
    return [
        {"ProcessId": 10, "ParentProcessId": 1, "CommandLine": 'python -u -m runner agent 과목 --runs "C:\\my runs"'},
        {"ProcessId": 20, "ParentProcessId": 10, "CommandLine": 'python -m runner bank 과목 --run-id "261001_01"'},
        {"ProcessId": 21, "ParentProcessId": 20, "CommandLine": 'python -m quizbank.run --title "약물대사 (조주연)"'},
        {"ProcessId": 30, "ParentProcessId": 99, "CommandLine": 'python -m runner bank 다른과목 --run-id other'},
    ]


def test_matches_live_agent_and_only_its_jobs_with_real_stage(tmp_path):
    (tmp_path / "agent.lock").write_text("pid 10", encoding="utf-8")
    os.utime(tmp_path / "agent.lock", (100, 100))
    (tmp_path / "agent.261001_01.log").write_text(
        "── 정답 확인·해설 작성\n" + "세부 작업\n" * 40 + "── 외부지식 검토\n검사 중\n", encoding="utf-8")
    state = collect(tmp_path, processes(), now=115)
    assert state.agent_pid == 10 and state.heartbeat_age == 15
    assert len(state.jobs) == 1
    assert state.jobs[0].title == "약물대사 (조주연)"
    assert state.jobs[0].stages == ("정답 확인·해설 작성", "외부지식 검토")


def test_stale_lock_does_not_invent_a_running_job(tmp_path):
    (tmp_path / "agent.lock").write_text("pid 10", encoding="utf-8")
    state = collect(tmp_path, processes()[1:])
    assert state.agent_pid is None and not state.jobs


def test_missing_logs_and_invalid_run_path_are_safe(tmp_path):
    assert not collect(tmp_path, []).jobs
    (tmp_path / "agent.lock").write_text("pid 10", encoding="utf-8")
    rows = processes()
    rows[1]["CommandLine"] = "python -m runner bank --run-id ../elsewhere"
    assert not collect(tmp_path, rows).jobs
    rows[1]["CommandLine"] = "python -m runner bank --run-id demo --points-only"
    job = collect(tmp_path, rows).jobs[0]
    assert job.kind == "출제 포인트 준비" and job.log_age is None and not job.stages


def test_read_error_is_visible_and_keeps_recent_local_events(tmp_path, monkeypatch):
    (tmp_path / "agent.log").write_text("마지막으로 완료한 작업\n", encoding="utf-8")
    def denied():
        raise subprocess.TimeoutExpired("powershell", 12)
    monkeypatch.setattr("runner.status.process_list", denied)
    state = collect(tmp_path)
    assert "확인 실패" in state.error
    assert state.events == ("마지막으로 완료한 작업",)


def test_large_log_tail_is_bounded_and_handles_partial_utf8(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text("큰 기록\n" * 100000 + "최근 단계\n완료\n", encoding="utf-8")
    assert tail(log, 2) == ("최근 단계", "완료")
    assert len(tail(log, 400)) == 400


def test_windows_options_preserve_spaces_and_korean():
    command = 'python -m quizbank.run --raw "C:\\my work\\raw.md" --title "약물대사 (조주연)"'
    assert option(command, "--raw") == "C:\\my work\\raw.md"
    assert option(command, "--title") == "약물대사 (조주연)"
    assert option(command, "--absent") == ""
