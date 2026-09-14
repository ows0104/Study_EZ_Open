"""검수 PDF 는 파일 이름을 다시 유추하지 않는다.

`contact_sheet` 가 `figure_id` + crop 으로 파일명을 스스로 만들고 있었다. 그런데
정답이 그림 안에 인쇄돼 가림이 붙으면 `Media.figure` 가 실제로 쓰는 이름은
`..._m1.png` 가 된다. 두 이름이 어긋나면 **빌드가 통째로 죽는다** —
`260818_01` 재저작(2026-08-26)이 `No such file: ..._fig_p11_01.png` 로 멈췄다.

그때까지 안 터진 이유는 운이었다. 같은 그림을 가리지 않고 쓰는 카드가 하나라도
있으면 안 가린 판이 함께 남아 있어 열렸다.
"""

import fitz

from quizgen.build import contact_sheet


class FakeMedia:
    def __init__(self, d):
        self.dir = d


def _png(path, w=40, h=30):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), False)
    pix.clear_with(255)
    pix.save(path)


def _card(fid, fmt="image_basic", crop=None, occ=None):
    return {"q": "질문", "a": "답", "slide_no": 3, "card_format": fmt,
            "media": {"figure_id": fid, "crop": crop, "occlusion_ids": occ or []}}


def test_가린_판만_있어도_검수_PDF_가_나온다(tmp_path):
    """예전 코드가 죽던 자리. 안 가린 이름은 존재하지 않는다."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    _png(media_dir / "ptest_fig_p11_01_m1.png")

    card = _card("fig_p11_01")
    out = contact_sheet(tmp_path, [card], FakeMedia(media_dir), "ptest",
                        {id(card): ("ptest_fig_p11_01_m1.png",)})

    assert out is not None and out.exists()
    with fitz.open(out) as doc:
        assert doc.page_count == 1
        assert doc[0].get_images()


def test_crop_이_붙은_이름도_받아_쓴다(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    name = "ptest_fig_p07_02_c0.0-0.0-1.0-0.75_m2.png"
    _png(media_dir / name)

    card = _card("fig_p07_02", crop=[0, 0, 1, 0.75])
    out = contact_sheet(tmp_path, [card], FakeMedia(media_dir), "ptest", {id(card): (name,)})
    assert out is not None and out.exists()


def test_오클루전은_앞뒤_두_장을_받는다(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    for n in ("ptest_fig_p02_01_a_front.png", "ptest_fig_p02_01_a_back.png"):
        _png(media_dir / n)

    card = _card("fig_p02_01", fmt="image_occlusion", occ=["occ_a"])
    out = contact_sheet(tmp_path, [card], FakeMedia(media_dir), "ptest",
                        {id(card): ("ptest_fig_p02_01_a_front.png",
                                    "ptest_fig_p02_01_a_back.png")})
    with fitz.open(out) as doc:
        assert len(doc[0].get_images()) == 2


def test_만들어진_이름이_없으면_그_카드는_건너뛴다(tmp_path):
    """이름을 못 받은 카드 하나 때문에 편 전체가 서지 않게 한다."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    _png(media_dir / "ptest_fig_p01_01.png")

    ok, missing = _card("fig_p01_01"), _card("fig_p99_01")
    out = contact_sheet(tmp_path, [ok, missing], FakeMedia(media_dir), "ptest",
                        {id(ok): ("ptest_fig_p01_01.png",)})
    with fitz.open(out) as doc:
        assert doc.page_count == 1


def test_이미지_카드가_없으면_만들지_않는다(tmp_path):
    card = {"q": "q", "a": "a", "slide_no": 1, "card_format": "basic", "media": None}
    assert contact_sheet(tmp_path, [card], FakeMedia(tmp_path), "ptest", {}) is None
