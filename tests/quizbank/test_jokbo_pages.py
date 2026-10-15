import json

import fitz

from quizbank.jokbo_pages import references, connect


def test_reference_identifiers_preserve_sitting_r_numbers_and_ranges():
    assert references("참고 2016-2 R3, R5; 2023 Q52–53") == [
        ("2016-2", "R3"), ("2016-2", "R5"), ("2023", "52"), ("2023", "53")]
    assert references("연도 미상") == []


def test_pdf_page_uses_the_cut_index_and_correct_older_source(tmp_path):
    for name, count in (("main.pdf", 1), ("older.pdf", 2)):
        with fitz.open() as doc:
            for number in range(count):
                doc.new_page().insert_text((20, 20), f"Exam question page {number + 1}")
            doc.save(tmp_path / name)
    (tmp_path / "index.json").write_text(json.dumps({"source_path": str(tmp_path / "main.pdf")}), encoding="utf-8")
    md = tmp_path / "slice.md"
    md.write_text("Past questions", encoding="utf-8")
    md.with_suffix(".json").write_text(json.dumps({"sources": [{"path": str(tmp_path / "older.pdf")}],
        "questions": [{"year": "2023", "no": "52", "pages": [1]},
                      {"year": "2016-2", "no": "R3", "pages": [2], "src": 0}]}), encoding="utf-8")
    q = {"question_id": "Q1", "source_refs": [{"source_id": "S2", "locator": "2023 52; 2016-2 R3"}]}
    report, images = connect({"questions": [q]}, md, tmp_path / "images", "demo")
    refs = report["questions"]["Q1"]["locators"]["2023 52; 2016-2 R3"]
    assert {(r["pdfFilename"], r["page"]) for r in refs} == {("main.pdf", 1), ("older.pdf", 2)}
    assert len(images) == 2 and all(p.is_file() for p in images)
    assert not report["questions"]["Q1"]["unresolved"]


def test_ambiguous_sitting_does_not_guess_a_pdf_page(tmp_path):
    md = tmp_path / "slice.md"
    md.write_text("Past questions", encoding="utf-8")
    md.with_suffix(".json").write_text(json.dumps({"questions": [
        {"year": "2016-1", "no": "1", "pages": [2]}, {"year": "2016-2", "no": "1", "pages": [3]}]}), encoding="utf-8")
    q = {"question_id": "Q1", "source_refs": [{"source_id": "S2", "locator": "2016 1"}]}
    report, images = connect({"questions": [q]}, md, tmp_path / "images", "demo")
    assert images == []
    assert report["questions"]["Q1"]["unresolved"] == ["2016 1"]
