"""예습 덱의 분량 계약과, 해설이 서는 자리.

둘 다 2026-09-03 에 관리자가 짚은 것이다.
  · 문항 수가 부담된다 → 상한 30 → 20 (2026-10-04 에 다시 15)
  · 답 아래 있어야 할 해설이 **옆으로 붙는다**
"""

from __future__ import annotations

import re

from quizgen.build import CSS
from quizgen.prequiz.build import PRE_CSS
from quizgen.prequiz.schema import MAX_CARDS, MIN_CARDS, MUST_KNOW_SCHEMA


def rule(css: str, selector: str) -> str:
    """`selector { ... }` 한 덩이. 없으면 빈 문자열."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else ""


# ── 분량 ──────────────────────────────────────────────────────────

def test_10장을_기준으로_8_12장이다():
    """2026-10-06: 총 8~12문항 안에 선택 도전 1~2문항."""
    assert (MIN_CARDS, MAX_CARDS) == (8, 12)


def test_항목이_카드보다_많을_수_없다():
    """항목 하나에 카드가 최소 한 장이라, 항목 상한이 카드 상한을 넘으면 배정이
    성립하지 않는다. 25 로 굳어 있던 동안 카드 상한만 내려와 그 자리가 어긋났다."""
    assert MUST_KNOW_SCHEMA["properties"]["items"]["maxItems"] <= MAX_CARDS


def test_배정_수_설명이_계약_값을_따라간다():
    """글로 박아 두면 상한을 고칠 때 한 자리가 남는다."""
    cards = (MUST_KNOW_SCHEMA["properties"]["items"]["items"]
             ["properties"]["cards"]["description"])
    assert f"{MIN_CARDS}~{MAX_CARDS}" in cards


# ── 해설이 서는 자리 ───────────────────────────────────────────────
#
# `.a`·`.warn`·`.exam`·`.bridge` 는 안쪽 글을 왼쪽으로 세우면서 덩어리는 가운데
# 두려고 `display: inline-block` 이었다. 그러면 **이웃한 inline-block 과 같은 줄
# 상자를 나눠 쓴다** — 짧은 답 옆에 해설이 붙는다.

def test_해설은_답과_같은_줄을_안_쓴다():
    assert "inline-block" not in rule(PRE_CSS, ".bridge")
    assert "display: block" in rule(PRE_CSS, ".bridge")


def test_답과_경고도_같은_함정에_있었다():
    """`.a` 뒤에 바로 `.warn` 이 오는 복습 뒷면도 같은 자리다 (`build.TAIL`)."""
    for selector in (".a", ".warn", ".exam"):
        body = rule(CSS, selector)
        assert body, selector
        assert "inline-block" not in body, selector
        assert "display: block" in body, selector


def test_생김새는_그대로_가운데에_선다():
    """`fit-content` 가 아니면 덩어리가 카드 폭을 통째로 먹어 경계선이 늘어진다."""
    for css, selector in ((CSS, ".a"), (CSS, ".warn"), (CSS, ".exam"),
                          (PRE_CSS, ".bridge")):
        body = rule(css, selector)
        assert "fit-content" in body, selector
        assert re.search(r"margin:[^;]*\bauto\b", body), selector
