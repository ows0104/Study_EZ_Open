import copy
import json
from pathlib import Path

import fitz
import pytest

from quizbank import run, web_audit
from quizbank.schema import without_retired
from quizbank.validate import validate_dropping
from studyez_llm.codex import SessionError

RAW = """## 0. Exam Point Plan
| point_id | point | source_refs |
| --- | --- | --- |
| P001 | 회수할 원본 사실 | S1 p.1 |

## 3. Question Bank
"""

@pytest.fixture
def bank():
    original = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    return without_retired(validate_dropping(original, ["S1", "S2"])[0])

def report(bank):
    return {"summary": "검토", "pages": [{"page": 1, "status": "checked", "note": ""}],
        "checks": [{"point_id": "P001", "status": "covered", "question_ids": [bank["questions"][0]["question_id"]], "note": "직접 회수"}],
        "plan_issues": [], "question_issues": [], "duplicates": [],
        "classifications": [{"question_id": q["question_id"], "recommended_mode": q["mcq_mode"], "reason": "학습 목표 확인"}
                            for q in bank["questions"] if q["format"] in ("mcq", "multi_select")]}

def test_plan_is_read_from_web_and_never_silently_recreated():
    assert web_audit.parse_points(RAW)[0]["point_id"] == "P001"
    with pytest.raises(SessionError, match="Exam Point Plan"):
        web_audit.parse_points("포인트 없이 문제만 출력")
    with pytest.raises(SessionError, match="중복"):
        web_audit.parse_points(RAW.replace("\n\n## 3", "\n| P001 | 다른 사실 | S1 p.1 |\n\n## 3"))
    assert web_audit.enabled("1.29") and web_audit.enabled("v1.30")
    assert not web_audit.enabled("1.27") and not web_audit.enabled("2.3")

def test_report_requires_complete_source_point_and_mcq_checks(bank):
    valid = report(bank)
    points = web_audit.parse_points(RAW)
    checked = web_audit.shape_report(valid, bank, points, 1)
    assert checked["status"] == "verified" and not checked["requiresRevision"]
    for key, message in [("pages", "원본 쪽"), ("checks", "출제 포인트"), ("classifications", "객관식")]:
        invalid = {**valid, key: []}
        with pytest.raises(SessionError, match=message):
            web_audit.shape_report(invalid, bank, points, 1)
    invalid = copy.deepcopy(valid)
    invalid["checks"][0]["question_ids"] = ["absent"]
    with pytest.raises(SessionError, match="문항 ID"):
        web_audit.shape_report(invalid, bank, points, 1)


def test_pdf_point_locations_expand_ranges_and_never_invent_page_one(bank):
    assert web_audit.authored_pages("S1 pp.3–7,10; S2 p.1") == [3, 4, 5, 6, 7, 10]
    assert web_audit.authored_pages("S3 p.2-3; S1 p.1", "S3") == [2, 3]
    valid = report(bank)
    valid["pages"] = [{"page": p, "status": "checked", "note": ""} for p in range(1, 8)]
    points = [{"point_id": "P001", "point": "근거 범위", "source_refs": "S1 pp.3–7; S2 p.1"}]
    checked = web_audit.shape_report(valid, bank, points, 7)
    assert [p["page"] for p in checked["pages"] if p["points"]] == [3, 4, 5, 6, 7]
    points[0]["source_refs"] = "S2 2025-1"
    checked = web_audit.shape_report(valid, bank, points, 7)
    assert not any(p["points"] for p in checked["pages"])

def test_missing_condition_duplicates_or_wrong_mode_require_web_revision(bank):
    original = copy.deepcopy(bank)
    points = web_audit.parse_points(RAW)
    for kind in ("partial", "duplicate", "mode"):
        raw = report(bank)
        if kind == "partial":
            raw["checks"][0]["status"] = "partial"
        elif kind == "duplicate":
            raw["duplicates"] = [{"question_ids": [q["question_id"] for q in bank["questions"][:2]], "reason": "동일 판단", "suggested_action": "통합"}]
        else:
            row = raw["classifications"][0]
            row["recommended_mode"] = "comparison" if row["recommended_mode"] == "recall_first" else "recall_first"
        checked = web_audit.shape_report(raw, bank, points, 1)
        assert checked["requiresRevision"] and checked["status"] == "partial"
        assert bank == original

def test_new_web_flow_keeps_questions_and_never_calls_supplement(bank, tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Source fact")
        doc.save(pdf)
    raw_path = tmp_path / "raw.md"
    raw_path.write_text(RAW, encoding="utf-8")
    monkeypatch.setattr(run.organize, "organize", lambda *a, **k: (copy.deepcopy(bank), {}))
    def forbid(*a, **k):
        raise AssertionError("CLI must not supplement web-authored questions")
    monkeypatch.setattr(run.coverage, "audit_and_supplement", forbid)
    monkeypatch.setattr(run, "validate_dropping", forbid)
    def fake_call(prompt, schema, work, model, label):
        assert len(json.loads((work / "source-pages.json").read_text(encoding="utf-8"))) == 1
        assert "P001" in (work / "point-plan.json").read_text(encoding="utf-8")
        return report(bank), {}
    monkeypatch.setattr(web_audit, "_call", fake_call)
    out = tmp_path / "out"
    result = run.run(raw_path, pdf, "강의", "lecture", [{"id": "S1"}, {"id": "S2"}], out,
                     prompt_version="1.29", do_review=False)
    assert result["pass"] and not result["requiresRevision"]
    assert json.loads((out / "bank.json").read_text(encoding="utf-8")) == bank
    assert result["coverage"]["addedQuestions"] == result["coverage"]["addedMcq"] == 0
