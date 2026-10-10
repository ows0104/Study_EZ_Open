"""계정, 앱별 사용 권한, 공지사항."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class Profile(Base):
    """계정과 플랫폼 관리자 여부. 앱 사용 권한은 AppGrant가 관리한다.

    is_approved는 권한 이관 전의 보존 칼럼이며 현재 접근 판정에 쓰지 않는다."""

    __tablename__ = "profile"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Supabase auth.users.id
    email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # 예습을 시작할 때 AI에 보내는 프롬프트. 사람마다 예습하는 방식이 달라서
    # 각자 고쳐 쓴다. **비어 있으면 화면의 기본값을 쓴다** — 여기에 기본 문구를
    # 복사해 두면 기본이 바뀌어도 옛 문구를 든 사람만 남는다.
    preview_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    review_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")


# ─────────────────────────────────────────────────────────────────────
# 형제 앱들. 계정은 하나, 문은 앱마다.
# ─────────────────────────────────────────────────────────────────────

APP_STUDYEZ = "studyez"
APP_SPOTTER = "spotter"

# 누가 들어오나. **앱을 더할 때 정하는 것은 이 값 하나다.**
#
#   auto    로그인하면 열린다. 우리가 만든 것을 우리 학년에 여는 앱.
#   manual  사람이 승인해야 열린다. 남이 만든 자료를 내보내는 앱.
#
# 전에는 이 갈림이 `profile.is_approved` 불리언 하나였고, 그 불리언은 이름이
# 전역인데 뜻은 Study_EZ 전용이었다. 앱이 셋이 되면 `is_approved_xxx`가 줄줄이
# 늘어난다 — 그래서 표로 옮겼다.
POLICY_AUTO = "auto"
POLICY_MANUAL = "manual"
APP_POLICY = {APP_STUDYEZ: POLICY_MANUAL, APP_SPOTTER: POLICY_AUTO}
ROLE_MEMBER = "member"
ROLE_ADMIN = "admin"


class AppGrant(Base):
    """사용자별 앱 접근 권한. 플랫폼 관리자를 정하는 profile.is_admin과 별개다."""

    __tablename__ = "app_grant"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    app: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_MEMBER)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_app_grant_app", "app", "role"),)


class Notice(Base):
    """관리자가 쓰는 공지사항. pinned는 목록 순서이며 읽음 표시는 브라우저가 관리한다."""

    __tablename__ = "notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
