"""Load/save learner state through the existing retention and study policies."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bank_personal, bank_retention, study_engine as engine
from app.auth import CurrentUser
from app.models import BankState, QuizBank
from app.study_engine.engine import reschedule_bank

from .common import _usable


def _study_bank(db: Session, row: QuizBank, user: CurrentUser) -> dict:
    _usable(row)
    return bank_personal.augment(db, row, user.id)


def _load_state(db: Session, user: CurrentUser, row: QuizBank) -> BankState:
    """이 사람의 상태. 은행이 새로 만들어졌으면 옛 상태를 밀어 두고 새로 시작한다."""
    state = db.scalars(select(BankState).where(
        BankState.user_id == user.id, BankState.subject == row.subject, BankState.run_id == row.run_id
    ).with_for_update()).first()
    if state is None:
        state = BankState(user_id=user.id, subject=row.subject, run_id=row.run_id, build_id=row.build_id,
                          state=engine.empty_state())
        db.add(state)
    elif state.build_id != row.build_id:
        bank_retention.save_version(db, row.subject, row.run_id, row.build_id, row.bank)
        bank_retention.transition(db, state, row)
    elif row.bank and bank_retention.content_changed(db, state, row):
        bank_retention.save_version(db, row.subject, row.run_id, row.build_id, row.bank)
        bank_retention.transition(db, state, row)
    if row.bank:
        state.state = reschedule_bank(bank_personal.augment(db, row, user.id), state.state)
        known = state.state.get('_question_fingerprints', {})
        current = bank_retention.manifest(bank_retention.augmented(db, row, row.bank, user.id, row.build_id, state.state))
        if any(qid not in known for qid in current):
            state.state = {**state.state, '_question_fingerprints': {**known, **current}}
    if state.state.get('_study_build_id') != row.build_id:
        state.state = {**state.state, '_study_build_id': row.build_id}
    return state


def _save(state: BankState, value: dict) -> None:
    # JSON 칼럼은 새 객체를 넣어야 바뀐 줄 안다.
    state.state = value
