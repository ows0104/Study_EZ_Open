"""게시 뒤 근거 보강: 실패해도 게시를 되돌리지 않고, 성공하면 root_evidence/<revision>.json 하나를 올린다."""
import json
from pathlib import Path

from runner import root_evidence, transport


class Client:
    base = "https://api.example.invalid"

    def __init__(self, missing_after=()):
        self.calls, self.missing_after = [], list(missing_after)

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/uploads"):
            return {"files": [{"filename": b["filename"], "uploadUrl": "https://r2.example.invalid/put"} for b in body]}
        return {"missing": self.missing_after}


def _inputs(tmp_path):
    notes = tmp_path / "source-0.pdf"; notes.write_bytes(b"%PDF")
    text = tmp_path / "source-1.md"; text.write_text("x", encoding="utf-8")
    packet = {"sources": [{"id": "S1", "localPath": str(notes)}, {"id": "S9", "localPath": str(text)}]}
    payload = {"document": {"revision": "rev-1", "review": {"sources": [{"source_id": "S1"}]}}}
    return packet, payload


def test_성공하면_판_이름으로_한_파일만_올린다(tmp_path, monkeypatch):
    packet, payload = _inputs(tmp_path)
    seen = {}

    def build(document, sources, out, run_id, *, model=None, run=None):
        seen["sources"] = sorted(sources)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{document['revision']}.json"; path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(root_evidence, "build", build)
    monkeypatch.setattr(transport, "_put_with_retry", lambda client, url, upload: seen.setdefault("put", upload))
    client = Client()
    assert root_evidence.publish(client, "감염과 면역", "261104_02", tmp_path, packet, payload) is True
    assert seen["sources"] == ["S1"]  # PDF이고 판이 아는 원본만
    assert seen["put"].kind == "root_evidence" and seen["put"].filename == "rev-1.json"
    assert [c[1].rsplit("/", 1)[-1] for c in client.calls] == ["uploads", "complete"]


def test_실패는_로그만_남기고_게시를_막지_않는다(tmp_path, monkeypatch, capsys):
    packet, payload = _inputs(tmp_path)
    monkeypatch.setattr(root_evidence, "build", lambda *a, **k: None)
    assert root_evidence.publish(Client(), "s", "r", tmp_path, packet, payload) is False
    monkeypatch.setattr(root_evidence, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("지문 불일치")))
    assert root_evidence.publish(Client(), "s", "r", tmp_path, packet, payload) is False
    assert "지문 불일치" in capsys.readouterr().out


def test_서버가_못_찾으면_실패로_센다(tmp_path, monkeypatch):
    packet, payload = _inputs(tmp_path)
    monkeypatch.setattr(root_evidence, "build", lambda d, s, out, r, **k: (out.mkdir(parents=True, exist_ok=True),
                        (out / "rev-1.json").write_text("{}"), out / "rev-1.json")[-1])
    monkeypatch.setattr(transport, "_put_with_retry", lambda *a: None)
    assert root_evidence.publish(Client(missing_after=["rev-1.json"]), "s", "r", tmp_path, packet, payload) is False
