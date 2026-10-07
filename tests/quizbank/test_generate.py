import json

import fitz
import pytest

from quizbank import generate
from studyez_llm.codex import SessionError


def test_prompt_uses_canonical_template_and_preserves_cloze():
    body, version = generate.prompt_for("강의", "2026-10-20", [
        {"id": "S1", "kind": "notes_current", "filename": "a.pdf"}])
    assert version != "unknown" and "Version:" not in body
    assert "{{title}}" not in body and "a.pdf" in body and "{{c1::" in body


def test_generate_reads_pdf_and_continues_without_completion(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Source text")
        doc.save(pdf)
    calls = []
    def run(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {"text": "문항 " * 100 if len(calls) == 1 else "나머지\nSTUDYEZ_BANK_COMPLETE",
                "session_id": "s1", "session_usage": {"input_tokens": 5},
                "usage": {"input_tokens": 5}, "cost_usd": None, "duration_ms": 100}
    monkeypatch.setattr(generate.codex, "run", run)
    out = tmp_path / "out"
    context = {"title": "강의", "sources": [{"id": "S1", "kind": "notes_current", "filename": "a.pdf"}]}
    result = generate.generate(pdf, context, out)
    assert calls[0][1]["blind"] is False
    assert calls[1][1]["resume"] == "s1" and calls[1][1]["previous_usage"] == {"input_tokens": 5}
    assert "Source text" in (out / "source-text.md").read_text(encoding="utf-8")
    assert len(json.loads((out / "source-pages.json").read_text())) == 1
    assert (out / "raw.md").read_text(encoding="utf-8").endswith("STUDYEZ_BANK_COMPLETE")
    assert len(result["usage"]) == 2


def test_registered_jokbo_must_be_available(tmp_path):
    with pytest.raises(SessionError, match="족보"):
        generate.generate(tmp_path / "missing.pdf", {"sources": [{"kind": "jokbo"}]}, tmp_path / "out")
