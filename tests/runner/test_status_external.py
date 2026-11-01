import json

from runner.status import collect


def register(root, **extra):
    registry = root / "runs/status-jobs"
    registry.mkdir(parents=True, exist_ok=True)
    data = dict(id="audit", label="1.66 추가 대조", owner="검수 세션", script="work/qa/audit.py",
                outputs="work/qa/results", log="work/qa/progress.log",
                targets={"261012_02": "항생제 원리"})
    data.update(extra)
    (registry / "audit.json").write_text(json.dumps(data), encoding="utf-8")
    return root / "runs"


def test_active_audit_is_visible_without_agent_and_uv_duplicates_are_coalesced(tmp_path):
    runs = register(tmp_path)
    output = tmp_path / "work/qa/results/261012_02/web-audit"
    output.mkdir(parents=True)
    (output / "context.json").write_text(json.dumps({"title": "항생제 치료의 기본 원리"}), encoding="utf-8")
    rows = [
        {"ProcessId": 10, "ParentProcessId": 1, "CommandLine": "python ../work/qa/audit.py"},
        {"ProcessId": 11, "ParentProcessId": 10, "CommandLine": "python ../work/qa/audit.py"},
        {"ProcessId": 12, "ParentProcessId": 11, "CommandLine": f'python "{tmp_path}/work/qa/audit.py" "{output.parent}"'},
        {"ProcessId": 13, "ParentProcessId": 12, "Name": "codex.exe", "CommandLine": "codex.exe exec --json -"},
    ]
    state = collect(runs, rows)
    assert state.agent_pid is None
    assert len(state.jobs) == 1 and state.jobs[0].pid == 12
    assert state.jobs[0].title == "항생제 치료의 기본 원리"
    assert state.jobs[0].owner == "검수 세션" and "CLI" in state.jobs[0].stages[-1]
    # A saved started record cannot masquerade as a live process after exit.
    assert not collect(runs, []).jobs


def test_quiet_fixed_target_and_changed_source_commands_are_supported(tmp_path):
    runs = register(tmp_path, run_id="261007_02", targets={"261007_02": "체액1 v4"})
    state = collect(runs, [{"ProcessId": 40, "ParentProcessId": 1, "CommandLine": "python work/qa/audit.py"}])
    assert state.jobs[0].title == "체액1 v4" and state.jobs[0].log_age is None
    runs = register(tmp_path)
    state = collect(runs, [{"ProcessId": 50, "ParentProcessId": 1, "CommandLine": "python work/qa/audit.py 261012_02"}])
    assert state.jobs[0].title == "항생제 원리"


def test_completed_output_does_not_override_live_cli_or_invent_jobs(tmp_path):
    runs = register(tmp_path, run_id="261012_02")
    output = tmp_path / "work/qa/results/261012_02"
    output.mkdir(parents=True)
    (output / "ready.json").write_text('{"questions":91}', encoding="utf-8")
    log = tmp_path / "work/qa/progress.log"
    log.write_text('{"run_id":"261012_02","applied":true}\n', encoding="utf-8")
    rows = [{"ProcessId": 12, "ParentProcessId": 1, "CommandLine": "python work/qa/audit.py"},
            {"ProcessId": 13, "ParentProcessId": 12, "Name": "codex.exe", "CommandLine": "codex.exe exec"}]
    assert "CLI" in collect(runs, rows).jobs[0].stages[-1]
    assert "반영·확인" in collect(runs, rows[:1]).jobs[0].stages[-1]
    state = collect(runs, [])
    assert not state.jobs and any("반영 완료" in line for line in state.events)


def test_invalid_registration_and_unrelated_script_are_ignored(tmp_path):
    runs = register(tmp_path)
    assert not collect(runs, [{"ProcessId": 5, "ParentProcessId": 1, "CommandLine": "python work/other/audit.py"}]).jobs
    register(tmp_path, outputs="../../outside")
    assert not collect(runs, [{"ProcessId": 5, "ParentProcessId": 1, "CommandLine": "python work/qa/audit.py"}]).jobs
    (runs / "status-jobs/audit.json").write_text("{partial", encoding="utf-8")
    assert not collect(runs, []).jobs


def test_metadata_restoration_does_not_claim_an_extra_content_review(tmp_path):
    runs = register(tmp_path, activity="metadata", state_file="work/qa/worker.json",
                    label="이전 검수본 복원 · 학습 구조/근거 연결",
                    stages={"waiting_for_worker": "대기 · 생성 작업 자리 기다리는 중",
                            "metadata_only": "이전 검수본 복원 · 학습 구조/근거 연결"})
    marker = tmp_path / "work/qa/worker.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"pid":50,"state":"waiting_for_worker"}', encoding="utf-8")
    rows = [{"ProcessId": 50, "ParentProcessId": 1, "CommandLine": "python work/qa/audit.py"},
            {"ProcessId": 51, "ParentProcessId": 50, "Name": "codex.exe", "CommandLine": "codex.exe exec"}]
    assert "기다리는 중" in collect(runs, rows).jobs[0].stages[-1]
    marker.write_text('{"pid":50,"state":"metadata_only","run_id":"261012_02"}', encoding="utf-8")
    job = collect(runs, rows).jobs[0]
    assert job.title == "항생제 원리"
    assert job.stages[-1] == "이전 검수본 복원 · 학습 구조/근거 연결"
    marker.write_text('{"pid":99,"state":"waiting_for_worker"}', encoding="utf-8")
    assert "기다리는 중" not in collect(runs, rows).jobs[0].stages[-1]
