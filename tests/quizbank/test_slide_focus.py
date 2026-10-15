import copy
import json

import fitz
import pytest

from quizbank import slide_focus, evidence
from quizbank.session import SessionError
from server.app.bank_validation.slide_focus import question_hash, selected_pages, authored_hash
from server.app.bank_validation.slide_focus import selected_references, all_selected_pages, external_filename
from quizbank import evidence_sources


def bank():
    return {"questions": [{"question_id": "Q1", "question": "A의 관계는?", "answer": "B",
        "format": "basic", "source_refs": [{"source_id": "S1", "locator": "p1"}], "option_pools": []}]}


def output(mode="single", pages=(2,)):
    return {"selections": [{"question_id": "Q1", "pool_id": "", "candidate_id": "", "mode": mode,
        "reason": "정답의 관계를 직접 설명한다", "slides": [{"page": p, "evidence": "A is related to B"} for p in pages]}]}


def test_semantic_selection_can_use_a_later_uncited_page_and_keeps_content_immutable():
    original = bank()
    before = copy.deepcopy(original)
    report = slide_focus.shape(output(), original, 3, "source")
    assert selected_pages(report, original["questions"][0], [1, 2, 3]) == {2}
    assert original == before


@pytest.mark.parametrize("mode,pages", [("single", (1, 2)), ("single", ()), ("linked", (1,)),
                                        ("unresolved", (1,)), ("single", (99,)), ("linked", (1, 1))])
def test_missing_duplicate_out_of_range_or_nonminimal_selections_are_rejected(mode, pages):
    with pytest.raises(SessionError):
        slide_focus.shape(output(mode, pages), bank(), 3, "source")


def test_every_target_requires_a_record_and_specific_evidence():
    for raw in ({"selections": []}, {"selections": output()["selections"] * 2}, output()):
        if len(raw["selections"]) == 1:
            raw["selections"][0]["slides"][0]["evidence"] = ""
        with pytest.raises(SessionError):
            slide_focus.shape(raw, bank(), 3, "source")


def test_pool_exposure_uses_evidence_for_actual_correct_candidate():
    q = bank()["questions"][0]
    q["option_pools"] = [{"pool_id": "P", "correct_when": "false", "candidates": []}]
    selection = lambda page: {"mode": "single", "slides": [{"page": page, "evidence": "actual candidate reason"}]}
    report = {"version": 2, "questions": {"Q1": {"questionHash": question_hash(q),
        "base": selection(1), "candidates": {"P/C1": selection(2), "P/C2": selection(3)}}}}
    actual = {**q, "choice_variant": {"poolId": "P", "forms": {"C1": "true", "C2": "false"}}}
    assert selected_pages(report, q, [1, 2, 3], actual) == {3}
    assert selected_pages(report, q, [1, 2], actual) == set()


def test_selection_cache_invalidates_on_answer_or_source_change(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 30), "background")
        doc.new_page().insert_text((30, 30), "A is related to B")
        doc.save(pdf)
    calls = []
    def call(prompt, schema, work, model, label):
        calls.append(work)
        assert (work / "source-pages/page-0002.png").is_file()
        return output(), {}
    monkeypatch.setattr(slide_focus, "_call", call)
    out = tmp_path / "selection"
    original = bank()
    report, _ = slide_focus.select(original, pdf, out)
    assert report["questions"]["Q1"]["base"]["slides"][0]["page"] == 2
    slide_focus.select(original, pdf, out)
    assert len(calls) == 1
    changed = copy.deepcopy(original)
    changed["questions"][0]["answer"] = "C"
    slide_focus.select(changed, pdf, out)
    assert len(calls) == 2


def test_finalize_preserves_bank_content_and_adds_selected_uncited_page(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        doc.save(pdf)
    original = bank()
    for name, body in (("bank.json", original), ("validation.json", {"pass": True}),
                       ("result.json", {"pass": True}), ("pages.json", {"Q1": [1]})):
        (tmp_path / name).write_text(json.dumps(body), encoding="utf-8")
    before = (tmp_path / "bank.json").read_bytes()
    report = slide_focus.shape(output(), original, 2, "source")
    monkeypatch.setattr(slide_focus, "select", lambda *a, **k: (report, []))
    result = evidence.enrich(pdf, tmp_path, "demo")
    assert (tmp_path / "bank.json").read_bytes() == before
    assert json.loads((tmp_path / "pages.json").read_text())["Q1"] == [1, 2]
    assert (tmp_path / "slides/demo_s002.png").is_file()
    assert result["slideFocus"] == {"single": 1, "linked": 0, "unresolved": 0}


def test_new_authoring_metadata_survives_compact_parsing_without_entering_question_schema():
    from quizbank.compact import read_blocks, restore
    raw = ('### Q1 | basic | Core | 4 | 2 | direct\n문제: A의 관계는?\n정답: ["B"]\n'
           '출처: S1 p2\n근거: {"mode":"single","slides":[{"page":2,"evidence":"A → B"}],'
           '"reference_pages":[1],"reason":"직접 관계","jokbo":[]}\n')
    blocks = read_blocks(raw)
    assert blocks[0]["source_evidence"]["slides"][0]["page"] == 2
    original = bank()
    restore(original, blocks)
    assert "source_evidence" not in original["questions"][0]
    assert original["questions"][0]["answer"] == "B"


def test_new_unchanged_questions_use_authored_evidence_without_another_model_call(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        doc.save(pdf)
    original = bank()
    authored = {"Q1": {"authoredHash": authored_hash(original["questions"][0]), "evidence": {
        "mode": "single", "reason": "원본에 직접 작성된 관계", "slides": [{"page": 2, "evidence": "A → B"}],
        "reference_pages": [1], "jokbo": []}}}
    def forbidden(*args, **kwargs):
        raise AssertionError("An unchanged authored selection must not be regenerated")
    monkeypatch.setattr(slide_focus, "_call", forbidden)
    original["questions"][0]["explanation"] = "CLI 부연 해설"
    report, usage = slide_focus.select(original, pdf, tmp_path / "focus", authored=authored)
    assert report["selectionOrigin"] == "authored" and not usage
    assert selected_pages(report, original["questions"][0], [1, 2]) == {2}


def test_a_changed_answer_invalidates_the_authored_selection(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        doc.save(pdf)
    original = bank()
    authored = {"Q1": {"authoredHash": authored_hash(original["questions"][0]), "evidence": {
        "mode": "single", "reason": "옛 정답 근거", "slides": [{"page": 1, "evidence": "old"}]}}}
    original["questions"][0]["answer"] = "C"
    calls = []
    monkeypatch.setattr(slide_focus, "_call", lambda *a, **k: (calls.append(a) or output(), {}))
    report, _ = slide_focus.select(original, pdf, tmp_path / "focus", authored=authored)
    assert len(calls) == 1 and report["reselectedCount"] == 1
    assert selected_pages(report, original["questions"][0], [1, 2]) == {2}


def test_same_page_in_two_lectures_requires_both_images_and_does_not_pollute_own_pages():
    raw = output("linked", (2, 2))
    raw["selections"][0]["slides"][1]["source_id"] = "other"
    sources = {"other": {"runId": "other", "pageCount": 4, "sourceSha256": "a" * 64}}
    report = slide_focus.shape(raw, bank(), 3, "self-hash", sources=sources)
    q = bank()["questions"][0]
    assert report["version"] == 3
    assert all_selected_pages(report, "Q1") == {2}
    assert selected_references(report, q, {("self", 2)}) == set()
    assert selected_references(report, q, {("self", 2), ("other", 2)}) == {("self", 2), ("other", 2)}
    assert selected_references(report, {**q, "answer": "changed"}, {("self", 2), ("other", 2)}) == set()


def test_related_sources_need_real_identity_page_and_complete_absence_search():
    sources = {"other": {"pageCount": 2}}
    raw = output()
    raw["selections"][0]["slides"][0]["source_id"] = "missing"
    with pytest.raises(SessionError):
        slide_focus.shape(raw, bank(), 3, "s", sources=sources)
    raw["selections"][0]["slides"][0].update(source_id="other", page=3)
    with pytest.raises(SessionError):
        slide_focus.shape(raw, bank(), 3, "s", sources=sources)
    raw = output("unresolved", ())
    raw["selections"][0].update(unresolved_cause="uncertain", searched_sources=["self"])
    with pytest.raises(SessionError):
        slide_focus.shape(raw, bank(), 3, "s", sources=sources)
    raw["selections"][0]["searched_sources"].append("other")
    assert slide_focus.shape(raw, bank(), 3, "s", sources=sources)["questions"]["Q1"]["base"]["mode"] == "unresolved"


def make_pdf(path, text="A is B"):
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 30), text)
        doc.save(path)


def test_authored_absence_is_searched_again_and_related_source_changes_invalidate_cache(tmp_path, monkeypatch):
    pdf, other = tmp_path / "self.pdf", tmp_path / "other.pdf"
    make_pdf(pdf)
    make_pdf(other)
    original = bank()
    authored = {"Q1": {"authoredHash": authored_hash(original["questions"][0]), "evidence": {
        "mode": "unresolved", "reason": "자기 강의에서 없음", "slides": []}}}
    calls = []
    raw = output(pages=(1,))
    raw["selections"][0]["slides"][0]["source_id"] = "other"
    def call(prompt, schema, work, model, label):
        calls.append(work)
        catalog = json.loads((work / "sources.json").read_text(encoding="utf-8"))
        assert Path(catalog["other"]["images"][0]).is_file()
        return raw, {}
    from pathlib import Path
    monkeypatch.setattr(slide_focus, "_call", call)
    kwargs = dict(authored=authored, related={"other": other})
    out = tmp_path / "focus"
    slide_focus.select(original, pdf, out, **kwargs)
    slide_focus.select(original, pdf, out, **kwargs)
    assert len(calls) == 1
    other.unlink()
    make_pdf(other, "changed relationship")
    slide_focus.select(original, pdf, out, **kwargs)
    assert len(calls) == 2


def test_selected_related_pages_are_rendered_as_separate_content_addressed_assets(tmp_path):
    other = tmp_path / "other.pdf"
    make_pdf(other)
    meta = evidence_sources.describe(other, "other")
    raw = output(pages=(1,))
    raw["selections"][0]["slides"][0]["source_id"] = "other"
    report = slide_focus.shape(raw, bank(), 3, "s", sources={"other": meta})
    made = evidence_sources.render_selected(report, {"other": other}, tmp_path / "slides", "demo")
    assert len(made) == 1 and made[0].name == external_filename("demo", "other", meta["sourceSha256"], 1)
    assert all_selected_pages(report, "Q1") == set()
    assert not list((tmp_path / "slides").glob("*_s*.png"))


def test_source_discovery_stays_with_this_course_year_and_latest_lecture_version(tmp_path):
    own = tmp_path / "[261001_01] ownv1.pdf"
    for name in [own.name, "[261001_02] otherv1.pdf", "[261001_02] otherv3.pdf", "[251001_02] oldv9.pdf", "exam.pdf"]:
        (tmp_path / name).write_bytes(b"placeholder")
    found = evidence_sources.discover(own)
    assert list(found) == ["261001_02"]
    assert found["261001_02"].name.endswith("v3.pdf")
