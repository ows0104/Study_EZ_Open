"""Personal lecture visibility; shared material and study history stay intact."""

from sqlalchemy import DDL, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StudyHiddenLecture(Base):
    __tablename__ = "study_hidden_lecture"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lecture_key: Mapped[str] = mapped_column(String(512), primary_key=True)


event.listen(StudyHiddenLecture.__table__, "after_create",
             DDL("ALTER TABLE study_hidden_lecture ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
