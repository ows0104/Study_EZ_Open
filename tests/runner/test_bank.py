"""Quiz Bank 의 러너 쪽 — 일감 갈래 · 끝 판정 · 족보 조각 캐시 · `runner bank` 의 올리기.

모델도 서버도 부르지 않는다. 하위 프로세스는 가짜로 바꾼다.
"""

import json
import os
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


def test_point_job_only_prepares_points_and_does_not_publish_a_bank(tmp_path, monkeypatch):
    job = agent.Job(id=7, subject="약리학", run_id="261002_02", kind=agent.BANK_POINTS)
    assert _agent(tmp_path).make_argv(job)[-1] == "--points-only"
    assert job.what == "출제포인트 준비"
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"source")
    monkeypatch.setattr(bank, "_notes_pdf", lambda *args: pdf)
    client = FakeClient()
    def call(method, path, payload=None):
        client.calls.append((method, path, payload))
        assert method == "GET" and path.endswith("/bank/source-context")
        return {"title": "강의", "sources": [{"id": "S1", "kind": "notes_current", "filename": pdf.name}],
                "raw": "must not reach point extraction", "existingBank": {"secret": True}}
    client.call = call
    def prepare(argv, **kwargs):
        assert argv[2] == "quizbank.independent"
        out = Path(argv[argv.index("--out") + 1])
        context = json.loads((out / "context.json").read_text(encoding="utf-8"))
        assert set(context) == {"title", "sources"}
        points = out / "authored-points.json"
        points.write_text('[{"point_id":"P1","point":"objective","source_refs":"S1 p.1"}]', encoding="utf-8")
        (out / "points-result.json").write_text(json.dumps({"completed": True, "reused": True,
            "pointPlanPath": str(points), "points": 1}), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, "run", prepare)
    assert bank.prepare_points(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 0
    assert len(client.calls) == 1
    worker, reports = _agent(tmp_path), []
    monkeypatch.setattr(worker, "report", lambda job, **fields: reports.append(fields) or {})
    worker.finish_bank(job, 0, ["Quiz Bank points 261002_02: 저장된 결과 재사용 · 포인트 1개"], tmp_path / "log")
    assert reports[-1]["state"] == "done"
    worker.finish_bank(job, 0, ["── 원본 독립 출제포인트 추출"], tmp_path / "log")
    assert reports[-1]["state"] == "failed"


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
    monkeypatch.setattr(bank, "jokbo_slices", lambda *args: {"261002_02": tmp_path / "j.md"})
    client = FakeClient()
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 0
    puts = [c for c in client.calls if c[0] == "PUT"]
    assert puts[-1][1].endswith("/261002_02/bank")
    body = puts[-1][2]
    assert body["respondedAt"] == "2026-10-04T01:00:00+00:00" and body["pages"] == {"Q1": [13]}
    assert [c for c in client.calls if c[0] == "FILE"][0][1] == "u/261002_02_s013.png"
    assert "Quiz Bank 261002_02: ready" in capsys.readouterr().out


def test_revision_failure_uploads_diagnostics_without_replacing_bank(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(bank, "_notes_pdf", lambda *args: pdf)
    monkeypatch.setattr(bank, "jokbo_slices", lambda *args: {"261002_02": tmp_path / "j.md"})
    def fake_run(argv, **kwargs):
        out = Path(argv[argv.index("--out") + 1])
        (out / "result.json").write_text(json.dumps({"requiresRevision": True}))
        (out / "validation.json").write_text(json.dumps({"pass": False, "errors": ["Q1: leak"]}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    client = FakeClient()
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 1
    payload = [c for c in client.calls if c[0] == "PUT"][-1][2]
    assert payload["revision"]["validation"]["errors"] == ["Q1: leak"]
    assert "bank" not in payload
    assert "학습 가능한 구조" in payload["message"]
    assert "ChatGPT 응답 수정" not in payload["message"]


def test_unresolved_content_is_uploaded_with_findings_and_permission(tmp_path, monkeypatch):
    pdf = tmp_path / 'a.pdf'
    pdf.write_bytes(b'%PDF')
    monkeypatch.setattr(bank, '_notes_pdf', lambda *args: pdf)
    monkeypatch.setattr(bank, 'jokbo_slices', lambda *args: {'261002_02': tmp_path / 'j.md'})
    def fake_run(argv, **kwargs):
        got = _fake_quizbank(False)(argv, **kwargs)
        out = Path(argv[argv.index('--out') + 1])
        result = json.loads((out / 'result.json').read_text(encoding='utf-8'))
        result.update(requiresRevision=True, publication={'allowed': True})
        (out / 'result.json').write_text(json.dumps(result), encoding='utf-8')
        (out / 'web-audit.json').write_text('{"question_issues":[{"question_id":"Q1","severity":"error"}]}')
        return got
    monkeypatch.setattr(subprocess, 'run', fake_run)
    client = FakeClient()
    assert bank.run(client, tmp_path, '약리학', '261002_02', '2026', '2025', tmp_path) == 0
    payload = [c for c in client.calls if c[0] == 'PUT'][-1][2]
    assert payload['allowUnresolved'] and 'bank' in payload
    assert not payload['validation']['pass']
    assert payload['revision']['audit']['question_issues'][0]['severity'] == 'error'


def test_revision_summary_reports_remaining_errors_and_gaps_without_doubts(tmp_path):
    for name, data in (("web-audit.json", {
            "question_issues": [{"question_id": "Q1", "severity": "error"},
                                {"question_id": "Q2", "severity": "doubt"}],
            "plan_issues": [{"kind": "missing_point"}], "duplicates": [{"question_ids": ["Q3", "Q4"]}]}),
            ("review.json", {"reviews": [{"question_id": "Q1", "verdict": "wrong"},
                                          {"question_id": "Q2", "verdict": "doubt"}], "missing": []})):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    summary = bank._revision_summary(tmp_path, {"coverage": {"gapCount": 2}})
    assert "문항 오류 1건(Q1)" in summary
    assert "미충족 포인트 2건" in summary and "누락된 출제 목표 1건" in summary
    assert "중복 묶음 1건" in summary and "Q2" not in summary


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


def test_resume_requires_the_same_original_bank_build_and_pdf(tmp_path):
    import hashlib
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"old-source")
    bank_path = tmp_path / "checkpoint.json"
    plan_path = tmp_path / "point-plan.json"
    bank_path.write_text("{}")
    plan_path.write_text("{}")
    got = {"existingBank": {"questions": []}, "baseBuildId": "old-build"}
    record = {"expectedBankHash": hashlib.sha256(json.dumps(got["existingBank"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
              "sourceSha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "baseBuildId": "old-build",
              "bankPath": str(bank_path), "pointPlanPath": str(plan_path)}
    path = tmp_path / "demo/bank/resume.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record))
    assert bank._resume(tmp_path, "demo", got, pdf) == record
    assert bank._resume(tmp_path, "demo", {**got, "baseBuildId": "new-build"}, pdf) is None
    assert bank._resume(tmp_path, "demo", {**got, "existingBank": {"questions": [{"question_id": "new"}]}}, pdf) is None
    pdf.write_bytes(b"changed-source")
    assert bank._resume(tmp_path, "demo", got, pdf) is None


def test_resumed_supplement_counts_include_the_saved_checkpoint(tmp_path):
    original = {"questions": [{"format": "basic"}]}
    current = {"questions": [{"format": "basic"}, {"format": "mcq"}, {"format": "basic"}]}
    coverage = {"bankHash": "unchanged", "addedQuestions": 0, "addedMcq": 0}
    for name, data in (("bank.json", current), ("validation.json", {"coverage": coverage}),
                       ("coverage.json", coverage), ("result.json", {"coverage": coverage})):
        (tmp_path / name).write_text(json.dumps(data))
    bank._record_additions(tmp_path, original)
    for name in ("validation.json", "result.json"):
        report = json.loads((tmp_path / name).read_text())["coverage"]
        assert report == {"bankHash": "unchanged", "addedQuestions": 2, "addedMcq": 1}


def test_response_resume_is_bound_to_response_sources_version_and_pdf(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"source")
    got = {"raw": "original response", "respondedAt": "one", "promptVersion": "1.31",
           "title": "lecture", "sources": [{"id": "S1", "filename": "a.pdf"}]}
    out = tmp_path / "demo/bank/build"
    out.mkdir(parents=True)
    (out / "bank.json").write_text("{}")
    (out / "authored-points.json").write_text("[]")
    bank._record_response_resume(tmp_path, "demo", got, pdf, out)
    record = bank._response_resume(tmp_path, "demo", got, pdf)
    assert record["bankPath"] == str((out / "bank.json").resolve())
    for field, changed in (("raw", "new response"), ("respondedAt", "two"), ("promptVersion", "1.32"),
                           ("title", "other"), ("sources", [{"id": "S2", "filename": "a.pdf"}])):
        assert bank._response_resume(tmp_path, "demo", {**got, field: changed}, pdf) is None
    pdf.write_bytes(b"updated source")
    assert bank._response_resume(tmp_path, "demo", got, pdf) is None


def test_response_resume_rejects_changed_jokbo_content(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"source")
    jokbo = tmp_path / "j.md"
    jokbo.write_text("old answer key", encoding="utf-8")
    got = {"raw": "response", "respondedAt": "one", "title": "lecture"}
    out = tmp_path / "demo/bank/build"
    out.mkdir(parents=True)
    (out / "bank.json").write_text("{}")
    (out / "authored-points.json").write_text("[]")
    bank._record_response_resume(tmp_path, "demo", got, pdf, out, jokbo)
    assert bank._response_resume(tmp_path, "demo", got, pdf, jokbo)
    jokbo.write_text("corrected answer key", encoding="utf-8")
    assert bank._response_resume(tmp_path, "demo", got, pdf, jokbo) is None
    assert bank._response_resume(tmp_path, "demo", got, pdf, None) is None


def test_runner_retries_from_cli_bank_and_point_plan_instead_of_original_response(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    jokbo = tmp_path / "j.md"
    jokbo.write_text("source")
    client = FakeClient()
    got = client.call("GET", "/unused")
    saved = tmp_path / "261002_02/bank/previous"
    saved.mkdir(parents=True)
    (saved / "bank.json").write_text("{}")
    (saved / "authored-points.json").write_text("[]")
    bank._record_response_resume(tmp_path, "261002_02", got, pdf, saved, jokbo, remaining_repair_rounds=1)
    monkeypatch.setattr(bank, "_notes_pdf", lambda *args: pdf)
    monkeypatch.setattr(bank, "jokbo_slices", lambda *args: {"261002_02": jokbo})
    def fake_run(argv, **kwargs):
        assert argv[argv.index("--existing-bank") + 1] == str((saved / "bank.json").resolve())
        assert argv[argv.index("--point-plan") + 1] == str((saved / "authored-points.json").resolve())
        assert argv[argv.index("--max-repair-rounds") + 1] == "1"
        assert "--preserve-existing" not in argv
        out = Path(argv[argv.index("--out") + 1])
        (out / "authored-points.json").write_text("[]")
        (out / "repairs.json").write_text('[{"round": 1}]')
        return _fake_quizbank(True)(argv, **kwargs)
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 0
    record = bank._response_resume(tmp_path, "261002_02", got, pdf, jokbo)
    assert record["remainingRepairRounds"] == 0


def test_response_resume_cannot_reference_another_lecture_or_missing_file(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"source")
    got = {"raw": "response", "respondedAt": "one", "title": "lecture"}
    root = tmp_path / "demo/bank"
    root.mkdir(parents=True)
    other = tmp_path / "other.json"
    other.write_text("{}")
    (root / "response-resume.json").write_text(json.dumps({"identity": bank._response_identity(got, pdf),
        "bankPath": str(other), "pointPlanPath": str(other)}))
    assert bank._response_resume(tmp_path, "demo", got, pdf) is None
    local = root / "missing.json"
    (root / "response-resume.json").write_text(json.dumps({"identity": bank._response_identity(got, pdf),
        "bankPath": str(local), "pointPlanPath": str(local)}))
    assert bank._response_resume(tmp_path, "demo", got, pdf) is None


def test_response_resume_accepts_three_rounds_but_preserves_legacy_budget(tmp_path):
    pdf = tmp_path / 'a.pdf'
    pdf.write_bytes(b'source')
    got = {'raw': 'response', 'respondedAt': 'one', 'title': 'lecture'}
    out = tmp_path / 'demo/bank/saved'
    out.mkdir(parents=True)
    (out / 'bank.json').write_text('{}')
    (out / 'authored-points.json').write_text('[]')
    bank._record_response_resume(tmp_path, 'demo', got, pdf, out, remaining_repair_rounds=3)
    assert bank._response_resume(tmp_path, 'demo', got, pdf)['remainingRepairRounds'] == 3
    record_path = out.parent / 'response-resume.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    record['remainingRepairRounds'] = 4
    record_path.write_text(json.dumps(record), encoding='utf-8')
    assert bank._response_resume(tmp_path, 'demo', got, pdf) is None
    record.pop('remainingRepairRounds')
    record_path.write_text(json.dumps(record), encoding='utf-8')
    assert bank._response_resume(tmp_path, 'demo', got, pdf) is not None


def test_runner_keeps_cli_candidate_when_a_model_session_exits_before_result(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    jokbo = tmp_path / "j.md"
    jokbo.write_text("source")
    monkeypatch.setattr(bank, "_notes_pdf", lambda *args: pdf)
    monkeypatch.setattr(bank, "jokbo_slices", lambda *args: {"261002_02": jokbo})
    def fail_after_candidate(argv, **kwargs):
        out = Path(argv[argv.index("--out") + 1])
        (out / "bank.json").write_text('{"questions": []}')
        (out / "authored-points.json").write_text("[]")
        (out / "checkpoint.json").write_text('{"repairs":{"attempts":1,"acceptedAttempts":0}}')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(subprocess, "run", fail_after_candidate)
    client = FakeClient()
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 1
    got = client.call("GET", "/unused")
    assert bank._response_resume(tmp_path, "261002_02", got, pdf, jokbo)['remainingRepairRounds'] == 2


def test_interrupted_or_changed_source_outputs_are_not_recorded(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"source")
    got = {"raw": "response", "respondedAt": "one", "title": "lecture"}
    out = tmp_path / "demo/bank/build"
    out.mkdir(parents=True)
    (out / "bank.json").write_text("{")
    (out / "authored-points.json").write_text("[]")
    bank._record_response_resume(tmp_path, "demo", got, pdf, out)
    assert not (out.parent / "response-resume.json").exists()
    (out / "bank.json").write_text("{}")
    identity = bank._response_identity(got, pdf)
    pdf.write_bytes(b"updated")
    bank._record_response_resume(tmp_path, "demo", got, pdf, out, identity=identity)
    assert not (out.parent / "response-resume.json").exists()


def test_응답이_없으면_자동_출제_후_기존_정리와_업로드(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    os.utime(pdf, (1, 1))
    monkeypatch.setattr(bank, "_notes_pdf", lambda *args: pdf)
    monkeypatch.setattr(bank, "jokbo_slices", lambda *args: {"261002_02": tmp_path / "j.md"})
    client = FakeClient()
    original_call = client.call
    def call(method, path, payload=None):
        answer = original_call(method, path, payload)
        if method == "GET":
            answer["raw"] = ""
        return answer
    monkeypatch.setattr(client, "call", call)
    seen = []
    def fake_run(argv, **kwargs):
        seen.append(argv[2])
        out = Path(argv[argv.index("--out") + 1])
        if argv[2] == "quizbank.generate":
            (out / "raw.md").write_text("문항 " * 100 + "STUDYEZ_BANK_COMPLETE", encoding="utf-8")
            (out / "generation.json").write_text(json.dumps({"promptVersion": "1.15",
                                                               "usage": [{"step": "출제"}]}))
            return SimpleNamespace(returncode=0)
        return _fake_quizbank(True)(argv, **kwargs)
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert bank.run(client, tmp_path, "약리학", "261002_02", "2026", "2025", tmp_path) == 0
    assert seen == ["quizbank.generate", "quizbank.run"]
    puts = [c for c in client.calls if c[0] == "PUT"]
    assert puts[0][1].endswith("bank-generated-response")
    assert puts[-1][2]["usage"][0]["step"] == "출제"
