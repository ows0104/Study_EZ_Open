"""시간표, 강의, 산출물, 다운로드와 관리자 체크리스트."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Date as SADate
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now

# 산출물 계약이 정한 종류. 여기 없는 종류가 필요해지면 계약을 먼저 고친다.
ASSET_KINDS = frozenset(
    {
        "notes_current",  # 올해 필기 PDF
        "notes_prev",  # 작년 필기 PDF (Pre-Quiz·예습용)
        "main_apkg",  # <강의>.apkg
        "pre_apkg",  # <강의>_예습.apkg
        "media",  # 예습 슬라이드 렌더. 이름이 갈래를 안 말하는 것은 역사다
        "main_media",  # 복습 슬라이드 렌더
        "jokbo",  # 이 강의의 족보 조각(.md). Quiz Bank 를 만들 때 ChatGPT 에 붙인다
        "bank_media",  # Quiz Bank 가 인용한 필기 쪽 렌더
        "root_evidence",  # Main-Quiz 판별 근거 보강 JSON(`<revision>.json`, quizbank/root_evidence.py)
        "root_choices",  # Main-Quiz 단답·나열 「선지 보기」 JSON(`<revision>.json`, quizbank/root_choices.py)
    }
)

# 예습·복습·Quiz Bank는 같은 slide_no를 쓸 수 있어 저장 갈래를 분리한다.
# 예습의 "media"는 운영 데이터에 쓰인 값이므로 유지한다.
SLIDE_KINDS = {"pre": "media", "main": "main_media", "bank": "bank_media"}

# 관리자가 강의마다 채우는 다섯 칸. 사용자 화면의 점 둘이 이것을 두 갈래로 묶는다 —
# 앞 셋이 예습, 뒤 둘이 복습이다.
CHECKLIST_ITEMS = ("notes_prev", "preview", "pre_apkg", "notes_current", "bank")

# "받아 갔다"로 셀 종류. `media`는 뺀다 — 오답 해설이 근거 슬라이드를 띄울 때
# 서명이 자동으로 나가므로, 세면 사용자가 받은 것이 아니라 해설을 본 것이 된다.
GRABBABLE_KINDS = frozenset({"notes_prev", "notes_current", "pre_apkg", "main_apkg", "jokbo"})


class TimetableEvent(Base):
    """공식 시간표의 강의·시험·휴일 등 한 칸. 산출물 유무와 관계없이 표시한다."""

    __tablename__ = "timetable_event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 시간표 JSON의 id
    date: Mapped[Date] = mapped_column(SADate, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "09:00"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    professor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(16), nullable=False)  # lecture|practice|exam|holiday|elective|study
    # 시간표 제목에서 뒤 번호를 뗀 것("감염과 면역 12" → "감염과 면역").
    # Synology 폴더명과 같다는 보장이 없어서 `course_alias`가 이어 준다.
    course: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 비교용. 실물에 "면역의 기초"와 "면역의기초"가 같이 있어서 표기 그대로
    # 묶으면 한 과목이 두 줄로 갈라진다.
    course_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 교시. 09:00이 1교시이므로 (시각 - 8)이다. 정각이 아닌 칸은 비어 있다.
    slot: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_timetable_event_date", "date"),)


class CourseAlias(Base):
    """공식 시간표 과목명과 Synology 폴더명의 관리자 지정 매핑."""

    __tablename__ = "course_alias"

    course_key: Mapped[str] = mapped_column(Text, primary_key=True)  # 시간표 쪽, 정규화된 이름
    course: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 표시용 원문
    subject: Mapped[str] = mapped_column(Text, nullable=False)  # 폴더 쪽 이름
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Lecture(Base):
    """로컬 러너가 파일명에서 읽어 낸 강의 하나. 산출물 계약 그대로다."""

    __tablename__ = "lecture"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)  # 폴더명 "병리학"
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "260813_03"
    uid: Mapped[str] = mapped_column(Text, nullable=False)  # "260813_03#조직재생및수복#김혜령"
    date: Mapped[Date] = mapped_column(SADate, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_end: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)  # 표시용 원문
    professors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    author: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 필기자
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preview_source: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 캘린더 칸과의 연결. 자동 매칭이 붙이고 관리자가 고칠 수 있다.
    timetable_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 관리자가 눈으로 확인했는가. 자동 매칭 결과는 False로 남는다.
    match_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_lecture_date", "date"),
        Index("ix_lecture_timetable_event", "timetable_event_id"),
    )


class Asset(Base):
    """R2에 올라간 파일 한 개. 서명 URL로만 나간다."""

    __tablename__ = "asset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # ASSET_KINDS
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/octet-stream")
    # media/*.png는 파일명 끝의 `_s012.png`에서 슬라이드 번호를 읽어 둔다.
    # 오답 해설이 근거 슬라이드를 띄울 때 이것으로 찾는다.
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("subject", "run_id", "kind", "filename", name="uq_asset_slot"),
        Index("ix_asset_lecture", "subject", "run_id"),
    )


class RunMeta(Base):
    """`run.meta.json` 통째로. 관리자 화면이 배포 가부를 여기서 읽는다."""

    __tablename__ = "run_meta"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quiz_kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # main|pre
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    # 목록 화면이 payload를 다 펼치지 않고도 정렬·경고할 수 있게 꺼내 둔다.
    review_flagged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slides_unused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class AssetGrab(Base):
    """강의 파일 요청 기록. 자동 첨부/열기/받기를 모두 포함하며 전송 완료가 아니다.

    여러 파일을 한 종류로 묶고 count는 서명 URL 또는 모아받기 확인 요청 횟수다.
    서명 URL은 유효기간 동안 재사용할 수 있어 실제 파일 전송 횟수와 다르다."""

    __tablename__ = "asset_grab"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)  # GRABBABLE_KINDS
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (Index("ix_asset_grab_user_lecture", "user_id", "subject", "run_id"),)


class LectureWaive(Base):
    """관리자가 해당 없다고 닫은 강의 체크 항목. 자료가 나중에 올라와도 유지한다."""

    __tablename__ = "lecture_waive"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item: Mapped[str] = mapped_column(String(24), primary_key=True)  # CHECKLIST_ITEMS
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )
