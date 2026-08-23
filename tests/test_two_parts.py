"""계획이 두 묶음으로 선다 — 강의록 파트와 기출 파트.

가른 이유는 **기출의 예산이 하나뿐이었기 때문**이다. 260821_03 을 세 번 돌리면
기출직결 카드가 33 → 26 → 27 로 거의 안 움직이는데 배분만 뒤집힌다:
(기출카드 2 / 태그 31) → (12 / 14) → (4 / 23). 프롬프트로 한쪽을 밀면 다른 쪽이
빠졌다. 같은 주머니를 나눠 쓰고 있었던 것이다.
"""

from jsonschema import Draft202012Validator

from pdf2anki.assemble import topic_count
from pdf2anki.review import render
from pdf2anki.schema import PLAN_SCHEMA
from pdf2anki.validate import validate


def _prep(n_slides=10):
    return {"source": "테스트 강의", "slides": n_slides,
            "pages": [{"slide": i, "lecture_text": "", "annotations": [],
                       "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _plan(**kw):
    p = {"objectives": [{"objective": "역형성의 형태학적 특징을 열거한다",
                         "retrieval_targets": ["핵의 다형성"], "slides": [3],
                         "importance": "core", "jokbo_refs": ["2023-61"]}],
         "jokbo_objectives": [
             {"objective": "역형성 문항의 오답 선지가 각각 왜 답이 아닌지 구분한다",
              "retrieval_targets": ["극성의 소실은 침습성보다 확실성이 낮다"],
              "jokbo_refs": ["2023-61", "2022-55", "2020-68"],
              "importance": "core", "axis": "오답 선지"}],
         "rejected_candidates": []}
    p.update(kw)
    return p


def _card(q, **kw):
    c = {"q": q, "a": "답", "explanation": "왜", "card_format": "basic",
         "card_type": "fact", "importance": "core", "source_type": "lecture",
         "evidence_type": "lecture_text", "exam_hit": False, "slide_no": 3}
    c.update(kw)
    return c


# ── 스키마 ────────────────────────────────────────────────────────

def test_기출_목표가_스키마에_선다():
    assert list(Draft202012Validator(PLAN_SCHEMA).iter_errors(_plan())) == []


def test_기출_목표는_슬라이드가_없어도_된다():
    """근거가 슬라이드가 아니라 기출 문항이다. 강의록에 없는 것도 설 수 있다."""
    p = _plan()
    assert "slides" not in p["jokbo_objectives"][0]
    assert list(Draft202012Validator(PLAN_SCHEMA).iter_errors(p)) == []


def test_기출_목표에_근거_문항이_없으면_계약_위반이다():
    p = _plan()
    del p["jokbo_objectives"][0]["jokbo_refs"]
    assert list(Draft202012Validator(PLAN_SCHEMA).iter_errors(p)) != []


def test_기출_묶음이_없는_계획도_그대로_통과한다():
    """당분간 두 판이 섞여 돈다 — 옛 계획을 깨지 않는다."""
    p = _plan()
    del p["jokbo_objectives"]
    assert list(Draft202012Validator(PLAN_SCHEMA).iter_errors(p)) == []


# ── 실질 주제 수 ──────────────────────────────────────────────────

def test_주제_수는_묶음을_하나로_센다():
    """문항 수로 세면 같은 주제를 다섯 해치 따로 세우게 된다."""
    stats = {"n_questions": 15,
             "repeat_pairs": [{"a": "2020-68", "b": "2022-55", "jaccard": 1.0},
                              {"a": "2022-55", "b": "2023-61", "jaccard": 1.0}]}
    topics, n_cl, n_sg = topic_count(stats)
    assert (topics, n_cl, n_sg) == (13, 1, 12)     # 3문항이 한 주제로 접힌다


def test_반복이_없으면_주제_수가_문항_수와_같다():
    assert topic_count({"n_questions": 15, "repeat_pairs": []}) == (15, 0, 15)


# ── 검토지 ────────────────────────────────────────────────────────

def test_검토지가_두_파트를_따로_펼친다():
    md, stats = render(_plan(), _prep())
    assert "## 기출 파트 — 목표 1개" in md
    assert stats["jokbo_objectives"] == 1
    assert "[오답 선지]" in md
    assert "3해 반복" in md


def test_기출_목표가_없으면_그_절도_없다():
    p = _plan()
    del p["jokbo_objectives"]
    md, stats = render(p, _prep())
    assert "기출 파트" not in md and stats["jokbo_objectives"] == 0


# ── 커버리지 ──────────────────────────────────────────────────────

def test_기출_목표를_덮은_카드가_없으면_잡힌다():
    raw = {"cards": [_card("역형성의 형태학적 특징은?")], "learning_plan": _plan()}
    _, s = validate(raw, _prep(), None)
    assert len(s["coverage"]["jokbo_objectives_without_card"]) == 1


def test_인용_문항이_같으면_덮은_것으로_본다():
    """기출 목표는 슬라이드로 못 맞춘다. 인용 문항이 겹치는지로 본다."""
    jc = _card("극성의 소실이 침습성보다 확실한 지표다.", source_type="jokbo",
               evidence_type="jokbo_question", slide_no=None, card_format="ox", a="X",
               jokbo_ref={"year": "2023", "no": "61", "role": "source"})
    raw = {"cards": [_card("역형성의 형태학적 특징은?"), jc], "learning_plan": _plan()}
    _, s = validate(raw, _prep(), None)
    assert s["coverage"]["jokbo_objectives_without_card"] == []
    assert s["coverage"]["jokbo_objectives_total"] == 1
