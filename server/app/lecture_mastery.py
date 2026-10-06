"""사용자별 강의 학습도를 읽기만 한다. 은행 교체 전 상태와 비공개 은행은 제외한다."""

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, load_only

from app.models import BankState, QuizBank
from app.study_engine import empty_state, now_ms
from app.study_engine.mastery import lecture_mastery


def for_bank(row: QuizBank | None, state: BankState | None, *, is_admin: bool, now: int | None = None) -> dict | None:
    if (not row or (not is_admin and not row.open_to_students)
            or not row.bank or not (row.validation or {}).get("pass")):
        return None
    current = state.state if state and state.build_id == row.build_id else empty_state()
    return lecture_mastery(row.bank, current, now=now_ms() if now is None else now)


def lecture_masteries(db: Session, user_id: str, keys: list[tuple[str, str]],
                      *, is_admin: bool) -> dict[tuple[str, str], dict | None]:
    if not keys:
        return {}
    query = select(QuizBank).options(load_only(
        QuizBank.subject, QuizBank.run_id, QuizBank.build_id, QuizBank.bank,
        QuizBank.validation, QuizBank.open_to_students,
    )).where(tuple_(QuizBank.subject, QuizBank.run_id).in_(keys))
    if not is_admin:
        query = query.where(QuizBank.open_to_students.is_(True))
    states = {(s.subject, s.run_id): s for s in db.scalars(select(BankState).options(load_only(
        BankState.subject, BankState.run_id, BankState.user_id, BankState.build_id, BankState.state,
    )).where(BankState.user_id == user_id, tuple_(BankState.subject, BankState.run_id).in_(keys)))}
    now = now_ms()
    return {(r.subject, r.run_id): for_bank(r, states.get((r.subject, r.run_id)), is_admin=is_admin, now=now)
            for r in db.scalars(query)}
