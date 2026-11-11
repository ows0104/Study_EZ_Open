"""Main-Quiz 근거 보강: 정리본 족보 쪽 머리 색인과 Quiz Bank 함수 재사용(모델은 가짜)."""
import hashlib
import json

import fitz
import pytest

from quizbank import exam_focus, root_evidence, slide_focus
from studyez_contracts.bank.slide_focus import question_hash


def _pdf(path, pages):
    doc = fitz.open()
    for text in pages:
        doc.new_page().insert_text((40, 60), text, fontname="korea")  # 실제 정리본처럼 한글 머리
    doc.save(path)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _question(qid, refs):
    return {"question_id": qid, "question": f"{qid}?", "answer": "A", "answer_units": ["A"], "format": "basic",
            "source_refs": refs, "options": [], "correct_option_ids": [], "conflict_id": ""}


@pytest.fixture
def lecture(tmp_path):
    notes = _pdf(tmp_path / "notes.pdf", ["slide 1", "slide 2", "slide 3"])
    exam = _pdf(tmp_path / "exam.pdf", [
        "Infection | Pathology\n2023 | Kim | 79　\n",  # 머리 모양이 아닌 쪽(번호 뒤 '번' 없음)
        "Infection | Pathology\n2023 | Kim | 79번\nquestion",
        "Infection | Pathology\n2021 | Kim | 16번\nquestion",
        "Infection | Pathology\n2021 | Kim | 16번\ncontinued",
        "answer table",
    ])
    bank = {"questions": [
        _question("Q1", [{"source_id": "S1", "locator": "physical PDF page 2"},
                         {"source_id": "S2", "locator": "2023 김지은 79번 ④"}]),
        _question("Q2", [{"source_id": "S1", "locator": "physical PDF page 3"},
                         {"source_id": "S2", "locator": "physical PDF page 4; selected original image crop"}]),
        _question("Q3", [{"source_id": "S1", "locator": "physical PDF page 1"}]),
    ], "source_conflicts": []}
    document = {"revision": "rev-1", "bank_snapshot": bank, "review": {"sources": [
        {"source_id": "S1", "sha256": _sha(notes), "kind": "notes", "label": "notes.pdf", "page_count": 3},
        {"source_id": "S2", "sha256": _sha(exam), "kind": "exam", "label": "exam.pdf", "page_count": 5}]}}
    return document, {"S1": notes, "S2": exam}


def test_정리본_족보는_쪽_머리로_번호를_찾는다(lecture):
    _, sources = lecture
    assert root_evidence.exam_index(sources["S2"]) == {("2023", "79"): [2], ("2021", "16"): [3, 4]}


def test_보강은_quiz_bank_함수로_족보와_핵심을_묶는다(lecture, tmp_path, monkeypatch):
    document, sources = lecture
    calls = []

    def focus(bank, pdf, out, *, model=None, **_):
        calls.append(("focus", pdf.name))
        q = {q["question_id"]: q for q in bank["questions"]}
        return {"version": 2, "sourceSha256": _sha(pdf), "questions": {
            "Q1": {"questionHash": question_hash(q["Q1"]), "base": {"mode": "single", "reason": "r",
                   "slides": [{"page": 2, "evidence": "e"}]}},
            "Q2": {"questionHash": question_hash(q["Q2"]), "base": {"mode": "unresolved", "reason": "족보에만",
                   "unresolved_cause": "exam_only", "slides": []}},
        }}, [{"step": "focus"}]

    def exam(targets, out, model=None):
        calls.append(("exam", [t["question_id"] for t in targets]))
        return {t["question_id"]: {"mode": "single", "reason": "r", "pages": [
            {**{k: v for k, v in t["candidates"][0].items() if k not in ("id", "image")}, "evidence": "e"}]}
            for t in targets}, [{"step": "exam"}]

    monkeypatch.setattr(slide_focus, "select", focus)
    monkeypatch.setattr(exam_focus, "select", exam)
    evidence = root_evidence.enrich(document, sources, tmp_path / "out", "261104_02")

    assert calls == [("focus", "notes.pdf"), ("exam", ["Q2"])]
    assert evidence["schema"] == "root-evidence/1" and evidence["revision"] == "rev-1"
    assert evidence["sources"] == {"S1": _sha(sources["S1"]), "S2": _sha(sources["S2"])}
    q1 = evidence["jokboPages"]["questions"]["Q1"]["locators"]["2023 김지은 79번 ④"]
    assert [(r["year"], r["number"], r["page"]) for r in q1] == [("2023", "79", 2)]
    q2 = evidence["jokboPages"]["questions"]["Q2"]
    assert [(r["page"], r["references"]) for r in q2["locators"]["physical PDF page 4; selected original image crop"]] \
        == [(4, ["2021 16번"])]
    assert q2["unresolved"] == []
    core = evidence["evidenceResolution"]["questions"]["Q2"]["base"]["examCore"]
    assert core["mode"] == "single" and core["pages"][0]["page"] == 4
    # 로컬 경로가 결과에 남지 않는다(서버·학생 응답으로 나간다).
    assert str(tmp_path) not in json.dumps(evidence, ensure_ascii=False)


def test_고정_지문이_다르면_멈춘다(lecture, tmp_path):
    document, sources = lecture
    document["review"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="지문"):
        root_evidence.enrich(document, sources, tmp_path / "out", "261104_02")


def _reviews():
    """review-evidence/1 판의 문항 검토: Q1·Q3는 쪽을 증명했고 Q2는 필기에서 못 찾았다."""
    proof = lambda *pages: {"mode": "single" if len(pages) == 1 else "linked", "reason": "r",
                            "slides": [{"page": p, "evidence": f"e{p}"} for p in pages]}
    return [{"question_id": "Q1", "evidence": proof(2)}, {"question_id": "Q2", "evidence": {"mode": "unresolved", "reason": "r", "slides": []}},
            {"question_id": "Q3", "evidence": proof(1, 3)}]


def test_검토_근거_쪽은_다시_고르지_않는다(lecture, tmp_path, monkeypatch):
    """docs/changes/2026-11-11-evidence-from-citations R3: 검토가 증명한 문항은 모델 재선택 대상이 아니다."""
    from studyez_contracts.bank.slide_focus import authored_hash
    document, sources = lecture
    sent = {}

    def call(prompt, schema, out, model, label):
        sent["targets"] = [t["question_id"] for t in json.loads((out / "targets.json").read_text(encoding="utf-8"))]
        return {"selections": [{"question_id": "Q2", "pool_id": "", "candidate_id": "", "mode": "unresolved", "reason": "족보에만",
                                "slides": [], "unresolved_cause": "exam_only", "searched_sources": ["self"], "exam_pages": []}]}, {"seconds": 1}

    monkeypatch.setattr(slide_focus, "_call", call)
    monkeypatch.setattr(exam_focus, "select", lambda targets, out, model=None: ({}, []))
    evidence = root_evidence.enrich(document, sources, tmp_path / "out", "261110_03", reviews=_reviews(), review_source="S1")

    focus = evidence["slideFocus"]
    assert sent["targets"] == ["Q2"]  # 증명 못 한 문항만
    assert focus["selectionOrigin"] == "mixed" and focus["authoredCount"] == 2 and focus["reselectedCount"] == 1
    assert focus["questions"]["Q1"]["base"]["slides"] == [{"source_id": "self", "page": 2, "evidence": "e2"}]
    assert focus["questions"]["Q3"]["base"]["mode"] == "linked"
    q1 = document["bank_snapshot"]["questions"][0]
    assert root_evidence.authored_from_reviews(document["bank_snapshot"], _reviews(), "S1", "S1")["Q1"]["authoredHash"] == authored_hash(q1)


def test_모든_문항을_검토가_증명하면_모델을_부르지_않는다(lecture, tmp_path, monkeypatch):
    document, sources = lecture
    reviews = [r for r in _reviews() if r["question_id"] != "Q2"]
    reviews.append({"question_id": "Q2", "evidence": {"mode": "single", "reason": "r", "slides": [{"page": 3, "evidence": "e3"}]}})
    monkeypatch.setattr(slide_focus, "_call", lambda *a, **k: pytest.fail("모델을 불렀다"))
    monkeypatch.setattr(exam_focus, "select", lambda targets, out, model=None: ({}, []))
    evidence = root_evidence.enrich(document, sources, tmp_path / "out", "261110_03", reviews=reviews, review_source="S1")
    assert evidence["slideFocus"]["selectionOrigin"] == "authored" and evidence["slideFocus"]["reselectedCount"] == 0


def test_다른_원본의_검토_근거는_쓰지_않는다(lecture):
    document, _ = lecture
    assert root_evidence.authored_from_reviews(document["bank_snapshot"], _reviews(), "S2", "S1") is None
    assert root_evidence.authored_from_reviews(document["bank_snapshot"], [], "S1", "S1") is None
