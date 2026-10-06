"""Quiz Bank 의 러너 쪽 — 일감 갈래 · 끝 판정 · 족보 조각 캐시 · `runner bank` 의 올리기.

모델도 서버도 부르지 않는다. 하위 프로세스는 가짜로 바꾼다.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from runner import agent, ahead, bank, filenames, publish


def _agent(tmp_path: Path) -> agent.Agent:
    return agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path, announce=lambda *_: None)


def _job(**kw) -> agent.Job:
    return agent.Job(id=7, subject="약리학", run_id="261002_02", kind=agent.BANK, **kw)


# ── 일감 갈래 ─────────────────────────────────────────────────────

def test_bank_갈래는_runner_bank_를_부른다(tmp_path):
    argv = _agent(tmp_path).make_argv(_job())
    assert argv[2:] == ["runner", "bank", "약리학", "--run-id", "261002_02"]
    assert _job().what == "Main-Quiz"


def test_bank_는_작년_자리를_막지_않는다(tmp_path):
    (tmp_path / "251002_01").mkdir()
    (tmp_path / "251002_01" / "pre_target.json").write_text(
        '{"subject": "약리학", "run_id": "261002_02"}', encoding="utf-8")
    assert _agent(tmp_path).building_seats(_job()) == {tmp_path / "261002_02"}


def _finish(tmp_path, monkeypatch, code, lines):
    worker, seen = _agent(tmp_path), []
    monkeypatch.setattr(worker, "report", lambda job, **f: seen.append(f) or {})
    worker.finish_bank(_job(), code, lines, tmp_path / "agent.log")
    return seen[-1]


def test_요약_줄이_있어야_끝난_것이다(tmp_path, monkeypatch):
    done = _finish(tmp_path, monkeypatch, 0, ["── 정리", "Quiz Bank 261002_02: ready · 문항 36 · 검토 {...}"])
    assert done["state"] == "done" and done["message"].startswith("Quiz Bank 261002_02: ready")
    # 0 으로 끝났어도 요약이 없으면 올라간 것이 아니다
    assert _finish(tmp_path, monkeypatch, 0, ["── 정리"])["state"] == "failed"


def test_멈춘_이유가_화면에_선다(tmp_path, monkeypatch):
    failed = _finish(tmp_path, monkeypatch, 1, ["── 정리", "멈췄다 — 정리: claude 가 1 로 끝났다"])
    assert failed["state"] == "failed" and "정리: claude 가 1 로 끝났다" in failed["message"]


# ── 족보 조각 ─────────────────────────────────────────────────────

def _cut(tmp_path: Path) -> Path:
    cut = tmp_path / "_materials" / "약리학"
    cut.mkdir(parents=True)
    (cut / "index.json").write_text("{}", encoding="utf-8")
    md = cut / "L12-13.md"
    md.write_text("# 족보", encoding="utf-8")
    return cut


def test_족보_조각을_재고_적어_두었다가_다시_안_잰다(tmp_path, monkeypatch):
    cut = _cut(tmp_path)
    monkeypatch.setattr(bank.deck, "jokbo_dir", lambda runs, subject: cut)
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        out = Path(argv[argv.index("--out") + 1])
        out.write_text(json.dumps([{"source": "x/[261002_02] 콜린성.pdf", "slice": str(cut / "L12-13.md"),
                                    "score": 1.0, "why": ""},
                                   {"source": "x/[261002_03] 없음.pdf", "slice": None, "score": None,
                                    "why": "문턱 아래"}]), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sources = {"261002_02": Path("x/[261002_02] 콜린성.pdf"), "261002_03": Path("x/[261002_03] 없음.pdf")}
    found = bank.jokbo_slices(tmp_path, "약리학", sources)
    assert found == {"261002_02": cut / "L12-13.md"}
    assert bank.jokbo_slices(tmp_path, "약리학", sources) == found
    assert len(calls) == 1                               # 두 번째는 적어 둔 것을 읽는다
    cached = json.loads((tmp_path / "261002_03" / "bank" / "jokbo.json").read_text(encoding="utf-8"))
    assert cached["slice"] == "" and cached["why"] == "문턱 아래"


def test_족보를_안_잘랐으면_조용히_빈손(tmp_path, monkeypatch):
    monkeypatch.setattr(bank.deck, "jokbo_dir", lambda runs, subject: tmp_path / "없는곳")
    assert bank.jokbo_slices(tmp_path, "약리학", {"r": Path("a.pdf")}) == {}


# ── runner bank ───────────────────────────────────────────────────

def test_올해_필기_전에도_시간표_교수의_족보를_예습에_올린다(tmp_path, monkeypatch):
    root, runs = tmp_path / "data", tmp_path / "runs"
    folder = root / "약리학" / "필기" / "2025"
    folder.mkdir(parents=True)
    pdf = folder / "[251002_02] 콜린성 약리학(2)(김작년)_홍길동v1.pdf"
    pdf.write_bytes(b"%PDF")
    prev = filenames.parse(pdf)
    cell = ahead.Cell(date="2026-10-02", slot=2, start_time="10:00", title="약물의 이해",
                      heading="콜린성 약리학(2)", body=("콜린성 약리학(2)",),
                      professors=("이올해",), course="약물의 이해")
    monkeypatch.setattr(ahead, "plan", lambda *a: ([SimpleNamespace(cell=cell, prev=prev, source="confirmed")], []))
    seen = {}
    md = tmp_path / "올해족보.md"
    md.write_text("# 올해 교수 족보", encoding="utf-8")

    def slices(runs_dir, subject, sources):
        seen.update(sources)
        return {cell.key: md}

    monkeypatch.setattr(bank, "jokbo_slices", slices)
    plans, _ = publish.plan_subject(root, "약리학", "2026", "2025", runs,
                                    notes_only=True, timetable=tmp_path / "timetable.json")
    assert "이올해" in seen[cell.key].name and "김작년" not in seen[cell.key].name
    assert [(u.kind, u.path) for u in plans[0].uploads] == [("notes_prev", pdf), ("jokbo", md)]


class FakeClient:
    def __init__(self):
        self.calls = []

    def call(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET":
            return {"raw": "응답 STUDYEZ_BANK_COMPLETE", "respondedAt": "2026-10-04T01:00:00+00:00",
                    "title": "콜린성 약리학(2)", "sources": [{"id": "S1", "kind": "notes_current", "filename": "a.pdf"},
                                                         {"id": "S2", "kind": "jokbo", "filename": "j.md"}]}
        if path.endswith("/uploads"):
            return {"files": [{"filename": p["filename"], "uploadUrl": "u/" + p["filename"]} for p in payload]}
        if path.endswith("/uploads/complete"):
            return {"missing": [] if len([c for c in self.calls if c[1].endswith("complete")]) > 1
                    else [p["filename"] for p in payload]}
        return {"status": "ready"}

    def put_file(self, url, path):
        self.calls.append(("FILE", url, None))


def _fake_quizbank(passed: bool):
    def fake_run(argv, **kw):
        out = Path(argv[argv.index("--out") + 1])
        (out / "slides").mkdir(parents=True, exist_ok=True)
        (out / "slides" / "261002_02_s013.png").write_bytes(b"png")
        for name, data in (("bank.json", {"questions": []}), ("validation.json", {"pass": passed, "errors": []}),
                           ("pages.json", {"Q1": [13]}),
                           ("result.json", {"pass": passed, "questions": 36, "errors": 0 if passed else 3,
                                            "review": {"ok": 36}})):
            (out / name).write_text(json.dumps(data), encoding="utf-8")
        (out / "usage.jsonl").write_text('{"step": "정리", "seconds": 1}\n', encoding="utf-8")
        assert argv[argv.index("--source") + 1] == "S1|notes_current|a.pdf"
        return SimpleNamespace(returncode=0)
    return fake_run


def test_정리해서_슬라이드와_결과를_올린다(tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(publish, "plan_subject", lambda *a, **k: ([SimpleNamespace(run_id="261002_02",
                                                                                   item=SimpleNamespace(path=pdf))], []))
    monkeypatch.setattr(subprocess, "run", _fake_quizbank(True))
    client = FakeClient()
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 0
    puts = [c for c in client.calls if c[0] == "PUT"]
    assert puts[-1][1].endswith("/261002_02/bank")
    body = puts[-1][2]
    assert body["respondedAt"] == "2026-10-04T01:00:00+00:00" and body["pages"] == {"Q1": [13]}
    assert [c for c in client.calls if c[0] == "FILE"][0][1] == "u/261002_02_s013.png"
    assert "Quiz Bank 261002_02: ready" in capsys.readouterr().out


def test_필기를_못_찾으면_서버에_실패를_적는다(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(publish, "plan_subject", lambda *a, **k: ([], []))
    client = FakeClient()
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 1
    last = [c for c in client.calls if c[0] == "PUT"][-1]
    assert "bank" not in last[2] and "못 찾았다" in last[2]["message"]
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("멈췄다 — ")


def test_md_는_text_markdown_으로_올라간다():
    assert publish.content_type(Path("L12-13.md")) == "text/markdown"
    assert "jokbo" in publish.NOTES_KINDS
