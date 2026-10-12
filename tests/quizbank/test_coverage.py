import copy
import json
from pathlib import Path

import fitz
import pytest

from quizbank import coverage, run
from quizbank.schema import without_retired
from quizbank.validate import validate_dropping
from quizbank.points import shape_plan, match_report
from studyez_llm.codex import SessionError


@pytest.fixture
def bank():
    raw = json.loads((Path(__file__).parent / "fixtures" / "bank_261002_02.json").read_text(encoding="utf-8"))
    return without_retired(validate_dropping(raw, ["S1", "S2"])[0])


def report(qid, count=1):
    return {"summary": "원본 대조", "pages": [{"page": p, "status": "checked", "note": "",
            "points": [{"fact": "출제 사실", "status": "covered", "question_ids": [qid]}]} for p in range(1, count + 1)],
            "mcq_opportunities": []}


def patch_for(bank):
    patch = copy.deepcopy(bank)
    patch["questions"] = [{**copy.deepcopy(bank["questions"][0]), "question_id": "SUP_Q1", "question": "추가 출제 포인트를 회상하시오."}]
    patch["concepts"] = patch["concepts"][:1]
    patch["retrieval_plan"] = patch["retrieval_plan"][:1]
    patch["source_conflicts"] = []
    patch["audit_summary"]["changes"] = ["원본 누락 보강"]
    return patch


def test_missing_pages_and_unknown_question_are_not_verified(bank):
    checked = coverage.shape_report(report("nonexistent"), bank, 2)
    assert checked["status"] == "partial" and checked["gapCount"] == 1
    assert checked["unreadablePages"] == 1 and checked["totalPages"] == 2
    with pytest.raises(SessionError, match="중복 쪽"):
        coverage.shape_report({**report("Q001"), "pages": report("Q001")["pages"] * 2}, bank, 1)
    with pytest.raises(SessionError, match="제외 근거"):
        coverage.shape_report({**report("Q001"), "pages": [{"page": 1, "status": "excluded", "note": "", "points": []}]}, bank, 1)


def test_supplement_preserves_questions_and_rejects_overwrite_or_invalid_answer(bank):
    original = copy.deepcopy(bank)
    patch = patch_for(bank)
    merged = coverage.merge_additions(bank, patch, ["S1", "S2"])
    assert bank == original
    assert merged["questions"][:-1] == original["questions"]
    assert merged["questions"][-1]["question_id"] == "SUP_Q1"
    patch["questions"][0]["question_id"] = original["questions"][0]["question_id"]
    with pytest.raises(SessionError, match="재사용"):
        coverage.merge_additions(bank, patch, ["S1", "S2"])
    patch = patch_for(bank)
    patch["questions"][0]["answer_units"] = []
    with pytest.raises(SessionError, match="검증 실패"):
        coverage.merge_additions(bank, patch, ["S1", "S2"])


def test_audit_uses_all_pdf_pages_and_independent_post_supplement_check(bank, tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    with fitz.open() as doc:
        for _ in range(2):
            doc.new_page().insert_text((40, 40), "Source fact")
        doc.save(pdf)
    plan = {"summary": "출제 포인트", "objectives": [{"objective_id": "O1", "objective": "원본 사실을 인출한다", "slides": [1, 2],
        "retrieval_targets": [{"point_id": "P1", "target": "원본의 독립 사실"}]}], "rejected_candidates": [], "unreadable_pages": []}
    initial = {"summary": "누락", "checks": [{"point_id": "P1", "status": "gap", "question_ids": [], "note": "없음"}], "mcq_opportunities": []}
    final = {"summary": "보강 후 확인", "checks": [{"point_id": "P1", "status": "covered", "question_ids": ["SUP_Q1"], "note": "직접 출제"}], "mcq_opportunities": []}
    calls = []
    def fake(prompt, schema, work, model, label):
        calls.append(label)
        assert len(json.loads((work / "source-pages.json").read_text())) == 2
        assert "PDF p.2" in (work / "source-text.md").read_text(encoding="utf-8")
        if len(calls) == 1:
            assert not (work / "bank.json").exists()
            return plan, {}
        assert json.loads((work / "point-plan.json").read_text(encoding="utf-8"))["objectives"] == plan["objectives"]
        return (initial if len(calls) == 2 else patch_for(bank) if len(calls) == 3 else final), {}
    monkeypatch.setattr(coverage, "_call", fake)
    sources = [{"id": "S1", "kind": "notes_current", "filename": pdf.name}, {"id": "S2", "kind": "jokbo", "filename": "j.md"}]
    enriched, checked, usage = coverage.audit_and_supplement(bank, pdf, "강의", sources, tmp_path / "out")
    assert len(calls) == 4 and len(usage) == 4
    assert checked["status"] == "verified" and checked["addedQuestions"] == 1
    assert checked["bankHash"] == coverage.bank_hash(enriched)
    assert checked["sourceSha256"]
    assert checked["pointCount"] == checked["coveredPointCount"] == 1


def test_fixed_point_plan_cannot_be_shrunk_by_missing_matches(bank):
    plan = shape_plan({"summary": "", "objectives": [{"objective_id": "O1", "objective": "식별한다", "slides": [1],
        "retrieval_targets": [{"point_id": "P1", "target": "첫 사실"}, {"point_id": "P2", "target": "둘째 사실"}]}],
        "rejected_candidates": [], "unreadable_pages": []}, 2)
    assert plan["unreadable_pages"] == [2]
    checked = match_report({"summary": "", "checks": [{"point_id": "P1", "status": "covered", "question_ids": [bank["questions"][0]["question_id"]], "note": ""}],
                           "mcq_opportunities": []}, bank, plan, 2)
    assert checked["pointCount"] == 2 and checked["coveredPointCount"] == 1 and checked["gapCount"] == 1
    assert checked["pages"][0]["points"][1]["status"] == "gap"


def test_existing_bank_bypasses_reorganization_and_retains_audit_report(bank, tmp_path, monkeypatch):
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps(bank), encoding="utf-8")
    raw = tmp_path / "raw.md"
    raw.write_text("", encoding="utf-8")
    monkeypatch.setattr(run.organize, "organize", lambda *a, **k: pytest.fail("Existing cards must not be reorganized"))
    monkeypatch.setattr(run.coverage, "audit_and_supplement", lambda *a, **k: (bank, {"status": "partial", "gapCount": 1,
        "unreadablePages": 0, "addedQuestions": 0, "addedMcq": 0}, []))
    monkeypatch.setattr(run.slides, "render", lambda *a, **k: ([], []))
    result = run.run(raw, tmp_path / "a.pdf", "강의", "test", [{"id": "S1"}, {"id": "S2"}],
                     tmp_path / "out", existing_bank=existing, do_review=False)
    assert result["pass"] and result["coverage"]["status"] == "partial"
    assert json.loads((tmp_path / "out" / "validation.json").read_text(encoding="utf-8"))["coverage"]["gapCount"] == 1
