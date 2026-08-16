"""시간표 칸 ↔ 필기에서 읽어 낸 강의.

둘은 같은 강의를 다르게 부른다.

    시간표   title="감염과 면역 12"  details="선천면역 I\\n성승용"
    필기     [260813_03]선천면역(1)(성승용)_최나예v1.pdf

시간표의 `title`은 과목과 회차이고, **진짜 강의 제목은 `details`의 첫 줄**이다.
그래서 비교는 `details` 쪽을 먼저 본다.

자동 매칭은 **제안일 뿐이다.** `match_confirmed`가 켜지기 전까지는 관리자가
`/admin`에서 눈으로 확인해야 하는 값이고, 확인된 연결은 다시 덮어쓰지 않는다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CourseAlias, Lecture, TimetableEvent
from app.naming import normalize_stem

# 시간표 칸 중 붙일 자료가 있을 수 있는 것. 시험·휴일·자율학습은 후보가 아니다.
LINKABLE_CATEGORIES = ("lecture", "practice")


def lecture_titles(event: TimetableEvent) -> list[str]:
    """이 칸이 가리킬 수 있는 강의 제목 후보. 앞에 오는 것이 더 그럴듯하다.

    `details`에서 교수 이름 줄을 빼고 남은 줄이 실제 제목이다. 다 빼고 나면
    시간표 `title`로 물러선다 — 회차 번호까지 붙은 이름이라 잘 맞지는 않지만,
    비어 있는 것보다는 낫다.
    """
    professor = (event.professor or "").replace(" ", "")
    candidates = []
    for line in (event.details or "").split("\n"):
        line = line.strip()
        if not line or line.replace(" ", "") == professor:
            continue
        candidates.append(line)
    candidates.append(event.title)
    return candidates


def find_timetable_event(db: Session, lecture: Lecture) -> TimetableEvent | None:
    """이 강의가 놓일 시간표 칸. 못 찾으면 None — 추측해서 붙이지 않는다."""
    events = db.scalars(
        select(TimetableEvent).where(
            TimetableEvent.date == lecture.date,
            TimetableEvent.category.in_(LINKABLE_CATEGORIES),
        )
    ).all()
    if not events:
        return None

    # 연강이면 시작 교시부터 끝 교시까지 어느 칸에나 놓일 수 있다.
    slots = set(range(lecture.slot, max(lecture.slot, lecture.slot_end) + 1))
    same_slot = [event for event in events if event.slot in slots]
    if not same_slot:
        return None

    # 과목 별칭이 이어져 있으면 그것으로 먼저 좁힌다. 선택형 과목은 한 교시에
    # 강의가 셋씩 열리므로, 제목이 비슷할 때 과목이 가장 확실한 구분자다.
    # 아무것도 남지 않으면 좁히지 않은 것으로 되돌린다 — 별칭이 아직 없다는
    # 뜻이지 후보가 없다는 뜻이 아니다.
    aliases = {row.course_key: row.subject for row in db.scalars(select(CourseAlias))}
    if aliases:
        narrowed = [event for event in same_slot if aliases.get(event.course_key) == lecture.subject]
        if narrowed:
            same_slot = narrowed

    if len(same_slot) == 1:
        return same_slot[0]

    # 그래도 여럿이면 제목으로 가른다.
    target = normalize_stem(lecture.title)
    for rank in (0, 1):
        for event in same_slot:
            titles = lecture_titles(event)
            if rank < len(titles) and normalize_stem(titles[rank]) == target:
                return event
    # 어느 것도 정확히 맞지 않으면 붙이지 않는다. 틀린 칸에 붙은 강의는
    # 안 붙은 강의보다 찾기 어렵다.
    return None


def relink(db: Session, lecture: Lecture) -> None:
    """관리자가 확인하지 않은 연결만 다시 계산한다."""
    if lecture.match_confirmed:
        return
    event = find_timetable_event(db, lecture)
    lecture.timetable_event_id = event.id if event else None
