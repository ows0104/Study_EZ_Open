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
