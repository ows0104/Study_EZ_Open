"""사람이 편마다 족보 조각을 지정한다 — `_materials/<과목>/pins.json`.

2026-09-24 약리학에서 필요해졌다. 족보(2025판)가 항암을 `유전자 표적 항암 약리` 로
묶는데 올해 시간표는 `항대사/항호르몬 항암제` 로 가르고, 제목 대조가 그 편을
`갑상선 및 부갑상선 호르몬 약리` 에 0.33 으로 붙였다. PBL 은 족보가 없는데 `약물대사`
에 0.40 으로 붙었다. 아래 제목은 그 판의 것을 줄여 옮겼다.
"""

import json
from pathlib import Path

from quizgen.assemble import slice_for_recorded
from quizgen.pack import find_jokbo, jokbo_pin

LECTURES = [
    ("7-8", "약물대사 (1)~(2)", "L7-8_약물대사-1-2"),
    ("29", "유전자 표적 항암 약리", "L29_유전자-표적-항암-약리"),
    ("35", "갑상선 및 부갑상선 호르몬 약리", "L35_갑상선-및-부갑상선-호르몬-약리"),
]


def cut(tmp_path: Path, pins: dict | None = None) -> Path:
    subject = tmp_path / "_materials" / "약리학"
    edition = subject / "260924-1232"
    edition.mkdir(parents=True)
    lectures = []
    for key, title, file in LECTURES:
        lectures.append({"lecture_key": key, "title": title, "file": file, "may_contain": []})
        (edition / f"{file}.json").write_text(json.dumps(
            {"lecture_key": key, "title": title, "may_contain": [],
             "stats": {"repeat_rate": 0.1}, "questions": []}, ensure_ascii=False), encoding="utf-8")
    (edition / "index.json").write_text(json.dumps({"lectures": lectures}, ensure_ascii=False),
                                        encoding="utf-8")
    if pins is not None:
        (subject / "pins.json").write_text(json.dumps(pins, ensure_ascii=False), encoding="utf-8")
    return edition


def prep(stem: str) -> dict:
    return {"source": f"{stem}.pdf"}


ANTIMETABOLITE = "[261014_03]항대사, 항호르몬 항암제(가나다)_라마바v1"
PBL = "[261002_05]PBL1 맞춤약물요법 1(F-drug WS 1)_가나다"


def test_지정이_없으면_제목_대조가_틀린_조각을_붙인다(tmp_path):
    """이 파일이 왜 있는가. 지정이 없을 때의 실측 모양을 고정해 둔다."""
    edition = cut(tmp_path)
    path, score, _ = find_jokbo(prep(ANTIMETABOLITE), edition)
    assert path.name.startswith("L35_")


def test_제목으로_지정한다(tmp_path):
    edition = cut(tmp_path, {"261014_03": "유전자 표적 항암 약리"})
    path, score, top = find_jokbo(prep(ANTIMETABOLITE), edition)
    assert path == edition / "L29_유전자-표적-항암-약리.json"
    assert score == 1.0 and top[0][1]["lecture_key"] == "29"


def test_lecture_key_로도_지정한다(tmp_path):
    edition = cut(tmp_path, {"261014_03": "29"})
    path, _, _ = find_jokbo(prep(ANTIMETABOLITE), edition)
    assert path.name.startswith("L29_")


def test_null_은_족보가_없다는_뜻이다(tmp_path):
    edition = cut(tmp_path, {"261002_05": None})
    assert find_jokbo(prep(PBL), edition) == (None, 0.0, [])


def test_지정한_조각이_판에_없으면_대조로_넘어가고_말한다(tmp_path, capsys):
    edition = cut(tmp_path, {"261014_03": "대사 타겟 항암제"})
    path, _, _ = find_jokbo(prep(ANTIMETABOLITE), edition)
    assert path.name.startswith("L35_")
    assert "이 판에 없다" in capsys.readouterr().out


def test_다른_편은_지정의_영향을_안_받는다(tmp_path):
    edition = cut(tmp_path, {"261014_03": "29"})
    path, _, _ = find_jokbo(prep("[261001_01]약물대사(가나다)_라마바v1"), edition)
    assert path.name.startswith("L7-8_")


def test_지정은_판이_아니라_과목_폴더에_산다(tmp_path):
    """다시 자르면 판 폴더가 새로 선다. 거기 두면 지정이 조용히 사라진다."""
    edition = cut(tmp_path, {"261014_03": "29"})
    assert (edition.parent / "pins.json").is_file()
    assert jokbo_pin(ANTIMETABOLITE, edition) == (True, "29")


def test_기록에_지정이라고_남는다(tmp_path):
    edition = cut(tmp_path, {"261014_03": "29", "261002_05": None})
    path, _, _, rec = slice_for_recorded(prep(ANTIMETABOLITE), edition)
    assert rec["attached"] and "pins.json" in rec["by"]
    path, _, _, rec = slice_for_recorded(prep(PBL), edition)
    assert path is None and "족보가 없다" in rec["why_not"]
