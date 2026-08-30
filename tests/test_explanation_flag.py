"""해설이 없다는 것을 두 파이프라인이 다르게 본다.

**복습에서는 결함이 아니다**(2026-08-30 관리자 판정) — "헷갈리지 않은 이상 해설을
잘 안 보게 된다". 표시하던 동안 복습 카드 3,762장 중 1,657장(44%)에 붙어서 실제로
봐야 할 신호를 덮고 있었다. 끄고 나니 `off_plan` 109장이 맨 위로 올라왔다.

**예습에서는 목적의 절반이다.** 거기서 해설은 「이 내용이 수업에서 어디에 쓰이는지」를
잇는 다리라, `missing_bridge_to_lecture` 라는 제 이름으로 따로 본다. 실측으로 예습
카드 276장이 전부 해설을 달고 있지만(프롬프트가 지킨다) 검사는 남겨 둔다.

두 갈래가 같은 값을 다르게 본다는 것이 이 파일이 지키는 것이다.
"""

from pdf2anki.prequiz.validate import validate as pre_validate
from pdf2anki.validate import validate as main_validate


def _prep(n_slides=6):
    return {"slides": n_slides,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _main_card(**kw):
    c = {"q": "급성 염증에서 혈관 확장을 일으키는 매개체는?", "a": "histamine",
         "card_format": "basic", "card_type": "fact", "importance": "core",
         "source_type": "lecture", "evidence_type": "lecture_text",
         "exam_hit": False, "slide_no": 1}
    c.update(kw)
    return c


def _pre_card(**kw):
    c = {"q": "GVHD 는 무엇의 약어인가?", "a": "graft versus host disease",
         "card_format": "basic", "card_type": "abbrev", "reason": "vocabulary",
         "source_type": "lecture", "evidence_type": "lecture_text", "slide_no": 1}
    c.update(kw)
    return c


def _flags(kept):
    return {f for c in kept for f in c["review_flags"]}


# ------------------------------------------------- 복습은 안 본다

def test_복습은_해설이_없어도_표시하지_않는다():
    kept, _ = main_validate({"cards": [_main_card(explanation=None)],
                             "learning_plan": {"objectives": []}}, _prep(), None)
    assert kept
    assert "missing_explanation" not in _flags(kept)


def test_복습은_해설이_있어도_당연히_조용하다():
    kept, _ = main_validate({"cards": [_main_card(explanation="비만세포에서 나온다")],
                             "learning_plan": {"objectives": []}}, _prep(), None)
    assert "missing_explanation" not in _flags(kept)


# ------------------------------------------------- 예습은 본다

def test_예습은_해설이_없으면_다리가_없다고_표시한다():
    kept, _ = pre_validate({"cards": [_pre_card(explanation=None)]}, _prep(), None)
    assert kept
    assert "missing_bridge_to_lecture" in _flags(kept)


def test_예습도_해설이_있으면_조용하다():
    kept, _ = pre_validate(
        {"cards": [_pre_card(explanation="이식 뒤 합병증을 다룰 때 이 약어가 계속 나온다")]},
        _prep(), None)
    assert "missing_bridge_to_lecture" not in _flags(kept)
