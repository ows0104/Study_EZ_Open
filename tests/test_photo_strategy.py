"""사진 중심 전략의 기계 검증."""

from pdf2anki.assemble import guidance_without_jokbo, image_strategy_body
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


# ── 누출 금지가 프롬프트 맨 앞에 서 있는가 ────────────────────────────────
#
# 같은 규칙이 `prompts/core/media.md` 에도 있는데 260818_01 의 이미지 카드 37장 중
# 31장이 사진을 가려도 풀렸다. 규칙이 없어서가 아니라 밀린 것이었다. 기준선에서
# 한 문단만 앞에 세웠더니 17% → 55% 로 올랐다(`docs/doby-is-free.md`). 그 자리를 지킨다.

def test_사진_전략은_판독_소견을_질문에_쓰지_말라고_먼저_말한다():
    for has_jokbo in (True, False):
        body = image_strategy_body(has_jokbo)
        assert "질문이 사진을 대신 읽어 주지 마라" in body
        # 맨 앞 문단 다음에 와야 한다. 뒤로 밀리면 이 시험이 막는다.
        assert body.index("질문이 사진을 대신 읽어 주지 마라") < 200


def test_반대쪽도_같이_말한다():
    """앞 문단만 넣었을 때 「사진을 줘도 못 푸는」 카드가 5장 → 18장이 됐다."""
    body = image_strategy_body(True)
    assert "그림이 줄 수 없는 것은 질문에 준다" in body
    assert body.index("질문이 사진을 대신") < body.index("그림이 줄 수 없는 것은")


def test_사람이_고른_사진_전략은_족보가_없어도_그_규칙을_들고_간다():
    assert "질문이 사진을 대신 읽어 주지 마라" in guidance_without_jokbo("image")
