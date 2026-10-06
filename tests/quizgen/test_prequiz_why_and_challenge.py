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


def test_왜_냈나에_답이_들어도_된다():
    """답 뒤에 보이므로(같은 날 관리자 — 「풀고 나서 이유가 보이는 건 어때」) 재지 않는다."""
    cards = [_card(i) for i in range(12)]
    cards[0]["a"] = "트로포닌"
    cards[0]["why_asked"] = "트로포닌은 진단에서 가장 먼저 오른다"
    kept, _ = _flags({"cards": cards})
    assert not any("leak" in f and "why" in f for f in kept[0]["review_flags"])


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
    cards = [_card(i) for i in range(5 + MAX_CHALLENGE)]
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
    for f in ("missing_why_asked", "why_asked_too_long",
              "why_cites_exam_without_ref", "missing_why_tags", "why_tag_not_in_signals"):
        assert f in FLAG_LABEL, f


def test_앞면에는_배지만_뒷면에_글이_붙는다():
    from quizgen.prequiz.build import why_back
    c = {"why_asked": "심근경색 진단에서 <먼저> 오른다", "challenge": True, "why_tags": ["clinical"]}
    head = why_of(c)
    assert "도전 문제" in head and "임상" in head
    assert "심근경색" not in head          # 글은 앞면에 없다
    back = why_back(c)
    assert "왜 냈나" in back and "&lt;먼저&gt;" in back   # 이스케이프한다
    assert why_of({"why_asked": "", "challenge": False}) == ""
    # 예전 카드(칸이 없다)는 아무것도 안 붙는다.
    assert why_of({}) == "" and why_back({}) == ""


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
                      for i in range(5)]}


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
    # 「왜 냈나」는 답 뒤에 보인다 — 도전 문제가 풀리는 대목을 이름으로 적어도 된다.
    assert "답을 편 뒤" in contract
    assert "부분에서 답이 나온다" in contract
    # 학생에게 하는 말 — 관리자가 「한국어가 좀 어색하다」고 짚은 꼴을 계약이 적고 있다.
    assert "자연스러운 한국어 한 문장" in contract
    # 글은 배지를 되풀이하지 않는다 — 기출 이유만 몰리지 않게.
    assert "글은 배지를 되풀이하지 않는다" in contract


# ── 「왜 냈나」의 유형 배지 ───────────────────────────────────────────

def _linked(signals, **card):
    """승인본 항목 m01 에 근거가 있고, 카드 열둘이 m01..m12 에 붙는다."""
    must = {"items": [{"id": f"m{i + 1:02d}", "item": f"항목{i}", "reason": "spine",
                       "why": "막힌다", "slides": [i + 1], "cards": 1,
                       **({"signals": signals} if i == 0 else {"signals": []})}
                      for i in range(12)]}
    cards = [_card(i, must_id=f"m{i + 1:02d}", why_tags=["basis"]) for i in range(12)]
    cards[0].update(card)
    return {"cards": cards, "must_know": must}


def test_배지가_근거에_있으면_표시가_없다():
    raw = _linked([{"kind": "clinical", "detail": "진단에 쓴다"}], why_tags=["clinical"])
    kept, _ = _flags(raw)
    assert "why_tag_not_in_signals" not in kept[0]["review_flags"]
    assert "missing_why_tags" not in kept[0]["review_flags"]


def test_근거에_없는_배지는_표시가_선다():
    raw = _linked([{"kind": "clinical", "detail": "진단에 쓴다"}], why_tags=["later"])
    kept, _ = _flags(raw)
    assert "why_tag_not_in_signals" in kept[0]["review_flags"]


def test_기본_개념_배지는_언제나_된다():
    kept, _ = _flags(_linked([]))
    assert all("why_tag_not_in_signals" not in c["review_flags"] for c in kept)


def test_기출_배지는_근거에서_문항을_채운다():
    raw = _linked([{"kind": "exam", "detail": "2025 기출", "ref": "2025-28"}],
                  why_tags=["exam"], why_asked="강의 후반 약물 비교의 기준이다")
    kept, s = _flags(raw)
    assert kept[0]["jokbo_ref"] == {"year": "2025", "no": "28"}
    assert "why_cites_exam_without_ref" not in kept[0]["review_flags"]
    assert s["autofixed"].get("jokbo_ref_from_signals") == 1


def test_문항을_못_채우면_표시가_남는다():
    raw = _linked([{"kind": "exam", "detail": "여러 해 나왔다"}],
                  why_tags=["exam"], why_asked="강의 후반 약물 비교의 기준이다")
    kept, _ = _flags(raw)
    assert "why_cites_exam_without_ref" in kept[0]["review_flags"]


def test_기출_근거가_있으면_글이_달라도_기출_배지가_붙는다():
    """2026-10-04 — 배지를 글의 유형으로 고르게 했더니 6편에서 16장이 기출 배지를 잃었다."""
    raw = _linked([{"kind": "exam", "detail": "2025 기출", "ref": "2025-28"},
                   {"kind": "later", "detail": "뒤에서 또"}],
                  why_tags=["later", "annotation"], why_asked="뒤의 약물 비교의 기준이다")
    kept, s = _flags(raw)
    assert kept[0]["why_tags"][0] == "exam"
    assert "later" in kept[0]["why_tags"]          # 있던 배지는 그대로 남는다
    assert s["autofixed"].get("exam_tag_from_signals") == 1
    # 기출 근거가 없는 항목의 카드는 손대지 않는다.
    assert "exam" not in kept[1]["why_tags"]


def test_배지가_없으면_표시가_선다():
    raw = _linked([], why_tags=[])
    kept, _ = _flags(raw)
    assert "missing_why_tags" in kept[0]["review_flags"]


def test_근거_칸이_없던_승인본은_배지를_안_잰다():
    """10-04 전 승인본에는 `signals` 칸이 없다. 재면 모든 배지가 「근거 밖」이 된다."""
    raw = _linked([], why_tags=["clinical"])
    for it in raw["must_know"]["items"]:
        it.pop("signals")
    kept, _ = _flags(raw)
    assert "why_tag_not_in_signals" not in kept[0]["review_flags"]


def test_앞면에_유형_배지가_붙는다():
    from quizgen.prequiz.schema import WHY_TAG_LABEL
    head = why_of({"why_asked": "강의 후반 감별 내내 쓴다", "why_tags": ["exam", "later", "bogus"]})
    assert '<span class="tag exam">기출</span>' in head
    assert f'<span class="tag later">{WHY_TAG_LABEL["later"]}</span>' in head
    assert "bogus" not in head                      # 모르는 값은 안 그린다


def test_다른_근거가_있으면_필기_강조_배지를_뗀다():
    """2026-10-05 관리자 — 「필기 강조는 다른 근거 있으면 빼줘」."""
    from quizgen.prequiz.validate import prune_annotation
    assert prune_annotation(["exam", "annotation"]) == ["exam"]
    assert prune_annotation(["annotation", "later", "clinical"]) == ["later", "clinical"]
    assert prune_annotation(["annotation"]) == ["annotation"]          # 그것뿐이면 남긴다
    assert prune_annotation(["annotation", "basis"]) == ["annotation", "basis"]
    raw = _linked([{"kind": "annotation", "detail": "별표"}, {"kind": "clinical", "detail": "진단"}],
                  why_tags=["annotation", "clinical"])
    kept, s = _flags(raw)
    assert kept[0]["why_tags"] == ["clinical"]
    assert s["autofixed"].get("annotation_tag_dropped") == 1
