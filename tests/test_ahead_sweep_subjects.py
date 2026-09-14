"""러너의 쓸기가 볼 과목을 시간표에서 푼다.

이 자리가 생긴 이유는 실패 하나다 — 예약 작업에 `-Subject 병리학` 이 **박혀 있었고**
블럭이 바뀌어도 아무도 안 바꿨다. 2026-08-30 에 병리학 블럭은 이틀 전에 끝났는데
러너는 여전히 병리학만 쓸고 있었고, 그날 열리는 기생충학은 쓸기 밖이었다.

사람이 매 블럭 손으로 바꾸는 자리는 언젠가 잊힌다. 그래서 **매 회차 시간표에 다시
물어본다.** 여기서 지키는 것은 그 약속이다 — 블럭이 넘어가면 과목도 넘어간다.
"""

import json
from pathlib import Path

from runner import ahead

# 블럭 둘. 이름도 과목 폴더도 다르다.
TIMETABLE = [
    {"date": "2026-08-12", "startTime": "09:00", "title": "질병의 병리학적 이해 1",
     "details": "병리학 소개\n정경천", "professor": "정경천", "category": "lecture"},
    {"date": "2026-08-13", "startTime": "09:00", "title": "질병의 병리학적 이해 2",
     "details": "세포의 손상\n고지원", "professor": "고지원", "category": "lecture"},
    {"date": "2026-08-14", "startTime": "09:00", "title": "질병의 병리학적 이해 시험",
     "details": "", "professor": "", "category": "exam"},
    # 한 이름 아래 두 과목이 서는 블럭 (기생충학 ~09-01, 미생물학 그 뒤).
    {"date": "2026-08-31", "startTime": "09:00", "title": "감염의 기초",
     "details": "기생충학 총론\n최민호", "professor": "최민호", "category": "lecture"},
    {"date": "2026-09-01", "startTime": "09:00", "title": "감염의 기초 1",
     "details": "미생물학의 역사\n조남혁", "professor": "조남혁", "category": "lecture"},
]


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    """자료 폴더·산출물 폴더·시간표를 세운다."""
    root, runs = tmp_path / "drive", tmp_path / "runs"
    for subject in ("병리학", "기생충학", "미생물학"):
        (root / subject / "필기" / "2026").mkdir(parents=True)
    # 병리학만 올해 필기가 있다. 나머지 둘은 블럭 첫날이라 비어 있다.
    (root / "병리학" / "필기" / "2026" / "[260812_01] 병리학 소개(정경천)_홍길동v1.pdf"
     ).write_bytes(b"%PDF-1.4\n")

    pairs = runs / ahead.PAIRS_DIR
    pairs.mkdir(parents=True)
    for subject in ("기생충학", "미생물학"):
        (pairs / f"{subject}.json").write_text(
            json.dumps({ahead.BLOCK_KEY: "감염의 기초"}, ensure_ascii=False), encoding="utf-8")

    table = tmp_path / "timetable.json"
    table.write_text(json.dumps(TIMETABLE, ensure_ascii=False), encoding="utf-8")
    return root, runs, table


def _pick(tmp_path: Path, day: str) -> list[str]:
    from datetime import date as Date
    root, runs, table = _world(tmp_path)
    picked, _ = ahead.subjects_in_block(root, "2026", runs, Date.fromisoformat(day), table)
    return picked


# ------------------------------------------------------ 블럭이 바뀌면 과목이 바뀐다

def test_병리학_블럭에는_병리학만_쓴다(tmp_path):
    assert _pick(tmp_path, "2026-08-12") == ["병리학"]


def test_다음_블럭이_서면_과목이_통째로_넘어간다(tmp_path):
    """시험이 끝나고 다음 블럭이 열리면 아무도 안 건드려도 바뀐다."""
    assert _pick(tmp_path, "2026-08-31") == ["기생충학", "미생물학"]


def test_블럭이_끝난_직후에는_직전_블럭으로_물러난다(tmp_path):
    """늦게 올라온 필기를 잃지 않으려는 것이다 (`blocks.current`)."""
    assert _pick(tmp_path, "2026-08-20") == ["병리학"]


# ------------------------------------------- 올해 필기가 없어도 적어 둔 이름으로 잡는다

def test_올해_필기가_없어도_적어_둔_이름으로_잡힌다(tmp_path):
    """블럭 첫날 두 과목 다 필기가 0편이다. `_block` 이 없으면 둘 다 못 찾는다."""
    root, runs, table = _world(tmp_path)
    (runs / ahead.PAIRS_DIR / "미생물학.json").unlink()

    from datetime import date as Date
    picked, _ = ahead.subjects_in_block(root, "2026", runs, Date(2026, 8, 31), table)
    assert picked == ["기생충학"]


# ------------------------------------------------------------- 못 풀면 말한다

def test_어느_블럭에도_안_들면_빈_목록과_이유를_준다(tmp_path):
    """빈 목록을 받은 러너는 `--all` 로 물러난다. 조용히 아무것도 안 하면 안 된다."""
    root, runs, table = _world(tmp_path)

    from datetime import date as Date
    picked, note = ahead.subjects_in_block(root, "2026", runs, Date(2020, 1, 1), table)
    assert picked == []
    assert "블럭" in note
