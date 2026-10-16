import copy
import json

import fitz
import pytest

from quizbank import priority, web_audit
from quizbank.session import SessionError
from tests.quizbank.test_web_audit import RAW, bank, report


def test_essential_requires_explicit_memorization_or_exam_evidence(bank):
    rows = report(bank)["tier_checks"]
    for basis in ("objective", "past_exam", "emphasis", "clinical", "detail"):
        rows[0].update(recommended_tier="Essential", recommended_importance=5, basis=basis)
        with pytest.raises(SessionError, match="Essential"):
            priority.assess(bank, rows)
    for basis in ("must_memorize", "exam_explicit"):
        rows[0].update(recommended_tier="Essential", recommended_importance=5, basis=basis)
        checked, issues = priority.assess(bank, rows)
        assert checked["checkedCount"] == len(bank["questions"])
        assert any(issue["question_id"] == rows[0]["question_id"] for issue in issues)


def test_every_question_needs_a_distinct_source_grounded_decision(bank):
    rows = report(bank)["tier_checks"]
    checked, issues = priority.assess(bank, rows)
    assert checked["checkedCount"] == len(bank["questions"]) and not issues
    for invalid in (rows[:-1], rows + [rows[0]]):
        with pytest.raises(SessionError, match="빠졌|중복"):
            priority.assess(bank, invalid)
    for key in ("tested_target", "evidence", "reason", "source_refs"):
        invalid = copy.deepcopy(rows)
        invalid[0][key] = [] if key == "source_refs" else " "
        with pytest.raises(SessionError, match="근거"):
            priority.assess(bank, invalid)


def test_core_cannot_be_supported_only_by_surrounding_detail_or_utility(bank):
    rows = report(bank)["tier_checks"]
    rows[0].update(recommended_tier="Core", basis="detail")
    with pytest.raises(SessionError, match="Core"):
        priority.assess(bank, rows)
    for basis in ("emphasis", "clinical"):
        rows[0].update(basis=basis)
        with pytest.raises(SessionError, match="Core"):
            priority.assess(bank, rows)
    rows[0].update(basis="objective", recommended_importance=5)
    checked, _ = priority.assess(bank, rows)
    assert checked["checkedCount"] == len(bank["questions"])


def test_importance_only_disagreement_is_actionable_without_changing_tier(bank):
    original = copy.deepcopy(bank)
    rows = report(bank)["tier_checks"]
    q = bank["questions"][0]
    importance = rows[0]["recommended_importance"]
    q["importance"] = 1
    original = copy.deepcopy(bank)
    checked, issues = priority.assess(bank, rows)
    assert checked["mismatchCount"] == 1 and len(issues) == 1
    assert f"importance={importance}" in issues[0]["suggested_action"]
    assert bank == original
    for invalid in (0, 6, True, "2"):
        rows[0]["recommended_importance"] = invalid
        with pytest.raises(SessionError, match="중요도"):
            priority.assess(bank, rows)


def test_historical_reports_without_depth_must_be_reviewed_again(bank):
    rows = report(bank)["tier_checks"]
    for row in rows:
        row.pop("recommended_advanced")
    with pytest.raises(SessionError, match="심화"):
        priority.assess(bank, rows)


def test_depth_only_disagreement_requires_repair_without_promoting_priority(bank):
    rows = report(bank)["tier_checks"]
    before = copy.deepcopy(bank)
    rows[0].update(recommended_advanced=True, advanced_reason="여러 개념의 복합 조건 적용")
    checked, issues = priority.assess(bank, rows)
    assert checked["mismatchCount"] == 1
    assert "advanced=True" in issues[0]["suggested_action"]
    assert bank == before


def test_demotion_is_actionable_and_preserves_existing_content_findings(bank):
    original = copy.deepcopy(bank)
    raw = report(bank)
    q = next(q for q in bank["questions"] if q["tier"] == "Core")
    row = next(r for r in raw["tier_checks"] if r["question_id"] == q["question_id"])
    row.update(recommended_tier="Optional", recommended_importance=2, basis="detail", evidence="명시 강조 없는 주변 약물 예시",
               reason="해당 약물명에 직접 강조·기출·필수 의존성·심화 목표가 없다")
    existing = {"question_id": q["question_id"], "severity": "doubt", "issue": "원본 불확실성",
                "reason": "기존 doubt", "suggested_action": "한계 보존"}
    raw["question_issues"].append(existing)
    checked = web_audit.shape_report(raw, bank, web_audit.parse_points(RAW), 1)
    assert checked["requiresRevision"] and checked["tierReview"]["mismatchCount"] == 1
    assert existing in checked["webAudit"]["question_issues"]
    assert any(r["issue"] == priority.ISSUE for r in checked["webAudit"]["question_issues"])
    assert bank == original


def test_inferred_priority_findings_are_saved_for_repair_and_publication(bank, tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Source objective")
        doc.save(pdf)
    raw = report(bank)
    q = next(q for q in bank["questions"] if q["tier"] == "Core")
    row = next(r for r in raw["tier_checks"] if r["question_id"] == q["question_id"])
    row.update(recommended_tier="Optional", recommended_importance=2, basis="detail")
    monkeypatch.setattr(web_audit, "_call", lambda *a: (raw, {}))
    checked, _ = web_audit.inspect(bank, RAW, pdf, "강의", [{"id": "S1"}], tmp_path)
    saved = json.loads((tmp_path / "web-audit.json").read_text(encoding="utf-8"))
    assert saved == checked["webAudit"]
    assert any(r["issue"] == priority.ISSUE for r in saved["question_issues"])
