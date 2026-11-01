"""관리자가 함께 사용하는 사이트 프롬프트."""

from sqlalchemy import DDL, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SitePrompt(Base):
    __tablename__ = "site_prompt"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)


event.listen(
    SitePrompt.__table__, "after_create",
    DDL("ALTER TABLE site_prompt ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
)
