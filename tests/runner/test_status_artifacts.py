import os

from runner.status import collect


def fixture(root):
    (root / "agent.lock").write_text("pid 10", encoding="utf-8")
    log = root / "agent.demo.log"
    log.write_text("── 응답 받기\n", encoding="utf-8")
    os.utime(log, (100, 100))
    out = root / "demo/bank/current"
    out.mkdir(parents=True)
    rows = [
        {"ProcessId": 10, "ParentProcessId": 1, "CommandLine": "python -m runner agent"},
        {"ProcessId": 20, "ParentProcessId": 10, "CommandLine": "python -m runner bank --run-id demo"},
        {"ProcessId": 21, "ParentProcessId": 20, "CommandLine": f'python -m quizbank.run --out "{out}" --title "실행 중 강의"'},
    ]
    return rows, out, log


def test_quiet_log_uses_only_exact_live_attempt_and_labels_observations(tmp_path):
    rows, out, _ = fixture(tmp_path)
    validation = out / "validation.json"
    validation.write_text("{}", encoding="utf-8")
    os.utime(validation, (120, 120))
    old = out.parent / "other-attempt"
    old.mkdir()
    (old / "result.json").write_text("{}", encoding="utf-8")
    state = collect(tmp_path, rows, now=125)
    job = state.jobs[0]
    assert job.stages[-1] == "산출물 확인 · 구조 검증 결과 저장됨"
    assert job.log_age == 5 and "current" in job.lines[-1]
    assert "최종" not in job.stages[-1]


def test_new_stage_log_takes_priority_and_exit_does_not_become_completion(tmp_path):
    rows, out, log = fixture(tmp_path)
    (out / "bank.json").write_text("{}", encoding="utf-8")
    os.utime(out / "bank.json", (120, 120))
    log.write_text("── 원본·출제 포인트·중복 검수\n", encoding="utf-8")
    os.utime(log, (130, 130))
    assert collect(tmp_path, rows, now=135).jobs[0].stages[-1] == "원본·출제 포인트·중복 검수"
    assert not collect(tmp_path, rows[:1], now=135).jobs


def test_output_outside_the_lecture_is_not_observed(tmp_path):
    rows, out, _ = fixture(tmp_path)
    (out / "result.json").write_text("{}", encoding="utf-8")
    rows[-1]["CommandLine"] = f'python -m quizbank.run --out "{out.parent.parent.parent}"'
    assert collect(tmp_path, rows).jobs[0].stages[-1] == "응답 받기"
