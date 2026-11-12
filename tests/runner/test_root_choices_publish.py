"""게시 뒤 선지 작성: 실패해도 게시를 되돌리지 않고, 성공하면 root_choices/<revision>.json 하나를 올린다."""
from runner import root_choices, transport


class Client:
    base = "https://api.example.invalid"

    def __init__(self):
        self.calls = []

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/uploads"):
            return {"files": [{"filename": b["filename"], "uploadUrl": "https://r2.example.invalid/put"} for b in body]}
        return {"missing": []}


PAYLOAD = {"document": {"revision": "rev-1", "bank_snapshot": {"questions": []}}}


def test_성공하면_판_이름으로_한_파일만_올린다(tmp_path, monkeypatch):
    seen = {}

    def build(document, out, run_id, *, model=None, run=None):
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{document['revision']}.json"; path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(root_choices, "build", build)
    monkeypatch.setattr(transport, "_put_with_retry", lambda client, url, upload: seen.setdefault("put", upload))
    client = Client()
    assert root_choices.publish(client, "감염과 면역", "261110_03", tmp_path, PAYLOAD) is True
    assert seen["put"].kind == "root_choices" and seen["put"].filename == "rev-1.json"
    assert [c[1].rsplit("/", 1)[-1] for c in client.calls] == ["uploads", "complete"]


def test_실패는_로그만_남기고_게시를_막지_않는다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(root_choices, "build", lambda *a, **k: None)
    client = Client()
    assert root_choices.publish(client, "s", "r", tmp_path, PAYLOAD) is False and client.calls == []
    monkeypatch.setattr(root_choices, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("깨진 결과")))
    assert root_choices.publish(client, "s", "r", tmp_path, PAYLOAD) is False
    assert "선지 작성 실패" in capsys.readouterr().out


def test_생성기는_하위_프로세스로_돌고_실패하면_파일을_만들지_않는다(tmp_path):
    seen = {}

    class Done:
        returncode = 1

    def run(args, cwd=None):
        seen["args"] = args
        return Done()

    assert root_choices.build(PAYLOAD["document"], tmp_path, "r", model="m", run=run) is None
    assert seen["args"][1:3] == ["-m", "quizbank.root_choices"] and seen["args"][-2:] == ["--model", "m"]


def _run(runs, gid, run_id, revision, *, status="ready", posted=None, nested=True):
    import json
    folder = runs / "_root-generation" / gid
    (folder / "generation").mkdir(parents=True)
    (folder / "packet.json").write_text(json.dumps({"runId": run_id, "subject": "감염과 면역"}), encoding="utf-8")
    (folder / "published.json").write_text(json.dumps({"status": status, "revision": posted or revision}), encoding="utf-8")
    target = folder / "generation" / "result.json" if nested else folder / "result.json"
    target.write_text(json.dumps({"document": {"revision": revision, "bank_snapshot": {"questions": []}}}), encoding="utf-8")
    return folder


def test_게시된_실행만_고르고_판이_어긋난_것은_쓰지_않는다(tmp_path):
    import os
    import pytest
    _run(tmp_path, "a" * 32, "261110_03", "rev-old")
    newest = _run(tmp_path, "b" * 32, "261110_03", "rev-new")
    os.utime(newest / "published.json", (2_000_000_000, 2_000_000_000))
    _run(tmp_path, "c" * 32, "261110_03", "rev-x", status="pending")
    _run(tmp_path, "d" * 32, "261110_03", "rev-y", posted="rev-other")
    _run(tmp_path, "e" * 32, "261111_02", "rev-z")
    folder, packet, payload = root_choices.published_run(tmp_path, "261110_03")
    assert folder.name == "b" * 32 and payload["document"]["revision"] == "rev-new" and packet["subject"] == "감염과 면역"
    assert root_choices.published_run(tmp_path, "261110_03", generation="a" * 32)[0].name == "a" * 32
    with pytest.raises(SystemExit):
        root_choices.published_run(tmp_path, "261199_01")


def test_no_upload는_만들기만_하고_서버를_부르지_않는다(tmp_path, monkeypatch, capsys):
    folder = _run(tmp_path, "a" * 32, "261110_03", "rev-1")
    seen = {}

    def build(document, out, run_id, *, model=None, run=None):
        seen["out"] = out
        return out / "rev-1.json"

    monkeypatch.setattr(root_choices, "build", build)
    monkeypatch.setattr(root_choices, "publish", lambda *a, **k: (_ for _ in ()).throw(AssertionError("올리면 안 된다")))
    assert root_choices.main(["--run-id", "261110_03", "--runs", str(tmp_path), "--no-upload"]) == 0
    assert seen["out"] == folder / "choices" and "만들기만 함" in capsys.readouterr().out


def test_게시_경로는_선지_단계를_부르지_않는다():
    from pathlib import Path
    source = (Path(root_choices.__file__).parent / "connection_generation.py").read_text(encoding="utf-8")
    assert "root_choices" not in source


def test_여러_강의를_함께_돌리고_한_강의의_실패가_나머지를_막지_않는다(tmp_path, monkeypatch, capsys):
    import threading
    for gid, run_id in (("a" * 32, "261102_02"), ("b" * 32, "261102_03"), ("c" * 32, "261104_03")):
        _run(tmp_path, gid, run_id, "rev-" + run_id)
    _run(tmp_path, "d" * 32, "261199_01", "rev-other")
    import json
    other = tmp_path / "_root-generation" / ("d" * 32) / "packet.json"
    other.write_text(json.dumps({"runId": "261199_01", "subject": "다른 과목"}), encoding="utf-8")
    together, seen, lock = threading.Barrier(2, timeout=5), [], threading.Lock()

    def build(document, out, run_id, *, model=None, run=None):
        with lock:
            seen.append(run_id)
        if run_id in ("261102_02", "261102_03"):
            together.wait()  # 앞의 두 강의는 서로를 기다릴 수 있어야 끝난다: 함께 돈다
        return None if run_id == "261102_03" else out / f"{document['revision']}.json"

    monkeypatch.setattr(root_choices, "build", build)
    code = root_choices.main(["--all-published", "--subject", "감염과 면역", "--runs", str(tmp_path), "--no-upload", "--workers", "2"])
    assert code == 1 and sorted(seen) == ["261102_02", "261102_03", "261104_03"]
    out = capsys.readouterr().out
    assert "성공 2 · 실패 1 (261102_03)" in out and "261199_01" not in out


def test_all_published에는_과목이_필요하다(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        root_choices.main(["--all-published", "--runs", str(tmp_path), "--no-upload"])
    with pytest.raises(SystemExit):
        root_choices.main(["--runs", str(tmp_path), "--no-upload"])
