"""예습의 읽기 근거, 학습 지원 전달, 핵심/도전 분량을 검사한다."""
from copy import deepcopy

import pytest

from quizgen.prequiz.build import support_back, why_of
from quizgen.prequiz.validate import validate
from runner.deck import _web_items


def card(i=0, **extra):
    return {"q": f"개념 {i}의 구분 기준은?", "a": f"기준{i}", "card_format": "basic",
            "card_type": "comparison", "reason": "spine", "source_type": "note",
            "evidence_type": "preview_note", "why_asked": "뒤의 비교 설명을 이해할 기준이다",
            "why_tags": ["basis"], "explanation": "두 범주를 구분한다",
            "learning_support": {"hint": "분류할 때 사용한 축을 떠올려 보자",
                                 "scope": "구분 기준 하나만 알면 충분하다",
                                 "lecture_focus": "수업에서 이 기준의 적용을 살펴보자",
                                 "preview_excerpt": "범주는 기준으로 구분한다."}, **extra}


def check(cards, text="범주는 기준으로\n구분한다."):
    return validate({"cards": deepcopy(cards)}, {"slides": 1, "pages": []}, None, preview_text=text)


def test_ten_total_includes_one_or_two_challenges():
    for total in (8, 10, 12):
        for challenges in (1, 2):
            cards = [card(i, challenge=i >= total - challenges) for i in range(total)]
            assert not check(cards)[1]["contract_violations"]
    for total, challenges in ((7, 1), (13, 2), (10, 0), (10, 3)):
        cards = [card(i, challenge=i >= total - challenges) for i in range(total)]
        assert check(cards)[1]["contract_violations"]


def test_preview_excerpt_must_exist_and_core_must_have_it():
    valid = card()
    missing = card(1)
    missing["learning_support"]["preview_excerpt"] = ""
    invented = card(2)
    invented["learning_support"]["preview_excerpt"] = "없는 문장"
    kept, _ = check([valid, missing, invented])
    assert "preview_excerpt_not_found" not in kept[0]["review_flags"]
    assert "missing_preview_evidence" in kept[1]["review_flags"]
    assert "preview_excerpt_not_found" in kept[2]["review_flags"]
    challenge = card(challenge=True)
    challenge["learning_support"]["preview_excerpt"] = ""
    assert "missing_preview_evidence" not in check([challenge])[0][0]["review_flags"]


def test_legacy_without_note_is_supported_but_new_support_is_reviewed():
    old = card()
    old.pop("learning_support")
    assert "missing_learning_support" not in check([old], None)[0][0]["review_flags"]
    assert "missing_learning_support" in check([old])[0][0]["review_flags"]
    assert "missing_preview_evidence" not in check([old], "")[0][0]["review_flags"]


def test_support_reaches_web_and_anki_without_exposing_excerpt():
    c = card()
    c["learning_support"]["hint"] = "<축>을 떠올려 보자"
    assert _web_items([c])[0]["learning_support"] == c["learning_support"]
    front, back = why_of(c), support_back(c)
    assert "<details" in front and "&lt;축&gt;" in front
    assert c["learning_support"]["scope"] not in front
    assert c["learning_support"]["scope"] in back
    assert c["learning_support"]["lecture_focus"] in back
    assert c["learning_support"]["preview_excerpt"] not in front + back


@pytest.mark.parametrize("field,text", [
    ("q", "설명본에 따르면 여과액이 다음으로 지나는 구조는?"),
    ("q", "예습 자료에서 약물이 몸에 미치는 작용을 무엇이라 하는가?"),
    ("hint", "설명본의 네프론 지도에서 근위세뇨관 뒤의 화살표를 따라가 보세요."),
    ("hint", "'설명본'에서 몸과 약물 중 어느 쪽이 무엇을 하는지 살펴보세요."),
])
def test_source_narration_in_question_or_hint_is_reviewed(field, text):
    c = card()
    if field == "q":
        c["q"] = text
    else:
        c["learning_support"]["hint"] = text
    kept, suspects = check([c])
    assert len(kept) == 1  # 문구 문제는 삭제 사유가 아닌 검토 표시다.
    assert "preview_narration" in kept[0]["review_flags"]
    assert suspects["flag_counts"]["preview_narration"] == 1


def test_direct_situation_and_private_excerpt_do_not_trigger_narration_flag():
    c = card(q="약물 투여 뒤 혈압이 낮아졌다. 약물이 몸에 미치는 작용을 무엇이라 하는가?")
    c["learning_support"]["hint"] = "변화를 일으키는 주체가 몸인지 약물인지 먼저 구분해 보세요."
    c["learning_support"]["preview_excerpt"] = "설명본에서는 약물이 몸에 미치는 작용을 다룬다."
    kept, _ = check([c], c["learning_support"]["preview_excerpt"])
    assert "preview_narration" not in kept[0]["review_flags"]
