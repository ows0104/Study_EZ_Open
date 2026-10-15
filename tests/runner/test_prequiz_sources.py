import json

import fitz
import pytest

from runner import prequiz_sources as sources, runlayout


def fixture(tmp_path):
    pdf = tmp_path / "lecture.pdf"
    with fitz.open() as doc:
        for text in ("first source", "second source"):
            doc.new_page().insert_text((40, 40), text)
        doc.save(pdf)
    item = {"id": "c001", "stem": "question", "answer": "answer", "slide_no": None}
    manifest = {"version": 1, "pdf_sha256": sources.pdf_hash(pdf), "items": {
        "c001": {"content_sha256": sources.item_hash(item), "slide_no": 2}}}
    (tmp_path / sources.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return pdf, item


def test_reviewed_reference_survives_export_and_renders_original_page(tmp_path):
    pdf, item = fixture(tmp_path)
    linked = sources.attach(tmp_path, [item], pdf)
    assert item["slide_no"] is None  # original generation is unchanged
    assert linked[0]["slide_no"] == 2
    assert sources.render(tmp_path, "lecture", linked, pdf) == 1
    image = fitz.Pixmap(tmp_path / "slides" / "lecture_s002.png")
    with fitz.open(pdf) as doc:
        expected = doc[1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        assert image.samples == expected.samples


def test_changed_question_cannot_reuse_old_source(tmp_path):
    pdf, item = fixture(tmp_path)
    with pytest.raises(ValueError, match="c001 changed"):
        sources.attach(tmp_path, [{**item, "answer": "different"}], pdf)


def test_changed_pdf_cannot_reuse_old_source(tmp_path):
    pdf, item = fixture(tmp_path)
    pdf.write_bytes(b"new edition")
    with pytest.raises(ValueError, match="source PDF changed"):
        sources.attach(tmp_path, [item], pdf)


def test_existing_reference_is_preserved(tmp_path):
    pdf, item = fixture(tmp_path)
    assert sources.attach(tmp_path, [{**item, "slide_no": 1}], pdf)[0]["slide_no"] == 1


def test_unreviewed_lecture_and_owned_manifest(tmp_path):
    assert sources.attach(tmp_path, [], None) == []
    assert runlayout.is_lecture_own(sources.MANIFEST)


def test_invalid_page_fails_before_any_image_is_written(tmp_path):
    pdf, item = fixture(tmp_path)
    with pytest.raises(ValueError, match="outside PDF"):
        sources.render(tmp_path, "lecture", [{**item, "slide_no": 3}], pdf)
    assert not (tmp_path / "slides").exists()


def test_contract_keeps_reviewed_sources_without_deleting_live_images(tmp_path, monkeypatch):
    from runner import deck

    pdf, _ = fixture(tmp_path)
    card = {"id": "c001", "q": "question", "a": "answer", "card_format": "basic"}
    package = tmp_path / "pre.apkg"
    package.write_bytes(b"unchanged package")
    monkeypatch.setattr(deck, "promote", lambda *args: package)
    monkeypatch.setattr(deck, "config_of", lambda *args: {"pdf": str(pdf)})
    monkeypatch.setattr(deck, "cards_of", lambda *args: [card])
    monkeypatch.setattr(deck, "_attempt_mark", lambda *args: {})
    monkeypatch.setattr(deck.quizgen_build, "counts", lambda *args: {"n_notes": 1, "n_cards": 1})
    def must_not_clear(*args):
        pytest.fail("reviewed source exports must not clear their live slides directory")
    monkeypatch.setattr(deck, "_slides", must_not_clear)
    for _ in range(2):
        meta = deck.contract(tmp_path, "lecture", "title", deck.PRE)
        assert meta["web_source_slides"] == [2]
        assert meta["slides_exported"] == 1
        exported = json.loads((tmp_path / "pre_items.final.json").read_text(encoding="utf-8"))
        assert exported["items"][0]["slide_no"] == 2
    assert card.get("slide_no") is None
    assert package.read_bytes() == b"unchanged package"
