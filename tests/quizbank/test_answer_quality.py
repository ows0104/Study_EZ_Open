"""정답의 회상 부담과 구조 단서를 **잰다**. 선은 규칙이 아니라 분포의 꼬리다.

2026-11-08 관리자 지적 — 「초등학생이 문장 구조만 봐도 X라고 하겠다」, 「답이 너무
길면 회상이 힘들다. 그 정도로 길면 cloze나 객관식으로 내던가」. 진단은 감염과 면역
261104_02 「감염성 질환의 병리 1」 98문항에서 예/아니오 축 6문항의 정답이 전부
부정이고, cloze·객관식이 0개였다는 것이었다.

여기서 재는 것은 전부 **warnings** 다. 문항을 떨어뜨리지 않는다 — `validate_dropping`
이 errors 만 보고 빼기 때문이고, 결함을 막지 않고 올리는 현행 정책이기도 하다.
경고는 repair 단계 입력(`validation`)과 관리자 화면 issues 로 돌아간다.
"""

import json
from pathlib import Path

import pytest

from studyez_contracts.bank.quality import (
    LONG_ANSWER_CHARS,
    LONG_UNIT_CHARS,
    MAX_ANSWER_UNITS,
    answer_polarity,
    quality_errors,
    recall_chars,
)
from quizbank.validate import validate_bank

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def real_bank():
    return json.loads((FIX / "bank_261002_02.json").read_text(encoding="utf-8"))


def bank_of(*questions: dict, schema_version: str = "3.2") -> dict:
    """품질 측정이 실제로 읽는 자리만 채운 은행."""
    filled = []
    for i, q in enumerate(questions, start=1):
        base = {"question_id": f"Q{i:03d}", "format": "basic", "question": "무엇인가?",
                "answer": "답", "answer_units": [], "retrieval_direction": "direct"}
        base.update(q)
        if not base["answer_units"] and base["format"] in ("basic", "list"):
            base["answer_units"] = [base["answer"]]
        filled.append(base)
    return {"build_meta": {"schema_version": schema_version}, "questions": filled}


def warnings_of(bank: dict) -> list[str]:
    errors, warnings = quality_errors(bank)
    assert errors == [], "측정은 errors 를 늘리지 않는다"
    return warnings


def kinds(warnings: list[str]) -> list[str]:
    """경고 한 줄을 종류로 줄인다 — 문구가 아니라 측정이 걸렸는지만 본다."""
    found = []
    for line in warnings:
        for key, name in (("회상 부담이 크다", "회상 부담"), ("예/아니오로 답한다", "예아니오 축"),
                          ("단정어", "단정어×부정"), ("정답이 모두", "정답 쏠림"),
                          ("형식이 좁다", "형식 쏠림"),
                          ("basic인데 채점 단위", "basic 단위")):
            if key in line:
                found.append(name)
                break
    return found


# ── 측정은 문항을 떨어뜨리지 않는다 ──────────────────────────────────────────

def test_실물_은행의_오류_목록은_그대로다(real_bank):
    """261002_02 의 list 채점단위 셋. 측정을 붙여도 errors 는 늘지 않는다."""
    v = validate_bank(real_bank, ["S1", "S2"])
    assert v["errors"] == ["Q009: list는 개별 채점 단위 2개 이상 필요",
                           "Q015: list는 개별 채점 단위 2개 이상 필요",
                           "Q026: list는 개별 채점 단위 2개 이상 필요"]


def test_옛_3_0_은행은_아무것도_재지_않는다():
    long_answer = "가" * (LONG_ANSWER_CHARS["basic"] + 20)
    bank = bank_of({"answer": long_answer}, schema_version="3.0")
    assert quality_errors(bank) == ([], [])


# ── 구조 단서와 정답의 상관 ──────────────────────────────────────────────────

def test_basic이_예_아니오로_답하면_적는다():
    bank = bank_of({"question": "감염성 질환이라는 이유만으로 전파되는 질환이라고 단정할 수 있는가?",
                    "answer": "단정할 수 없다"})
    assert "예아니오 축" in kinds(warnings_of(bank))


def test_정답이_O로_시작하는_약물명은_극성이_아니다():
    """운영 은행에서 Olaparib·O₂·OCT1 을 34번 예/아니오로 잘못 짚었다(2026-11-08)."""
    for answer in ("Olaparib", "O₂", "OCT1", "OKT3(muromonab-CD3)", "Osteoclast(파골세포)"):
        question = {"question": "BRCA 결함 암에서 PARP를 억제하는 약물은?", "answer": answer}
        assert answer_polarity(bank_of(question)["questions"][0]) is None, answer
        assert kinds(warnings_of(bank_of(question))) == []


def test_ox의_한_글자_정답은_극성이다():
    assert answer_polarity({"format": "ox", "answer": "X"}) == "neg"
    assert answer_polarity({"format": "ox", "answer": "O"}) == "pos"


def test_예_아니오_정답이_한쪽으로_쏠리면_적고_섞이면_적지_않는다():
    one_sided = bank_of(*[{"format": "ox", "question": f"{i} 판단", "answer": "X",
                           "answer_units": ["X"]} for i in range(3)])
    assert "정답 쏠림" in kinds(warnings_of(one_sided))
    mixed = bank_of(*[{"format": "ox", "question": f"{i} 판단", "answer": answer,
                       "answer_units": [answer]}
                      for i, answer in enumerate(("X", "X", "O"))])
    assert "정답 쏠림" not in kinds(warnings_of(mixed))


def test_예_아니오가_둘뿐이면_쏠림을_말하지_않는다():
    """두 개로는 분포를 말할 수 없다. 개별 문항 경고만 남는다."""
    bank = bank_of(*[{"format": "ox", "question": f"{i} 판단", "answer": "X",
                      "answer_units": ["X"]} for i in range(2)])
    assert "정답 쏠림" not in kinds(warnings_of(bank))


def test_단정어는_그_자체로는_적지_않는다():
    """정본 §3.5 — 단정어를 일괄 금지하지 않는다. 부정 정답과 겹칠 때만 적는다."""
    affirmed = bank_of({"format": "ox", "question": "결핵은 반드시 건락성 육아종을 만든다. (O/X)",
                        "answer": "O", "answer_units": ["O"]})
    assert "단정어×부정" not in kinds(warnings_of(affirmed))
    denied = bank_of({"format": "ox",
                      "question": "염증이 관찰되면 원인이 반드시 감염이라고 결론 내릴 수 있다. (O/X)",
                      "answer": "X", "answer_units": ["X"]})
    assert "단정어×부정" in kinds(warnings_of(denied))


# ── 정답의 회상 부담 ────────────────────────────────────────────────────────

def test_공백은_회상_글자에_세지_않는다():
    assert recall_chars({"format": "basic", "answer": "M. tuberculosis"}) == 14


def test_basic_정답이_선을_넘으면_적는다():
    line = LONG_ANSWER_CHARS["basic"]
    assert kinds(warnings_of(bank_of({"answer": "가" * line}))) == []
    assert "회상 부담" in kinds(warnings_of(bank_of({"answer": "가" * (line + 1)})))


def test_basic은_채점_단위가_하나다():
    """여러 요구를 한 발문에 묶은 basic 은 형식이 틀렸다 — 2026-11-08 Map 판 basic 72개 중 62개."""
    one = bank_of({"answer": "MERS"})
    assert kinds(warnings_of(one)) == []
    two = bank_of({"answer": "넓은 정의: histiocyte 집합; 좁은 정의: epithelioid histiocyte 집합",
                   "answer_units": ["넓은 정의: histiocyte 집합", "좁은 정의: epithelioid histiocyte 집합"]})
    assert kinds(warnings_of(two)) == ["basic 단위"]
    as_list = bank_of({"format": "list", "answer": "가; 나", "answer_units": ["가", "나"]})
    assert "basic 단위" not in kinds(warnings_of(as_list))


def test_list는_단위_길이와_단위_수를_따로_본다():
    short_many = bank_of({"format": "list", "answer": "; ".join(["가"] * (MAX_ANSWER_UNITS + 1)),
                          "answer_units": ["가"] * (MAX_ANSWER_UNITS + 1)})
    assert "회상 부담" in kinds(warnings_of(short_many))
    one_long = bank_of({"format": "list", "answer": "가; " + "나" * (LONG_UNIT_CHARS + 1),
                        "answer_units": ["가", "나" * (LONG_UNIT_CHARS + 1)]})
    assert "회상 부담" in kinds(warnings_of(one_long))
    ordinary = bank_of({"format": "list", "answer": "결핵: M. tuberculosis; 한센병: M. leprae",
                        "answer_units": ["결핵: M. tuberculosis", "한센병: M. leprae"]})
    assert kinds(warnings_of(ordinary)) == []


def test_cloze_프레임에는_길이_선을_긋지_않는다():
    """cloze 의 answer 는 빈칸을 채운 문장 전체다. 그 길이는 회상 부담이 아니다."""
    frame = "MALT는 " + "가" * 200 + " 이차 림프기관이다"
    bank = bank_of({"format": "cloze", "question": "MALT는 " + "가" * 200 + " {{c1}}이다",
                    "answer": frame, "answer_units": ["이차 림프기관"]})
    assert kinds(warnings_of(bank)) == []


# ── 형식 쏠림 ───────────────────────────────────────────────────────────────

def _wide(count: int, *, answer: str) -> list[dict]:
    return [{"question_id": f"Q{i:03d}", "answer": answer} for i in range(count)]


def test_긴_정답이_있는데_cloze도_객관식도_없으면_적는다():
    long_answer = "가" * (LONG_ANSWER_CHARS["basic"] + 1)
    narrow = bank_of(*_wide(20, answer=long_answer))
    assert "형식 쏠림" in kinds(warnings_of(narrow))


def test_cloze와_객관식이_있으면_형식_쏠림을_말하지_않는다():
    long_answer = "가" * (LONG_ANSWER_CHARS["basic"] + 1)
    questions = _wide(18, answer=long_answer) + [
        {"format": "cloze", "question": "{가}다", "answer": "가다", "answer_units": ["가"]},
        {"format": "mcq", "question": "무엇인가?", "answer": "A", "answer_units": ["A"]}]
    assert "형식 쏠림" not in kinds(warnings_of(bank_of(*questions)))


def test_정답이_짧으면_형식_구성을_따지지_않는다():
    """cloze 가 없다는 것만으로는 적지 않는다 — 돌릴 긴 정답이 있을 때만 말이 된다."""
    assert "형식 쏠림" not in kinds(warnings_of(bank_of(*_wide(30, answer="짧은 답"))))


def test_작은_은행에서는_형식_구성을_따지지_않는다():
    long_answer = "가" * (LONG_ANSWER_CHARS["basic"] + 1)
    assert "형식 쏠림" not in kinds(warnings_of(bank_of(*_wide(19, answer=long_answer))))
