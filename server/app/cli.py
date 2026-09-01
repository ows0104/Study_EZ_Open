"""운영용 잡일. 학기 초에 한 번씩, 그리고 파이프라인을 갈아엎을 때 한 번.

    python -m app.cli init-db                    표를 세우고 빠진 칼럼을 붙인다
    python -m app.cli seed-timetable             data/timetable/의 최신 학기 파일
    python -m app.cli seed-timetable <경로>       다른 것을 먹일 때
    python -m app.cli purge-artifacts            무엇이 지워질지만 본다
    python -m app.cli purge-artifacts --apply    정말 지운다

마이그레이션 도구를 두지 않았다. 표가 열둘이고 고치는 사람이 한 명이라
Alembic이 얹는 무게가 그것으로 막는 사고보다 크다. 스키마가 바뀌면 여기서
다시 만든다.

**칼럼 하나가 느는 것은 그 「다시 만든다」로 못 한다.** `create_all`은 없는 표만
세우고 이미 서 있는 표는 손대지 않는다. 그래서 `ADDED_COLUMNS`에 한 줄로 적고
`init-db`가 지나며 붙인다.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from datetime import date as Date
from pathlib import Path

from sqlalchemy import inspect, select, text

from app.database import Base, SessionLocal, engine
from app.matching import relink
from app.models import Lecture, TimetableEvent
from app.naming import (
    course_from_title,
    nfc,
    normalize_stem,
    professor_names,
    slot_from_time,
    strip_lead_topic,
)
from app.storage import ObjectStorage, StorageNotConfigured

# 표가 선 뒤에 붙은 칼럼. **`create_all`은 없는 표는 세우지만 없는 칼럼은 안 붙인다** —
# 이미 서 있는 운영 DB는 여기를 지나야 새 칼럼을 갖는다. 이미 있으면 건너뛴다.
#
# 마이그레이션 도구를 두지 않은 사정은 이 파일 첫머리에 있다. 그 대신 **붙인 칼럼을
# 여기 한 줄로 남긴다** — 다음 사람이 운영 DB와 모델이 어디서 갈라졌는지 볼 자리다.
ADDED_COLUMNS = (
    # 2026-08-25 개인 예습도 ChatGPT·Gemini·Claude 중 어디에서 만든 것인지 남긴다.
    ("user_preview", "provider", "VARCHAR(32) NOT NULL DEFAULT 'chatgpt'"),
    # 2026-08-24 복습 덱도 같은 우편함을 쓰게 되면서.
    ("prequiz_job", "kind", "VARCHAR(8) NOT NULL DEFAULT 'pre'"),
    # 2026-08-24 「다시 만들기」가 러너까지 가려면 이 값이 표에 남아야 한다.
    ("prequiz_job", "force", "BOOLEAN NOT NULL DEFAULT FALSE"),
    # 2026-09-01 재료가 도착하면 자동으로 세운다. 상한은 자동에만 건다.
    ("prequiz_job", "origin", "VARCHAR(8) NOT NULL DEFAULT 'button'"),
    # 2026-09-01 일꾼이 둘이 되면서 — 끊겼다 붙은 일꾼이 자기 편을 되찾는 값.
    ("prequiz_job", "worker", "VARCHAR(16) NOT NULL DEFAULT ''"),
    # 2026-09-01 「어디까지 왔나·얼마나 남았나」를 화면이 말하려면 표에 있어야 한다.
    ("prequiz_job", "stage_index", "INTEGER NOT NULL DEFAULT 0"),
    ("prequiz_job", "stage_total", "INTEGER NOT NULL DEFAULT 0"),
    ("prequiz_job", "eta_seconds", "INTEGER NOT NULL DEFAULT 0"),
    ("prequiz_job", "stage_started_at", "TIMESTAMP WITH TIME ZONE"),
)


def ensure_columns() -> None:
    inspector = inspect(engine)
    added = []
    with engine.begin() as connection:
        for table, column, ddl in ADDED_COLUMNS:
            if table not in inspector.get_table_names():
                continue
            if column in {row["name"] for row in inspector.get_columns(table)}:
                continue
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            added.append(f"{table}.{column}")
    if added:
        print(f"칼럼을 붙였습니다: {', '.join(added)}")


def init_db() -> None:
    Base.metadata.create_all(engine)
    ensure_columns()
    print(f"{len(Base.metadata.tables)}개 표를 준비했습니다.")


# 학기 시간표가 사는 자리. `server/`는 따로 배포되지만 이 명령은 로컬에서만 돈다
# (운영 DB를 향해 사람이 손으로 부른다) — 저장소 안을 봐도 된다.
TIMETABLE_DIR = Path(__file__).resolve().parents[2] / "data" / "timetable"


def latest_timetable() -> Path:
    """경로를 안 주면 먹일 파일. **이름순 마지막이 최신 학기다**(`2026_본1_2학기_…`).

    2026-08-31까지 이 파일은 옛 파이프라인 저장소에 혼자 있었고, 그래서 부르는 자리마다
    절대경로를 손으로 적었다. 적는 자리가 많으면 하나는 낡은 사본을 가리키게 된다.
    """
    found = sorted(TIMETABLE_DIR.glob("*.json"))
    if not found:
        raise SystemExit(f"{TIMETABLE_DIR}에 시간표 JSON이 없습니다. 경로를 주세요.")
    return found[-1]


def seed_timetable(path: Path) -> None:
    """시간표 JSON → `timetable_event`.

    캘린더가 이것만으로 그려진다. 파이프라인 산출물은 나중에 점으로 붙는다.
    """
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise SystemExit("시간표 JSON은 배열이어야 합니다.")

    # 담당 칸 앞에 소제목이 끌려 들어온 칸을 되돌린다. 이름 사전이 시간표 전체에서
    # 나오므로 한 칸씩 볼 수 없고 여기서 먼저 모은다(`naming.strip_lead_topic`).
    names = professor_names([
        (str(raw.get("details", "")), str(raw.get("professor", ""))) for raw in events
    ])

    with SessionLocal() as db:
        seen: set[str] = set()
        skipped: list[str] = []
        mended: list[str] = []
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
            given = nfc(str(raw.get("professor", "")))
            event.professor = strip_lead_topic(event.details, given, names)
            if event.professor != given:
                mended.append(f"{date_text} {start_time} {event.title}: {given} → {event.professor}")
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
    if mended:
        # 손댄 자리는 전부 찍는다. 규칙이 오탐을 내면 여기서만 보인다 — 화면에서는
        # 「제목이 있는 칸」과 구별되지 않는다.
        print(f"담당 칸에서 소제목을 뗀 칸 {len(mended)}개:")
        for line in mended:
            print(f"  {line}")
    if skipped:
        # 읽지 못한 줄은 반드시 이유와 함께 보고한다. 조용히 넘어가면 캘린더에
        # 구멍이 뚫린 것을 아무도 모른다.
        print(f"읽지 못한 칸 {len(skipped)}개 (id·date·startTime 중 빠진 것이 있습니다):")
        for line in skipped:
            print(f"  {line}")


# 파이프라인이 만든 것. **강의록 PDF는 여기 없다** — 그건 제3자 저작물이고
# 파이프라인과 무관하게 학생에게 필요하다. 지우면 사이트가 빈 채로 남는다.
ARTIFACT_KINDS = ("main_apkg", "pre_apkg", "media")


# 컬럼 모양이 통째로 바뀐 표. 지운 뒤 새 스키마로 다시 세운다.
RESHAPED_TABLES = ("quiz_attempt", "pre_item")


def purge_artifacts(apply: bool = False) -> None:
    """파이프라인이 만든 것을 서버에서 내린다. 덱·문항·풀이 기록·근거 슬라이드.

    **되돌릴 수 없다.** 학생이 보던 자료가 사라지므로 기본은 세어 보여 주기만 하고,
    정말 지우려면 `--apply`를 준다.

    남기는 것:

        강의·시간표      캘린더가 이것으로 그려진다
        강의록 PDF       제3자 저작물이고 파이프라인과 무관하다
        예습 링크        사람이 만든 대화다. 덱과 함께 지울 이유가 없다
        계정·승인        말할 것도 없다

    **ORM을 쓰지 않고 SQL을 직접 쓴다.** 이 명령이 도는 시점의 DB는 아직 옛
    스키마이고 모델은 이미 새 모양이라, 매핑을 태우면 `pre_item.card_type이 없다`로
    죽는다. 지우는 일이 스키마를 아는 것보다 앞선다.
    """
    kinds = ", ".join(f"'{kind}'" for kind in ARTIFACT_KINDS)
    with SessionLocal() as db:
        rows = db.execute(text(
            f"SELECT kind, count(*), coalesce(sum(size_bytes), 0), "
            f"count(distinct subject || '/' || run_id) "
            f"FROM asset WHERE kind IN ({kinds}) GROUP BY kind")).all()
        counts = {name: int(db.execute(text(f"SELECT count(*) FROM {name}")).scalar() or 0)
                  for name in ("run_meta", "pre_item", "quiz_attempt")}
        assets = db.execute(text(
            f"SELECT object_key FROM asset WHERE kind IN ({kinds})")).scalars().all()

        print("지울 것:")
        total_bytes = 0
        for kind, count, size, lectures in rows:
            total_bytes += int(size or 0)
            print(f"  R2 {kind:<11} {count:>5}개 · {int(size or 0) / 1024 / 1024:>8.1f}MB · 강의 {lectures}편")
        for name, count in counts.items():
            print(f"  {name:<14} {count:>5}행")
        print(f"  합계           {len(assets)}개 파일 · {total_bytes / 1024 / 1024:.1f}MB")
        print("남기는 것: 강의 · 시간표 · 강의록 PDF · 예습 링크 · 계정")

        if not apply:
            print("--apply 를 주면 정말 지웁니다.")
            return

        removed, failed = 0, []
        try:
            storage = ObjectStorage()
        except StorageNotConfigured:
            storage = None
            print("⚠ R2 설정이 없다 — DB만 지우고 버킷의 파일은 남는다")
        if storage is not None:
            for key in assets:
                try:
                    storage.delete(key)
                    removed += 1
                except Exception as cause:                      # noqa: BLE001
                    # 한 파일이 안 지워졌다고 멈추지 않는다. 대신 **전부 적는다** —
                    # 조용히 넘기면 버킷에 남은 것을 아무도 모른다.
                    failed.append(f"{key}: {type(cause).__name__}")

        # 새 모양으로 다시 세운다. 컬럼이 바뀐 표라 비우는 것만으로는 안 된다.
        for table in RESHAPED_TABLES:
            db.execute(text(f"DROP TABLE IF EXISTS {table}"))
        db.execute(text("DELETE FROM run_meta"))
        db.execute(text(f"DELETE FROM asset WHERE kind IN ({kinds})"))
        db.commit()

    Base.metadata.create_all(engine)
    ensure_columns()
    print(f"R2에서 {removed}개를 지웠습니다. "
          f"DB 행 {sum(counts.values())}개를 지우고 {len(RESHAPED_TABLES)}개 표를 새 모양으로 세웠습니다.")
    if failed:
        print(f"버킷에서 못 지운 것 {len(failed)}개:")
        for line in failed[:20]:
            print(f"  {line}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    command = sys.argv[1]
    if command == "init-db":
        init_db()
    elif command == "seed-timetable":
        seed_timetable(Path(sys.argv[2]) if len(sys.argv) > 2 else latest_timetable())
    elif command == "purge-artifacts":
        purge_artifacts(apply="--apply" in sys.argv[2:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
