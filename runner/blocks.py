"""오늘이 어느 블럭인지 시간표에 물어본다.

`watch`가 이걸로 큐를 좁힌다. 없으면 `필기/2026` 폴더가 있는 과목을 전부 훑고
날짜 오름차순으로 자르기 때문에, 학기가 바뀌어도 지난 학기 필기가 먼저 걸린다 —
2026-08-17 밤에 실제로 조직학 3월 6편이 prep까지 갔다. 그날 올라온 병리학은
한 편도 안 잡혔다.

## 블럭을 어떻게 세우나

시간표 한 칸의 `course`는 제목에서 뒤 번호를 뗀 것이다("질병의 병리학적 이해 12"
→ "질병의 병리학적 이해"). 여기서 `실습`·`시험`·`CBL` 같은 꼬리를 더 떼면 한
블럭의 칸이 한 이름으로 모인다. 그 이름이 걸쳐 있는 최소~최대 날짜가 구간이다.

오늘을 담는 구간이 여럿이면 **칸이 가장 많은 것**을 고른다. 11월에 `감염과 면역`
(78칸, 11-02~11-26)과 `임상의학입문`(5칸, 11-03~12-01)이 겹치는데, 그 시기의
블럭은 앞의 것이고 임상의학입문은 블럭을 가로질러 얹힌 과목이다. 구간으로 거르므로
그 안에 든 임상의학입문 강의는 그대로 들어온다.

## 이 방법이 안 통하는 자리

11월 말부터 시간표 제목이 강의 단위다("발생 1~2주", "집단유전학"). 하루짜리
이름만 남아 어느 구간도 오늘을 담지 못한다. 그런 날은 `current()`가 None을 주고,
`watch`는 **큐를 비우고 보고만 한다.** 잘못 넓히면 지난 학기가 통째로 딸려 온다.
그때는 사람이 `--since`/`--until`로 준다.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 서버가 `python -m app.cli seed-timetable`로 먹인 사본. 운영 DB는 Supabase에
# 있지만 야간 러너는 네트워크 없이 돌아야 해서 이걸 본다. 학기 시간표를 다시
# 넣었으면 여기도 다시 넣어야 한다 — 어긋나면 `watch`가 엉뚱한 구간을 고른다.
DEFAULT_SOURCE = REPO_ROOT / "server" / "local_test_data" / "studyez.db"

# 블럭 이름에 붙는 꼬리. 떼고 나면 한 블럭의 칸이 한 이름으로 모인다.
SUFFIXES = ("실습시험", "필기시험", "실습", "시험", "평가", "PBL", "CBL", "TBL", "CBL/TBL")

# 수업이 서는 칸. 나머지(holiday·elective·study)는 구간을 만들지 않는다.
TEACHING = ("lecture", "practice")

# 같은 이름이라도 이만큼 넘게 비면 다른 구간이다. 2026-2 시간표에서 진짜 블럭
# 다섯의 내부 최대 공백은 3~4일이었고(면역의 기초 3, 질병의 병리학적 이해 4,
# 감염의 기초 3, 약물의 이해 4, 감염과 면역 4), 이 값을 넘긴 것은 09-22의 `CBL`과
# 12-03의 `CBL/TBL`이 한 이름으로 붙어 72일 구간이 된 건뿐이었다.
# 시험일을 블럭 끝으로 끌어올 때도 같은 창을 쓴다 — 실측 +1~+5일이다.
MAX_GAP_DAYS = 7


@dataclass(frozen=True)
class Block:
    name: str
    start: Date
    end: Date
    events: int
    days: int

    def contains(self, day: Date) -> bool:
        return self.start <= day <= self.end

    def label(self) -> str:
        return f"{self.name} ({self.start.isoformat()}~{self.end.isoformat()})"


# 시간표는 과목 이름 뒤에 회차를 붙여 쓴다("감염과 면역 12"). 서버는
# `app.naming.course_from_title`이 같은 일을 하는데, 그 표를 안 거치고 시간표
# JSON을 직접 읽는 경로가 있어서 여기서도 뗀다. 안 떼면 회차마다 다른 이름이
# 되어 하루짜리 구간이 수십 개 생기고, 블럭이 하나도 안 선다.
_TRAILING_NUMBER = re.compile(r"[\s\-–—]*\d{1,3}\s*$")


def base_name(course: str) -> str:
    """`질병의 병리학적 이해 실습 3` → `질병의 병리학적 이해`."""
    name = unicodedata.normalize("NFC", course).strip()
    changed = True
    while changed:
        # 회차와 꼬리가 번갈아 붙는다 — "감염과 면역 CBL 3"은 둘 다 떼야 한다.
        trimmed = _TRAILING_NUMBER.sub("", name).strip()
        changed = bool(trimmed) and trimmed != name
        name = trimmed or name
        for suffix in SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix):
                stripped = name[: -len(suffix)].strip(" -–—/")
                if stripped:
                    name, changed = stripped, True
                    break
    return name


def read_events(source: Path) -> list[tuple[Date, str, str]]:
    """`(날짜, course, category)`. sqlite면 표에서, `.json`이면 시간표 원본에서."""
    if not source.exists():
        raise FileNotFoundError(source)

    if source.suffix.lower() == ".json":
        # `seed-timetable`이 먹는 것과 같은 배열. course 열이 없으므로 제목을 쓴다.
        raw = json.loads(source.read_text(encoding="utf-8"))
        rows = []
        for item in raw:
            day, title = str(item.get("date", "")), str(item.get("title", ""))
            if day and title:
                rows.append((Date.fromisoformat(day), title,
                             str(item.get("category", "lecture")) or "lecture"))
        return rows

    db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        return [
            (Date.fromisoformat(day), course or title, category)
            for day, title, course, category in db.execute(
                "select date, title, course, category from timetable_event")
        ]
    finally:
        db.close()


def _runs(days: list[Date]) -> list[list[Date]]:
    """공백이 `MAX_GAP_DAYS`를 넘는 자리에서 끊는다."""
    groups: list[list[Date]] = []
    for day in sorted(days):
        if groups and (day - groups[-1][-1]).days <= MAX_GAP_DAYS:
            groups[-1].append(day)
        else:
            groups.append([day])
    return groups


def build(events: list[tuple[Date, str, str]]) -> list[Block]:
    """이름별로 묶어 구간을 만든다. 하루짜리는 블럭이 아니다."""
    teaching: dict[str, set[Date]] = {}
    exams: dict[str, set[Date]] = {}
    for day, course, category in events:
        name = base_name(course)
        if not name:
            continue
        if category in TEACHING:
            teaching.setdefault(name, set()).add(day)
        elif category == "exam":
            exams.setdefault(name, set()).add(day)

    blocks = []
    for name, days in teaching.items():
        for run in _runs(list(days)):
            if len(run) < 2:
                # 12월처럼 시간표 제목이 강의 단위인 구간. 이건 블럭이 아니다.
                continue
            start, last = run[0], run[-1]
            # 시험일까지가 한 블럭이다. 중간 평가(구간 안의 시험)는 끝을 못 민다.
            mine = [d for d in exams.get(name, set())
                    if start <= d and (d - last).days <= MAX_GAP_DAYS]
            blocks.append(Block(name=name, start=start, end=max([last, *mine]),
                                events=len(run) + len(mine), days=len(run)))
    return sorted(blocks, key=lambda b: (b.start, b.name))


def current(blocks: list[Block], today: Date) -> tuple[Block | None, bool]:
    """오늘의 블럭과, 그것이 이미 끝난 블럭인지.

    오늘을 담는 것이 여럿이면 칸이 많은 쪽을 고른다 — 11월의 `감염과 면역`(78칸)과
    `임상의학입문`(5칸)에서 블럭은 앞의 것이다.

    담는 것이 없으면 **가장 늦게 시작한 지난 블럭**으로 물러난다. 블럭이 끝난
    주말에 올라온 늦은 필기를 잃지 않으려는 것이다 — 다음 블럭으로 넘어가면
    그 강의 날짜는 영영 어느 창에도 안 들어온다.
    """
    holding = [b for b in blocks if b.contains(today)]
    if holding:
        return max(holding, key=lambda b: (b.events, -(b.end - b.start).days)), False
    past = [b for b in blocks if b.start <= today]
    if not past:
        return None, False
    return max(past, key=lambda b: (b.start, b.events)), True


@dataclass(frozen=True)
class Found:
    block: Block | None
    ended: bool          # 오늘이 블럭 밖이라 직전 블럭으로 물러났다
    table: list[Block]
    source: Path


def find(today: Date, source: Path | None = None) -> Found:
    """`watch`가 부르는 자리. 고른 블럭과 전체 표, 실제로 읽은 파일을 함께 준다."""
    path = Path(source) if source else DEFAULT_SOURCE
    table = build(read_events(path))
    block, ended = current(table, today)
    return Found(block=block, ended=ended, table=table, source=path)
