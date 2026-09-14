"""한 블럭 이름을 두 과목이 나눠 쓸 때, 어디까지가 내 칸인가.

2026-2 `감염의 기초`가 그렇다 — 08-31~09-09 이 기생충학이고 09-11~09-23 이
미생물학인데 시간표 이름은 하나다. 둘 다 `_block`에 그 이름을 적어 두므로
**각자 블럭 전체를 자기 것으로 셌다.**

짝이 없어 자리가 서지는 않았다. 그런데 못 찾은 칸마다 경고가 한 줄씩 나왔고
(2026-08-31 쓸기 한 번에 93줄), 그중 한 줄이 `agent.blocked_reason`을 타고
「덱을 못 만들었다: ⚠ 기생충학/260917_01 바이러스의 증식 및 배양 — 작년 짝을 못
찾았다」로 나갔다. 누른 사람은 260831_01을 눌렀고 260917_01은 미생물학 강의다.

가르는 날은 사람이 적는다(`_block_from`·`_block_until`). 시간표가 둘을 가르는
표시를 안 들고 있어서 코드가 알아낼 자리가 아니다.
"""

import json
from pathlib import Path

from runner import ahead, filenames

# 두 과목이 나눠 쓰는 한 블럭. 이름은 셋 다 `감염의 기초`로 모인다
# (`blocks.base_name`이 뒤 번호를 뗀다).
TIMETABLE = [
    {"date": "2026-08-31", "startTime": "09:00", "title": "감염의 기초",
     "details": "기생충학 총론 (1)\n최민호", "professor": "최민호", "category": "lecture"},
    {"date": "2026-09-10", "startTime": "09:00", "title": "감염의 기초 필기시험",
     "details": "(열대의학)", "professor": "", "category": "exam"},
    {"date": "2026-09-11", "startTime": "09:00", "title": "감염의 기초 1",
     "details": "미생물학의 역사\n조남혁", "professor": "조남혁", "category": "lecture"},
    {"date": "2026-09-17", "startTime": "09:00", "title": "감염의 기초 13",
     "details": "바이러스의 증식 및 배양\n석승혁", "professor": "석승혁", "category": "lecture"},
]


def _timetable(tmp_path: Path) -> Path:
    path = tmp_path / "timetable.json"
    path.write_text(json.dumps(TIMETABLE, ensure_ascii=False), encoding="utf-8")
    return path


def _pairs(runs_dir: Path, subject: str, table: dict) -> None:
    folder = runs_dir / ahead.PAIRS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{subject}.json").write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")


def _prev(tmp_path: Path) -> list[filenames.LectureFile]:
    folder = tmp_path / "prev"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "[250915_01] 기생충학 총론1(최민호)_박영은v1.pdf").write_bytes(b"%PDF-1.4\n")
    return list(filenames.scan(folder).files)


def _plan(tmp_path: Path, subject: str, table: dict):
    runs_dir = tmp_path / "runs"
    _pairs(runs_dir, subject, table)
    return ahead.plan(subject, [], _prev(tmp_path), _timetable(tmp_path), runs_dir)


# ------------------------------------------------- 안 적으면 예전 그대로다


def test_안_적으면_블럭_전체를_본다(tmp_path):
    _, warnings = _plan(tmp_path, "기생충학", {ahead.BLOCK_KEY: "감염의 기초"})
    # 09-11·09-17은 미생물학 강의다. 자르지 않으면 여기에 대고 짝을 찾는다.
    assert any("260917_01" in line for line in warnings)


# ------------------------------------------------------------- 잘라 본다


def test_끝을_적으면_그_뒤_칸은_안_본다(tmp_path):
    seats, warnings = _plan(tmp_path, "기생충학", {
        ahead.BLOCK_KEY: "감염의 기초", ahead.UNTIL_KEY: "2026-09-10"})

    assert [seat.cell.key for seat in seats] == ["260831_01"]
    # 남의 과목 칸 이야기가 통째로 사라진다.
    assert not any("260911_01" in line or "260917_01" in line for line in warnings)
    # 대신 무엇을 안 봤는지는 한 줄로 남는다. 조용히 자르면 빠진 줄도 모른다.
    assert any("블럭을 나눠 쓴다" in line and "2칸" in line for line in warnings)


def test_시작을_적으면_그_앞_칸은_안_본다(tmp_path):
    _, warnings = _plan(tmp_path, "미생물학", {
        ahead.BLOCK_KEY: "감염의 기초", ahead.FROM_KEY: "2026-09-11"})

    assert not any("260831_01" in line for line in warnings)
    assert any("260917_01" in line for line in warnings)


def test_구간_안의_칸은_그대로_붙는다(tmp_path):
    """자르는 것이 짝 붙이는 일을 건드리면 안 된다."""
    seats, _ = _plan(tmp_path, "기생충학", {
        ahead.BLOCK_KEY: "감염의 기초", ahead.UNTIL_KEY: "2026-09-10"})
    assert seats[0].prev.path.stem.startswith("[250915_01]")


# --------------------------------------------- 못 읽는 값은 버리고 말한다


def test_날짜_꼴이_아니면_말하고_블럭_전체를_본다(tmp_path):
    _, warnings = _plan(tmp_path, "기생충학", {
        ahead.BLOCK_KEY: "감염의 기초", ahead.UNTIL_KEY: "9월 10일"})

    assert any(ahead.UNTIL_KEY in line and "YYYY-MM-DD" in line for line in warnings)
    # 조용히 죽지 않는다 — 자르기만 못 할 뿐 자리는 선다.
    assert any("260917_01" in line for line in warnings)


def test_거꾸로_적으면_말하고_블럭_전체를_본다(tmp_path):
    seats, warnings = _plan(tmp_path, "기생충학", {
        ahead.BLOCK_KEY: "감염의 기초",
        ahead.FROM_KEY: "2026-09-11", ahead.UNTIL_KEY: "2026-09-10"})

    assert any("아무 칸도 안 남는다" in line for line in warnings)
    assert [seat.cell.key for seat in seats] == ["260831_01"]


def test_구간은_짝_표가_아니다(tmp_path):
    """`_`로 시작하는 키는 짝으로 안 읽는다. 안 그러면 「해당하는 빈 칸이 없다」가 뜬다."""
    _, warnings = _plan(tmp_path, "기생충학", {
        ahead.BLOCK_KEY: "감염의 기초", ahead.UNTIL_KEY: "2026-09-10"})
    assert not any("확인해 준 짝" in line for line in warnings)
