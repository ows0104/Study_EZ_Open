"""아직 필기가 없는 강의에도 작년 필기를 붙인다.

`publish`의 계획은 **올해 필기에서** 나온다. 파일이 있어야 강의를 알기 때문이다.
그런데 예습이 필요한 쪽은 **아직 안 지나간 강의**이고, 거기엔 올해 필기가 없다.
그래서 그 자리는 계획에 아예 안 들어왔다 — 병리학 2026에서 24칸이 그랬다.

여기서는 그 자리를 **시간표에서** 찾아온다.

    올해 필기가 있는 칸    파일명이 강의를 말해 준다        → publish.plan_subject
    올해 필기가 없는 칸    시간표 칸이 강의를 말해 준다      → 여기

## 과목 이름을 어떻게 아나

시간표는 `질병의 병리학적 이해`라 부르고 폴더는 `병리학`이다. 이어 줄 표를 따로
두지 않고 **이미 붙은 것에서 읽는다** — 올해 필기가 앉은 칸의 블럭 이름이 곧 그
과목의 이름이다. 14편이 전부 한 이름을 가리키면 그것으로 나머지 칸을 찾는다.

올해 필기가 한 편도 없는 과목은 기준점이 없어서 못 찾는다. 그때는 아무것도 하지
않고 그 사실을 말한다. 추측해서 남의 과목 칸을 가져오면 캘린더가 조용히 틀린다.

## 확정만 붙인다

작년 짝은 `studyez.matching`이 고르는데, 시간표 제목과 파일명이 같은 강의를 다르게
부른다. 실측(병리학 24칸): 확정 16 · 확인 필요 7 · 짝 없음 1이었고, **눈으로 보면
24칸 모두 맞는 짝이 있었다.** 점수가 낮은 것은 대개 실습이다 —
시간표 `종양의 병리 실습(1)` ↔ 파일 `질병의 병리학적 이해 실습 7-종양의 병리 실습(1)`.

그래도 확정만 자동으로 붙인다. 틀린 강의록이 붙은 칸은 안 붙은 칸보다 나쁘다 —
학생은 그게 자기 강의인 줄 알고 읽는다. 나머지는 후보와 함께 보고하고, 사람이
확인한 짝은 `runs/_pairs/<과목>.json`에 적어 두면 다음부터 그대로 쓴다.

## 올해 필기가 이미 가져간 작년 파일은 후보가 아니다

이걸 안 빼면 8/18 실습 칸이 작년 `급성 염증의 병태 생리`를 0.75로 가져간다.
그건 8/14 강의의 짝이다. 실측에서 실제로 나온 오류다.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import blocks, filenames, matching
from .filenames import LectureFile

# 사람이 확인해 준 짝. `runs/_pairs/<과목>.json`에 `{run_id: 작년 파일 어간}`.
PAIRS_DIR = "_pairs"

# 수업이 서는 칸만. 시험·휴일·자율학습에는 붙일 자료가 없다.
TEACHING = ("lecture", "practice")


@dataclass(frozen=True)
class Cell:
    """시간표 칸 하나. 강의를 파일 대신 여기서 읽는다."""

    date: str
    slot: int
    start_time: str
    title: str            # 시간표 제목 ("질병의 병리학적 이해 7")
    heading: str          # details의 첫 줄 — 진짜 강의 이름
    professors: tuple[str, ...]
    course: str

    @property
    def key(self) -> str:
        return f"{self.date[2:4]}{self.date[5:7]}{self.date[8:10]}_{self.slot:02d}"

    def as_lecture(self) -> LectureFile:
        """파일명에서 읽은 강의와 같은 모양으로. 점수기가 이 꼴만 받는다."""
        stripped, seq, _ = filenames._split_parens(filenames.canonical(self.heading))
        if seq is None:
            trailing = filenames._TRAILING_SEQ_RE.search(stripped)
            seq = int(trailing.group(1)) if trailing else None
        return LectureFile(
            path=Path(self.heading), key=self.key, date=self.date,
            slot=self.slot, slot_end=self.slot, start_time=self.start_time,
            title=self.heading, stem=filenames._JUNK_RE.sub("", stripped), seq=seq,
            professors=self.professors, author="", version=1)


def _slot_from_time(start_time: str) -> int | None:
    """09:00부터 세고 04가 점심이라 교시는 시각 - 8이다.

    `server/app/naming.py`와 같은 규칙이다. 정각이 아닌 칸은 교시가 없어서
    `run_id`를 만들 수 없다 — 그런 칸은 붙이지 않는다.
    """
    hour, _, minute = start_time.partition(":")
    if minute.strip() != "00":
        return None
    try:
        slot = int(hour) - 8
    except ValueError:
        return None
    return slot if 1 <= slot <= 15 else None


def _professors(raw: str) -> tuple[str, ...]:
    """담당 교수. 실습 칸은 서른 명이 들어 있어 앞의 셋만 본다 — 짝을 고를 때
    가산점 용도라 전부 필요하지 않고, 전부 넣으면 어느 실습이나 다 걸린다."""
    names = [n.strip() for n in unicodedata.normalize("NFC", raw or "").split(",")]
    return tuple(n for n in names if n)[:3]


def read_cells(source: Path) -> list[Cell]:
    """시간표를 읽는다. sqlite면 표에서, `.json`이면 시드 원본에서.

    `blocks.read_events`와 같은 파일을 보지만 그쪽은 (날짜, course, category)만
    준다. 여기서는 교시와 제목까지 필요해서 따로 읽는다.
    """
    if not source.exists():
        raise FileNotFoundError(source)

    rows: list[tuple[str, str, int | None, str, str, str, str, str]] = []
    if source.suffix.lower() == ".json":
        for item in json.loads(source.read_text(encoding="utf-8")):
            start_time = str(item.get("startTime", ""))
            title = unicodedata.normalize("NFC", str(item.get("title", "")))
            rows.append((
                str(item.get("date", "")), start_time, _slot_from_time(start_time), title,
                unicodedata.normalize("NFC", str(item.get("details", ""))),
                str(item.get("professor", "")), str(item.get("category", "lecture")),
                blocks.base_name(title)))
    else:
        db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            rows = list(db.execute(
                "select date, start_time, slot, title, details, professor, category, course "
                "from timetable_event"))
        finally:
            db.close()

    cells = []
    for date, start_time, slot, title, details, professor, category, course in rows:
        if category not in TEACHING or not date or slot is None:
            continue
        lines = [line.strip() for line in (details or "").split("\n") if line.strip()]
        flat = (professor or "").replace(" ", "")
        lines = [line for line in lines if line.replace(" ", "") != flat]
        cells.append(Cell(
            date=date, slot=int(slot), start_time=start_time,
            title=unicodedata.normalize("NFC", title or ""),
            heading=unicodedata.normalize("NFC", lines[0] if lines else (title or "")),
            professors=_professors(professor), course=course or title or ""))
    return sorted(cells, key=lambda cell: (cell.date, cell.slot))


def block_names(cells: list[Cell], this_files: list[LectureFile]) -> set[str]:
    """올해 필기가 앉은 칸의 블럭 이름. 이것이 이 과목의 시간표 이름이다."""
    seats = {(f.date, f.slot) for f in this_files}
    return {blocks.base_name(cell.course) for cell in cells if (cell.date, cell.slot) in seats}


def load_pairs(runs_dir: Path, subject: str) -> dict[str, str]:
    """사람이 확인해 준 짝. `{올해 run_id: 작년 run_id 또는 파일 어간}`.

    손으로 적는 파일이라 **작년 run_id로 적는 것이 기본이다** — 파일 어간은 길고,
    Synology 파일명에 끝점(`김정빈v2.`)이나 NFD가 섞여 있어 옮겨 적기 어렵다.
    한 교시에 작년 강의가 둘이면 키로는 못 가리므로 그때만 어간으로 적는다.
    """
    path = runs_dir / PAIRS_DIR / f"{subject}.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): unicodedata.normalize("NFC", str(v)) for k, v in raw.items() if v}


@dataclass
class Seat:
    """붙일 자리 하나. 확정된 짝이 있으면 `prev`가 찬다."""

    cell: Cell
    prev: LectureFile | None
    score: float
    source: str           # 'matched' | 'confirmed' — 점수기가 골랐나, 사람이 적었나
    note: str = ""


def plan(
    subject: str,
    this_files: list[LectureFile],
    prev_files: list[LectureFile],
    timetable: Path,
    runs_dir: Path,
) -> tuple[list[Seat], list[str]]:
    """올해 필기가 없는 칸에 작년 필기를 앉힌다. (앉은 자리, 사람이 볼 말)"""
    warnings: list[str] = []
    try:
        cells = read_cells(timetable)
    except (FileNotFoundError, ValueError, sqlite3.Error) as cause:
        return [], [f"{subject}: 시간표를 읽지 못했다 ({cause}) — 예습 자리를 세우지 않는다. "
                    f"`python -m app.cli seed-timetable`을 먼저 돌리거나 --timetable으로 준다"]

    names = block_names(cells, this_files)
    if not names:
        return [], [f"{subject}: 올해 필기가 앉은 칸이 없어 시간표에서 이 과목을 못 찾는다 — "
                    f"예습 자리를 세우지 않는다"]
    if len(names) > 1:
        # 실습이 별도 블럭 이름을 갖는 등 여럿일 수 있다. 전부 쓰되 적어 둔다.
        warnings.append(f"{subject}: 시간표 이름이 {len(names)}개다 — {', '.join(sorted(names))}")

    seats = {(f.date, f.slot) for f in this_files}
    empty = [cell for cell in cells
             if blocks.base_name(cell.course) in names and (cell.date, cell.slot) not in seats]
    if not empty:
        return [], warnings

    # 올해 필기가 이미 가져간 작년 파일은 후보에서 뺀다.
    claimed = {m.prev_year.uid for m in matching.match_years(this_files, prev_files) if m.prev_year}
    free = [item for item in prev_files if item.uid not in claimed]

    confirmed = load_pairs(runs_dir, subject)
    by_stem = {item.path.stem: item for item in free}
    by_key: dict[str, LectureFile | None] = {}
    for item in free:
        # 한 교시에 작년 강의가 둘이면 키로는 못 가린다. 그런 키는 비워 둔다.
        by_key[item.key] = None if item.key in by_key else item
    taken: set[str] = set()
    planned: dict[str, Seat] = {}

    for cell in empty:
        wanted = confirmed.get(cell.key)
        if not wanted:
            continue
        item = by_key.get(wanted) or by_stem.get(wanted)
        if item is None:
            reason = ("그 교시에 작년 강의가 둘 이상이다 — 파일 어간으로 적어라"
                      if wanted in by_key else "그런 작년 필기가 없다")
            warnings.append(f"{subject}: 확인해 준 짝을 못 찾았다 — {cell.key} → {wanted[:40]} ({reason})")
            continue
        planned[cell.key] = Seat(cell=cell, prev=item, score=1.0, source="confirmed")
        taken.add(item.uid)

    # 어느 칸에도 안 걸린 줄. 교시를 잘못 적었거나 그 사이 올해 필기가 올라온
    # 것이다. 조용히 넘기면 사람은 자기가 적어 둔 짝이 붙은 줄 안다.
    # `_`로 시작하는 키는 주석 자리다.
    for key in sorted(confirmed):
        if not key.startswith("_") and key not in {cell.key for cell in empty}:
            warnings.append(f"{subject}: 확인해 준 짝 {key}에 해당하는 빈 칸이 없다 — "
                            f"교시를 잘못 적었거나 올해 필기가 이미 올라왔다")

    rest = [cell for cell in empty if cell.key not in planned]
    pool = [item for item in free if item.uid not in taken]
    for match in matching.match_years([cell.as_lecture() for cell in rest], pool):
        cell = next(c for c in rest if c.key == match.this_year.key)
        if match.confident and match.prev_year is not None:
            planned[cell.key] = Seat(cell=cell, prev=match.prev_year,
                                     score=match.score, source="matched")
            continue
        if match.prev_year is not None:
            warnings.append(
                f"{subject}/{cell.key} {cell.heading[:22]} — 작년 짝이 확정이 아니다 "
                f"({match.score:.2f}, 후보 {match.prev_year.path.stem[:40]})")
        else:
            warnings.append(f"{subject}/{cell.key} {cell.heading[:22]} — 작년 짝을 못 찾았다")

    return [planned[key] for key in sorted(planned)], warnings
