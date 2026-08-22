"""운영용 잡일 둘. 학기 초에 한 번씩 돌린다.

    python -m app.cli init-db
    python -m app.cli seed-timetable "…/2026_본1_2학기_시간표.json"

마이그레이션 도구를 두지 않았다. 표가 열둘이고 고치는 사람이 한 명이라
Alembic이 얹는 무게가 그것으로 막는 사고보다 크다. 스키마가 바뀌면 여기서
다시 만든다.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from datetime import date as Date
from pathlib import Path

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.matching import relink
from app.models import Lecture, TimetableEvent
from app.naming import course_from_title, nfc, normalize_stem, slot_from_time


def init_db() -> None:
    Base.metadata.create_all(engine)
    print(f"{len(Base.metadata.tables)}개 표를 준비했습니다.")


def seed_timetable(path: Path) -> None:
    """시간표 JSON → `timetable_event`.

    캘린더가 이것만으로 그려진다. 파이프라인 산출물은 나중에 점으로 붙는다.
    """
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise SystemExit("시간표 JSON은 배열이어야 합니다.")

    with SessionLocal() as db:
        seen: set[str] = set()
        skipped: list[str] = []
        for raw in events:
            event_id = str(raw.get("id", "")).strip()
            date_text = str(raw.get("date", "")).strip()
            start_time = str(raw.get("startTime", "")).strip()
            if not event_id or not date_text or not start_time:
                skipped.append(json.dumps(raw, ensure_ascii=False)[:80])
                continue
            seen.add(event_id)

            event = db.get(TimetableEvent, event_id)
            if event is None:
                event = TimetableEvent(id=event_id)
                db.add(event)
            event.date = Date.fromisoformat(date_text)
            event.start_time = start_time
            event.end_time = str(raw.get("endTime", "")).strip()
            # 시간표 JSON도 NFD가 섞일 수 있다. 여기서 모아 두지 않으면 과목
            # 이름이 두 갈래로 갈라져 매칭이 통째로 빗나간다.
            event.title = nfc(str(raw.get("title", "")))
            event.details = unicodedata.normalize("NFC", str(raw.get("details", "")))
            event.professor = nfc(str(raw.get("professor", "")))
            event.category = str(raw.get("category", "lecture")).strip() or "lecture"
            event.course = course_from_title(event.title)
            event.course_key = normalize_stem(event.course)
            event.slot = slot_from_time(start_time)

        stale = [
            event
            for event in db.scalars(select(TimetableEvent))
            if event.id not in seen
        ]
        for event in stale:
            db.delete(event)
        db.flush()

        # 시간표가 바뀌면 붙어 있던 강의의 자리도 바뀐다. 관리자가 확인한
        # 연결은 건드리지 않는다.
        relinked = 0
        for lecture in db.scalars(select(Lecture)):
            before = lecture.timetable_event_id
            relink(db, lecture)
            relinked += lecture.timetable_event_id != before
        db.commit()

    print(f"시간표 {len(seen)}칸을 넣었습니다. 지운 칸 {len(stale)}, 다시 붙인 강의 {relinked}.")
    if skipped:
        # 읽지 못한 줄은 반드시 이유와 함께 보고한다. 조용히 넘어가면 캘린더에
        # 구멍이 뚫린 것을 아무도 모른다.
        print(f"읽지 못한 칸 {len(skipped)}개 (id·date·startTime 중 빠진 것이 있습니다):")
        for line in skipped:
            print(f"  {line}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    command = sys.argv[1]
    if command == "init-db":
        init_db()
    elif command == "seed-timetable":
        if len(sys.argv) < 3:
            raise SystemExit("시간표 JSON 경로가 필요합니다.")
        seed_timetable(Path(sys.argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
