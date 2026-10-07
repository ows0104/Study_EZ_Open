"""추가는 필수 예산을 늘리지 않고 Anki에서도 별도로 선택한다."""
import json
import sqlite3
import zipfile
import fitz
from copy import deepcopy
from types import SimpleNamespace

from jsonschema import Draft202012Validator

from quizgen.prequiz.build import build
from quizgen.prequiz.schema import GENERATE_SCHEMA, is_extra
from quizgen.prequiz.simple import extra_exam_context
from quizgen.prequiz.validate import validate
from tests.quizgen.test_prequiz_difficulty import cards


def extras(n=5):
    rows = deepcopy(cards()[:n])
    for i, row in enumerate(rows):
        row.update(q=f"구분 항목 {i}의 대표값은?", a=f"대표값{i}", must_id=None)
    return rows


def test_extra_is_separate_from_required_budget_and_difficulty():
    core = cards()
    for i, row in enumerate(core):
        row["must_id"] = f"m{i}"
    raw = {"cards": core, "extra_cards": extras(), "must_know": {"items": [
        {"id": f"m{i}", "item": f"개념{i}", "reason": "vocabulary", "cards": 1} for i in range(10)]}}
    assert not list(Draft202012Validator(GENERATE_SCHEMA).iter_errors({"cards": cards(), "extra_cards": extras()}))
    kept, report = validate(raw, {"slides": 1, "pages": []}, None)
    assert len(kept) == 15 and sum(map(is_extra, kept)) == 5
    assert not report["contract_violations"]
    assert not report["coverage"]["cards_per_item_mismatch"]
    assert not any("off_must" in row["review_flags"] for row in kept)
    assert report["difficulty_mix"] == {"basic": 5, "advanced": 3, "challenge": 2}
    # Checked flat output remains stable when validated again.
    flat = [{key: value for key, value in row.items() if key != "review_flags"} for row in kept]
    again, report = validate({"cards": flat}, {"slides": 1, "pages": []}, None)
    assert sum(map(is_extra, again)) == 5 and not report["contract_violations"]


def test_extra_cannot_fill_missing_required_cards_or_hide_ox_ratio():
    _, report = validate({"cards": cards()[:7], "extra_cards": extras()}, {"slides": 1, "pages": []}, None)
    assert any("최소 8" in issue for issue in report["contract_violations"])
    more = extras() + [dict(extras()[0], q="다른 대응의 기준값은?", a="다른값")]
    _, report = validate({"cards": cards(), "extra_cards": more}, {"slides": 1, "pages": []}, None)
    assert any("최대 5" in issue for issue in report["contract_violations"])
    core = cards()
    for i in range(3):
        core[i].update(card_format="ox", q=f"서로 다른 진술 {i}이다", a="O")
    _, report = validate({"cards": core, "extra_cards": extras()}, {"slides": 1, "pages": []}, None)
    assert any("3/10" in issue for issue in report["contract_violations"])


def test_extra_does_not_duplicate_required_or_invent_exam_reference(tmp_path):
    kept, report = validate({"cards": cards(), "extra_cards": [cards()[0]]}, {"slides": 1, "pages": []}, None)
    assert len(kept) == 10 and report["dropped"][0]["code"] == "exact_duplicate"
    assert extra_exam_context(SimpleNamespace(slice_path=None)) == ""
    source = tmp_path / "slice.json"
    source.write_text(json.dumps({"questions": [{"year": "2025", "no": "19", "q": "Verified question"}]}), encoding="utf-8")
    context = extra_exam_context(SimpleNamespace(slice_path=source))
    assert "Verified question" in context and "추가 학습에만" in context
    extra = extras()[0]
    extra.update(source_type="jokbo", evidence_type="jokbo_question", jokbo_ref={"year": "2025", "no": "19"})
    _, report = validate({"cards": cards(), "extra_cards": [extra]}, {"slides": 1, "pages": []}, {"questions": []})
    assert report["dropped"] or report["flag_counts"].get("extra_exam_unverified")


def test_anki_package_keeps_optional_deck_separate(tmp_path):
    pdf = fitz.open()
    pdf.new_page()
    pdf.save(tmp_path / "source.pdf")
    pdf.close()
    (tmp_path / "prep.json").write_text(json.dumps({"slides": 1, "pages": [], "annotated_pdf": "source.pdf", "clean_pdf": "source.pdf"}), encoding="utf-8")
    kept, _ = validate({"cards": cards(), "extra_cards": extras()}, {"slides": 1, "pages": []}, None)
    (tmp_path / "items.checked.json").write_text(json.dumps({"cards": kept}), encoding="utf-8")
    result = build(tmp_path, "과목::강의::예습", "test-extra")
    with zipfile.ZipFile(result["apkg"]) as package:
        package.extract("collection.anki2", tmp_path)
    with sqlite3.connect(tmp_path / "collection.anki2") as db:
        decks = json.loads(db.execute("select decks from col").fetchone()[0])
        counts = {decks[str(did)]["name"]: n for did, n in db.execute("select did,count(*) from cards group by did")}
        assert counts == {"과목::강의::예습": 10, "과목::강의::추가 학습": 5}
        assert db.execute("select count(*) from notes where tags like '%추가학습%'").fetchone()[0] == 5
