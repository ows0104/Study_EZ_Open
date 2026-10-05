"""족보는 올해 그 강의 교수가 낸 해를 앞에 둔다 · 옛 판(2020판)을 덧붙여 2015년까지 덮는다.

2026-10-05 관리자 — *"족보를 2026, 2020년꺼를 써서, 2026-2015까지를 커버할 수 있도록
하자. 그리고 이제 부터 올해 실제 강의교수가 낸 족보만을 근거로 하자."* 같은 날 고쳤다 —
*"본인 족보를 우선시하는거로. 다른 족보도 참고 정도는 해도 될듯."*

여기서 재는 것:

- 가르는 규칙(`split_by_professor`) — 그 해 칸에 올해 교수가 있으면 앞, 없거나 모르면
  뒤 「참고」. **빼지 않는다.** 옛 판 문항은 제 칸(`by`)을 따른다.
- 올해 교수를 어디서 읽는가(`lecture_professors`) — 예습 자리는 **작년 필기**로
  만들므로 파일명의 교수가 작년 교수다.
- `find_jokbo` 가 가른 조각을 돌려주고, 그 기록이 `jokbo.used.json` 에 남는가.
- 옛 판을 잇는 규칙(`merge_older`) — 번호가 아니라 목차 제목으로 잇는다.
- 교수 표의 색 글씨 메모와 다음 쪽으로 넘어간 행(`parse_toc`).
"""

import json
from pathlib import Path

import fitz

from quizgen import jokbo as J
from quizgen.assemble import slice_for_recorded
from quizgen.pack import PROFESSOR_DIR, find_jokbo, lecture_professors


def q(year: str, no: str, stem: str = "", **extra) -> dict:
    return {"year": year, "no": no, "stem": stem or f"{year}년 {no}번 문항 본문 낱말 넷 이상",
            "options": [], "answer": "1", **extra}


def payload(questions: list[dict], by_year: dict, key: str = "24-25",
            title: str = "종양의 생물학적 특성, 발암의 원인", **stats) -> dict:
    return {"lecture_key": key, "title": title, "may_contain": [],
            "stats": {"professors_by_year": by_year, "repeat_rate": 0.0, **stats},
            "questions": questions}


def own_of(new: dict) -> list[str]:
    return [x["no"] for x in new["questions"] if not x.get("reference")]


def ref_of(new: dict) -> list[str]:
    return [x["no"] for x in new["questions"] if x.get("reference")]


# ────────────────────────────────────────────────── 가르는 규칙


def test_올해_교수가_낸_해는_앞에_나머지는_참고로_뒤에_둔다():
    p = payload([q("2022", "3"), q("2025", "1"), q("2019", "4"), q("2023", "2")],
                {"25": ["강경훈"], "23": ["강경훈"], "22": ["김정호"]})
    new, note = J.split_by_professor(p, ["강경훈"])
    assert own_of(new) == ["1", "2"] and ref_of(new) == ["3", "4"]
    assert [x["no"] for x in new["questions"]] == ["1", "2", "3", "4"]   # 빼지 않는다
    assert note["own_years"] == ["2025", "2023"]
    # 표에 없는 해(2019)는 「출제자 모름」으로 참고에 간다
    assert {r["year"]: r["by"] for r in note["reference"]} == {"2022": ["김정호"], "2019": None}


def test_통계는_올해_교수의_해로만_잰다():
    p = payload([q("2023", "1"), q("2022", "2")],
                {"23": ["강경훈"], "22": ["김정호"], "25": ["김정호"], "26": ["강경훈"]},
                professor_changed_2026=True)
    new, _ = J.split_by_professor(p, ["강경훈"])
    assert new["stats"]["n_questions"] == 1 and new["stats"]["n_reference"] == 1
    assert new["stats"]["professor_changed_2026"] is False
    assert new["stats"]["professor_2026"] == ["강경훈"]
    # 앞에 둔 해와 올해만 적는다 — 참고 해의 교수를 「담당 교수」로 보이지 않게
    assert new["stats"]["professors_by_year"] == {"23": ["강경훈"], "26": ["강경훈"]}


def test_올해_교수가_낸_해가_없으면_전부_참고이고_교수_교체로_친다():
    """새로 맡은 교수. 지금까지의 「교수 교체」 지침(기출은 신호로만)이 그대로 이 경우다."""
    p = payload([q("2025", "1"), q("2023", "2")], {"25": ["박성혜"], "23": ["박성혜"]})
    new, note = J.split_by_professor(p, ["김은나"])
    assert own_of(new) == [] and ref_of(new) == ["1", "2"]
    assert new["stats"]["professor_changed_2026"] is True
    assert new["stats"]["n_questions"] == 2


def test_함께_맡은_해는_통째로_앞에_둔다():
    p = payload([q("2025", "1"), q("2025", "2")], {"25": ["고지원", "이철"]})
    new, _ = J.split_by_professor(p, ["고지원"])
    assert own_of(new) == ["1", "2"]


def test_파일명이_이름을_붙여_써도_같은_사람이다():
    p = payload([q("2025", "1")], {"25": ["문경철"]})
    new, _ = J.split_by_professor(p, ["문경철김혜령"])
    assert own_of(new) == ["1"]


def test_옛_판_문항은_제_칸을_따른다():
    """흡수된 섹션에서는 섹션의 그 해 칸이 이 문항의 출제자가 아니다."""
    p = payload([q("2018", "1", by=["문경철"]), q("2018", "2"), q("2017", "3", by=[])],
                {"18": ["정경천"], "17": ["문경철"]})
    new, note = J.split_by_professor(p, ["문경철"])
    assert own_of(new) == ["1"] and ref_of(new) == ["2", "3"]
    assert note["n_own"] == 1


def test_흡수한_섹션은_흡수된_강의의_교수도_본다():
    p = payload([q("2025", "1")], {"25": ["배정모"]},
                absorbed_professors_by_year={"25": ["박수경"]})
    new, _ = J.split_by_professor(p, ["박수경"])
    assert own_of(new) == ["1"]


def test_조각_md_는_올해_교수_해를_앞에_참고를_뒤에_싣는다():
    p = payload([q("2022", "2"), q("2025", "1")], {"25": ["강경훈"], "22": ["김정호"]})
    new, _ = J.split_by_professor(p, ["강경훈"])
    sec = J.Section(lecture_key=new["lecture_key"], title=new["title"])
    sec.questions = [J.Question(**{k: v for k, v in x.items()}) for x in new["questions"]]
    md = J.to_markdown(sec, new["stats"])
    assert "올해 교수(강경훈)가 낸 해 1문항(2025)을 앞에 두었다" in md
    assert "올해 담당 교수가 낸 문항을 우선한다" in md
    assert md.index("## 2025") < md.index("## 참고 — 올해 교수가 내지 않은 해") < md.index("## 참고 · 2022")


# ────────────────────────────────────────────────── 올해 교수를 어디서 읽나


def cut(tmp_path: Path, slices: list[dict], subject: str = "병리학") -> Path:
    edition = tmp_path / "runs" / "_materials" / subject / "261005-1200"
    edition.mkdir(parents=True)
    lectures = []
    for s in slices:
        file = J.slug(s["lecture_key"], s["title"])
        lectures.append({"lecture_key": s["lecture_key"], "title": s["title"], "file": file,
                         "may_contain": []})
        (edition / f"{file}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    (edition / "index.json").write_text(json.dumps({"lectures": lectures}, ensure_ascii=False),
                                        encoding="utf-8")
    return edition


def test_필기_파일명의_마지막_괄호가_교수다(tmp_path):
    edition = cut(tmp_path, [])
    stem = "[260812_02] 세포의 손상 및 적응(1)-세포의 손상(1)(고지원)_정현영v2"
    assert lecture_professors({"source": f"{stem}.pdf"}, edition) == (["고지원"], "필기 파일명")
    stem = "[260908_05] 감염의 기초 실습 6 - 세포내 원충, 의용곤충(2) (송현범, 김주현)"
    assert lecture_professors({"source": f"{stem}.pdf"}, edition)[0] == ["송현범", "김주현"]


def test_예습_자리는_pre_target_의_올해_교수를_쓴다(tmp_path):
    """예습은 작년 필기로 만든다. 파일명의 (유경상) 은 작년 교수다."""
    edition = cut(tmp_path, [])
    run = tmp_path / "runs" / "250926_02"
    run.mkdir(parents=True)
    (run / "pre_target.json").write_text(json.dumps(
        {"run_id": "260929_02", "professors": ["허기영"]}, ensure_ascii=False), encoding="utf-8")
    stem = "[250926_02]약동학(1) 약물의 흡수와 분포(유경상)_이승준_v1"
    names, how = lecture_professors({"source": f"{stem}.pdf"}, edition)
    assert names == ["허기영"] and "pre_target" in how


def test_pre_target_이_비었으면_작년_교수로_내려가지_않는다(tmp_path):
    edition = cut(tmp_path, [])
    run = tmp_path / "runs" / "250926_02"
    run.mkdir(parents=True)
    (run / "pre_target.json").write_text(json.dumps({"professors": []}), encoding="utf-8")
    stem = "[250926_02]약동학(1) 약물의 흡수와 분포(유경상)_이승준_v1"
    assert lecture_professors({"source": f"{stem}.pdf"}, edition)[0] == []


# ────────────────────────────────────────────────── find_jokbo 가 가른 조각을 준다

ONCO = payload([q("2025", "1"), q("2023", "2"), q("2022", "3")],
               {"25": ["이혜승"], "23": ["이혜승"], "22": ["다른이"]})
INFLAM = payload([q("2025", "9"), q("2023", "8")], {"25": ["고재문"], "23": ["정두현"]},
                 key="7", title="급성염증의 병태생리")


def test_가른_조각을_교수별_자리에_세워_돌려준다(tmp_path):
    edition = cut(tmp_path, [ONCO])
    stem = "[260825_01] 종양의 생물학적 특성, 발암의 원인(이혜승)_김솔립"
    path, score, top = find_jokbo({"source": f"{stem}.pdf"}, edition)
    assert path.parent == edition / PROFESSOR_DIR / "이혜승"
    got = json.loads(path.read_text(encoding="utf-8"))
    assert own_of(got) == ["1", "2"] and ref_of(got) == ["3"]
    # 카드를 만드는 쪽은 .md 를 읽는다(`assemble`) — 같은 자리에 같이 선다
    assert "올해 교수(이혜승)" in path.with_suffix(".md").read_text(encoding="utf-8")
    assert top[0][1]["professor_filter"]["n_own"] == 2


def test_올해_교수가_낸_해가_없어도_조각은_붙고_전부_참고다(tmp_path):
    edition = cut(tmp_path, [ONCO])
    stem = "[260825_01] 종양의 생물학적 특성, 발암의 원인(새교수)_김솔립"
    path, stats, _, rec = slice_for_recorded({"source": f"{stem}.pdf"}, edition)
    assert rec["attached"] and stats["professor_changed_2026"] is True
    assert rec["professor_filter"]["n_own"] == 0 and rec["professor_filter"]["n_reference"] == 3


def test_올해_교수를_모르면_가르지_않는다(tmp_path):
    edition = cut(tmp_path, [ONCO])
    stem = "[260825_01] 종양의 생물학적 특성, 발암의 원인_김솔립"
    path, _, _, rec = slice_for_recorded({"source": f"{stem}.pdf"}, edition)
    assert path.parent == edition
    assert "가르지 않았다" in rec["professor_filter"]["skipped"]


def test_붙은_편의_기록에도_가른_것이_남는다(tmp_path):
    edition = cut(tmp_path, [ONCO])
    stem = "[260825_01] 종양의 생물학적 특성, 발암의 원인(이혜승)_김솔립"
    _, _, _, rec = slice_for_recorded({"source": f"{stem}.pdf"}, edition)
    assert rec["attached"] and rec["professor_filter"]["own_years"] == ["2025", "2023"]


def test_제목이_엇비슷하면_올해_교수가_낸_조각을_고른다(tmp_path):
    """병리학 `종양의 병태생리(5) 발암의 원인(이혜승)` 이 「병태생리」에 끌려
    `7 급성염증의 병태생리` 에 0.50, 제 조각 24-25 에 0.46 이었다."""
    edition = cut(tmp_path, [INFLAM, ONCO])
    stem = "[260825_01] 종양의 병태생리(5) 발암의 원인(이혜승)_김솔립"
    path, score, top = find_jokbo({"source": f"{stem}.pdf"}, edition)
    assert top[0][1]["lecture_key"] == "24-25"
    assert path.name.startswith("L24-25_")


def test_실습_조각은_거르지_않는다(tmp_path):
    prac = payload([q("2025", "1")], {}, key="PRAC", title="병리학 실습")
    edition = cut(tmp_path, [prac])
    stem = "[260812_05] 질병의 병리학적 이해 실습 1-면역조직화학염색 실습 (고지원)"
    path, _, top = find_jokbo({"source": f"{stem}.pdf"}, edition)
    assert path == edition / f"{J.slug('PRAC', '병리학 실습')}.json"


# ────────────────────────────────────────────────── 옛 판 잇기


def sec(key: str, title: str, years: list[str], may_contain=()) -> J.Section:
    s = J.Section(lecture_key=key, title=title, may_contain=list(may_contain))
    s.questions = [J.Question(year=y, no=str(i), stem="문항") for i, y in enumerate(years)]
    return s


def test_번호가_아니라_제목으로_잇고_이번_판에_있는_해는_안_가져온다():
    sections = [sec("5-6", "조직 재생 및 수복 (1)~(2)", ["2025", "2020"])]
    lectures = [("5-6", "조직 재생 및 수복 (1)~(2)")]
    profs = {"5-6": {"25": ["김혜령"], "20": ["김혜령"]}}
    older = {"sections": [sec("6-7", "조직 재생 및 수복 (1)~(2)", ["2020", "2019", "2015", "unknown"])],
             "profs": {"6-7": {"20": ["김혜령"], "19": ["김혜령"], "15": ["정경천"]}}}
    report = J.merge_older(sections, lectures, profs, older, src=0)
    got = sections[0].questions
    assert sorted(x.year for x in got) == ["2015", "2019", "2020", "2025"]
    new = [x for x in got if x.src == 0]
    assert {x.year: x.by for x in new} == {"2019": ["김혜령"], "2015": ["정경천"]}
    assert profs["5-6"]["19"] == ["김혜령"] and profs["5-6"]["20"] == ["김혜령"]
    assert report["matched"][0]["took"] == 2


def test_이번_판_본문에_없는_강의는_흡수한_섹션으로_간다():
    """병리학 2026판 `4 세포의 손상 및 적응 (3)~(4)` 는 목차에만 있고 2-3 에 흡수돼 있다.
    섹션끼리만 대조하던 첫 판은 2020판의 그 강의를 2-3 에 0.64 로 붙였다 — 결과는
    같은 섹션이어도 **문항마다 제 교수(문경철)를 달아야** 거를 때 안 섞인다."""
    sections = [sec("2-3", "세포의 손상 및 적응 (1)~(2)", ["2025"],
                    may_contain=[("4", "세포의 손상 및 적응 (3)~(4)*")])]
    lectures = [("2-3", "세포의 손상 및 적응 (1)~(2)"), ("4", "세포의 손상 및 적응 (3)~(4)*")]
    older = {"sections": [sec("4-5", "세포의 손상 및 적응 (3)~(4)", ["2018"])],
             "profs": {"4-5": {"18": ["문경철"]}}}
    report = J.merge_older(sections, lectures, {}, older, src=0)
    assert report["matched"][0]["matched"] == "4"
    added = [x for x in sections[0].questions if x.src == 0]
    assert added[0].by == ["문경철"]


def test_목차에만_있고_흡수도_안_됐으면_섹션을_새로_세운다():
    sections = [sec("1", "병리학 소개", ["2025"])]
    lectures = [("1", "병리학 소개"), ("28", "건강/질병 현상의 기술")]
    older = {"sections": [sec("18", "건강/질병 현상의 기술", ["2017"])],
             "profs": {"18": {"17": ["박병주"]}}}
    J.merge_older(sections, lectures, {}, older, src=0)
    assert [s.lecture_key for s in sections] == ["1", "28"]


def test_제목이_엇비슷하면_교수가_겹치는_쪽으로_잇는다():
    sections = [sec("26", "분자면역병리 (1)", ["2025"]), sec("27", "분자면역병리 (2)", ["2025"])]
    lectures = [("26", "분자면역병리 (1)"), ("27", "분자면역병리 (2)")]
    profs = {"26": {"20": ["원재경"]}, "27": {"20": ["배정모"]}}
    older = {"sections": [sec("31", "분자면역병리 (3)", ["2018"])],
             "profs": {"31": {"18": ["배정모"], "20": ["배정모"]}}}
    report = J.merge_older(sections, lectures, profs, older, src=0)
    assert report["matched"][0]["matched"] == "27"


def test_옛_판_섹션이_다른_강의를_흡수했으면_교수가_같은_해만_안다():
    """병리학 2020판 `유전질환` 섹션에 `소아질환` 문항이 섞여 있다."""
    old = sec("12-14", "유전질환 (1)~(3)", ["2018", "2017"],
              may_contain=[("15-17", "소아질환의 병태생리 (1)~(3)")])
    old_profs = {"12-14": {"18": ["강경훈"], "17": ["김정호"]},
                 "15-17": {"18": ["박성혜"], "17": ["김정호"]}}
    assert J._older_author(old, old_profs, "18", 3) == []
    assert J._older_author(old, old_profs, "17", 3) == ["김정호"]


def test_타겟과_표적은_같은_말이다():
    assert J._title_sim("유전자 타겟 항암약리", "유전자 표적 항암 약리") == 1.0


# ────────────────────────────────────────────────── 교수 표 읽기

KO = "korea-s"
COLS = {"26": 300, "25": 360, "23": 420}


def _row(page, y, key, title, names):
    page.insert_text((60, y), key, fontsize=9, fontname=KO)
    page.insert_text((90, y), title, fontsize=9, fontname=KO)
    for (col, x), name in zip(COLS.items(), names):
        page.insert_text((x - 12, y), name, fontsize=9, fontname=KO)


def toc_doc() -> fitz.Document:
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((150, 40), "약물의 이해 교수님 목록", fontsize=12, fontname=KO)
    p.insert_text((90, 80), "수업제목", fontsize=9, fontname=KO)
    for col, x in COLS.items():
        p.insert_text((x - 6, 80), col, fontsize=9, fontname=KO)
    _row(p, 110, "9", "중추신경계 약리 기초", ["성지혜", "성지혜", "김혜선"])
    # 표 왼쪽 여백의 파란 메모. 제목 열로 들어가면 9 행이 번호를 잃는다
    p.insert_text((2, 112), "26년도 14-15강", fontsize=5, fontname=KO, color=(0, 0, 1))
    _row(p, 140, "11", "자율신경계 약리 기초", ["이철환", "이철환", "이철환"])
    # 다음 쪽 머리에 머리글 없이 이어지는 행, 그리고 표 아래 「문제 출처」 행
    q = doc.new_page()
    _row(q, 40, "35", "갑상선 및 부갑상선 호르몬 약리", ["조정현", "조정현", "조정현"])
    q.insert_text((90, 70), "문제 출처", fontsize=9, fontname=KO)
    for x in COLS.values():
        q.insert_text((x - 12, 70), "학습부", fontsize=9, fontname=KO)
    return doc


def test_색_글씨_메모를_빼고_다음_쪽까지_읽고_출처_행에서_멈춘다():
    lectures, profs, warn = J.parse_toc(toc_doc())
    assert [k for k, _ in lectures] == ["9", "11", "35"]
    assert profs["9"] == {"26": ["성지혜"], "25": ["성지혜"], "23": ["김혜선"]}
    assert profs["35"]["26"] == ["조정현"]
    assert all("학습부" not in names for cells in profs.values() for names in cells.values())
