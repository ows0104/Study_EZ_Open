"""목차가 없는 족보 — 본문의 강의 머리로 강의 목록을 세운다.

약리학 2026판(2026-09-30)이 처음이었다. 목차 쪽도 교수 목록 쪽도 없이 1쪽부터
`1 약리학 소개` · `2-4 약동학` 문항이 시작한다. 목차로만 강의를 세우던 때라 **강의
0개**로 잘렸고, 그 빈 판이 `current` 가 되었다. 아래 줄들은 그 판의 조판을 줄여
옮긴 것이다 — 머리가 한 줄인 것, 번호만 한 줄인 것, 제목이 두 줄로 접힌 것,
같은 `★` 가 두 번 나오는 것.
"""

import fitz

from quizgen.jokbo import headers_as_toc, split_regions

HEADER = "약물의 이해 2026 족보"

PAGE_1 = [
    HEADER,
    "1", "약리학 소개", "2025", "시험에 출제되지 않았습니다.",
    "2-4 약동학 (1)~(3)", "2025",
    "46. 다음 중 약물의 투여 방식에 대한 설명으로 알맞지 않은 것은?",
    "① 정맥주사는 작용 시간이 빠르다.",
    "47. 생체이용률에 대한 설명으로 옳은 것은?",
    "5) Labetalol",
]
PAGE_2 = [
    HEADER,
    "25", "아미노글라이코사이드계,", "설파계/퀴놀론 항생제", "2025",
    "79. Aminoglycoside 에 대한 설명으로 옳은 것은?",
    "★ 항암 항체 치료제", "2021",
    "87. 다음 중 Cetuximab 에 대한 설명으로 옳은 것은?",
    "★ 표적 항암 약리", "2023",
    "64. 다음 중 표적항암제의 표적이 알맞게 짝지어진 것은?",
    "12",
]


def book(tmp_path, pages):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        for i, text in enumerate(lines):
            y = 40 + i * 18
            if text == "12":
                y = page.rect.height - 20           # 쪽번호 자리
            page.insert_text((40, y), text, fontsize=10, fontname="korea")
    path = tmp_path / "jokbo.pdf"
    doc.save(path)
    return fitz.open(path)


def test_본문_머리로_강의를_세운다(tmp_path):
    doc = book(tmp_path, [PAGE_1, PAGE_2, PAGE_1])
    got = headers_as_toc(doc, [0, 1])
    assert got == [
        ("1", "약리학 소개"),
        ("2-4", "약동학 (1)~(3)"),
        ("25", "아미노글라이코사이드계, 설파계/퀴놀론 항생제"),
        ("★", "항암 항체 치료제"),
        ("★2", "표적 항암 약리"),
    ]


def test_보기와_쪽번호는_머리가_아니다(tmp_path):
    """`5) Labetalol` 은 뒤에 연도가 없고, 맨 아래 `12` 는 쪽번호다."""
    doc = book(tmp_path, [PAGE_1, PAGE_2, PAGE_1])
    keys = [key for key, _ in headers_as_toc(doc, [0, 1])]
    assert "5" not in keys and "12" not in keys


def test_문항이_있는_1쪽은_표지로_버리지_않는다(tmp_path):
    doc = book(tmp_path, [PAGE_1, PAGE_2, PAGE_1])
    assert 0 in split_regions(doc)["written_q"]


def test_문항이_없는_1쪽은_여전히_표지다(tmp_path):
    doc = book(tmp_path, [[HEADER, "약물의 이해", "2025 족보"], PAGE_1, PAGE_2])
    regions = split_regions(doc)
    assert 0 not in regions["written_q"] and 0 in regions["front"]


def test_섹션을_못_잡은_판으로는_current를_안_돌린다(tmp_path):
    """2026-09-30 에 강의 0개짜리 판이 `current` 가 됐다. 지금 판을 그대로 둔다."""
    from quizgen import cutmark
    from quizgen.jokbo import main

    good = tmp_path / "좋은.pdf"
    doc = fitz.open()
    for lines in (PAGE_1, PAGE_2):
        page = doc.new_page()
        for i, text in enumerate(lines):
            page.insert_text((40, 40 + i * 18), text, fontsize=10, fontname="korea")
    doc.save(good)
    empty = tmp_path / "빈.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((40, 40), "아무 문항도 없다", fontname="korea")
    doc.save(empty)

    subject = tmp_path / "약리학"
    assert main([str(good), "-o", str(subject)]) == 0
    before = cutmark.resolve(subject).name
    assert main([str(empty), "-o", str(subject)]) == 1
    assert cutmark.resolve(subject).name == before


def test_한_칸에_이름이_넘치면_섞인_칸이다():
    """목차 표의 행이 이웃 행에 붙으면 한 해에 이름이 둘 셋 잡힌다(약리학 2026 완전판의
    10 · 28). 그 칸의 교수로 「교수 교체」를 세우면 안 된다."""
    from quizgen.jokbo import _crowded

    assert _crowded("10", {"26": ["성지혜", "성지혜"]})
    assert not _crowded("12-13", {"26": ["이철환", "이철환"]})
    assert not _crowded("7", {"26": ["조주연"], "25": ["조주연"]})
