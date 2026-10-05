"""한 해에 시험이 둘인 머리글(`2016-1`)과, 한 해 안에서 번호가 겹치는 정답표.

2026-10-05 에 약리학 2020판의 「2017」이 310문항(다른 해 100 안팎)인 것을 쫓다가 둘이
나왔다.

① 연도 머리글이 `2016-1` · `2016-2` 인 판이 있다(약리학·기생충학 2020판). 맨 `2016` 만
   받던 동안 두 회차가 앞 머리글 2017 에 붙었다.
② 정답표는 (연도, 번호)로 전역 결합하는데, 한 해 안에서 다른 강의와 번호가 겹치는 판이
   있다(약리학 2026판 70문항 · 기생충학 2026판 141문항). 나중 정답이 앞 것을 덮어 한쪽이
   남의 정답을 받았다. 바뀐 정답 중 판단할 수 있는 7개를 보니 7개 다 고친 쪽이 맞았다 —
   예: 「first pass effect 에 영향을 주지 않는 것」 ⑤ → ③ 신장 내 대사효소.
"""

import fitz

from quizgen import jokbo as J

KO = "korea-s"


def test_회차_머리글을_연도로_읽는다():
    assert J.RE_YEAR.match("2016-1") and J.RE_YEAR.match("2016 - 2") and J.RE_YEAR.match("2019")
    assert not J.RE_YEAR.match("2016-12")
    assert J.year_key(" 2016 - 1 ") == "2016-1"
    assert J.yy("2016-1") == "16" and J.yy("2025") == "25"


def test_회차_문항은_제_회차의_교수_칸을_본다():
    p = {"lecture_key": "2-4", "title": "약동학", "may_contain": [],
         "stats": {"professors_by_year": {"16": ["정재용"], "17": ["장인진"]}},
         "questions": [{"year": "2016-1", "no": "5", "stem": "가 나 다 라 마"},
                       {"year": "2017", "no": "5", "stem": "바 사 아 자 차"}]}
    new, note = J.split_by_professor(p, ["정재용"])
    assert note["own_years"] == ["2016-1"]


def _answer_doc() -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    for text in ["약동학", "2025", "99. 3", "2016-1", "5. 4",
                 "항진균 약물", "2025", "99. 2", "100. 1"]:
        page.insert_text((60, y), text, fontsize=10, fontname=KO)
        y += 20
    return doc


def test_번호가_겹치면_그_강의_머리_아래_정답을_쓴다():
    titles = J.title_aliases([("2-4", "약동학"), ("27", "항진균 약물")])
    answers = J.parse_answer_region(_answer_doc(), [0], titles)
    assert ("2025", "99") in answers.repeated
    pk = J.Question(year="2025", no="99")
    fungal = J.Question(year="2025", no="99")
    assert J.join_answer(answers, pk, "2-4")["answer"] == "3"
    assert J.join_answer(answers, fungal, "27")["answer"] == "2"


def test_한_번만_나온_번호는_전처럼_전역으로_붙는다():
    """정답 구역의 섹션 경계가 문항 구역과 어긋나도 깨지지 않던 성질을 그대로 둔다."""
    titles = J.title_aliases([("2-4", "약동학"), ("27", "항진균 약물")])
    answers = J.parse_answer_region(_answer_doc(), [0], titles)
    assert J.join_answer(answers, J.Question(year="2025", no="100"), "2-4")["answer"] == "1"
    assert J.join_answer(answers, J.Question(year="2016-1", no="5"), "27")["answer"] == "4"
