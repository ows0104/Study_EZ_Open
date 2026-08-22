"""예습 덱의 계약.

세 가지를 지킨다.
  · 예습 덱이 복습 덱과 **한 노드 아래 형제로** 선다.
  · 같은 질문이라도 예습 노트와 복습 노트의 **guid 가 갈린다.**
  · 20~30장·O/X 상한·교수 교체 시 `reason=repeated` 금지가 **실제로 걸린다.**
"""

import argparse
import json as _json

import genanki
import pytest

from pdf2anki.prequiz.build import guid_seed
from pdf2anki.prequiz.run import Runner, deck_of
from pdf2anki.prequiz.schema import MAX_CARDS, MIN_CARDS
from pdf2anki.prequiz.validate import validate


def test_예습_덱은_강의록_기출과_형제다():
    quiz_node = "병리학::종양의 분자생물학(1)"
    assert deck_of("종양의 분자생물학(1)", "병리학") == quiz_node + "::예습"


def test_같은_질문이어도_복습과_guid_가_갈린다():
    """이것이 없으면 Anki 가 한 노트로 보고 한쪽이 다른 쪽을 덮는다.

    `build.py` 의 guid 는 `(강의 ID, 질문)` 이다. 예습과 복습이 같은 용어를 같은
    문장으로 묻는 일은 용어 카드에서 충분히 일어난다.
    """
    q = "이형성증(dysplasia)이란?"
    quiz = genanki.guid_for("p260825_01", q)
    pre = genanki.guid_for(guid_seed("p260825_01"), q)
    assert quiz != pre


def _prep(n_slides=10):
    return {"slides": n_slides,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _card(q, a="답", **kw):
    c = {"q": q, "a": a, "card_format": "basic", "card_type": "term",
         "reason": "vocabulary", "source_type": "lecture", "evidence_type": "lecture_text",
         "slide_no": 1, "explanation": "수업에서 이렇게 쓰인다"}
    c.update(kw)
    return c


def test_카드가_모자라면_계약_위반으로_잡힌다():
    raw = {"cards": [_card(f"질문 {i}") for i in range(MIN_CARDS - 1)]}
    _, s = validate(raw, _prep(), None)
    assert any("최소" in v for v in s["contract_violations"])


def test_카드가_넘치면_계약_위반으로_잡힌다():
    raw = {"cards": [_card(f"질문 {i}") for i in range(MAX_CARDS + 1)]}
    _, s = validate(raw, _prep(), None)
    assert any("상한" in v for v in s["contract_violations"])


def test_계약_안이면_위반이_없다():
    raw = {"cards": [_card(f"질문 {i}") for i in range(MIN_CARDS + 2)]}
    kept, s = validate(raw, _prep(), None)
    assert len(kept) == MIN_CARDS + 2
    assert s["contract_violations"] == []


def test_OX_가_1_5_를_넘으면_잡힌다():
    """예습은 알게 하는 것이 목적이라 O/X 는 회수량이 적다."""
    cards = [_card(f"진술 {i}", "O", card_format="ox") for i in range(8)]
    cards += [_card(f"질문 {i}") for i in range(14)]
    _, s = validate({"cards": cards}, _prep(), None)
    assert any("O/X" in v for v in s["contract_violations"])


def test_교수가_바뀌면_repeated_는_탈락한다():
    """과거의 반복은 이전 교수의 습관이지 이 단원의 중심이 아니다."""
    cards = [_card("반복 출제된 것", reason="repeated",
                   jokbo_ref={"year": "2025", "no": "64"})]
    cards += [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    kept, s = validate({"cards": cards}, _prep(), None, professor_stayed=False)
    assert len(kept) == MIN_CARDS
    assert [d["code"] for d in s["dropped"]] == ["repeated_but_professor_changed"]


def test_교수가_유임이면_repeated_가_산다():
    cards = [_card("반복 출제된 것", reason="repeated",
                   jokbo_ref={"year": "2025", "no": "64"})]
    cards += [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    kept, s = validate({"cards": cards}, _prep(), None, professor_stayed=True)
    assert len(kept) == MIN_CARDS + 1
    assert s["dropped"] == []


def test_함정_유형은_스키마가_막는다():
    """복습에는 있고 예습에는 없다. 수업 전날 함정은 장애물을 하나 더 세우는 것이다."""
    cards = [_card("함정", card_type="trap")]
    cards += [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    _, s = validate({"cards": cards}, _prep(), None)
    assert [d["code"] for d in s["dropped"]] == ["schema"]


def test_수업으로_잇는_해설이_없으면_깃발이_선다():
    cards = [_card("해설 없음", explanation=None)]
    cards += [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    kept, s = validate({"cards": cards}, _prep(), None)
    assert s["flag_counts"].get("missing_bridge_to_lecture") == 1


@pytest.mark.parametrize("src,ok", [("lecture", False), ("note", True)])
def test_슬라이드_요구는_출처에_따라_다르다(src, ok):
    """작년 강의록에서 왔으면 슬라이드를 가리켜야 하고,
    예습 설명본에서 왔으면 가리킬 슬라이드가 없을 수 있다."""
    c = _card("질문", source_type=src, slide_no=None,
              evidence_type="lecture_text" if src == "lecture" else "preview_note")
    kept, _ = validate({"cards": [c]}, _prep(), None)
    assert (len(kept) == 1) is ok


# ── 한 줄 실행이 중간에 죽지 않는가 ────────────────────────────────
#
# 예습은 "명령 한 줄로 덱까지"가 요구사항이다. 실제로 두 군데서 죽었다 —
# ①계약 위반(카드 수·O/X)이 validate 의 종료코드 2 로 나와 실행을 멈췄고,
# ②--skip-reproduce 를 주면 산출물이 안 생기는데 step 이 그것을 요구했다.

def _runner(tmp_path, **kw):
    args = argparse.Namespace(
        skip_reproduce=False, repair_rounds=2, jobs=2, model=None, force=False,
        allow_size=False, hint=None, timeout=60, deck="D::L::예습", id="pX",
        pdf=None, pdf_name="x.pdf", note=None, jokbo_dir="out/jokbo",
        schema_dir="out/prequiz_schema", jokbo=None, stop_at_review=False,
        check_dir=str(tmp_path / "chk"), no_image_check=True)
    for k, v in kw.items():
        setattr(args, k, v)
    return Runner(tmp_path, args)


def test_계약_위반을_실행이_읽어_낸다(tmp_path):
    (tmp_path / "suspects.json").write_text(
        _json.dumps({"contract_violations": ["카드가 33장이다. 상한 30장"]},
                    ensure_ascii=False), encoding="utf-8")
    assert _runner(tmp_path).violations() == ["카드가 33장이다. 상한 30장"]


def test_계약_위반이_없으면_빈_목록(tmp_path):
    assert _runner(tmp_path).violations() == []


def test_재현_결함만_골라낸다(tmp_path):
    cards = [
        {"q": "a", "reproduce": {"verdict": "different", "reason": "needs_options"}},
        {"q": "b", "reproduce": {"verdict": "partial", "reason": "lecture_specific"}},
        {"q": "c", "reproduce": {"verdict": "same"}},
    ]
    (tmp_path / "items.reproduced.json").write_text(
        _json.dumps({"cards": cards}, ensure_ascii=False), encoding="utf-8")
    bad = _runner(tmp_path).defects()
    assert [c["q"] for c in bad] == ["a"]      # lecture_specific 은 결함이 아니다


def test_수선_0회면_아무_것도_안_한다(tmp_path):
    """--repair-rounds 0 은 모델을 부르지 않는다. 부르면 이 테스트가 멈춘다."""
    (tmp_path / "suspects.json").write_text(
        _json.dumps({"contract_violations": ["뭔가 위반"]}, ensure_ascii=False),
        encoding="utf-8")
    _runner(tmp_path, repair_rounds=0).repair()      # 예외 없이 그냥 돌아와야 한다


def test_결함도_위반도_없으면_수선하지_않는다(tmp_path):
    _runner(tmp_path).repair()                       # 모델을 부르면 멈춘다


def test_카드가_넘쳐도_validate_는_카드를_버리지_않는다():
    """계약 위반은 '버릴 것'이 아니라 '사람에게 알릴 것'이다."""
    raw = {"cards": [_card(f"질문 {i}") for i in range(MAX_CARDS + 3)]}
    kept, s = validate(raw, _prep(), None)
    assert len(kept) == MAX_CARDS + 3
    assert s["contract_violations"]
