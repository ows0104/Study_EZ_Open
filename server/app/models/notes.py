"""Personal free-form notes (자유 노트). Owned by one account; never shared or used for study stats."""

from datetime import datetime

from sqlalchemy import DDL, JSON, DateTime, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class UserNote(Base):
    __tablename__ = "user_note"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


event.listen(UserNote.__table__, "after_create",
             DDL("ALTER TABLE user_note ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
