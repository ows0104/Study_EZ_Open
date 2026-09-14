"""판이 갈렸을 때 **어느 슬라이드가** 갈렸는가.

여기서 틀리면 그 뒤가 전부 틀린다 — 카드는 `slide_no` 정수 하나로 슬라이드에 묶이므로,
짝을 잘못 지으면 **엉뚱한 카드를 지우고 멀쩡한 카드를 남긴다.**

실측에서 나온 함정 둘을 특히 지킨다.
  - `260903_05` 는 v1·v2 가 **둘 다 54쪽**인데 필기가 갈렸다. 쪽수로는 안 보인다.
  - 슬라이드가 하나 끼면 뒤가 통째로 밀린다. 번호로 맞대면 전부 「갈렸다」가 된다.
"""

from quizgen import slidediff


def page(no, text="", annotations=(), figures=()):
    return {"slide": no, "size": [960, 540], "lecture_text": text,
            "lecture_figures": list(figures), "lecture_emphasis": [],
            "annotations": [{"year": "2026", "text": t, "rect": [10, 10, 90, 30]}
                            for t in annotations],
            "markers": [], "pasted_images": [], "occlusion_candidates": [],
            "covered_by_annotation": []}


def prep(pages, source="x_v1.pdf"):
    return {"source": source, "slides": len(pages), "source_sha256": "sha",
            "pages": pages}


BODY = ["학습목표", "폐흡충의 생활사", "excyst 는 duodenum 에서 일어난다",
        "장흡충의 감별", "정리"]


def base():
    return [page(i + 1, t) for i, t in enumerate(BODY)]


# ── 안 갈렸으면 아무 말도 안 한다 ───────────────────────────────

def test_같은_판이면_갈린_슬라이드가_없다():
    d = slidediff.diff(prep(base()), prep(base()))
    assert d["changed_slides"] == []
    assert d["carry_map"] == {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
    assert d["ratio"] == 0.0


# ── 필기만 갈린 판 (쪽수가 같다) ────────────────────────────────

def test_필기만_갈려도_그_슬라이드를_잡는다():
    after = base()
    after[2] = page(3, BODY[2], annotations=["폐에서 worm capsule 을 만든다"])
    d = slidediff.diff(prep(base()), prep(after, "x_v2.pdf"))
    assert d["changed_slides"] == [3]
    assert d["pairs"][2]["changed"] == ["annotations"]
    assert "3" not in d["carry_map"]           # 이 슬라이드의 카드는 다시 쓴다
    assert d["carry_map"]["4"] == 4            # 나머지는 그대로 옮긴다


def test_본문이_고쳐지면_그_슬라이드만_갈린다():
    after = base()
    after[2] = page(3, "성충은 폐에서 worm capsule 안에 자리잡는다")
    d = slidediff.diff(prep(base()), prep(after, "x_v2.pdf"))
    assert d["changed_slides"] == [3]
    assert d["pairs"][2]["text_ratio"] < 1.0


# ── 슬라이드가 끼면 번호가 밀린다 ───────────────────────────────

def test_슬라이드가_끼면_뒤를_밀어서_짝짓는다():
    after = [page(1, BODY[0]), page(2, BODY[1]), page(3, BODY[2]),
             page(4, "새로 넣은 표: 흡충 감별"), page(5, BODY[3]), page(6, BODY[4])]
    d = slidediff.diff(prep(base()), prep(after, "x_v2.pdf"))
    assert d["added"] == [4]
    assert d["changed_slides"] == [4]                  # 새로 생긴 자리만 쓴다
    assert d["carry_map"] == {"1": 1, "2": 2, "3": 3, "4": 5, "5": 6}
    assert [(p["old"], p["new"]) for p in d["moved"]] == [(4, 5), (5, 6)]


def test_슬라이드가_빠지면_없어진_것으로_적는다():
    after = [page(1, BODY[0]), page(2, BODY[1]), page(3, BODY[3]), page(4, BODY[4])]
    d = slidediff.diff(prep(base()), prep(after, "x_v2.pdf"))
    assert d["removed"] == [3]
    assert d["carry_map"] == {"1": 1, "2": 2, "4": 3, "5": 4}


# ── 사람이 알려준 것 ────────────────────────────────────────────

def test_사람이_알려주면_코드가_못_봐도_갈린_것으로_친다():
    d = slidediff.diff(prep(base()), prep(base(), "x_v2.pdf"), hints=[3])
    assert d["changed_slides"] == [3]
    assert d["pairs"][2]["changed"] == ["hinted"]
    assert "3" not in d["carry_map"]


def test_없는_번호를_알려주면_조용히_삼키지_않는다():
    d = slidediff.diff(prep(base()), prep(base(), "x_v2.pdf"), hints=[99])
    assert d["hinted_missing"] == [99]
    assert "알려준 슬라이드" in slidediff.render(d)


# ── 본문이 없는 슬라이드 (실습 사진) ────────────────────────────

def test_한쪽에만_있는_채널은_안_맞댄다():
    """`260903_05` 에서 실제로 걸린 함정. 2026-09-03 에 `lecture_emphasis` 가 붙었는데
    그 전에 만든 `prep.json` 에는 키가 아예 없다. 그대로 대면 **강의는 그대로인데
    5장이 갈렸다**고 나온다 — 그 쌍의 진짜 갈림은 필기 2장뿐이었다."""
    before = base()
    after = base()
    for p in after:
        p["lecture_emphasis"] = [{"color": "#ff0000", "text": "강조"}]
    for p in before:
        del p["lecture_emphasis"]

    d = slidediff.diff(prep(before), prep(after, "x_v2.pdf"))
    assert d["changed_slides"] == []
    assert d["skipped_channels"] == ["lecture_emphasis"]
    assert "맞대지 않았다" in slidediff.render(d)


def test_키가_있고_비어_있는_것은_정상_비교다():
    before = base()
    after = base()
    after[1]["lecture_emphasis"] = [{"color": "#ff0000", "text": "강조"}]
    d = slidediff.diff(prep(before), prep(after, "x_v2.pdf"))
    assert d["skipped_channels"] == []
    assert d["changed_slides"] == [2]


def test_본문이_없어도_그림으로_짝짓는다():
    figs = [{"id": "fig_p02_01", "bbox": [10, 10, 400, 400], "px": [800, 800]}]
    other = [{"id": "fig_p03_01", "bbox": [20, 20, 500, 500], "px": [900, 900]}]
    before = [page(1, "표지"), page(2, "", figures=figs), page(3, "", figures=other)]
    after = [page(1, "표지"), page(2, "", figures=figs), page(3, "", figures=other)]
    d = slidediff.diff(prep(before), prep(after, "x_v2.pdf"))
    assert d["changed_slides"] == []
    assert d["carry_map"] == {"1": 1, "2": 2, "3": 3}
