"""사진 중심 전략의 기계 검증."""

from pdf2anki.validate import validate


def _prep():
    return {
        "slides": 1,
        "pages": [{
            "slide": 1,
            "lecture_figures": [
                {"id": "fig_p01_01", "bbox": [0, 0, 300, 240]},
                {"id": "fig_p01_02", "bbox": [310, 0, 610, 240]},
            ],
            "occlusion_candidates": [],
        }],
    }


def _card(n: int, image: bool):
    card = {
        "q": f"표본 {n}에서 판별해야 할 대상은?",
        "a": f"진단 {n}",
        "explanation": f"시각 단서 {n}으로 구분한다.",
        "slide_no": 1,
        "card_format": "image_basic" if image else "basic",
        "card_type": "fact",
        "importance": "core",
        "source_type": "lecture",
        "evidence_type": "lecture_figure" if image else "lecture_text",
        "exam_hit": False,
        "media": {"figure_id": f"fig_p01_0{n}"} if image else None,
    }
    return card


def test_사진_중심인데_이미지_카드가_절반_미만이면_경고한다():
    raw = {"cards": [_card(1, True), _card(2, False), _card(3, False)]}
    _, suspects = validate(raw, _prep(), None, strategy="image")
    assert suspects["photo_focus"]["image_share"] == 0.333
    assert suspects["strategy_warnings"] == ["photo_focus_below_half"]


def test_사진_중심에서_이미지_카드가_절반_이상이면_통과한다():
    raw = {"cards": [_card(1, True), _card(2, True), _card(3, False)]}
    _, suspects = validate(raw, _prep(), None, strategy="image")
    assert suspects["photo_focus"]["image_share"] == 0.667
    assert suspects["strategy_warnings"] == []
