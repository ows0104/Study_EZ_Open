"""문항 직접 근거 두 장을 우선하고 나머지 이미지는 보존한다."""
from unittest.mock import patch

from tests.test_bank import example_bank  # Sets an isolated local SQLite DB before app imports.
from app.bank_validation.pages import primary_pages
from app.database import Base, SessionLocal, engine
from app.models import Asset, QuizBank, SLIDE_KINDS
from app.routes.bank import _slides


def main():
    question = {"source_refs": [{"source_id": "S2", "locator": "p1"},
                                {"source_id": "S1", "locator": "p8"},
                                {"source_id": "S1", "locator": "p3–4"}],
                "option_pools": [{"candidates": [{"source_refs": [{"source_id": "S1", "locator": "p1"}]}]}]}
    assert primary_pages(question, [1, 3, 4, 8]) == {8, 3}
    assert primary_pages(question, [1, 3, 4]) == {3, 4}
    assert primary_pages(question, [1]) == {1}
    assert primary_pages(question, []) == set()
    assert primary_pages({}, [9, 10]) == {9}
    assert primary_pages({"source_refs": [{"source_id": "S1", "locator": "p8"}] * 2}, [8, 9]) == {8}
    bank = example_bank()
    bank["questions"][0].update(question)
    row = QuizBank(subject="slides", run_id="demo", build_id="slides-test", bank=bank,
                   pages={"Q1": [1, 3, 4, 8]}, validation={"pass": True})
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for page in [1, 3, 4, 8]:
            db.add(Asset(id=f"slide-{page}", subject="slides", run_id="demo", kind=SLIDE_KINDS["bank"],
                         slide_no=page, filename=f"{page}.png", object_key=f"slides/{page}.png"))
        db.commit()
        with patch("app.routes.bank.ObjectStorage") as storage:
            storage.return_value.presign_download.side_effect = lambda key: f"https://example.test/{key}"
            slides = _slides(db, row, "Q1")
        assert [slide["page"] for slide in slides] == [1, 3, 4, 8]
        assert [slide["page"] for slide in slides if slide["primary"]] == [3, 8]
        assert all(slide["url"].endswith(f"/{slide['page']}.png") for slide in slides)
    print("PASS: direct reference priority, two-slide limit, pools excluded, missing images, legacy fallback, full slide preservation")


if __name__ == "__main__":
    main()
