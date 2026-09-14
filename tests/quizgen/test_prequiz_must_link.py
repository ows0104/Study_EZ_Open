"""승인된 must-know 와 예습 카드를 잇는 끈, 그리고 그 끈이 없을 때의 침묵.

복습 쪽 `test_plan_link.py` 의 예습판이다. 다른 점이 둘 있다.

**① 예습에는 배정 수가 있다.** `must_know` 의 항목마다 `cards` 가 붙어 있는데, 카드가
어느 항목에서 왔는지 안 적어서 **그 배정이 지켜졌는지 볼 길이 없었다.** 편별 합계만
맞으면 통과였다(실측 9편 중 8편 일치).

**② 글자로는 대신 못 잰다.** 항목 문구와 카드 문구의 유사도로 재 보면 문턱 0.05~0.20
사이에서 안 닿은 항목이 8%~72% 로 흔들린다(예습 10편 · 항목 185개). 그 폭이면 문턱을
고르는 것이 답을 고르는 것이라, `must_id` 가 없는 편에서는 **아무 값도 내지 않는다.**

그리고 **슬라이드 커버리지는 여기서 재지 않는다.** 예습은 강의록을 다 훑는 덱이 아니라
중요한 것만 가져가는 덱이다 — 카드가 안 닿은 슬라이드가 있는 것은 결함이 아니다.
"""

import argparse
import json

import pytest

from quizgen.prequiz.run import Runner, load_must, stamp_must_ids
from quizgen.prequiz.schema import MIN_CARDS
from quizgen.prequiz.validate import validate
from quizgen.runbase import Failed


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


def _item(id_, item, cards=1, reason="vocabulary"):
    return {"id": id_, "item": item, "reason": reason, "why": "모르면 막힌다",
            "slides": [1], "cards": cards}


def _run(cards, items=None):
    raw = {"cards": cards}
    if items is not None:
        raw["must_know"] = {"items": items}
    return validate(raw, _prep(), None)


# ── 승인이 id 를 찍는다 ────────────────────────────────────────────

def test_승인할_때_항목에_id를_찍는다():
    must = {"items": [_item(None, "a"), _item(None, "b")]}
    stamp_must_ids(must)
    assert [it["id"] for it in must["items"]] == ["m01", "m02"]


def test_두_번_찍어도_안_바뀐다():
    """다시 승인해도 이미 나간 카드의 `must_id` 가 어긋나면 안 된다."""
    must = {"items": [_item("m07", "a"), _item(None, "b")]}
    stamp_must_ids(must)
    stamp_must_ids(must)
    assert [it["id"] for it in must["items"]] == ["m07", "m02"]


# ── 끈이 있으면 사실로 센다 ────────────────────────────────────────

def test_카드가_안_간_항목을_센다():
    items = [_item("m01", "용어 A"), _item("m02", "용어 B")]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)
    assert s["coverage"]["method"] == "must_id"
    assert s["coverage"]["objectives_without_card"] == ["용어 B"]


def test_배정한_수와_다르면_적어_둔다():
    """항목마다 `cards` 가 계약인데, 여태 편별 합계만 맞으면 통과였다."""
    items = [_item("m01", "용어 A", cards=3)]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)
    mism = s["coverage"]["cards_per_item_mismatch"]
    assert [(m["id"], m["assigned"], m["made"]) for m in mism] == [("m01", 3, MIN_CARDS)]


def test_승인본에_없는_항목을_대면_표시가_붙는다():
    items = [_item("m01", "용어 A", cards=MIN_CARDS)]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS - 1)]
    cards.append(_card("계획 밖의 것", must_id="m99"))
    kept, s = _run(cards, items)
    assert len(kept) == MIN_CARDS               # 버리지 않는다. 표시만 한다
    off = [c for c in kept if "off_must" in c["review_flags"]]
    assert [c["q"] for c in off] == ["계획 밖의 것"]


def test_항목을_아예_안_적어도_표시가_붙는다():
    items = [_item("m01", "용어 A", cards=MIN_CARDS)]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS - 1)]
    cards.append(_card("어디서 왔는지 없다"))
    _, s = _run(cards, items)
    assert s["flag_counts"].get("off_must") == 1


def test_이유가_항목과_어긋나면_잡는다():
    """예전에는 항목 이름이 카드 글자에 남아 있을 때만 볼 수 있어 185항목에서 0건이었다."""
    items = [_item("m01", "용어 A", cards=MIN_CARDS, reason="spine")]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)
    assert len(s["reason_mismatch"]) == MIN_CARDS
    assert s["reason_mismatch"][0]["must"] == "spine"
    assert s["reason_mismatch"][0]["card"] == "vocabulary"


# ── 끈이 없으면 추측하지 않는다 ────────────────────────────────────

def test_must_id_가_없는_편에서는_재지_않는다():
    """옛 편이다 — 승인본에도 id 가 없다. 글자로 물러나 8%~72% 사이의 아무 값을 내느니
    안 잰다고 적는다."""
    items = [_item(None, "용어 A"), _item(None, "용어 B")]
    cards = [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)
    assert s["coverage"]["method"] == "unlinked"
    assert s["coverage"]["objectives_without_card"] == []
    assert s["flag_counts"].get("off_must") is None


def test_승인본에_id가_있는데_카드가_안_적으면_계약_위반이다():
    """이것은 「잴 것이 없다」가 아니라 **조용한 실패**다. 한 갈래로 뭉치면 그냥 지나간다."""
    items = [_item("m01", "용어 A"), _item("m02", "용어 B")]
    cards = [_card(f"질문 {i}") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)
    assert s["coverage"]["method"] == "not_written"
    assert any("must_id" in v for v in s["contract_violations"])


def test_승인본이_아예_없어도_돌아간다():
    _, s = _run([_card(f"질문 {i}") for i in range(MIN_CARDS)])
    assert s["coverage"]["must_items"] == 0
    assert s["coverage"]["method"] == "unlinked"


# ── 예습은 슬라이드를 다 훑는 덱이 아니다 ──────────────────────────

def test_슬라이드_커버리지는_내지_않는다():
    """`runner/deck.py` 가 이 키로 `untouched_slides` 를 채운다. 예습에서는 비어야 하고,
    비어 있는 것이 「빠진 슬라이드가 없다」는 뜻이 아니라 「그것을 재지 않는다」는 뜻이다."""
    items = [_item("m01", "용어 A", cards=MIN_CARDS)]
    cards = [_card(f"질문 {i}", must_id="m01") for i in range(MIN_CARDS)]
    _, s = _run(cards, items)      # 10장짜리 강의록에 카드는 전부 1번 슬라이드다
    assert "untouched_undeclared" not in s["coverage"]


# ── ① 단계 산출물을 읽는 자리 ─────────────────────────────────────

def _write(tmp_path, obj):
    p = tmp_path / "must_know.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def _must(n=8):
    """스키마가 요구하는 최소 항목 수(8)를 채운 승인 전 산출물."""
    return {"items": [_item(None, f"용어 {i}") for i in range(n)],
            "rejected_candidates": []}


def test_한_겹_감싸여_나와도_풀어서_읽는다(tmp_path):
    """2026-08-27 에 한 편이 그렇게 나왔다. 승인이 항목을 0개로 읽었고 아무도 몰랐다."""
    got = load_must(_write(tmp_path, {"must_know": _must()}))
    assert len(got["items"]) == 8


def test_스키마를_어기면_거기서_멈춘다(tmp_path):
    """통과했다는 말이 항목이 실제로 있다는 뜻이어야 한다."""
    with pytest.raises(Failed):
        load_must(_write(tmp_path, {"items": [{"item": "이유도 슬라이드도 없다"}]}))


def test_멀쩡한_것은_그대로_읽는다(tmp_path):
    obj = _must()
    assert load_must(_write(tmp_path, obj)) == obj


# ── 족보를 못 물렸을 때 ────────────────────────────────────────────

def _runner(tmp_path, **kw):
    args = argparse.Namespace(
        skip_reproduce=False, repair_rounds=2, jobs=2, model=None, force=False,
        allow_size=False, hint=None, timeout=60, deck="D::L::예습", id="pX",
        pdf=None, pdf_name="x.pdf", note=None, jokbo_dir=str(tmp_path / "없는폴더"),
        schema_dir="out/prequiz_schema", jokbo=None, stop_at_review=False,
        check_dir=str(tmp_path / "chk"), no_image_check=True)
    for k, v in kw.items():
        setattr(args, k, v)
    return Runner(tmp_path, args)


def test_족보를_못_물리면_시끄럽고_유임이라_찍지_않는다(tmp_path, capsys):
    """기본값이 `True, "미상"` 이라 여태 「유임 → reason=repeated 사용 가능」 을 찍었다."""
    (tmp_path / "prep.json").write_text(json.dumps(_prep()), encoding="utf-8")
    r = _runner(tmp_path)
    r.read_professor()
    out = capsys.readouterr().out
    assert "족보를 물리지 않았다" in out              # 조용히 넘어가지 않는다
    line = next(x for x in out.splitlines() if "담당 교수" in x)
    assert "미상" in line and "유임" not in line and "사용 가능" not in line
    assert r.slice_path is None


# ── ①과 ② 사이에서 끊겼을 때 ─────────────────────────────────────
#
# `prompt.cards.md` 는 ①의 세션이 살아 있다고 보고 "앞에서 읽은 것이 전부 그대로
# 있다"로 시작한다. 실행이 그 사이에서 끊기면 다음 프로세스의 `sid` 가 비어서
# **자료가 하나도 없는 새 세션**이 그 말을 받는다. 2026-08-31 에 `250916_03` 이
# 그렇게 돌아 카드를 한 장도 안 만들고 저장소 소스를 고치러 갔다($2.98).

def _asked(r, monkeypatch):
    seen = []
    monkeypatch.setattr(r, "agent", lambda prompt, label, **kw: seen.append(prompt))
    return seen


def test_세션이_살아_있으면_이어받는_프롬프트를_쓴다(tmp_path, monkeypatch):
    (tmp_path / "prompt.cards.md").write_text("이어받기", encoding="utf-8")
    (tmp_path / "prompt.cards_full.md").write_text("자족", encoding="utf-8")
    r = _runner(tmp_path)
    r.sid = "sess-1"
    seen = _asked(r, monkeypatch)
    r.cards()
    assert "prompt.cards.md" in seen[0] and "cards_full" not in seen[0]


def test_세션이_없으면_자료를_다시_싣는_프롬프트를_쓴다(tmp_path, monkeypatch):
    (tmp_path / "prompt.cards.md").write_text("이어받기", encoding="utf-8")
    (tmp_path / "prompt.cards_full.md").write_text("자족", encoding="utf-8")
    r = _runner(tmp_path)
    seen = _asked(r, monkeypatch)
    r.cards()
    assert "prompt.cards_full.md" in seen[0]


def test_자족적인_프롬프트가_없으면_세션을_열지_않는다(tmp_path, monkeypatch):
    """옛 폴더다. 빈 세션에 「이미 다 있다」고 말하느니 멈춘다."""
    (tmp_path / "prompt.cards.md").write_text("이어받기", encoding="utf-8")
    r = _runner(tmp_path)
    monkeypatch.setattr(r, "agent", lambda *a, **k: pytest.fail("세션을 열면 안 된다"))
    with pytest.raises(Failed):
        r.cards()


# ── 누출 수선 고리 ────────────────────────────────────────────────

def test_누출이_없으면_세션을_안_연다(tmp_path, monkeypatch):
    """검사는 결정론적이라 공짜다. 누출이 없으면 이 단계는 아무 것도 안 쓴다."""
    import quizgen.reproduce as rp
    monkeypatch.setattr(rp, "hard_leaks", lambda d: [])
    r = _runner(tmp_path)
    monkeypatch.setattr(r, "agent", lambda *a, **k: pytest.fail("세션을 열면 안 된다"))
    r.leak_repair()


def test_누출이_줄지_않으면_멈춘다(tmp_path, monkeypatch):
    """무한히 다시 쓰지 않는다 — 재현 검사가 뒤에서 다시 막는다."""
    import quizgen.reproduce as rp
    leak = [{"kind": "answer_in_front", "id": "c01", "detail": "답",
             "card": {"q": "질문", "a": "답"}, "hard": True}]
    monkeypatch.setattr(rp, "hard_leaks", lambda d: leak)
    calls = []
    r = _runner(tmp_path, repair_rounds=3)
    monkeypatch.setattr(r, "agent", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(r, "validate", lambda: None)
    monkeypatch.setattr(r, "reproduce", lambda only=None: None)
    r.leak_repair()
    assert len(calls) == 1
