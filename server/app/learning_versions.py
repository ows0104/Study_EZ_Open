"""Content-addressed snapshots; neither regeneration nor rollback deletes history."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bank_validation.learning import fingerprint
from app.models import BankState, QuizBank
from app.models.learning import LearningBankVersion, LearningLegacyState


def snapshot(db: Session, row: QuizBank, now: int) -> str:
    key = fingerprint([row.subject, row.run_id, row.build_id, row.bank])
    if row.bank and db.get(LearningBankVersion, key) is None:
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(LearningBankVersion).values(id=key, subject=row.subject, run_id=row.run_id,
                   build_id=row.build_id, bank=row.bank, created_at=now).on_conflict_do_nothing(index_elements=["id"]))
        db.flush()
    return key


def archive_bank(db: Session, row: QuizBank, now: int) -> None:
    if not row.bank: return
    version = snapshot(db, row, now)
    for old in db.scalars(select(BankState).where(BankState.subject == row.subject,
            BankState.run_id == row.run_id, BankState.build_id == row.build_id)):
        if db.get(LearningLegacyState, (old.user_id, version)) is None:
            db.add(LearningLegacyState(user_id=old.user_id, version_id=version,
                                      data={"state": old.state, "previous": old.previous}))
