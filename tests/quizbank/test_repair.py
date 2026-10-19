import copy
import json
from pathlib import Path

import fitz
import pytest

from quizbank import explain, repair, run, web_audit
from quizbank.schema import without_retired
from quizbank.session import SessionError
from quizbank.validate import validate_dropping
from tests.quizbank.test_web_audit import RAW, report


@pytest.fixture
def bank():
    original = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    result = without_retired(validate_dropping(original, ["S1", "S2"])[0])
    for q in result["questions"]:
        q["importance"] = {"Core": 5, "Important": 4, "Optional": 2}[q["tier"]]
    return result


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Source fact")
        doc.save(pdf)
    raw = tmp_path / "raw.md"
    raw.write_text(RAW, encoding="utf-8")
    monkeypatch.setattr(run.slides, "render", lambda *a, **k: ([], []))
    return raw, pdf, tmp_path / "out"


def execute(bank, inputs, monkeypatch, **kwargs):
    raw, pdf, out = inputs
    monkeypatch.setattr(run.organize, "organize", lambda *a, **k: (copy.deepcopy(bank), {}))
    return run.run(raw, pdf, "강의", "lecture", [{"id": "S1"}, {"id": "S2"}], out,
                   prompt_version=kwargs.pop("prompt_version", "1.31"), **kwargs)


def audit(bank, *args, **kwargs):
    points = kwargs.get("points") or web_audit.parse_points(RAW)
    return web_audit.shape_report(report(bank), bank, points, 1), []


def good_review(bank, *args, **kwargs):
    return {"counts": {"ok": len(bank["questions"]), "wrong": 0, "doubt": 0}, "missing": [],
            "summary": "정답 오류 없음", "reviews": [{"question_id": q["question_id"], "verdict": "ok",
            "note": "", "suggested_answer": ""} for q in bank["questions"]]}, {}


def test_invalid_authored_question_is_repaired_then_reaudited_without_dropping(bank, inputs, monkeypatch):
    original = copy.deepcopy(bank)
    bank["questions"][0]["mcq_mode"] = "comparison"  # matching cannot have an MCQ mode
    seen = []
    def inspect(candidate, *args, **kwargs):
        data = report(candidate)
        if candidate["questions"][0]["mcq_mode"] == "comparison":
            data["checks"][0]["status"] = "gap"
        return web_audit.shape_report(data, candidate, web_audit.parse_points(RAW), 1), []
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        assert findings["validation"]["errors"]
        assert findings["audit"]["gapCount"] == 1
        assert findings["review"]["counts"]["ok"] == len(candidate["questions"])
        seen.append(number)
        return copy.deepcopy(original), web_audit.parse_points(raw), {"round": number}, {}
    monkeypatch.setattr(repair, "repair", fix)
    monkeypatch.setattr(web_audit, "inspect", inspect)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch)
    out = inputs[2]
    assert result["pass"] and not result["requiresRevision"]
    assert result["dropped"] == 0 and result["questions"] == len(original["questions"])
    assert seen == [1]
    assert json.loads((out / "bank.before-repair.json").read_text(encoding="utf-8")) == bank
    assert json.loads((out / "bank.json").read_text(encoding="utf-8")) == original


def test_content_checks_do_not_clear_semantic_validation_errors(bank, inputs, monkeypatch):
    bank["questions"][0]["mcq_mode"] = "comparison"
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch, max_repair_rounds=0)
    assert not result["pass"] and result["requiresRevision"]
    assert result["coverage"]["status"] == "verified"
    assert result["review"]["wrong"] == 0
    assert result["repairs"]["attempts"] == 0


def test_malformed_fields_wait_for_cli_repair_before_content_checks(bank, inputs, monkeypatch):
    original = copy.deepcopy(bank)
    bank["questions"][0]["answer_units"] = None
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        assert findings["validation"]["errors"]
        assert findings["audit"] is None and findings["review"] is None
        return copy.deepcopy(original), web_audit.parse_points(raw), {"round": number}, {}
    monkeypatch.setattr(repair, "repair", fix)
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch)
    assert result["pass"] and not result["requiresRevision"]
    assert result["repairs"]["attempts"] == 1


@pytest.mark.parametrize("final_verdict", ["ok", "doubt"])
def test_source_gap_and_wrong_answer_are_repaired_and_final_bank_is_reviewed(bank, inputs, monkeypatch, final_verdict):
    first = bank["questions"][0]["question_id"]
    reviewed = []
    def inspect(candidate, *args, **kwargs):
        data = report(candidate)
        if len(candidate["questions"]) == len(bank["questions"]):
            data["checks"][0]["status"] = "gap"
        return web_audit.shape_report(data, candidate, web_audit.parse_points(RAW), 1), []
    def review(candidate, *args, **kwargs):
        reviewed.append(copy.deepcopy(candidate))
        wrong = len(reviewed) == 1
        return {"counts": {"wrong": int(wrong), "doubt": int(not wrong and final_verdict == "doubt")}, "missing": [],
                "reviews": [{"question_id": first, "verdict": "wrong" if wrong else final_verdict,
                             "note": "정답 근거 확인", "suggested_answer": "근거에 따른 수정"}]}, {}
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        assert findings["audit"]["gapCount"] == 1 and findings["review"]["counts"]["wrong"] == 1
        changed = copy.deepcopy(candidate)
        new = copy.deepcopy(changed["questions"][0])
        new.update(question_id="NEW", question="누락 포인트를 회수하는 새 발문")
        changed["questions"].append(new)
        return changed, web_audit.parse_points(raw), {"round": number}, {}
    monkeypatch.setattr(repair, "repair", fix)
    monkeypatch.setattr(web_audit, "inspect", inspect)
    monkeypatch.setattr(run.review, "review", review)
    result = execute(bank, inputs, monkeypatch)
    assert not result["requiresRevision"] and len(reviewed) == 2
    assert result["coverage"]["addedQuestions"] == 1
    assert result["review"]["doubt"] == int(final_verdict == "doubt")
    assert len(reviewed[-1]["questions"]) == result["questions"]
    assert json.loads((inputs[2] / "review.json").read_text(encoding="utf-8"))["counts"]["wrong"] == 0


@pytest.mark.parametrize("verdict", ["wrong", "missing"])
@pytest.mark.parametrize("max_rounds", [0, 1, 2, 3])
def test_repair_limit_retains_latest_diagnostics_and_permits_publication(bank, inputs, monkeypatch, verdict, max_rounds):
    reviewed = []
    def bad_review(candidate, *args, **kwargs):
        reviewed.append(candidate)
        return {"counts": {"wrong": int(verdict == "wrong")},
                "missing": [candidate["questions"][0]["question_id"]] if verdict == "missing" else []}, {}
    attempts = []
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        attempts.append(number)
        changed = copy.deepcopy(candidate)
        changed["audit_summary"]["changes"].append(str(number))
        return changed, web_audit.parse_points(raw), {"round": number}, {}
    monkeypatch.setattr(repair, "repair", fix)
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", bad_review)
    result = execute(bank, inputs, monkeypatch, max_repair_rounds=max_rounds)
    assert result["requiresRevision"] and attempts == list(range(1, max_rounds + 1))
    assert len(reviewed) == max_rounds + 1
    assert result["repairs"]["attempts"] == result["repairs"]["maxAttempts"] == max_rounds
    stored = json.loads((inputs[2] / "review.json").read_text(encoding="utf-8"))
    assert stored["missing"] if verdict == "missing" else stored["counts"]["wrong"] == 1
    assert (inputs[2] / 'pages.json').exists()
    assert result['publication']['allowed'] and result['publication']['hasUnresolved']


def test_missing_reviews_require_cli_repair_then_independent_review(bank, inputs, monkeypatch):
    reviewed = []
    repaired = []
    first = bank["questions"][0]["question_id"]
    def inspect_answers(candidate, *args, **kwargs):
        reviewed.append(copy.deepcopy(candidate))
        if len(reviewed) == 1:
            return {"counts": {"wrong": 0, "doubt": 0}, "missing": [first]}, {}
        return good_review(candidate)
    def cli_repair(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        assert findings["review"] == inspected_before
        repaired.append(number)
        corrected = copy.deepcopy(candidate)
        corrected["questions"][0]["exam_rationale"] += " CLI 원본 조건 확인"
        return corrected, web_audit.parse_points(raw), {"round": number}, {}
    inspected_before = {"counts": {"wrong": 0, "doubt": 0}, "missing": [first]}
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", inspect_answers)
    monkeypatch.setattr(repair, "repair", cli_repair)
    result = execute(bank, inputs, monkeypatch)
    assert not result["requiresRevision"] and repaired == [1]
    assert len(reviewed) == 2 and reviewed[0] != reviewed[1]
    assert reviewed[1] == json.loads((inputs[2] / "bank.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("origin", ["answer", "source", "explanations", "all"])
def test_minor_doubts_are_visible_and_complete_without_any_repair_loop(bank, inputs, monkeypatch, origin):
    from tests.quizbank.test_explain import annotations
    first = explain.targets(bank)[0]["question_id"]
    def inspect(candidate, *args, **kwargs):
        raw = report(candidate)
        if origin in ("source", "all"):
            raw["question_issues"] = [{"question_id": first, "severity": "doubt", "issue": "조건 차이",
                "reason": "원본 검수 주의사항", "suggested_action": "표시"}]
        return web_audit.shape_report(raw, candidate, web_audit.parse_points(RAW), 1), []
    def inspect_answers(candidate, *args, **kwargs):
        checked, info = good_review(candidate)
        if origin in ("answer", "all"):
            row = next(row for row in checked["reviews"] if row["question_id"] == first)
            row.update(verdict="doubt", note="정답 검수 주의사항")
            checked["counts"].update(ok=len(candidate["questions"]) - 1, doubt=1)
        return checked, info
    def write_explanations(candidate, *args, **kwargs):
        data = annotations(candidate)
        data["annotations"][0].update(verdict="doubt", note="해설 검수 주의사항")
        updated, checked = explain.apply(candidate, data)
        return updated, checked, {}
    def forbid(*args, **kwargs):
        raise AssertionError("Minor doubt must not start a repair loop")
    monkeypatch.setattr(web_audit, "inspect", inspect)
    monkeypatch.setattr(run.review, "review", inspect_answers)
    monkeypatch.setattr(repair, "repair", forbid)
    monkeypatch.setattr(explain, "write", write_explanations)
    result = execute(bank, inputs, monkeypatch, prompt_version="1.32" if origin in ("explanations", "all") else "1.31")
    assert not result["requiresRevision"] and result["repairs"]["attempts"] == 0
    assert result["review"]["doubt"] == 1 and result["review"]["ok"] == len(bank["questions"]) - 1
    stored = json.loads((inputs[2] / "review.json").read_text(encoding="utf-8"))
    row = next(row for row in stored["reviews"] if row["question_id"] == first)
    assert row["verdict"] == "doubt" and "주의사항" in row["note"]
    if origin == "all":
        assert all(label in row["note"] for label in ("정답 검수", "원본 검수", "해설 검수"))
    assert (inputs[2] / "pages.json").is_file()


def test_skipped_answer_review_cannot_complete_or_attempt_content_repairs(bank, inputs, monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("Missing required review cannot be resolved by content edits")
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", forbid)
    monkeypatch.setattr(repair, "repair", forbid)
    result = execute(bank, inputs, monkeypatch, do_review=False)
    assert result["pass"] and result["requiresRevision"] and result["repairs"]["attempts"] == 0
    assert result['publication']['allowed'] and result['publication']['hasUnresolved']
    stored = json.loads((inputs[2] / 'validation.json').read_text(encoding='utf-8'))
    assert stored['revision']['review'] is None


def test_missing_plan_is_rebuilt_explicitly_in_cli(bank, inputs, monkeypatch):
    inputs[0].write_text("Question bank without point plan", encoding="utf-8")
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        assert "Exam Point Plan" in findings["audit"]["error"]
        return candidate, web_audit.parse_points(RAW), {"round": number, "pointsChanged": True}, {}
    monkeypatch.setattr(repair, "repair", fix)
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch)
    assert not result["requiresRevision"] and result["repairs"]["attempts"] == 1


def test_mcq_classification_is_applied_without_regenerating_passing_content(bank, inputs, monkeypatch):
    original = copy.deepcopy(bank)
    target = next(q for q in bank["questions"] if q["format"] == "mcq")
    recommended = "comparison" if target["mcq_mode"] == "recall_first" else "recall_first"
    def inspect(candidate, *args, **kwargs):
        data = report(candidate)
        next(row for row in data["classifications"] if row["question_id"] == target["question_id"])["recommended_mode"] = recommended
        return web_audit.shape_report(data, candidate, web_audit.parse_points(RAW), 1), []
    def forbid(*args, **kwargs):
        raise AssertionError("A mode-only recommendation needs no new repair session")
    monkeypatch.setattr(web_audit, "inspect", inspect)
    monkeypatch.setattr(repair, "repair", forbid)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch)
    updated = json.loads((inputs[2] / "bank.json").read_text(encoding="utf-8"))
    assert not result["requiresRevision"] and result["repairs"]["attempts"] == 0
    for before, after in zip(original["questions"], updated["questions"], strict=True):
        assert {k: v for k, v in before.items() if k != "mcq_mode"} == {k: v for k, v in after.items() if k != "mcq_mode"}
    assert next(q for q in updated["questions"] if q["question_id"] == target["question_id"])["mcq_mode"] == recommended


def test_repair_failure_keeps_original_bank_and_reports_cli_error(bank, inputs, monkeypatch):
    bank["questions"][0]["mcq_mode"] = "comparison"
    def fail(*a, **k):
        raise repair.RepairError("CLI 수정 파일 오류")
    monkeypatch.setattr(repair, "repair", fail)
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch)
    assert result["requiresRevision"] and result["repairError"] == "CLI 수정 파일 오류"
    assert result["repairs"]["attempts"] == 1 and result["repairs"]["acceptedAttempts"] == 0
    assert json.loads((inputs[2] / "bank.json").read_text(encoding="utf-8")) == bank


def test_cli_session_failure_propagates_for_runner_retry_without_a_final_result(bank, inputs, monkeypatch):
    bank["questions"][0]["mcq_mode"] = "comparison"
    def fail(*args, **kwargs):
        raise SessionError("CLI 세션 한도")
    monkeypatch.setattr(repair, "repair", fail)
    monkeypatch.setattr(web_audit, "inspect", audit)
    monkeypatch.setattr(run.review, "review", good_review)
    with pytest.raises(SessionError, match="세션 한도"):
        execute(bank, inputs, monkeypatch)
    assert not (inputs[2] / "result.json").exists()
    assert (inputs[2] / "validation.json").exists()
    checkpoint = json.loads((inputs[2] / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["repairs"]["attempts"] == 1


def test_uncertain_source_fact_preserves_doubt_without_repairing_it(bank, inputs, monkeypatch):
    first = bank['questions'][0]['question_id']
    def inspect(candidate, *args, **kwargs):
        raw = report(candidate)
        raw['checks'][0].update(status='uncertain', question_ids=[first], note='원본 사실의 불확실성')
        raw['plan_issues'] = [{'kind': 'uncertain', 'point_ids': [raw['checks'][0]['point_id']],
            'pages': [1], 'fact': '원본과 현대 설명의 차이', 'reason': '확정하지 않음'}]
        return web_audit.shape_report(raw, candidate, web_audit.parse_points(RAW), 1), []
    def forbid(*args, **kwargs):
        raise AssertionError('Uncertainty alone must not spend another repair round')
    monkeypatch.setattr(web_audit, 'inspect', inspect)
    monkeypatch.setattr(run.review, 'review', good_review)
    monkeypatch.setattr(repair, 'repair', forbid)
    result = execute(bank, inputs, monkeypatch)
    assert not result['requiresRevision'] and result['repairs']['attempts'] == 0
    source = json.loads((inputs[2] / 'coverage.json').read_text(encoding='utf-8'))
    assert source['uncertainPointCount'] == 1 and source['coveredPointCount'] == 0
    assert source['gapCount'] == 0 and source['webAudit']['checks'][0]['status'] == 'uncertain'
    reviewed = json.loads((inputs[2] / 'review.json').read_text(encoding='utf-8'))
    row = next(r for r in reviewed['reviews'] if r['question_id'] == first)
    assert row['verdict'] == 'doubt' and '원본 사실의 불확실성' in row['note']


def test_file_repair_logs_actual_changes_and_preserves_input(bank, inputs, monkeypatch):
    corrected = copy.deepcopy(bank)
    corrected["questions"][0]["exam_rationale"] += " 수정 근거"
    def write(prompt, schema, work, model, label):
        assert "웹·브라우저·ChatGPT" in prompt
        assert repair.item_quality_guidance() in prompt
        (work / "repaired-bank.json").write_text(json.dumps(corrected), encoding="utf-8")
        (work / "repaired-points.json").write_text(json.dumps(web_audit.parse_points(RAW)), encoding="utf-8")
        return {"written": True, "summary": "근거 수정", "changes": ["Q001의 근거 수정"]}, {}
    monkeypatch.setattr(repair, "_call", write)
    raw, pdf, out = inputs
    updated, points, log, _ = repair.repair(bank, RAW, pdf, "강의", [{"id": "S1"}], {}, out, 1)
    assert updated == corrected and log["questions"]["modified"] == [bank["questions"][0]["question_id"]]
    assert log["beforeHash"] != log["afterHash"]
    assert json.loads((out / "repair/1/bank.json").read_text(encoding="utf-8")) == bank
    assert json.loads((out / "authored-points.json").read_text(encoding="utf-8")) == points


def test_file_repair_rejects_no_change_and_wrong_metadata(bank, inputs, monkeypatch):
    for wrong_meta in (False, True):
        def write(prompt, schema, work, model, label, wrong_meta=wrong_meta):
            changed = copy.deepcopy(bank)
            if wrong_meta:
                changed["build_meta"]["lecture_title"] = "다른 강의"
            (work / "repaired-bank.json").write_text(json.dumps(changed), encoding="utf-8")
            (work / "repaired-points.json").write_text(json.dumps(web_audit.parse_points(RAW)), encoding="utf-8")
            return {"written": True, "summary": "수정", "changes": ["수정"]}, {}
        monkeypatch.setattr(repair, "_call", write)
        with pytest.raises(SessionError, match="제목|변경이 없습니다"):
            repair.repair(bank, RAW, inputs[1], "강의", [{"id": "S1"}], {}, inputs[2], 1)


def test_maintenance_keeps_existing_content_and_uses_additive_cli_flow(bank, inputs, monkeypatch):
    existing = inputs[0].with_name("existing.json")
    existing.write_text(json.dumps(bank), encoding="utf-8")
    def forbid(*args, **kwargs):
        raise AssertionError("Maintenance cannot rewrite existing questions")
    monkeypatch.setattr(repair, "repair", forbid)
    monkeypatch.setattr(web_audit, "inspect", forbid)
    monkeypatch.setattr(run, "validate_dropping", forbid)
    def supplement(candidate, *args, **kwargs):
        assert candidate == bank
        return candidate, {"status": "verified", "gapCount": 0, "unreadablePages": 0,
                           "addedQuestions": 0, "addedMcq": 0}, []
    monkeypatch.setattr(run.coverage, "audit_and_supplement", supplement)
    monkeypatch.setattr(run.review, "review", good_review)
    result = execute(bank, inputs, monkeypatch, existing_bank=existing, preserve_existing=True)
    assert result["pass"] and result["coverage"]["status"] == "verified"
    assert json.loads((inputs[2] / "bank.json").read_text(encoding="utf-8")) == bank


@pytest.mark.parametrize("remove", ["question", "point"])
def test_repair_cannot_hide_gaps_by_deleting_unreported_content(bank, inputs, monkeypatch, remove):
    def write(prompt, schema, work, model, label):
        changed = copy.deepcopy(bank)
        points = web_audit.parse_points(RAW)
        if remove == "question":
            changed["questions"].pop()
        else:
            points[0]["point_id"] = "REPLACEMENT"
        (work / "repaired-bank.json").write_text(json.dumps(changed), encoding="utf-8")
        (work / "repaired-points.json").write_text(json.dumps(points), encoding="utf-8")
        return {"written": True, "summary": "수정", "changes": ["삭제"]}, {}
    monkeypatch.setattr(repair, "_call", write)
    with pytest.raises(SessionError, match="보존|제거"):
        repair.repair(bank, RAW, inputs[1], "강의", [{"id": "S1"}], {}, inputs[2], 1)


def test_repair_can_merge_an_audited_duplicate_and_retain_one_representative(bank, inputs, monkeypatch):
    removed = bank["questions"][-1]["question_id"]
    kept = bank["questions"][0]["question_id"]
    corrected = copy.deepcopy(bank)
    corrected["questions"].pop()
    def write(prompt, schema, work, model, label):
        (work / "repaired-bank.json").write_text(json.dumps(corrected), encoding="utf-8")
        (work / "repaired-points.json").write_text(json.dumps(web_audit.parse_points(RAW)), encoding="utf-8")
        return {"written": True, "summary": "검수된 중복 통합", "changes": ["정상 대표 문항을 유지"]}, {}
    monkeypatch.setattr(repair, "_call", write)
    findings = {"audit": {"webAudit": {"duplicates": [{"question_ids": [kept, removed]}]}}}
    updated, _, log, _ = repair.repair(bank, RAW, inputs[1], "강의", [{"id": "S1"}], findings, inputs[2], 1)
    assert kept in {q["question_id"] for q in updated["questions"]}
    assert log["questions"]["removed"] == [removed]
