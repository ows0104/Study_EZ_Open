"""러너의 선지 단계(`root-mcq/2`, 2026-11-14 choices-merge): 게시 직후 기본 실행·족보 재료·v1 보존·v2 업로드 표시."""
import json
from types import SimpleNamespace

from runner import root_mcq


class Client:
    base = "https://api.example.invalid"

    def __init__(self):
        self.calls = []

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/uploads"):
            return {"files": [{"filename": b["filename"], "uploadUrl": "https://r2.example.invalid/put"} for b in body]}
        return {"missing": []}


def _run(runs, gid, run_id, revision, *, jokbo=None, evidence=False):
    folder = runs / "_root-generation" / gid
    (folder / "generation" / "evidence").mkdir(parents=True)
    sources = []
    if jokbo:
        pdf = folder / "source-1.pdf"
        pdf.write_bytes(b"%PDF")
        sources.append({"id": "S2", "kind": "jokbo", "sha256": jokbo, "filename": "족보.pdf", "localPath": str(pdf)})
    (folder / "packet.json").write_text(json.dumps({"runId": run_id, "subject": "감염과 면역", "sources": sources}), encoding="utf-8")
    (folder / "published.json").write_text(json.dumps({"status": "ready", "revision": revision}), encoding="utf-8")
    (folder / "generation" / "result.json").write_text(json.dumps(
        {"document": {"revision": revision, "title": f"강의 {run_id}", "bank_snapshot": {"questions": []}}}), encoding="utf-8")
    if evidence:
        (folder / "generation" / "evidence" / "evidence.json").write_text("{}", encoding="utf-8")
    return folder


def test_족보_목록과_근거_자리를_찾는다(tmp_path):
    a = _run(tmp_path, "a" * 32, "261113_01", "rev-a", jokbo="f" * 64, evidence=True)
    _run(tmp_path, "b" * 32, "261102_02", "rev-b")
    sources = root_mcq.jokbo_sources(tmp_path, "감염과 면역")
    assert [(x["run_id"], len(x["pdfs"])) for x in sources["lectures"]] == [("261102_02", 0), ("261113_01", 1)]
    assert sources["lectures"][1]["pdfs"][0]["sha256"] == "f" * 64
    assert root_mcq.evidence_path(a) == a / "generation" / "evidence" / "evidence.json"
    assert root_mcq.evidence_path(tmp_path / "_root-generation" / ("b" * 32)) is None


def test_생성기에_족보와_근거를_넘기고_v1은_남긴다(tmp_path):
    folder = _run(tmp_path, "a" * 32, "261113_01", "rev-a", evidence=True)
    out = folder / "mcq"
    out.mkdir()
    (out / "rev-a.json").write_text(json.dumps({"schema": "root-mcq/1", "revision": "rev-a"}), encoding="utf-8")
    seen = {}

    def run(args, cwd):
        seen["args"] = args
        (out / "mcq.json").write_text(json.dumps({"schema": "root-mcq/2", "revision": "rev-a"}), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    block, jokbo = root_mcq.materials(tmp_path, "감염과 면역")
    path = root_mcq.build({"revision": "rev-a"}, out, "261113_01", block=block, sheet=None, jokbo=jokbo,
                          evidence=root_mcq.evidence_path(folder), run=run)
    args = seen["args"]
    assert args[1:3] == ["-m", "quizbank.root_mcq"] and "--jokbo-sources" in args and "--evidence" in args
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == "root-mcq/2"
    assert json.loads((out / "v1-rev-a.json").read_text(encoding="utf-8"))["schema"] == "root-mcq/1"


def test_게시_직후_publish는_올리고_v2_표시를_남기며_missing은_v1_표시를_다시_돈다(tmp_path, monkeypatch):
    folder = _run(tmp_path, "a" * 32, "261113_01", "rev-a")
    (folder / "mcq").mkdir()
    (folder / "mcq" / "uploaded.json").write_text(json.dumps({"revision": "rev-a"}), encoding="utf-8")   # v1 때 표시
    assert root_mcq.uploaded(folder, "rev-a") is False

    def build(document, out, run_id, **k):
        path = out / f"{document['revision']}.json"
        path.write_text(json.dumps({"schema": "root-mcq/2"}), encoding="utf-8")
        return path

    uploads = []
    monkeypatch.setattr(root_mcq, "build", build)
    monkeypatch.setattr(root_mcq, "upload", lambda client, subject, run_id, path: uploads.append((subject, run_id, path.name)))
    payload = json.loads((folder / "generation" / "result.json").read_text(encoding="utf-8"))
    assert root_mcq.publish(Client(), "감염과 면역", "261113_01", folder, payload, model="m") is True
    assert uploads == [("감염과 면역", "261113_01", "rev-a.json")]
    assert root_mcq.uploaded(folder, "rev-a") is True and root_mcq.uploaded(folder, "rev-b") is False


def test_publish_실패는_로그만_남긴다(tmp_path, monkeypatch, capsys):
    folder = _run(tmp_path, "a" * 32, "261113_01", "rev-a")
    monkeypatch.setattr(root_mcq, "build", lambda *a, **k: None)
    payload = json.loads((folder / "generation" / "result.json").read_text(encoding="utf-8"))
    assert root_mcq.publish(Client(), "감염과 면역", "261113_01", folder, payload) is False
    assert "판은 게시됨" in capsys.readouterr().out
    monkeypatch.setattr(root_mcq, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("깨짐")))
    assert root_mcq.publish(Client(), "감염과 면역", "261113_01", folder, payload) is False
