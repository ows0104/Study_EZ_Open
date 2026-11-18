"""게시 뒤 순서 맞추기 판정(2026-11-18 ordering-screen): 실패해도 게시를 되돌리지 않고, 성공하면 root_order/<revision>.json 하나를 올린다."""
import json

from runner import root_order, transport

from test_root_choices_publish import PAYLOAD, Client, _run


def test_성공하면_판_이름으로_root_order_한_파일만_올린다(tmp_path, monkeypatch):
    seen = {}

    def build(document, out, *, model=None, run=None):
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{document['revision']}.json"; path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(root_order, "build", build)
    monkeypatch.setattr(transport, "_put_with_retry", lambda client, url, upload: seen.setdefault("put", upload))
    client = Client()
    assert root_order.publish(client, "감염과 면역", "261110_02", tmp_path, PAYLOAD) is True
    assert seen["put"].kind == "root_order" and seen["put"].filename == "rev-1.json"
    assert [c[1].rsplit("/", 1)[-1] for c in client.calls] == ["uploads", "complete"]
    assert json.loads((tmp_path / "order" / "uploaded.json").read_text(encoding="utf-8"))["schema"] == "root-order/1"


def test_실패는_로그만_남기고_게시를_막지_않는다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(root_order, "build", lambda *a, **k: None)
    client = Client()
    assert root_order.publish(client, "s", "r", tmp_path, PAYLOAD) is False and client.calls == []
    monkeypatch.setattr(root_order, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("깨진 결과")))
    assert root_order.publish(client, "s", "r", tmp_path, PAYLOAD) is False
    assert "순서 맞추기 판정 실패" in capsys.readouterr().out


def test_생성기는_하위_프로세스로_돈다(tmp_path):
    seen = {}

    class Done:
        returncode = 1

    def run(args, cwd=None):
        seen["args"] = args
        return Done()

    assert root_order.build(PAYLOAD["document"], tmp_path, model="m", run=run) is None
    assert seen["args"][1:3] == ["-m", "quizbank.root_order"] and seen["args"][-2:] == ["--model", "m"]


def test_missing은_올린_판을_건너뛴다(tmp_path, monkeypatch, capsys):
    done = _run(tmp_path, "a" * 32, "261102_02", "rev-a")
    _run(tmp_path, "b" * 32, "261113_02", "rev-b")
    (done / "order").mkdir()
    (done / "order" / "uploaded.json").write_text(json.dumps({"revision": "rev-a", "schema": "root-order/1"}), encoding="utf-8")
    built, sent = [], []

    def build(document, out, *, model=None, run=None):
        built.append(document["revision"])
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{document['revision']}.json"; path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(root_order, "build", build)
    monkeypatch.setattr(root_order, "upload", lambda client, subject, run_id, path: sent.append(run_id))
    monkeypatch.setattr("runner.cycle.runner_token", lambda token: "t")
    code = root_order.main(["--all-published", "--subject", "감염과 면역", "--missing", "--runs", str(tmp_path), "--api", "https://x.invalid"])
    assert code == 0 and built == ["rev-b"] and sent == ["261113_02"]
    assert "성공 1 · 실패 0 · 이미 있음 1" in capsys.readouterr().out
