"""예습 카드의 「왜 냈나」와 도전 문제 — 2026-10-04 관리자.

  · 생소한 문제를 본 학생이 「이것까지 알아야 하나?」 싶지 않게 **왜 냈는지**를
    앞면에 보인다(`why_asked`).
  · 흥미를 끌 만큼 중요하지만 어려운 문제를 **한두 장** 넣는다(`challenge`).
"""

from __future__ import annotations

from quizgen.prequiz.build import FLAG_LABEL, WARN_TRUST, tags_of, why_of
from quizgen.prequiz.schema import CARD_SCHEMA, MAX_CHALLENGE, MAX_WHY_CHARS
from quizgen.prequiz.validate import validate


def _prep(n_slides=20):
    return {"slides": n_slides,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


# 서로 안 겹치는 질문 열둘 — 비슷한 문구면 중복 표시가 섞여 무엇을 재는지 흐려진다.
TOPICS = ["심근경색", "폐색전", "당뇨", "통풍", "빈혈", "간경변",
          "패혈증", "갑상선", "신부전", "천식", "뇌졸중", "골다공증"]


def _card(i, **kw):
    c = {"q": f"{TOPICS[i]}의 정의는?", "a": f"정의{i}", "card_format": "basic",
         "card_type": "term", "reason": "vocabulary", "source_type": "lecture",
         "evidence_type": "lecture_text", "slide_no": i + 1,
         "explanation": "수업에서 이렇게 쓰인다",
         "why_asked": "강의 후반 감별 진단 내내 이 기준으로 가른다"}
    c.update(kw)
    return c


def _flags(raw):
    kept, s = validate(raw, _prep(), None)
    return kept, s


def test_새_칸이_카드_계약에_있다():
    props = CARD_SCHEMA["properties"]
    assert "why_asked" in props and "challenge" in props
    # 필수로 두지 않는다 — 빠뜨린 카드가 스키마에서 통째로 버려지면 덱이 모자란다.
    assert "why_asked" not in CARD_SCHEMA["required"]


def test_왜_냈나가_비면_표시가_선다():
    cards = [_card(i) for i in range(12)]
    cards[0]["why_asked"] = ""
    kept, _ = _flags({"cards": cards})
    assert "missing_why_asked" in kept[0]["review_flags"]
    assert "missing_why_asked" not in kept[1]["review_flags"]


def test_왜_냈나에_답이_들면_표시가_선다():
    cards = [_card(i) for i in range(12)]
    cards[0]["a"] = "트로포닌"
    cards[0]["why_asked"] = "트로포닌은 진단에서 가장 먼저 오른다"
    kept, _ = _flags({"cards": cards})
    assert "answer_leaked_in_why" in kept[0]["review_flags"]


def test_왜_냈나가_길면_표시가_선다():
    cards = [_card(i) for i in range(12)]
    cards[0]["why_asked"] = "가" * (MAX_WHY_CHARS + 1)
    kept, _ = _flags({"cards": cards})
    assert "why_asked_too_long" in kept[0]["review_flags"]


def test_기출을_이유로_들면_문항이_있어야_한다():
    cards = [_card(i) for i in range(12)]
    cards[0]["why_asked"] = "2024·2025 기출에 연달아 나왔다"
    kept, _ = _flags({"cards": cards})
    assert "why_cites_exam_without_ref" in kept[0]["review_flags"]
    # 근거 없는 이유를 학생에게 보인 것이라 겉면 층이다.
    assert "why_cites_exam_without_ref" in WARN_TRUST


def test_도전_문제는_상한까지는_위반이_아니다():
    cards = [_card(i) for i in range(12)]
    for c in cards[:MAX_CHALLENGE]:
        c["challenge"] = True
    _, s = _flags({"cards": cards})
    assert s["contract_violations"] == []
    assert s["challenge"] == MAX_CHALLENGE


def test_도전_문제가_넘치면_계약_위반이다():
    """계약 위반은 수선 고리로 간다 — 넘친 것을 false 로 돌리게 한다."""
    cards = [_card(i) for i in range(12)]
    for c in cards[:MAX_CHALLENGE + 1]:
        c["challenge"] = True
    _, s = _flags({"cards": cards})
    assert any("도전 문제" in v for v in s["contract_violations"])


def test_새_표시는_전부_사람이_읽을_말이_있다():
    for f in ("missing_why_asked", "answer_leaked_in_why", "why_asked_too_long",
              "why_cites_exam_without_ref"):
        assert f in FLAG_LABEL, f


def test_앞면에_왜_냈나와_도전_표시가_붙는다():
    head = why_of({"why_asked": "심근경색 진단에서 <먼저> 오른다", "challenge": True})
    assert "도전 문제" in head
    assert "&lt;먼저&gt;" in head          # 이스케이프한다
    assert why_of({"why_asked": "", "challenge": False}) == ""
    # 예전 카드(칸이 없다)는 아무것도 안 붙는다.
    assert why_of({}) == ""


def test_도전_문제는_태그로도_갈린다():
    c = _card(0, challenge=True)
    assert "도전문제" in tags_of(c, "p251004_01")
    assert "도전문제" not in tags_of(_card(1), "p251004_01")


# ── 「왜 냈나」의 재료는 ① 단계가 모은다 ────────────────────────────
#
# ② 단계에서 새로 지으면 근거 없는 이유가 끼어든다. ① 단계가 자료를 다 읽은 채로
# 항목마다 `signals` 를 적고, ② 는 거기서 뽑는다(2026-10-04 관리자와 정했다).

def _must(signals):
    return {"items": [{"item": f"항목{i}", "reason": "spine", "why": "막힌다",
                       "slides": [1], "cards": 1, **({"signals": signals} if i == 0 else {})}
                      for i in range(10)]}


def test_항목에_근거를_적을_수_있다():
    from jsonschema import Draft202012Validator

    from quizgen.prequiz.schema import MUST_KNOW_SCHEMA
    ok = _must([{"kind": "exam", "detail": "2024·2025 연달아", "ref": "2025-19"},
                {"kind": "clinical", "detail": "심근경색 진단에 쓴다"}])
    assert not list(Draft202012Validator(MUST_KNOW_SCHEMA).iter_errors(ok))
    # 근거가 없는 항목도 된다 — 용어 항목은 비는 것이 보통이다.
    assert not list(Draft202012Validator(MUST_KNOW_SCHEMA).iter_errors(_must([])))
    bad = _must([{"kind": "important", "detail": "중요하다"}])
    assert list(Draft202012Validator(MUST_KNOW_SCHEMA).iter_errors(bad))


def test_검토_문서에_근거가_보인다():
    from quizgen.prequiz.run import render_must
    doc = render_must(_must([{"kind": "exam", "detail": "2024·2025 연달아", "ref": "2025-19"}]))
    assert "근거·exam: 2024·2025 연달아 (2025-19)" in doc


def test_계약이_왜_냈나를_근거에서_뽑게_한다(tmp_path):
    from quizgen.prequiz.schema import dump
    dump(tmp_path)
    contract = (tmp_path / "contract.md").read_text(encoding="utf-8")
    assert "`signals` 에서 뽑는다" in contract
    # 도전 문제는 「어려운 문제」가 아니라 「수업이 답해 줄 질문」이다.
    assert "수업이 답해 줄 질문" in contract
    assert "대목에서 풀린다" in contract
