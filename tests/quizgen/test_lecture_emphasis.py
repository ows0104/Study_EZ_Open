"""강의록 자체의 글자색을 어떻게 읽는가.

여기 박아 두는 것은 **측정으로 고른 두 축**이다(2026-09-03, 강의록 12편).

- 본문색은 글자 크기가 아니라 **가장 많이 쓰인 색**으로 정한다. 크기로 찾으려던 판은
  작은 참조 텍스트가 많은 편에서 무너졌다(한 편이 본문 6pt 로 잡혀 유채색 전부가
  '제목급 100%' 가 됐다).
- 제외하는 것은 **쪽마다 같은 자리에 반복되는 템플릿** 하나뿐이다. 「이 색은 제목색」을
  색 단위로 판정하려던 판은 머리글과 강조를 겸하는 색에서 안 갈렸고(y 사분위폭 0.36),
  상단 비율 0.69 가 문턱 0.70 에 걸려 데이터 한 점에 문턱이 붙었다.
"""

import fitz
import pytest

from quizgen.prep import build_palette, emphasis_of, emphasis_text

BLACK, RED, BLUE, GRAY = (0, 0, 0), (1, 0, 0), (0, 0, 1), (0.5, 0.5, 0.5)
FILLER = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def page_with(doc, lines):
    """lines: [(y, text, color)] — 한 쪽을 그린다. 줄마다 따로 찍힌다."""
    pg = doc.new_page(width=400, height=300)
    for y, text, color in lines:
        pg.insert_text((40, y), text, fontsize=11, color=color)
    return pg


def texts(page, palette):
    return [e["text"] for e in emphasis_of(page, palette)]


def test_본문색은_가장_많이_쓰인_색이다():
    doc = fitz.open()
    page_with(doc, [(100, FILLER, BLACK), (130, "IMPORTANT", RED)])
    pal = build_palette(doc)
    assert pal["body_color"] == 0x000000
    assert texts(doc[0], pal) == ["IMPORTANT"]


def test_본문이_유채색이면_그것이_본문색이다():
    """검정을 본문으로 못 박지 않는다. 온통 파란 강의록도 있다."""
    doc = fitz.open()
    page_with(doc, [(100, FILLER, BLUE), (130, "IMPORTANT", RED)])
    pal = build_palette(doc)
    assert pal["body_color"] == 0x0000ff
    assert texts(doc[0], pal) == ["IMPORTANT"]


def test_회색은_강조가_아니다():
    """각주·출처는 강조가 아니라 약화다. 흰 글자도 색 띠 위의 제목이지 강조가 아니다."""
    doc = fitz.open()
    page_with(doc, [(100, FILLER, BLACK),
                    (130, "N Engl J Med 2016", GRAY),
                    (160, "IMPORTANT", RED)])
    pal = build_palette(doc)
    assert texts(doc[0], pal) == ["IMPORTANT"]


def test_쪽마다_같은_자리에_반복되면_템플릿이다():
    """머리글은 자리가 고정이고 강조는 옮겨 다닌다."""
    doc = fitz.open()
    for i in range(10):
        page_with(doc, [(40, "RUNNING HEAD", BLUE),
                        (150, FILLER, BLACK),
                        (170 + i * 8, f"emphasis {i}", RED)])
    pal = build_palette(doc)
    assert [c for c, _ in pal["template_slots"]] == [0x0000ff]
    assert 0x0000ff not in pal["colors"]
    assert texts(doc[0], pal) == ["emphasis 0"]


def test_자리가_흩어지면_템플릿이_아니다():
    doc = fitz.open()
    for i in range(10):
        page_with(doc, [(150, FILLER, BLACK), (60 + i * 20, "look here", RED)])
    pal = build_palette(doc)
    assert not pal["template_slots"]
    assert texts(doc[0], pal) == ["look here"]


def test_자리가_고정된_강조는_같이_날아간다():
    """알고 감수하는 대가다 — 반복만으로 판정하니 자리가 고정된 강조도 템플릿이 된다.

    실측 12편에서는 11편이 제외 0건이었다(발동한 한 편은 84쪽 중 63쪽짜리 머리글).
    실제 강의록의 강조는 옮겨 다니기 때문인데, 이 시험은 그 전제가 깨지는 자리를
    적어 둔 것이다. 여기를 고치려거든 먼저 편을 더 세어라.
    """
    doc = fitz.open()
    for _ in range(10):
        page_with(doc, [(150, FILLER, BLACK), (180, "always here", RED)])
    pal = build_palette(doc)
    assert texts(doc[0], pal) == []


def test_같은_줄에_본문색이_있으면_inline이다():
    """검은 본문 사이에 낀 색이 가장 센 신호다 — 진짜 강조는 문장 속에 있다."""
    doc = fitz.open()
    pg = doc.new_page(width=400, height=300)
    pg.insert_htmlbox(fitz.Rect(20, 60, 380, 120),
                      'The host is <span style="color:#ff0000">a second host</span> here.')
    pg.insert_text((40, 200), FILLER, fontsize=11, color=BLACK)
    pal = build_palette(doc)
    assert [(e["text"], e["inline"]) for e in emphasis_of(pg, pal)] == [("a second host", True)]


def test_줄_전체가_한_색이면_inline이_아니다():
    doc = fitz.open()
    page_with(doc, [(100, FILLER, BLACK), (130, "WHOLE LINE", RED)])
    pal = build_palette(doc)
    assert [e["inline"] for e in emphasis_of(doc[0], pal)] == [False]


@pytest.mark.parametrize("raw, want", [
    ("• Albumin", "Albumin"),
    ("- Chitin layer", "Chitin layer"),
    ("▪ Lipid", "Lipid"),
    ("Albumin", "Albumin"),
])
def test_앞에_붙은_글머리표는_벗긴다(raw, want):
    assert emphasis_text(raw) == want


@pytest.mark.parametrize("raw", ["•", "1)", "-", "▪▪", "  ", ""])
def test_기호만인_조각은_강조가_아니다(raw):
    assert emphasis_text(raw) == ""


def test_강의록에_유채색이_없으면_빈_채널이다():
    doc = fitz.open()
    page_with(doc, [(100, FILLER, BLACK)])
    pal = build_palette(doc)
    assert pal["colors"] == {}
    assert emphasis_of(doc[0], pal) == []


def test_빈_문서에서_죽지_않는다():
    doc = fitz.open()
    doc.new_page(width=400, height=300)
    pal = build_palette(doc)
    assert pal["body_color"] is None
    assert emphasis_of(doc[0], pal) == []
