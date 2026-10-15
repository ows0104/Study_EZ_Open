import copy
import json
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from quizbank import coverage, explain, incremental, review, run, web_audit
from quizbank.schema import without_retired
from quizbank.session import SessionError
from quizbank.validate import validate_dropping
from tests.quizbank.test_explain import annotations
from tests.quizbank.test_repair import good_review
from tests.quizbank.test_web_audit import RAW, report as source_report


@pytest.fixture
def bank():
    data = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    bank = without_retired(validate_dropping(data, ["S1", "S2"])[0])
    for q in bank["questions"]:
        q["prerequisites"], q["conflict_id"] = [], ""
        q["importance"] = {"Core": 5, "Important": 4, "Optional": 2}[q["tier"]]
    return bank


@pytest.fixture
def harness(bank, tmp_path, monkeypatch):
    pdf, jokbo, out = tmp_path / "a.pdf", tmp_path / "j.md", tmp_path / "out"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Source fact")
        doc.save(pdf)
    jokbo.write_text("Original exam reference", encoding="utf-8")
    out.mkdir()
    sources = [{"id": "S1", "kind": "notes_current", "filename": pdf.name},
               {"id": "S2", "kind": "jokbo", "filename": jokbo.name}]
    h = SimpleNamespace(pdf=pdf, jokbo=jokbo, out=out, sources=sources,
                        calls={"explain": [], "answer": [], "source": []},
                        verdicts={}, delta_mutate=lambda data: None, points=web_audit.parse_points(RAW))
    h.cache = incremental.Reviews(out, "lecture", sources, pdf, jokbo, None, "1.53")
    def explain_call(candidate, *args, **kwargs):
        h.calls["explain"].append([q["question_id"] for q in candidate["questions"]])
        data = annotations(candidate)
        for row in data["annotations"]:
            if row["question_id"] in h.verdicts:
                row.update(verdict=h.verdicts[row["question_id"]], note="Retained explanation finding")
        updated, checked = explain.apply(candidate, data)
        return updated, checked, {"seconds": 1}
    def answer_call(candidate, *args, **kwargs):
        h.calls["answer"].append([q["question_id"] for q in candidate["questions"]])
        data = good_review(candidate)[0]
        data["pool_checks"] = source_report(candidate)["pool_checks"]
        for row in data["reviews"]:
            if row["question_id"] in h.verdicts:
                row.update(verdict=h.verdicts[row["question_id"]], note="Retained independent finding")
        return review.shape(data, candidate), {"seconds": 1}
    def source_call(candidate, raw, pdf, title, sources, out, **kwargs):
        h.calls["source"].append(("full", [q["question_id"] for q in candidate["questions"]]))
        return web_audit.shape_report(source_report(candidate), candidate, kwargs["points"], 1), []
    def delta_call(prompt, schema, work, model, label):
        assert schema is incremental.DELTA_REPORT
        full = json.loads((work / "bank.json").read_text(encoding="utf-8"))
        subset = json.loads((work / "item-review-bank.json").read_text(encoding="utf-8"))
        h.calls["source"].append(("delta", [q["question_id"] for q in subset["questions"]]))
        assert len(json.loads((work / "source-pages.json").read_text(encoding="utf-8"))) == 1
        data = source_report(full)
        partial = source_report(subset) if subset["questions"] else {"classifications": [], "pool_checks": []}
        data.update(reviewed_question_ids=[q["question_id"] for q in subset["questions"]],
                    classifications=partial["classifications"], pool_checks=partial["pool_checks"])
        h.delta_mutate(data)
        return data, {"seconds": 1}
    monkeypatch.setattr(explain, "write", explain_call)
    monkeypatch.setattr(review, "review", answer_call)
    monkeypatch.setattr(web_audit, "inspect", source_call)
    monkeypatch.setattr(coverage, "_call", delta_call)
    return h


def test_unchanged_explanations_and_independent_judgments_need_no_new_cli_call(bank, harness):
    h = harness
    original = copy.deepcopy(bank)
    updated, first, _ = h.cache.explanations(bank, h.points, RAW)
    again, second, info = h.cache.explanations(updated, h.points, RAW)
    assert bank == original and again == updated
    assert len(h.calls["explain"]) == 1
    assert info["checked_questions"] == 0 and len(second["incremental"]["reusedQuestionIds"]) == len(explain.targets(bank))
    before, _ = h.cache.answers(updated, h.points, RAW)
    after, info = h.cache.answers(again, h.points, RAW)
    assert len(h.calls["answer"]) == 1 and info["checked_questions"] == 0
    assert before["reviews"] == after["reviews"] and not after["missing"]
    assert first["annotations"] == second["annotations"]


def test_priority_is_rechecked_globally_even_when_item_judgments_are_reused(bank, harness):
    h = harness
    first, _ = h.cache.source(bank, RAW, h.points)
    target = bank["questions"][0]["question_id"]
    assert first["tierReview"]["checkedCount"] == len(bank["questions"])
    def demote(data):
        row = next(r for r in data["tier_checks"] if r["question_id"] == target)
        row.update(recommended_tier="Optional", recommended_importance=2, basis="detail")
    h.delta_mutate = demote
    second, _ = h.cache.source(bank, RAW, h.points)
    assert h.calls["source"][-1] == ("delta", [])
    assert second["tierReview"]["mismatchCount"] >= 1
    h.delta_mutate = lambda data: None
    third, _ = h.cache.source(bank, RAW, h.points)
    assert third["tierReview"]["mismatchCount"] == 0
    assert not any(r["issue"] == "Tier 근거 불일치" for r in third["webAudit"]["question_issues"])


@pytest.mark.parametrize("verdict", ["wrong", "doubt"])
def test_reuse_preserves_findings_and_does_not_accumulate_display_notes(bank, harness, verdict):
    h = harness
    qid = explain.targets(bank)[0]["question_id"]
    h.verdicts[qid] = verdict
    updated, _, _ = h.cache.explanations(bank, h.points, RAW)
    first, _ = h.cache.answers(updated, h.points, RAW)
    run._review_with_notes(first, None, {"annotations": [{"question_id": qid, "verdict": "doubt", "note": "Display-only"}]})
    second, info = h.cache.answers(updated, h.points, RAW)
    assert info["checked_questions"] == 0
    assert second["counts"][verdict] == 1
    assert first["reviews"] == second["reviews"]
    _, checked, _ = h.cache.explanations(updated, h.points, RAW)
    assert next(r for r in checked["annotations"] if r["question_id"] == qid)["verdict"] == verdict


@pytest.mark.parametrize("field", ["question", "answer", "answer_units", "options", "explanation", "source_refs", "tier", "retrieval_direction"])
def test_any_question_change_rechecks_only_that_question(bank, harness, field):
    h = harness
    h.cache.answers(bank, h.points, RAW)
    changed = copy.deepcopy(bank)
    q = changed["questions"][0]
    if isinstance(q[field], list):
        q[field] = q[field] + (["changed"] if field == "answer_units" else [{"id": "NEW", "text": "Changed choice"}]
                             if field == "options" else [{"source_id": "S1", "locator": "p.1"}])
    else:
        q[field] = "Important" if field == "tier" else q[field] + " changed"
    result, _ = h.cache.answers(changed, h.points, RAW)
    assert h.calls["answer"][-1] == [q["question_id"]]
    assert set(result["incremental"]["reusedQuestionIds"]) == {q["question_id"] for q in bank["questions"][1:]}


@pytest.mark.parametrize("change", ["pdf", "jokbo", "conflict", "prompt", "model", "guidance"])
def test_context_or_policy_change_invalidates_all_prior_judgments(bank, harness, monkeypatch, tmp_path, change):
    h = harness
    h.cache.answers(bank, h.points, RAW)
    raw, points = RAW, copy.deepcopy(h.points)
    if change == "pdf":
        h.pdf.write_bytes(h.pdf.read_bytes() + b"\n%changed")
    elif change == "jokbo":
        h.jokbo.write_text("Changed reference", encoding="utf-8")
    elif change == "conflict":
        bank["source_conflicts"].append({"new": "changed conflict evidence"})
    elif change == "prompt":
        prompt = tmp_path / "prompt.md"
        prompt.write_text("Changed review criteria", encoding="utf-8")
        monkeypatch.setattr(incremental, "PROMPT", prompt)
    elif change == "model":
        h.cache.model = "gpt-6-sol"
    else:
        monkeypatch.setattr(incremental, "item_quality_guidance", lambda: "Changed common quality criteria")
    h.cache.answers(bank, points, raw)
    assert len(h.calls["answer"][-1]) == len(bank["questions"])


def test_changed_prerequisite_invalidates_transitive_dependents(bank, harness):
    h = harness
    a, b, c = bank["questions"][:3]
    a["prerequisites"], b["prerequisites"], c["prerequisites"] = [], [a["question_id"]], [b["question_id"]]
    for q in (a, b, c):
        q["conflict_id"] = ""
    h.cache.answers(bank, h.points, RAW)
    a["answer"] += " changed"
    h.cache.answers(bank, h.points, RAW)
    assert {a["question_id"], b["question_id"], c["question_id"]}.issubset(h.calls["answer"][-1])


def test_deleted_ids_are_not_reused_and_added_ids_are_checked(bank, harness):
    h = harness
    h.cache.answers(bank, h.points, RAW)
    changed = copy.deepcopy(bank)
    removed = changed["questions"].pop()
    extra = copy.deepcopy(changed["questions"][0])
    extra["question_id"] = "NEW"
    changed["questions"].append(extra)
    result, _ = h.cache.answers(changed, h.points, RAW)
    assert h.calls["answer"][-1] == ["NEW"]
    assert removed["question_id"] not in {r["question_id"] for r in result["reviews"]}
    assert not result["missing"]


def test_global_source_checks_repeat_while_unchanged_item_checks_do_not(bank, harness):
    h = harness
    first, _ = h.cache.source(bank, RAW, h.points)
    second, _ = h.cache.source(bank, RAW, h.points)
    assert h.calls["source"][-1] == ("delta", [])
    assert second["incremental"]["globalSourceCheck"]
    assert first["webAudit"]["classifications"] == second["webAudit"]["classifications"]
    assert len(second["webAudit"]["pages"]) == 1 and len(second["webAudit"]["checks"]) == len(h.points)
    def new_gap(data):
        data["checks"][0].update(status="gap", question_ids=[], note="Removed direction")
    h.delta_mutate = new_gap
    result, _ = h.cache.source(bank, RAW, h.points)
    assert result["gapCount"] == 1 and result["requiresRevision"]


def test_source_rechecks_changed_items_and_retains_new_global_findings(bank, harness):
    h = harness
    h.cache.source(bank, RAW, h.points)
    changed = copy.deepcopy(bank)
    changed["questions"][0]["question"] += " changed"
    stable_id = changed["questions"][1]["question_id"]
    issue = {"question_id": stable_id, "severity": "error", "issue": "New interaction",
             "reason": "Changed question conflicts with this one", "suggested_action": "Check both"}
    h.delta_mutate = lambda data: data["question_issues"].append(copy.deepcopy(issue))
    current, _ = h.cache.source(changed, RAW, h.points)
    assert h.calls["source"][-1] == ("delta", [changed["questions"][0]["question_id"]])
    assert issue in current["webAudit"]["question_issues"]
    h.delta_mutate = lambda data: None
    later, _ = h.cache.source(changed, RAW, h.points)
    assert issue in later["webAudit"]["question_issues"] and later["requiresRevision"]


@pytest.mark.parametrize("broken", ["reviewed_ids", "classifications", "pages", "checks"])
def test_incomplete_delta_report_cannot_certify_review(bank, harness, broken):
    h = harness
    h.cache.source(bank, RAW, h.points)
    q = next(q for q in bank["questions"] if q["format"] == "mcq")
    q["question"] += " changed"
    def corrupt(data):
        data["reviewed_question_ids" if broken == "reviewed_ids" else broken] = []
    h.delta_mutate = corrupt
    with pytest.raises(SessionError):
        h.cache.source(bank, RAW, h.points)


def test_missing_independent_review_is_never_reused_as_a_pass(bank, harness, monkeypatch):
    h = harness
    qid = bank["questions"][0]["question_id"]
    good = review.review
    def missing(candidate, *args, **kwargs):
        data, info = good(candidate, *args, **kwargs)
        data["reviews"] = [r for r in data["reviews"] if r["question_id"] != qid]
        data["missing"] = [qid]
        return data, info
    monkeypatch.setattr(review, "review", missing)
    h.cache.answers(bank, h.points, RAW)
    result, _ = h.cache.answers(bank, h.points, RAW)
    assert h.calls["answer"][-1] == [qid]
    assert result["missing"] == [qid]


def test_cache_is_run_local_and_requires_complete_source_identity(bank, harness):
    h = harness
    h.cache.answers(bank, h.points, RAW)
    fresh = incremental.Reviews(h.out, "lecture", h.sources, h.pdf, h.jokbo, None, "1.53")
    fresh.answers(bank, h.points, RAW)
    assert len(h.calls["answer"][-1]) == len(bank["questions"])
    assert incremental.Reviews.create(h.out, "lecture", [{"id": "S1"}], h.pdf, None, None, "1.53") is None


def test_pool_candidate_changes_invalidate_truth_checks(bank, harness):
    h = harness
    q = next(q for q in bank["questions"] if q["format"] == "mcq")
    q["option_pools"] = [{"pool_id": "P", "select_count": 1, "correct_when": "true", "candidates": [
        {"candidate_id": "C", "true_text": "True", "false_text": "False", "true_explanation": "Reason",
         "false_explanation": "Correction", "source_refs": [{"source_id": "S1", "locator": "p.1"}]}]}]
    h.cache.answers(bank, h.points, RAW)
    old = h.cache.entries["answer"][q["question_id"]]["checks"][0]["content_hash"]
    q["option_pools"][0]["candidates"][0]["false_text"] = "Changed false statement"
    h.cache.answers(bank, h.points, RAW)
    assert h.calls["answer"][-1] == [q["question_id"]]
    assert h.cache.entries["answer"][q["question_id"]]["checks"][0]["content_hash"] != old


def test_pipeline_keeps_three_repair_limit_and_full_final_review_records(bank, harness, monkeypatch):
    h = harness
    wrong_id = explain.targets(bank)[0]["question_id"]
    h.verdicts[wrong_id] = "wrong"
    edited_id = next(q["question_id"] for q in bank["questions"] if q["format"] == "basic")
    rounds = []
    def fix(candidate, raw, pdf, title, sources, findings, out, number, **kwargs):
        rounds.append(number)
        assert findings["review"]["counts"]["wrong"] == 1
        revised = copy.deepcopy(candidate)
        next(q for q in revised["questions"] if q["question_id"] == edited_id)["explanation"] += f" Revision {number}"
        return revised, copy.deepcopy(kwargs["points"]), {"round": number}, {}
    monkeypatch.setattr(run.repair, "repair", fix)
    monkeypatch.setattr(run.slides, "render", lambda *a, **k: ([], []))
    point_path = h.out / "authored-points.json"
    point_path.write_text(json.dumps(h.points), encoding="utf-8")
    result = run._run_authored(bank, RAW, h.pdf, "lecture", "L1", h.sources, h.out,
        pdf_source="S1", do_review=True, do_coverage=True, model=None,
        prompt_version="1.32", jokbo=h.jokbo, point_plan=point_path, max_repair_rounds=3)
    assert rounds == [1, 2, 3]
    assert len(h.calls["explain"]) == 1
    assert len(h.calls["answer"]) == 4
    assert all(ids == [edited_id] for ids in h.calls["answer"][1:])
    assert len(h.calls["source"]) == 4
    assert all(mode == "delta" and ids == [edited_id] for mode, ids in h.calls["source"][1:])
    assert result["requiresRevision"] and result["publication"]["hasUnresolved"]
    final = json.loads((h.out / "review.json").read_text(encoding="utf-8"))
    assert final["counts"]["wrong"] == 1 and len(final["reviews"]) == len(bank["questions"])
    events = [json.loads(s) for s in (h.out / "review-reuse.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(len(e["checkedQuestionIds"]) for e in events if e["stage"] == "answer") == len(bank["questions"]) + 3
    assert len([e for e in events if e["globalSourceCheck"]]) == 4


def test_full_source_fallback_uses_fresh_evidence_directory_on_source_change(bank, harness, monkeypatch):
    h = harness
    h.cache.source(bank, RAW, h.points)
    original = web_audit.inspect
    directories = []
    def inspect(candidate, raw, pdf, title, sources, out, **kwargs):
        directories.append(out)
        return original(candidate, raw, pdf, title, sources, out, **kwargs)
    monkeypatch.setattr(web_audit, "inspect", inspect)
    h.jokbo.write_text("New source evidence", encoding="utf-8")
    h.cache.source(bank, RAW, h.points)
    assert h.calls["source"][-1][0] == "full"
    assert directories[0] != h.out


def test_point_changes_recheck_linked_source_items_but_not_independent_answers(bank, harness):
    h = harness
    for i, q in enumerate(bank["questions"]):
        q["source_refs"] = [{"source_id": "S1", "locator": "p.1" if i == 0 else "p.2"}]
    h.cache.answers(bank, h.points, RAW)
    h.cache.source(bank, RAW, h.points)
    points = copy.deepcopy(h.points)
    points[0]["point"] += " Changed required target"
    answer, info = h.cache.answers(bank, points, RAW)
    source, _ = h.cache.source(bank, RAW, points)
    assert len(h.calls["answer"]) == 1 and info["checked_questions"] == 0
    assert not answer["missing"]
    assert h.calls["source"][-1] == ("delta", [bank["questions"][0]["question_id"]])
    assert source["incremental"]["globalSourceCheck"]


def test_authoring_history_does_not_churn_explanations_but_global_audit_still_runs(bank, harness):
    h = harness
    updated, _, _ = h.cache.explanations(bank, h.points, RAW)
    h.cache.source(updated, RAW, h.points)
    updated["audit_summary"]["summary"] = "Repair history changed"
    updated["warnings"].append("A new scope warning for the global audit")
    again, checked, info = h.cache.explanations(updated, h.points, RAW)
    assert len(h.calls["explain"]) == 1 and info["checked_questions"] == 0
    h.cache.source(again, RAW, h.points)
    assert h.calls["source"][-1] == ("delta", [])
    assert again["warnings"] == updated["warnings"]


def test_same_conflict_references_invalidate_otherwise_unchanged_answers(bank, harness):
    h = harness
    a, b = bank["questions"][:2]
    a["conflict_id"] = b["conflict_id"] = "SHARED"
    h.cache.answers(bank, h.points, RAW)
    a["answer"] += " Changed condition"
    h.cache.answers(bank, h.points, RAW)
    assert {a["question_id"], b["question_id"]}.issubset(h.calls["answer"][-1])


def test_referenced_context_is_read_only_and_transitive_conflicts_invalidate_cache(bank, harness):
    h = harness
    a, b, c = bank["questions"][:3]
    a["prerequisites"] = [b["question_id"]]
    b["conflict_id"] = c["conflict_id"] = "REFERENCE_CONFLICT"
    context = h.cache.related(bank, {a["question_id"]})
    assert {b["question_id"], c["question_id"]}.issubset({q["question_id"] for q in context})
    context[0]["question"] = "Do not mutate bank"
    assert bank["questions"][1]["question"] != "Do not mutate bank"
    h.cache.answers(bank, h.points, RAW)
    c["answer"] += " Changed conflict condition"
    h.cache.answers(bank, h.points, RAW)
    assert a["question_id"] in h.calls["answer"][-1]


def test_independent_review_prompt_separates_context_from_targets(bank, harness, monkeypatch):
    h = harness
    target, context = bank["questions"][:2]
    subset = {**bank, "questions": [target]}
    def call(prompt, schema, **kwargs):
        assert "RELATED_QUESTIONS" in prompt and context["question_id"] in prompt
        assert "읽기 전용" in prompt
        result = good_review(subset)[0]
        result["pool_checks"] = []
        return result, {}
    monkeypatch.setattr(review.session, "run_structured", call)
    # The harness wraps review.review; exercise the actual implementation here.
    import importlib.util
    spec = importlib.util.spec_from_file_location("quizbank._review_contract_probe", review.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checked, _ = module.review(subset, "lecture", related_questions=[context])
    assert [r["question_id"] for r in checked["reviews"]] == [target["question_id"]]
