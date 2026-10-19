"""사용자별 강의 학습도를 읽기만 한다. 은행 교체 전 상태와 비공개 은행은 제외한다."""

from app.bank_validation.publication import usable as bank_usable


from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, load_only

from app.models import BankState, BankPersonalEdit, QuizBank
from app import bank_personal
from app.study_engine import empty_state, now_ms
from app.study_engine.mastery import lecture_mastery
from app.study_engine.card_progress import card_progress


def for_bank(row: QuizBank | None, state: BankState | None, *, is_admin: bool, now: int | None = None,
             bank: dict | None = None) -> dict | None:
    if (not row or (not is_admin and not row.open_to_students)
            or not bank_usable(row.bank, row.validation)):
        return None
    current = state.state if state and state.build_id == row.build_id else empty_state()
    return lecture_mastery(bank if bank is not None else row.bank, current, now=now_ms() if now is None else now)


def lecture_masteries(db: Session, user_id: str, keys: list[tuple[str, str]],
                      *, is_admin: bool) -> dict[tuple[str, str], dict | None]:
    return {key: value["mastery"] for key, value in lecture_overviews(
        db, user_id, keys, is_admin=is_admin, include_cards=False).items()}


def lecture_overviews(db: Session, user_id: str, keys: list[tuple[str, str]],
                      *, is_admin: bool, include_cards: bool = True) -> dict[tuple[str, str], dict]:
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
    edits_by_key: dict[tuple[str, str], list] = {}
    for edit in db.scalars(select(BankPersonalEdit).where(
            BankPersonalEdit.user_id == user_id, tuple_(BankPersonalEdit.subject, BankPersonalEdit.run_id).in_(keys))):
        edits_by_key.setdefault((edit.subject, edit.run_id), []).append(edit)
    result = {}
    for row in db.scalars(query):
        key = (row.subject, row.run_id)
        state = states.get(key)
        usable = bank_usable(row.bank, row.validation)
        current = state.state if state and state.build_id == row.build_id else empty_state()
        bank = bank_personal.augment(db, row, user_id, edits=edits_by_key.get(key, []))
        result[key] = {"ready": usable,
                       "mastery": lecture_mastery(bank, current, now=now) if usable else None,
                       "cardProgress": card_progress(bank, current, now) if usable and include_cards else None}
    return result
