"""블럭 첫날, 올해 필기가 0편일 때 과목을 어떻게 찾는가.

`ahead`는 원래 **올해 필기가 앉은 칸의 블럭 이름**에서 과목의 시간표 이름을 읽는다.
그 방법은 블럭 첫날 아침에 반드시 실패한다 — 그날은 올해 필기가 한 편도 없다.
2026-08-30에 기생충학이 그랬고(`publish 기생충학` → "올릴 것이 없다"), 그 상태로는
작년 강의록이 캘린더에 안 올라가 예습이 통째로 하루 늦는다.

그래서 `_pairs/<과목>.json`에 사람이 시간표 이름을 적어 둘 수 있게 했다. 여기서
지키는 것은 그 줄의 **범위**다 — 첫날을 메우되, 필기가 앉은 뒤에는 물러난다.
적어 둔 것이 사실을 이기면, 사람이 한 번 잘못 적은 것이 학기 내내 남는다.
"""

import json
from pathlib import Path

from runner import ahead, filenames

TIMETABLE = [
    # 기생충학 — 블럭 첫날. 올해 필기가 아직 없는 칸이다.
    {"date": "2026-08-31", "startTime": "09:00", "title": "감염의 기초",
     "details": "기생충학 총론 (1)\n최민호", "professor": "최민호", "category": "lecture"},
    # 다른 블럭의 칸. `_block`을 적어도 여기까지 끌려오면 안 된다.
    {"date": "2026-10-01", "startTime": "09:00", "title": "약물의 이해 1",
     "details": "약동학\n유경상", "professor": "유경상", "category": "lecture"},
]


def _timetable(tmp_path: Path) -> Path:
    path = tmp_path / "timetable.json"
    path.write_text(json.dumps(TIMETABLE, ensure_ascii=False), encoding="utf-8")
    return path


def _notes(folder: Path, names: list[str]) -> list[filenames.LectureFile]:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"%PDF-1.4\n")
    return list(filenames.scan(folder).files)


def _pairs(runs_dir: Path, subject: str, table: dict) -> None:
    folder = runs_dir / ahead.PAIRS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{subject}.json").write_text(
        json.dumps(table, ensure_ascii=False), encoding="utf-8")


def _prev(tmp_path: Path) -> list[filenames.LectureFile]:
    return _notes(tmp_path / "prev", ["[250915_01] 기생충학 총론1(최민호)_박영은v1.pdf"])


# ----------------------------------------------------- 적어 둔 것이 없으면 안 세운다

def test_올해_필기도_적어_둔_이름도_없으면_자리를_세우지_않는다(tmp_path):
    seats, warnings = ahead.plan(
        "기생충학", [], _prev(tmp_path), _timetable(tmp_path), tmp_path / "runs")

    assert seats == []
    # 왜 못 세웠는지와 어디에 적으면 되는지가 같이 나와야 한다. 이 말이 없으면
    # 사람은 자기 과목이 빠진 줄도 모른다.
    assert len(warnings) == 1
    assert "_pairs/기생충학.json" in warnings[0]
    assert ahead.BLOCK_KEY in warnings[0]


# ------------------------------------------------------------- 첫날을 메운다

def test_적어_둔_시간표_이름으로_첫날_자리를_세운다(tmp_path):
    runs_dir = tmp_path / "runs"
    _pairs(runs_dir, "기생충학", {ahead.BLOCK_KEY: "감염의 기초"})

    seats, warnings = ahead.plan(
        "기생충학", [], _prev(tmp_path), _timetable(tmp_path), runs_dir)

    assert [seat.cell.key for seat in seats] == ["260831_01"]
    assert seats[0].prev.path.stem.startswith("[250915_01]")
    # 조용히 쓰면 안 된다 — 사람이 적어 둔 것으로 돌고 있다는 사실이 보여야 한다.
    assert any("감염의 기초" in line for line in warnings)


def test_적어_둔_이름은_그_블럭_밖의_칸을_끌어오지_않는다(tmp_path):
    runs_dir = tmp_path / "runs"
    _pairs(runs_dir, "기생충학", {ahead.BLOCK_KEY: "감염의 기초"})

    seats, _ = ahead.plan(
        "기생충학", [], _prev(tmp_path), _timetable(tmp_path), runs_dir)

    assert "261001_01" not in {seat.cell.key for seat in seats}


# --------------------------------------------------- 필기가 앉으면 물러난다

def test_올해_필기가_앉으면_적어_둔_이름보다_그쪽이_이긴다(tmp_path):
    """사람이 잘못 적어 두어도 학기 내내 남지 않아야 한다."""
    runs_dir = tmp_path / "runs"
    # 일부러 틀리게 적는다 — 이 과목의 진짜 칸은 `약물의 이해`인 상황.
    _pairs(runs_dir, "기생충학", {ahead.BLOCK_KEY: "감염의 기초"})
    this_files = _notes(tmp_path / "this", ["[261001_01] 약동학(유경상)_홍길동v1.pdf"])

    seats, warnings = ahead.plan(
        "기생충학", this_files, _prev(tmp_path), _timetable(tmp_path), runs_dir)

    # 필기가 `약물의 이해` 칸에 앉았으므로 이 과목의 이름은 그것이다.
    # 적어 둔 「감염의 기초」의 08-31 칸은 더 이상 이 과목의 자리가 아니다.
    assert "260831_01" not in {seat.cell.key for seat in seats}
    assert not any(ahead.BLOCK_KEY in line for line in warnings)
