"""Public-share verification, separate from mutable quiz validation/build results."""
from datetime import datetime
from sqlalchemy import DDL, JSON, DateTime, ForeignKeyConstraint, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class QuizPublicationCheck(Base):
    __tablename__ = 'quiz_publication_check'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    share_url: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (ForeignKeyConstraint(['subject', 'run_id'], ['lecture.subject', 'lecture.run_id'], ondelete='CASCADE'),)


event.listen(QuizPublicationCheck.__table__, 'after_create',
             DDL('ALTER TABLE quiz_publication_check ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
