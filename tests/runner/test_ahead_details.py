"""실습 칸의 강의 이름은 `details` 첫 줄에 없다.

감염의 기초 실습 6칸은 `details`가 `(MDL)`로 시작한다 — 강의실이지 강의 이름이
아니다. 그걸 `heading`으로 읽으면 어간이 `mdl`이 되어 작년 짝이 전부 0.00으로
떨어지고, `runs/_pairs/기생충학.json`이 그래서 여섯 칸을 손으로 물려 두었다.

화면은 같은 줄을 이미 빼고 있었다(`web/src/calendar/entries.ts`). 여기서 지키는
것은 **양쪽이 같은 줄을 뺀다**는 것이다.
"""

import json
from pathlib import Path

from runner import ahead

TIMETABLE = [
    # 실습 — 강의실 줄이 앞에 붙는다. 진짜 이름은 둘째 줄이다.
    {"date": "2026-08-31", "startTime": "13:00", "title": "감염의 기초 실습",
     "details": "(MDL)\n연충란\n최민호, 신은희, 여선주,\n송현범, 김주현",
     "professor": "최민호, 신은희, 여선주, 송현범, 김주현", "category": "practice"},
    # 강의 — 첫 줄이 그대로 이름이다. 여기는 달라지면 안 된다.
    {"date": "2026-08-31", "startTime": "09:00", "title": "감염의 기초",
     "details": "기생충학 총론 (1)\n최민호", "professor": "최민호", "category": "lecture"},
    # 괄호뿐인 칸. 뺄 것을 빼고 나면 아무것도 안 남는다.
    {"date": "2026-09-01", "startTime": "09:00", "title": "의료윤리학의 기본개념",
     "details": "(09:10~11:50)", "professor": "", "category": "lecture"},
]


def _timetable(tmp_path: Path) -> Path:
    path = tmp_path / "timetable.json"
    path.write_text(json.dumps(TIMETABLE, ensure_ascii=False), encoding="utf-8")
    return path


def _cells(tmp_path: Path) -> dict[str, ahead.Cell]:
    return {cell.key: cell for cell in ahead.read_cells(_timetable(tmp_path))}


def test_강의실_줄은_강의_이름이_아니다(tmp_path):
    cell = _cells(tmp_path)["260831_05"]

    assert cell.heading == "연충란"
    assert "(MDL)" not in cell.body
    # 어간이 여기서 나온다. `mdl`이면 작년 실습본이 하나도 안 붙는다.
    assert "mdl" not in cell.as_lecture().stem


def test_첫_줄이_이름인_칸은_그대로다(tmp_path):
    cell = _cells(tmp_path)["260831_01"]

    assert cell.heading == "기생충학 총론 (1)"
    assert cell.body == ("기생충학 총론 (1)",)


def test_뺄_것을_빼고_남는_것이_없으면_시간표_제목으로_돌아간다(tmp_path):
    cell = _cells(tmp_path)["260901_01"]

    # 빈 이름을 들고 가면 점수기가 아무 강의에나 붙는다.
    assert cell.heading == "의료윤리학의 기본개념"
    assert cell.body == ("의료윤리학의 기본개념",)
