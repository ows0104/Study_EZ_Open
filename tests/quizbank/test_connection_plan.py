import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from quizbank import connection_plan as package
from studyez_contracts.learning_links import LinkValidationError
from tests.contracts.test_learning_links import materialize


def build(folder, out):
    return package.build_package(folder / "review.json", folder / "bank.json", folder / "sources.json", out)


def test_package_is_deterministic_offline_and_preserves_all_inputs(tmp_path, monkeypatch):
    folder = tmp_path / "input"
    review, _ = materialize(folder)
    before = {p: p.read_bytes() for p in folder.iterdir()}
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    first, second = tmp_path / "one", tmp_path / "two"
    result = build(folder, first)
    build(folder, second)
    assert result["coverage_counts"] == {"covered": 1, "gap": 1, "unknown": 1}
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}
    assert {p: p.read_bytes() for p in folder.iterdir()} == before
    normalized = json.loads((first / "learning-links.json").read_text(encoding="utf-8"))
    assert normalized == review
    complete = json.loads((first / "complete.json").read_text())
    for name, digest in complete["outputs"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
    validation = json.loads((first / "validation.json").read_text())
    assert validation["medical_validation"] == "not_performed"
    assert validation["publication"] == "not_authorized"
    assert validation["learner_state"] == "not_created"


def test_existing_output_is_untouched(tmp_path):
    materialize(tmp_path / "input")
    out = tmp_path / "existing"
    out.mkdir()
    (out / "sentinel").write_text("keep")
    with pytest.raises(LinkValidationError, match="already exists"):
        build(tmp_path / "input", out)
    assert list(out.iterdir()) == [out / "sentinel"]


@pytest.mark.parametrize("change", ["source", "bank", "review", "manifest", "duplicate-key", "nan"])
def test_invalid_inputs_never_create_complete_output(tmp_path, change):
    folder, out = tmp_path / "input", tmp_path / "out"
    materialize(folder)
    if change == "source":
        (folder / "source.txt").write_text("changed")
    elif change == "bank":
        with (folder / "bank.json").open("a") as stream:
            stream.write(" ")
    elif change == "review":
        raw = json.loads((folder / "review.json").read_text(encoding="utf-8"))
        raw["mappings"][0]["question_id"] = "missing"
        (folder / "review.json").write_text(json.dumps(raw), encoding="utf-8")
    elif change == "manifest":
        raw = json.loads((folder / "sources.json").read_text())
        raw["sources"][0]["path"] = "missing.txt"
        (folder / "sources.json").write_text(json.dumps(raw))
    elif change == "duplicate-key":
        (folder / "review.json").write_text('{"x":1,"x":2}')
    else:
        (folder / "review.json").write_text('{"x":NaN}')
    with pytest.raises((ValueError, OSError)):
        build(folder, out)
    assert not out.exists()


def test_input_changes_during_writing_leave_failure_without_completion(tmp_path, monkeypatch):
    folder, out = tmp_path / "input", tmp_path / "out"
    materialize(folder)
    write = package.write_json
    def changing_write(path, value):
        write(path, value)
        if path.name == "validation.json":
            (folder / "source.txt").write_text("changed concurrently")
    monkeypatch.setattr(package, "write_json", changing_write)
    with pytest.raises(LinkValidationError, match="changed during packaging"):
        build(folder, out)
    assert not (out / "complete.json").exists()
    assert json.loads((out / "failure.json").read_text())["status"] == "incomplete"


def test_io_failure_preserves_partial_outputs_without_completion(tmp_path, monkeypatch):
    folder, out = tmp_path / "input", tmp_path / "out"
    materialize(folder)
    write = package.write_json
    def failing_write(path, value):
        if path.name == "manifest.json":
            raise OSError("simulated full disk")
        write(path, value)
    monkeypatch.setattr(package, "write_json", failing_write)
    with pytest.raises(OSError, match="full disk"):
        build(folder, out)
    assert (out / "learning-links.json").exists()
    assert (out / "failure.json").exists()
    assert not (out / "complete.json").exists()


def test_new_map_and_points_do_not_require_old_identifiers(tmp_path):
    folder, out = tmp_path / "input", tmp_path / "out"
    review, _ = materialize(folder)
    # A completely different authored map/point namespace is a new review, not a merge.
    raw = json.dumps(review, ensure_ascii=False)
    for old, new in [(f'"{prefix}{i}"', f'"NEW-{prefix}{i}"') for prefix in ("T", "D", "P", "R") for i in (1, 2, 3)]:
        raw = raw.replace(old, new)
    (folder / "review.json").write_text(raw, encoding="utf-8")
    build(folder, out)
    result = json.loads((out / "learning-links.json").read_text(encoding="utf-8"))
    assert result["points"][0]["point_id"] == "NEW-P1"
    assert result["targets"][0]["target_id"] == "NEW-T1"


def test_actual_cli_success_failure_and_required_arguments(tmp_path):
    folder, out = tmp_path / "input", tmp_path / "out"
    materialize(folder)
    root = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, "-m", "quizbank.connection_plan", "--review", str(folder / "review.json"),
           "--bank", str(folder / "bank.json"), "--sources", str(folder / "sources.json"), "--out", str(out)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "local_package_complete"
    again = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", env=env)
    assert again.returncode == 1 and json.loads(again.stderr)["status"] == "failed"
    missing = subprocess.run(cmd[:3], cwd=root, capture_output=True, env=env)
    assert missing.returncode == 2
