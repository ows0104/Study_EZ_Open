"""한 교시에 여러 강의가 열릴 때.

설계 문서가 경고하는 바로 그 자리다.

    [260303_02] 역사 속의 감염병(김옥주, 이규원)
    [260303_02] 질병사 관점에서 신종-재출현 감염병 (송진수)
    [260303_02] 건강과 질병(박영수)

`run_id`만으로는 유일하지 않으므로 서버 키가 `(subject, run_id)`인 것이고,
매칭도 날짜·교시만으로는 끝나지 않는다.

    server/.venv/Scripts/python.exe -m tests.test_matching
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-match-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'match.db').as_posix()}",
    RUNNER_TOKEN="runner-token",
)

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.matching import find_timetable_event  # noqa: E402
from app.models import CourseAlias, Lecture, TimetableEvent  # noqa: E402
from app.naming import normalize_stem  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def event(db, event_id: str, course: str, detail_title: str, professor: str, slot: int = 2):
    row = TimetableEvent(
        id=event_id,
        date=date(2026, 3, 3),
        start_time=f"{slot + 8:02d}:00",
        end_time=f"{slot + 8:02d}:50",
        title=f"{course} 1",
        details=f"{detail_title}\n{professor}",
        professor=professor,
        category="lecture",
        course=course,
        course_key=normalize_stem(course),
        slot=slot,
    )
    db.add(row)
    return row


def lecture(subject: str, run_id: str, title: str, slot: int = 2, slot_end: int | None = None) -> Lecture:
    return Lecture(
        subject=subject,
        run_id=run_id,
        uid=f"{run_id}#{normalize_stem(title)}",
        date=date(2026, 3, 3),
        slot=slot,
        slot_end=slot_end if slot_end is not None else slot,
        start_time=f"{slot + 8:02d}:00",
        title=title,
        professors=[],
    )


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        event(db, "e1", "의학의 역사", "역사 속의 감염병", "김옥주, 이규원")
        event(db, "e2", "감염과 면역", "질병사 관점에서 신종-재출현 감염병", "송진수")
        event(db, "e3", "건강과 사회", "건강과 질병", "박영수")
        event(db, "e4", "질병의 병리학적 이해", "조직 재생 및 수복", "김혜령", slot=5)
        db.commit()

        print("\n[1] 제목으로 가른다 — 세 강의가 한 교시에 열려도")
        found = find_timetable_event(db, lecture("의학사", "260303_02", "역사 속의 감염병"))
        check("맞는 칸을 골랐다", found is not None and found.id == "e1", found and found.id)

        print("\n[2] 제목이 어느 것과도 안 맞으면 붙이지 않는다")
        # 틀린 칸에 붙은 강의는 안 붙은 강의보다 찾기 어렵다.
        check(
            "None을 돌려준다",
            find_timetable_event(db, lecture("의학사", "260303_02", "전혀 다른 제목")) is None,
        )

        print("\n[3] 별칭이 있으면 과목으로 먼저 좁힌다")
        # 제목이 흔들려도(순번 괄호가 붙어도) 과목이 이어져 있으면 골라낸다.
        db.add(CourseAlias(course_key=normalize_stem("감염과 면역"), course="감염과 면역", subject="감염면역"))
        db.commit()
        found = find_timetable_event(db, lecture("감염면역", "260303_02", "신종 재출현 감염병(2)"))
        check("별칭이 후보를 하나로 좁혔다", found is not None and found.id == "e2", found and found.id)

        print("\n[4] 별칭이 아무것도 안 남기면 좁히지 않은 것으로 되돌린다")
        # 아직 이어 주지 않은 과목이라는 뜻이지 후보가 없다는 뜻이 아니다.
        found = find_timetable_event(db, lecture("사회의학", "260303_02", "건강과 질병"))
        check("제목 매칭으로 되돌아간다", found is not None and found.id == "e3", found and found.id)

        print("\n[5] 연강은 시작 교시부터 끝 교시까지 어디에나 놓일 수 있다")
        found = find_timetable_event(db, lecture("병리학", "260303_03", "조직 재생 및 수복", slot=3, slot_end=5))
        check("5교시 칸을 찾았다", found is not None and found.id == "e4", found and found.id)

        print("\n[6] 교시가 아예 다르면 붙이지 않는다")
        check(
            "None을 돌려준다",
            find_timetable_event(db, lecture("병리학", "260303_07", "조직 재생 및 수복", slot=7)) is None,
        )

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
