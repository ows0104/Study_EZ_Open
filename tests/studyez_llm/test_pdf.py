import fitz
import pytest

from studyez_llm.pdf import page_numbers, render


def test_selected_pages_keep_one_based_numbering(tmp_path):
    source = tmp_path / "sample.pdf"
    with fitz.open() as doc:
        for _ in range(3):
            doc.new_page()
        doc.save(source)
    result = render(source, "1,3", tmp_path / "images")
    assert [p.name for p in result] == ["page-0001.png", "page-0003.png"]
    assert all(p.read_bytes().startswith(b"\x89PNG") for p in result)
    assert page_numbers("1-2,2,3", 3) == [1, 2, 3]


@pytest.mark.parametrize("pages", ["0", "2-1", "1-4", "1-2-3"])
def test_invalid_page_ranges_fail(pages):
    with pytest.raises(ValueError):
        page_numbers(pages, 3)
