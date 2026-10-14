import json

import pytest

from quizbank import coverage, independent, question_first
from tests.quizbank.test_question_first import make_pdf, plan


def test_preparation_reuses_completed_source_only_points_without_a_second_cli_call(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    make_pdf(pdf)
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"title": "강의", "sources": [
        {"id": "S1", "kind": "notes_current", "filename": pdf.name}]}), encoding="utf-8")
    calls = []
    def call(prompt, schema, work, model, label):
        calls.append(work)
        assert schema == question_first.PLAN
        assert set(p.name for p in work.iterdir()) == {"context.json", "source-pages.json", "source-text.md", "source-pages"}
        return plan(), {}
    monkeypatch.setattr(coverage, "_call", call)
    for name in ("first", "again"):
        out = tmp_path / "cache" / name
        assert independent.main(["--pdf", str(pdf), "--context", str(context), "--out", str(out),
                                 "--cache-root", str(tmp_path / "cache")]) == 0
        result = json.loads((out / "points-result.json").read_text(encoding="utf-8"))
        assert result["completed"] and result["reused"] == (name == "again")
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["pdf", "jokbo", "title", "scope", "broken", "empty", "duplicate", "no_provenance"])
def test_cache_does_not_reuse_changed_sources_or_incomplete_artifacts(tmp_path, monkeypatch, change):
    pdf, jokbo = tmp_path / "a.pdf", tmp_path / "j.md"
    pdf.write_bytes(b"original")
    jokbo.write_text("original", encoding="utf-8")
    sources = [{"id": "S1", "kind": "notes_current", "filename": pdf.name},
               {"id": "S2", "kind": "jokbo", "filename": jokbo.name}]
    cache = tmp_path / "cache"
    cache.mkdir()
    origin = cache / "independent-origin.json"
    origin.write_text(json.dumps(question_first.point_origin(pdf, "강의", sources, jokbo=jokbo)), encoding="utf-8")
    point = {"point_id": "P1", "point": "objective", "source_refs": "S1 p.1"}
    points = cache / "authored-points.json"
    points.write_text(json.dumps([point]), encoding="utf-8")
    assert question_first.cached_points(cache, pdf, "강의", sources, jokbo=jokbo) == points
    title = "강의"
    if change == "pdf":
        pdf.write_bytes(b"changed")
    elif change == "jokbo":
        jokbo.write_text("changed", encoding="utf-8")
    elif change == "title":
        title = "다른 강의"
    elif change == "scope":
        monkeypatch.setattr(question_first, "lecture_scope", lambda *args: "changed scope")
    elif change == "broken":
        points.write_text("{", encoding="utf-8")
    elif change == "empty":
        points.write_text("[]", encoding="utf-8")
    elif change == "duplicate":
        points.write_text(json.dumps([point, point]), encoding="utf-8")
    else:
        origin.unlink()
    assert question_first.cached_points(cache, pdf, title, sources, jokbo=jokbo) is None
