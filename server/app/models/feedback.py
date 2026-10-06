"""사이트 피드백. 첨부 본문은 비공개 객체 저장소에 보관한다."""

from datetime import datetime

from sqlalchemy import DDL, JSON, DateTime, Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class SiteFeedback(Base):
    __tablename__ = "site_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    screenshots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_site_feedback_status", "status", "created_at"),)


event.listen(
    SiteFeedback.__table__, "after_create",
    DDL("ALTER TABLE site_feedback ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
)
