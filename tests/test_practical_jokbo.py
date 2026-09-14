"""실습 족보는 과목 족보와 따로 돈다.

2026-09-07에 기생충학 실습 5편이 **전부 기출 0장**으로 나간 것을 찾았다. 겹이 둘이었다.

① **재료가 없었다.** `studyez jokbo` 는 올해 폴더의 PDF 한 개만 자른다. 실습 문항은
   그 안의 실습 구역(2025 회차 40문항)이 전부였고, 해마다 누적되는 별도 실습 족보
   (2023~2015 · 8회차)는 자르는 자리에 아예 안 들어왔다.
② **그 40문항마저 안 붙었다.** `find_jokbo` 는 실습 강의에 PRAC 조각만 후보로 남기는데
   `slice_for` 가 거기에 제목 일치도 문턱(0.25)을 걸고 있었다. 고를 것이 없는 자리에서
   문턱은 거부만 한다 — 기생충학 실습은 파일명이 「감염의 기초 실습 4 - 조충류」라
   「기생충학 실습」과 겹치는 글자가 "실습" 뿐이어서 매번 0.20이 나왔다.

여기서 재는 것은 그 둘과, 실습 족보가 파일 여러 권으로 흩어져 있어도 지면 이미지가
제 원본을 찾아가는가다.
"""

import json

import fitz
import pytest

from quizgen.assemble import slice_for
from quizgen.build import Jokbo
from quizgen.jokbo import parse_practical, practical_layout

# ────────────────────────────────────────────────── 실습 족보 PDF 를 지어낸다

HEAD = "감염의 기초(기생충학) {year} 땡시"
# 기본 글꼴(helv)로는 한글이 점으로 나간다 — 회차 머리글도 문항도 안 읽힌다.
KO = "korea-s"


def _page(doc, header: str, lines: list[str], figure_after: int | None = None):
    page = doc.new_page()
    y = 60
    page.insert_text((50, y), header, fontsize=9, fontname=KO)
    for i, text in enumerate(lines):
        y += 22
        page.insert_text((50, y), text, fontsize=9, fontname=KO)
        if figure_after == i:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80))
            pix.clear_with(200)
            # 40pt 미만은 `page_images` 가 장식용 세선으로 보고 뺀다
            page.insert_image(fitz.Rect(50, y + 4, 150, y + 64), pixmap=pix)
            y += 66
    return page


# 문항면은 한 쪽에 넷씩. 실물도 이 언저리다(실측 3~7개) — 정답면(21~41개)과
# 번호줄 개수로 갈리는 것이 `practical_layout` 의 판정이므로 비율을 지켜 짓는다.
PER_PAGE = 4


def _sitting(doc, year: str, n: int, answers: list[str], mixed_tail: int = 0):
    """한 회차: 문항면 여러 쪽 + 정답면 한 쪽.

    `mixed_tail` 이면 마지막 문항 몇 개를 정답면 앞머리에 남긴다 — 2016-1학기
    실물이 그렇다(33·34·35번 뒤에 그 해 정답표가 이어 붙어 있다).
    """
    head = HEAD.format(year=year)
    nos = list(range(1, n + 1 - mixed_tail))
    for i in range(0, len(nos), PER_PAGE):
        body: list[str] = []
        for no in nos[i:i + PER_PAGE]:
            body += [f"{no}. {year}년 {no}번 문항이다.", "① 가나", "② 다라"]
        _page(doc, head, body, figure_after=0 if i == 0 else None)

    tail = [f"{no}. 정답면 앞머리에 남은 {no}번 문항이다."
            for no in range(n + 1 - mixed_tail, n + 1)]
    tail.append(f"{year} 기생충학 실습시험")
    tail += [f"{i}. {a}" for i, a in enumerate(answers, start=1)]
    _page(doc, head, tail)


@pytest.fixture
def practical_pdf(tmp_path):
    """회차 둘. 뒤 회차는 정답이 숫자가 아니고, 정답면 앞머리에 문항이 남아 있다."""
    doc = fitz.open()
    _sitting(doc, "2023", 20, [str((i % 4) + 1) for i in range(20)])
    _sitting(doc, "2015", 20, ["가나다라"[i % 4] for i in range(20)], mixed_tail=2)
    path = tmp_path / "실습족보.pdf"
    doc.save(path)
    doc.close()
    return path


# ────────────────────────────────────────────────────────────── 여러 회차 절단


def test_회차를_머리글로_가르고_각_회차의_정답면을_따로_찾는다(practical_pdf):
    doc = fitz.open(practical_pdf)
    rows = practical_layout(doc)
    doc.close()
    assert [r["year"] for r in rows] == ["2023"] * 6 + ["2015"] * 6
    # 첫 정답면 뒤를 전부 정답으로 보면 두 번째 회차의 문항이 통째로 삼켜진다.
    assert [r["answers"] for r in rows] == [False] * 5 + [True] + [False] * 5 + [True]


def test_두_회차의_문항과_정답이_각각_제_회차로_붙는다(practical_pdf):
    doc = fitz.open(practical_pdf)
    qs, _ = parse_practical(doc, "기생충학 실습")
    doc.close()

    years = {y: [q for q in qs if q.year == y] for y in ("2023", "2015")}
    assert len(years["2023"]) == 20
    assert {q.no for q in years["2023"]} == {str(i) for i in range(1, 21)}
    assert years["2023"][0].answer == "1"
    # 정답이 숫자가 아닌 해가 있다. 필기 족보용 `RE_ANSWER` 는 숫자만 받아 여기서 빈다.
    assert years["2015"][0].answer == "가"


def test_정답면_앞머리에_남은_문항을_잃지_않는다(practical_pdf):
    """2016-1학기 실물이 그렇다 — 33·34·35번 뒤에 그 해 정답표가 이어 붙어 있다."""
    doc = fitz.open(practical_pdf)
    qs, _ = parse_practical(doc, "기생충학 실습")
    doc.close()
    late = [q for q in qs if q.year == "2015" and q.no in ("19", "20")]
    assert len(late) == 2
    assert all("정답면 앞머리에 남은" in q.stem for q in late)


def test_머리글과_회차표제가_문항_본문에_붙지_않는다(practical_pdf):
    doc = fitz.open(practical_pdf)
    qs, _ = parse_practical(doc, "기생충학 실습")
    doc.close()
    assert not [q for q in qs if "땡시" in q.stem or "실습시험" in q.stem]


def test_그림이_그_쪽_문항에_붙는다(practical_pdf):
    doc = fitz.open(practical_pdf)
    qs, _ = parse_practical(doc, "기생충학 실습")
    doc.close()
    assert [q for q in qs if q.figures]


# ────────────────────────────────────────────────────── 실습은 문턱을 안 본다


def _jokbo_dir(tmp_path, entries: list[dict]) -> object:
    d = tmp_path / "_jokbo"
    d.mkdir(exist_ok=True)
    (d / "index.json").write_text(
        json.dumps({"source": "족보.pdf", "lectures": entries}, ensure_ascii=False),
        encoding="utf-8")
    for e in entries:
        (d / f"{e['file']}.json").write_text(
            json.dumps({"lecture_key": e["lecture_key"], "title": e["title"],
                        "stats": {"n_questions": e["n_questions"]}, "questions": []},
                       ensure_ascii=False),
            encoding="utf-8")
    return d


PRAC_ENTRY = {"lecture_key": "PRAC", "title": "기생충학 실습",
              "file": "LPRAC_기생충학-실습", "n_questions": 277}
LECTURE_ENTRY = {"lecture_key": "3", "title": "장내 선충증",
                 "file": "L3_장내-선충증", "n_questions": 17}


def test_실습_강의는_제목이_안_겹쳐도_실습_조각을_문다(tmp_path, capsys):
    """실물 값이다 — 「감염의 기초 실습 4 - 조충류」 대 「기생충학 실습」이 0.20이다."""
    d = _jokbo_dir(tmp_path, [PRAC_ENTRY, LECTURE_ENTRY])
    prep = {"source": "[260904_05] 감염의 기초 실습 4 - 조충류(송현범)_양서현 v1.pdf"}
    path, stats, mixed = slice_for(prep, d)
    assert path is not None and path.name == "LPRAC_기생충학-실습.json"
    assert stats["n_questions"] == 277
    assert "문턱을 안 본다" in capsys.readouterr().out


def test_실습이_아닌_강의는_문턱이_그대로다(tmp_path, capsys):
    d = _jokbo_dir(tmp_path, [PRAC_ENTRY, LECTURE_ENTRY])
    prep = {"source": "[260907_09] 아무 상관 없는 제목(아무개)_v1.pdf"}
    path, _, _ = slice_for(prep, d)
    assert path is None
    assert "못 찾았다" in capsys.readouterr().out


# ──────────────────────────────────────────── 조각이 자기 원본을 들고 다닌다


def _two_page_pdf(path, words: list[str]):
    doc = fitz.open()
    for w in words:
        doc.new_page().insert_text((50, 60), w, fontsize=12)
    doc.save(path)
    doc.close()


def test_문항마다_다른_원본에서_지면을_뜬다(tmp_path):
    """실습 족보는 회차가 여러 권에 흩어져 있다. 한 조각이 PDF 하나를 가리키던
    규칙 그대로 두면 뒷면 지면 이미지가 남의 책에서 나온다."""
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _two_page_pdf(a, ["A1", "A2"])
    _two_page_pdf(b, ["B1", "B2"])
    slice_path = tmp_path / "LPRAC.json"
    slice_path.write_text(json.dumps({
        "lecture_key": "PRAC", "title": "실습",
        "sources": [{"name": "a.pdf", "path": str(a), "pages": 2},
                    {"name": "b.pdf", "path": str(b), "pages": 2}],
        "questions": [
            {"year": "2025", "no": "1", "stem": "가", "options": [], "answer": "1",
             "objection": None, "pages": [2], "figures": [], "src": 0},
            {"year": "2015", "no": "1", "stem": "나", "options": [], "answer": "가",
             "objection": None, "pages": [2], "figures": [], "src": 1},
        ]}, ensure_ascii=False), encoding="utf-8")

    jk = Jokbo(slice_path, None, "ptest", tmp_path / "media")
    assert jk.has_pages()
    _, img_a = jk.block({"year": "2025", "no": "1"})
    _, img_b = jk.block({"year": "2015", "no": "1"})
    # 쪽 번호가 같아도 파일이 갈려야 한다
    assert "ptest_jokbo_s0p002.png" in img_a
    assert "ptest_jokbo_s1p002.png" in img_b
    assert len(jk.files) == 2


def test_과목_족보_한_권이면_이미지_이름이_그대로다(tmp_path):
    """이미 나간 덱과 어긋나지 않게, `src` 가 없는 문항의 이름은 안 바꾼다."""
    pdf = tmp_path / "족보.pdf"
    _two_page_pdf(pdf, ["P1", "P2"])
    slice_path = tmp_path / "L3.json"
    slice_path.write_text(json.dumps({
        "lecture_key": "3", "title": "장내 선충증",
        "questions": [{"year": "2025", "no": "1", "stem": "가", "options": [],
                       "answer": "1", "objection": None, "pages": [1], "figures": []}],
    }, ensure_ascii=False), encoding="utf-8")

    jk = Jokbo(slice_path, pdf, "ptest", tmp_path / "media")
    _, img = jk.block({"year": "2025", "no": "1"})
    assert "ptest_jokbo_p001.png" in img


# ─────────────────────────────────────── 다음 절단이 조용히 되돌아가지 않는다


def _index_with_sources(tmp_path, sources: list[dict]):
    d = tmp_path / "_jokbo"
    d.mkdir(exist_ok=True)
    (d / "index.json").write_text(
        json.dumps({"source": "족보.pdf", "lectures": [], "practical_sources": sources},
                   ensure_ascii=False), encoding="utf-8")
    return d / "index.json"


def test_지난번_실습_족보를_되살린다(tmp_path):
    from studyez.__main__ import remembered_practical

    pdf = tmp_path / "실습.pdf"
    _two_page_pdf(pdf, ["A"])
    index = _index_with_sources(tmp_path, [{"name": pdf.name, "path": str(pdf), "pages": 1}])
    found, lost = remembered_practical(index)
    assert [p.name for p in found] == ["실습.pdf"]
    assert lost == []


def test_지난번_실습_족보가_사라졌으면_이름을_돌려준다(tmp_path):
    from studyez.__main__ import remembered_practical

    index = _index_with_sources(
        tmp_path, [{"name": "없어진.pdf", "path": str(tmp_path / "없어진.pdf"), "pages": 1}])
    found, lost = remembered_practical(index)
    assert found == []
    assert lost == ["없어진.pdf"]


# ───────────────────────────── 인용 연도와 회차 이름이 한 겹 다른 자리


def test_2016이라_적힌_인용이_2016_1_회차를_찾아간다():
    from quizgen.schema import resolve_jokbo_key

    keys = {("2016-1", "7"), ("2015", "7"), ("2023", "7")}
    assert resolve_jokbo_key("2016", "7", keys) == ("2016-1", "7")
    assert resolve_jokbo_key("2015", "7", keys) == ("2015", "7")
    assert resolve_jokbo_key("2019", "7", keys) is None


def test_같은_해에_회차가_둘이면_고르지_않는다():
    """`2016-1`·`2016-2` 가 둘 다 그 번호를 들면 어느 쪽인지 알 수 없다.
    아무거나 집으면 남의 문항이 뒷면에 붙는다."""
    from quizgen.schema import resolve_jokbo_key

    keys = {("2016-1", "7"), ("2016-2", "7")}
    assert resolve_jokbo_key("2016", "7", keys) is None


def test_회차_이름이_갈려도_지면_이미지가_붙는다(tmp_path):
    pdf = tmp_path / "실습.pdf"
    _two_page_pdf(pdf, ["P1", "P2"])
    slice_path = tmp_path / "LPRAC.json"
    slice_path.write_text(json.dumps({
        "lecture_key": "PRAC", "title": "실습",
        "sources": [{"name": "실습.pdf", "path": str(pdf), "pages": 2}],
        "questions": [{"year": "2016-1", "no": "7", "stem": "가", "options": [],
                       "answer": "3", "objection": None, "pages": [2],
                       "figures": [], "src": 0}],
    }, ensure_ascii=False), encoding="utf-8")

    jk = Jokbo(slice_path, None, "ptest", tmp_path / "media")
    text, img = jk.block({"year": "2016", "no": "7"})
    assert "기출 2016-7 원문" in text
    assert "ptest_jokbo_s0p002.png" in img
