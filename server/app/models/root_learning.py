"""Separate immutable content and append-only learner events; no legacy state writes."""
from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, DDL, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import _now


class RootContent(Base):
    __tablename__ = 'root_content'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 원본(6–12 MB, 대부분 문항 그림). 검수·공개된 그대로 둔다. 요청마다 읽지 않게 미뤄 읽는다 — 계산·풀이는 `light`.
    document: Mapped[dict] = mapped_column(JSON, deferred=True)
    digest: Mapped[str] = mapped_column(String(64))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # 2026-11-12 저장 방식: 그림 바이트만 뺀 사본과 원본으로 계산한 문항 지문 {document, task_fingerprints}.
    # 넣을 때 자동으로 채운다(아래 before_insert). 그림은 root_image에 sha256으로. NULL이면 원본에서 만든다(채우기 전 행).
    # None은 SQL NULL로(JSON 'null'이 아니라) — 채우기 명령이 `IS NULL`로 찾는다.
    light: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True, deferred=True)


class RootImage(Base):
    """Main-Quiz 문항 그림 바이트. 키는 PNG 바이트의 sha256(계약 media.validate_images가 확인한다) — 판이 바뀌어도 같은 그림은 한 줄."""
    __tablename__ = 'root_image'
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    png_base64: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


@event.listens_for(RootContent, 'before_insert')
def _store_light(mapper, connection, target):
    """새 판(등록 경로 다섯 곳 전부)이 사본과 그림을 같이 갖게 한다. 원본은 고치지 않는다."""
    from app.root_learning.light import fill
    fill(connection, target)


class RootControl(Base):
    __tablename__ = 'root_control'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allowed_users: Mapped[list] = mapped_column(JSON, default=list)


class RootSession(Base):
    __tablename__ = 'root_session'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[str] = mapped_column(String(64))
    day: Mapped[str] = mapped_column(String(10))
    policy: Mapped[dict] = mapped_column(JSON)
    tasks: Mapped[list] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RootEvent(Base):
    __tablename__ = 'root_event'
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


for model in (RootContent, RootControl, RootSession, RootEvent):
    event.listen(model.__table__, 'after_create', DDL(
        f'ALTER TABLE {model.__tablename__} ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
