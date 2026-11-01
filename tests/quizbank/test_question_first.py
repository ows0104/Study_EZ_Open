import copy
import json
from pathlib import Path

import fitz
import pytest

from quizbank import coverage, file_organize, generate, option_pools, organize, question_first, run, web_audit
from quizbank.schema import without_retired
from quizbank.session import SessionError
from quizbank.validate import validate_bank, validate_dropping
from tests.quizbank.test_repair import good_review
from tests.quizbank.test_web_audit import report


@pytest.fixture
def bank():
    raw = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    result = without_retired(validate_dropping(raw, ["S1", "S2"])[0])
    for q in result["questions"]:
        q["importance"] = {"Core": 5, "Important": 4, "Optional": 2}[q["tier"]]
    return result


def structure_for(bank):
    plans = copy.deepcopy(bank["retrieval_plan"])
    for p in plans:
        p["directions"] = sorted({q["retrieval_direction"] for q in bank["questions"] if q["concept_id"] == p["concept_id"]})
    return {"concepts": copy.deepcopy(bank["concepts"]), "retrieval_plan": plans,
            "assignments": [{k: q[k] for k in ("question_id", "concept_id", "prerequisites")} for q in bank["questions"]],
            "summary": "Final question metadata"}


def make_pdf(path):
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), "Original source")
        doc.save(path)


def plan():
    return {"summary": "Source-only target", "objectives": [{"objective_id": "O1", "objective": "Identify", "slides": [1],
        "retrieval_targets": [{"point_id": "P001", "target": "Independent fact", "slides": [1]}]}],
        "rejected_candidates": [], "unreadable_pages": []}


@pytest.mark.parametrize('version', ['1.67', ''])
@pytest.mark.parametrize('legacy_resume', [False, True])
def test_web_postprocess_preserves_web_content_and_skips_authorship(bank, tmp_path, monkeypatch, version, legacy_resume):
    pdf, raw, out = tmp_path / 'source.pdf', tmp_path / 'raw.md', tmp_path / 'out'
    make_pdf(pdf)
    raw.write_text('Saved web response', encoding='utf-8')
    draft = question_first.as_draft(bank)
    monkeypatch.setattr(run.organize, 'organize', lambda *a, **k: (copy.deepcopy(draft), {}))
    def forbidden(*a, **k):
        raise AssertionError('duplicate authorship')
    monkeypatch.setattr(question_first, 'extract_points', forbidden)
    monkeypatch.setattr(option_pools, 'write', forbidden)
    old_plan = None
    if legacy_resume:
        old_plan = tmp_path / 'old-audit-points.json'
        old_plan.write_text(json.dumps([{'point_id':'old', 'point':'Old audit index', 'source_refs':'S1 p.1'}]), encoding='utf-8')
    def inspect(candidate, *a, **kw):
        assert candidate == draft
        assert kw['web_postprocess'] and kw['max_repair_rounds'] == 0
        assert kw['question_first_mode']
        points = json.loads(kw['point_plan'].read_text(encoding='utf-8'))
        assert len(points) == len(bank['questions'])
        assert not (out / 'independent-origin.json').exists()
        return {'verified': True}
    monkeypatch.setattr(run, '_run_authored', inspect)
    assert run.run(raw, pdf, '강의', 'lecture', [{'id':'S1'},{'id':'S2'}], out,
                   prompt_version=version, web_postprocess=True, point_plan=old_plan) == {'verified': True}


@pytest.mark.parametrize('version', ['1.12', '1.67', ''])
def test_web_postprocess_keeps_findings_and_runs_each_review_once(bank, tmp_path, monkeypatch, version):
    pdf, raw, out = tmp_path / 'source.pdf', tmp_path / 'raw.md', tmp_path / 'out'
    make_pdf(pdf)
    raw.write_text('Saved response', encoding='utf-8')
    candidate = question_first.as_draft(bank) if question_first.enabled(version) or not version else copy.deepcopy(bank)
    monkeypatch.setattr(run.organize, 'organize', lambda *a, **k: (copy.deepcopy(candidate), {}))
    def forbidden(*a, **k):
        raise AssertionError('web content must not be rewritten')
    for module, name in ((question_first,'extract_points'), (option_pools,'write'), (run.explain,'write'), (run.repair,'repair')):
        monkeypatch.setattr(module, name, forbidden)
    calls = []
    def inspect(current, *a, **kw):
        calls.append('source')
        data = report(current)
        data['checks'] = [{'point_id':p['point_id'], 'status':'covered',
                           'question_ids':[q['question_id']], 'note':'test'}
                          for p,q in zip(kw['points'], current['questions'])]
        data['checks'][0]['status'] = 'gap'
        data['checks'][0]['question_ids'] = []
        return web_audit.shape_report(data, current, kw['points'], 1), []
    monkeypatch.setattr(web_audit, 'inspect', inspect)
    def review(current, *a, **k):
        calls.append('answer')
        return good_review(current)
    monkeypatch.setattr(run.review, 'review', review)
    monkeypatch.setattr(question_first, 'connect', lambda current,*a,**k:
                        (question_first.apply_structure(current, structure_for(bank)), structure_for(bank), {}))
    monkeypatch.setattr(run.slides, 'render', lambda *a, **k: ([], []))
    result = run.run(raw, pdf, '강의', 'lecture', [{'id':'S1'},{'id':'S2'}], out,
                     prompt_version=version, web_postprocess=True)
    assert calls == ['source', 'answer']
    assert result['repairs']['attempts'] == 0 and result['requiresRevision']
    assert result['publication']['hasUnresolved']
    assert question_first.content_hash(json.loads((out/'bank.json').read_text(encoding='utf-8'))) == question_first.content_hash(bank)


def test_web_contract_and_organizer_defer_learning_metadata():
    body, version = generate.prompt_for("강의", "", [{"id": "S1", "kind": "notes_current", "filename": "a.pdf"}])
    assert question_first.enabled(version) and not question_first.enabled("1.41")
    assert not question_first.enabled("2.0")
    assert "### Q001 | cloze | Core | 5 | 2 | mechanism" in body
    assert "### Q002 | mcq | Core | 5 | 2 | discrimination | comparison" in body
    assert "question_id | tier" not in body and "Final Statistics" not in body
    assert "\n0. Exam Point Plan\n" not in body and "\n1. Concept Map\n" not in body
    prompt = organize.organizer_prompt("draft", {"title": "강의", "sources": [], "prompt_version": version})
    assert "문항 우선 출력 계약" in prompt
    assert "문항 우선 출력 계약" not in organize.organizer_prompt("old", {"title": "강의", "sources": [], "prompt_version": "1.41"})


def test_question_ids_without_concept_column_still_protect_all_rows():
    raw = "| question_id | question | answer |\n| --- | --- | --- |\n| Q001 | question | answer |\n" \
          "| question_id | options |\n| --- | --- |\n| Q999 | details |\n"
    assert file_organize.question_ids(raw) == {"Q001"}


def test_draft_checks_content_but_default_publish_validation_rejects_it(bank):
    draft = question_first.as_draft(bank)
    assert validate_bank(draft, ["S1", "S2"], learning_structure=False)["pass"]
    assert not validate_bank(draft, ["S1", "S2"])["pass"]
    draft["questions"][0]["answer_units"] = []
    assert not validate_bank(draft, ["S1", "S2"], learning_structure=False)["pass"]
    assert validate_bank(bank, ["S1", "S2"])["pass"]


def test_structure_links_metadata_without_mutating_reviewed_content(bank):
    draft = question_first.as_draft(bank)
    linked = question_first.apply_structure(draft, structure_for(bank))
    assert linked["questions"] == bank["questions"] and linked is not bank
    assert question_first.content_hash(linked) == question_first.content_hash(draft)
    assert not draft["concepts"] and all(not q["concept_id"] for q in draft["questions"])


def test_reviewed_learning_positions_preserve_content_and_reset_with_draft(bank):
    metadata = structure_for(bank)
    for row in metadata["assignments"]:
        row["learning_page"] = 26
    metadata["assignments"][-1]["learning_page"] = 0  # No authored S1 position.
    draft = question_first.as_draft(bank)
    linked = question_first.apply_structure(draft, metadata)
    assert linked["questions"][0]["learning_page"] == 26
    assert "learning_page" not in linked["questions"][-1]
    assert question_first.content_hash(linked) == question_first.content_hash(draft)
    assert all("learning_page" not in q for q in question_first.as_draft(linked)["questions"])
    metadata["assignments"][0]["learning_page"] = -1
    with pytest.raises(SessionError):
        question_first.apply_structure(draft, metadata)


@pytest.mark.parametrize("problem", ["missing", "duplicate", "extra", "answer_rewrite"])
def test_structure_cannot_drop_add_or_rewrite_questions(bank, problem):
    metadata = structure_for(bank)
    if problem == "missing":
        metadata["assignments"].pop()
    elif problem == "duplicate":
        metadata["assignments"][0] = copy.deepcopy(metadata["assignments"][1])
    elif problem == "extra":
        metadata["assignments"].append({"question_id": "EXTRA", "concept_id": "C", "prerequisites": []})
    else:
        metadata["assignments"][0]["answer"] = "Do not alter answers"
    with pytest.raises(SessionError):
        question_first.apply_structure(question_first.as_draft(bank), metadata)


@pytest.mark.parametrize("problem", ["missing_plan", "missing_direction", "unused_concept"])
def test_structure_cannot_claim_unlinked_concepts_or_directions(bank, problem):
    metadata = structure_for(bank)
    if problem == "missing_plan":
        metadata["retrieval_plan"].pop()
    elif problem == "missing_direction":
        metadata["retrieval_plan"][0]["directions"] = []
    else:
        concept = copy.deepcopy(metadata["concepts"][0])
        concept["concept_id"] = "UNUSED"
        metadata["concepts"].append(concept)
        metadata["retrieval_plan"].append({**copy.deepcopy(metadata["retrieval_plan"][0]), "concept_id": "UNUSED"})
    with pytest.raises(SessionError):
        question_first.apply_structure(question_first.as_draft(bank), metadata)


@pytest.mark.parametrize("reported", [[], ["direct", "reverse"], ["trap"], ["direct", "direct"]])
def test_plan_directions_are_derived_without_reclassifying_questions(bank, reported):
    draft, metadata = question_first.as_draft(bank), structure_for(bank)
    plan = metadata["retrieval_plan"][0]
    cid = plan["concept_id"]
    actual = sorted({q["retrieval_direction"] for q in bank["questions"] if q["concept_id"] == cid})
    plan["directions"] = reported
    original = copy.deepcopy(metadata)
    resolved, corrections = question_first.resolve_directions(draft, metadata)
    assert metadata == original
    assert resolved["retrieval_plan"][0]["directions"] == actual
    assert corrections == ([{"concept_id": cid, "reported": reported, "actual": actual}]
                           if set(reported) != set(actual) or len(reported) != len(actual) else [])
    assert resolved["assignments"] == metadata["assignments"]
    assert resolved["concepts"] == metadata["concepts"]
    linked = question_first.apply_structure(draft, resolved)
    assert question_first.content_hash(linked) == question_first.content_hash(draft)


@pytest.mark.parametrize("problem", ["missing", "duplicate", "unknown_concept", "missing_plan"])
def test_direction_resolution_keeps_broken_links_blocked(bank, problem):
    metadata = structure_for(bank)
    if problem == "missing":
        metadata["assignments"].pop()
    elif problem == "duplicate":
        metadata["assignments"][0] = copy.deepcopy(metadata["assignments"][1])
    elif problem == "unknown_concept":
        metadata["assignments"][0]["concept_id"] = "MISSING"
    else:
        metadata["retrieval_plan"].pop()
    with pytest.raises(SessionError):
        question_first.resolve_directions(question_first.as_draft(bank), metadata)


def test_connect_records_raw_and_resolved_directions_in_one_cli_call(bank, tmp_path, monkeypatch):
    metadata = structure_for(bank)
    metadata["retrieval_plan"][0]["directions"] = []
    calls = []
    def call(*args):
        calls.append(args)
        return metadata, {"seconds": 1}
    monkeypatch.setattr(coverage, "_call", call)
    draft = question_first.as_draft(bank)
    linked, resolved, info = question_first.connect(draft, [], "lecture", tmp_path)
    assert len(calls) == 1 and info == {"seconds": 1}
    assert json.loads((tmp_path / "learning-structure.raw.json").read_text(encoding="utf-8")) == metadata
    audit = json.loads((tmp_path / "learning-structure.resolution.json").read_text(encoding="utf-8"))
    assert audit["structure"] == resolved and len(audit["directionCorrections"]) == 1
    assert question_first.content_hash(linked) == question_first.content_hash(draft)
    assert validate_bank(linked, ["S1", "S2"])["pass"]


def test_extract_is_source_only_and_resume_requires_matching_provenance(tmp_path, monkeypatch):
    pdf, out = tmp_path / "a.pdf", tmp_path / "out"
    make_pdf(pdf)
    out.mkdir()
    (out / "bank.json").write_text("Do not read this bank", encoding="utf-8")
    def call(prompt, schema, work, model, label):
        assert schema == question_first.PLAN
        assert not (work / "bank.json").exists() and not (work / "response.md").exists()
        assert (work / "source-text.md").is_file() and (work / "source-pages.json").is_file()
        return plan(), {}
    monkeypatch.setattr(coverage, "_call", call)
    sources = [{"id": "S1", "kind": "notes_current", "filename": pdf.name}]
    points, usage = question_first.extract_points(pdf, "강의", sources, out)
    assert points[0]["point_id"] == "P001" and len(usage) == 1
    next_out = tmp_path / "next"
    next_out.mkdir()
    reused, usage = question_first.extract_points(pdf, "강의", sources, next_out, reuse=out / "authored-points.json")
    assert reused == points and not usage
    with pytest.raises(SessionError, match="달라"):
        question_first.extract_points(pdf, "다른 강의", sources, next_out, reuse=out / "authored-points.json")


@pytest.mark.parametrize("scenario", ["clean", "remaining_gap", "remaining_gap_directions", "graph_cycle", "pools", "cached_points"])
def test_pipeline_order_limits_and_publication_with_retained_findings(bank, tmp_path, monkeypatch, scenario):
    raw, pdf, out = tmp_path / "raw.md", tmp_path / "a.pdf", tmp_path / "out"
    raw.write_text("Question-first response without planning tables", encoding="utf-8")
    make_pdf(pdf)
    events = []
    sources = [{"id": "S1"}, {"id": "S2"}]
    prefix = [] if scenario == "cached_points" else ["points"]
    cache = tmp_path / "cache"
    if scenario == "cached_points":
        cache.mkdir()
        (cache / "independent-origin.json").write_text(json.dumps(question_first.point_origin(pdf, "강의", sources)), encoding="utf-8")
        (cache / "authored-points.json").write_text(json.dumps([
            {"point_id": "P001", "point": "objective", "source_refs": "S1 p.1"}]), encoding="utf-8")
    def call(prompt, schema, work, model, label):
        if schema == question_first.PLAN:
            events.append("points")
            assert not (work / "bank.json").exists()
            return plan(), {}
        if schema == option_pools.PROPOSALS:
            from tests.quizbank.test_option_pools_authoring import proposal
            assert events == ["points", "organize"]
            events.append("pools")
            return proposal(bank), {}
        assert schema == question_first.SEQUENCED_STRUCTURE and events[-1] == "review"
        events.append("graph")
        metadata = structure_for(bank)
        if scenario == "graph_cycle":
            a, b = metadata["assignments"][:2]
            a["prerequisites"], b["prerequisites"] = [b["question_id"]], [a["question_id"]]
        if scenario == "remaining_gap_directions":
            metadata["retrieval_plan"][0]["directions"] = []
        return metadata, {}
    monkeypatch.setattr(coverage, "_call", call)
    def convert(*args, **kwargs):
        assert events == prefix
        events.append("organize")
        return question_first.as_draft(bank), {}
    monkeypatch.setattr(run.organize, "organize", convert)
    monkeypatch.setattr(run.explain, "write", lambda candidate, *a, **k: (candidate, {"requiresRevision": False, "annotatedCount": 0, "annotations": []}, {}))
    def inspect(candidate, *args, **kwargs):
        assert kwargs["defer_structure"] and not candidate["concepts"]
        if scenario == "pools":
            assert any(q["option_pools"] for q in candidate["questions"])
        events.append("audit")
        data = report(candidate)
        if scenario.startswith("remaining_gap"):
            data["checks"][0]["status"] = "gap"
        return web_audit.shape_report(data, candidate, kwargs["points"], 1), []
    monkeypatch.setattr(web_audit, "inspect", inspect)
    def review(candidate, *args, **kwargs):
        if scenario == "pools":
            assert any(q["option_pools"] for q in candidate["questions"])
        events.append("review")
        return good_review(candidate)
    monkeypatch.setattr(run.review, "review", review)
    def fix(candidate, *args, **kwargs):
        assert kwargs["defer_structure"]
        events.append("repair")
        return copy.deepcopy(candidate), kwargs["points"], {"round": events.count("repair")}, {}
    monkeypatch.setattr(run.repair, "repair", fix)
    monkeypatch.setattr(run.slides, "render", lambda *a, **k: ([], []))
    result = run.run(raw, pdf, "강의", "lecture", sources, out,
                     prompt_version="1.43" if scenario == "pools" else "1.42", points_cache_root=cache)
    assert events[:len(prefix) + 1] == prefix + ["organize"]
    if scenario in ("clean", "pools", "cached_points"):
        assert result["pass"] and not result["requiresRevision"]
        assert result["learningStructure"]["status"] == "connected"
        assert events == prefix + ["organize"] + (["pools"] if scenario == "pools" else []) + ["audit", "review", "graph"]
        final = json.loads((out / "bank.json").read_text(encoding="utf-8"))
        for original, current in zip(bank["questions"], final["questions"]):
            assert {k: v for k, v in original.items() if k != "option_pools"} == {k: v for k, v in current.items() if k != "option_pools"}
    elif scenario.startswith("remaining_gap"):
        assert events.count("repair") == 3 and events.count("audit") == events.count("review") == 4
        assert events.count('graph') == 1 and result['requiresRevision'] and result['pass']
        assert result['learningStructure']['status'] == 'connected'
        assert result['publication']['allowed'] and result['publication']['hasUnresolved']
        stored = json.loads((out / 'validation.json').read_text(encoding='utf-8'))
        assert stored['revision']['audit']['checks'][0]['status'] == 'gap'
    else:
        assert events.count("audit") == 1 and events.count("graph") == 1
        assert result["requiresRevision"] and not result["pass"]
        assert result["learningStructure"]["status"] == "failed"
        assert any("순환" in e for e in result["learningStructure"]["errors"])
        assert not result['publication']['allowed']
