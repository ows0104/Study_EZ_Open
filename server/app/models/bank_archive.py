"""A complete snapshot before an administrator removes a lecture's quiz."""

from datetime import datetime

from sqlalchemy import DDL, JSON, DateTime, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class QuizBankArchive(Base):
    __tablename__ = "quiz_bank_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    deleted_by: Mapped[str] = mapped_column(String(64), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)


event.listen(QuizBankArchive.__table__, "after_create",
             DDL("ALTER TABLE quiz_bank_archive ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
