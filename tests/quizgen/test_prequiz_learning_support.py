"""예습의 읽기 근거, 학습 지원 전달, 핵심/도전 분량을 검사한다."""
from copy import deepcopy

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


def test_five_core_and_optional_challenge():
    core = [card(i) for i in range(5)]
    assert not check(core)[1]["contract_violations"]
    assert not check(core + [card(5, challenge=True)])[1]["contract_violations"]
    assert check(core + [card(5)])[1]["contract_violations"]
    assert check(core[:4] + [card(5, challenge=True)])[1]["contract_violations"]


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
