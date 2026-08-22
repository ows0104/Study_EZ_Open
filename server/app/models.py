"""서버가 들고 있는 전부.

읽기 전용이 원칙이다. 로컬 러너가 채우고 웹이 읽는다. 사용자가 쓰는 표는 둘뿐이다 —
`quiz_attempt`(Pre-Quiz 웹 풀이의 채점 결과)와 `asset_grab`(파일을 받아 갔다).

**키는 언제나 `(subject, run_id)` 복합이다.** `run_id`는 `260813_03` 같은
날짜_교시라서 과목을 포함하지 않는다. 같은 교시에 여러 과목이 열리므로
`run_id` 단독은 학기 안에서 유일하지 않다.
"""

from __future__ import annotations

from datetime import date as Date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date as SADate,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# 산출물 계약이 정한 다섯 가지. 여기 없는 종류가 필요해지면 계약을 먼저 고친다.
ASSET_KINDS = frozenset(
    {
        "notes_current",  # 올해 필기 PDF
        "notes_prev",  # 작년 필기 PDF (Pre-Quiz·예습용)
        "main_apkg",  # <강의>.apkg
        "pre_apkg",  # <강의>_예습.apkg
        "media",  # media/*.png — 슬라이드 렌더
    }
)

# 관리자가 강의마다 채우는 다섯 칸. 사용자 화면의 점 둘이 이것을 두 갈래로 묶는다 —
# 앞 셋이 예습, 뒤 둘이 복습이다.
CHECKLIST_ITEMS = ("notes_prev", "preview", "pre_apkg", "notes_current", "main_apkg")

# "받아 갔다"로 셀 종류. `media`는 뺀다 — 오답 해설이 근거 슬라이드를 띄울 때
# 서명이 자동으로 나가므로, 세면 사용자가 받은 것이 아니라 해설을 본 것이 된다.
GRABBABLE_KINDS = frozenset({"notes_prev", "notes_current", "pre_apkg", "main_apkg"})


class Profile(Base):
    """계정. 불리언 둘이다.

    `is_admin`은 올릴 수 있는 사람인가, `is_approved`는 볼 수 있는 사람인가.
    소유권 검사는 없다 — 콘텐츠가 모두에게 동일하므로 "볼 수 있는가"까지만
    가르면 된다.

    가입은 누구나 하지만 승인 전에는 아무것도 안 보인다. Supabase에 가입한
    사람과 이 학년 학생이 같지 않기 때문이고, 그 판단은 사람이 한다.
    """

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


class TimetableEvent(Base):
    """교실이 배포한 공식 시간표. 캘린더가 그리는 것은 이 표다.

    파이프라인 산출물을 기다리지 않는다. 강의가 아닌 칸(시험·휴일·자율학습)도
    들어 있고, 그것들은 붙일 자료가 없다.
    """

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
    """시간표의 과목 이름 ↔ Synology 폴더 이름.

    시간표는 "질병의 병리학적 이해"라 쓰고 필기 폴더는 "병리학"이다. 어느 쪽도
    상대를 유추할 수 없으므로 관리자가 한 번 이어 준다.

    이어 두면 **한 교시에 여러 과목이 열릴 때 매칭이 확실해진다.** 선택형
    과목은 같은 날짜·교시에 강의가 셋씩 열리는데, 그때 제목만으로 가르는 것보다
    과목으로 먼저 좁히는 편이 훨씬 안전하다.
    """

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


class Preview(Base):
    """예습 대화 링크.

    `share_url`이 기본이다 — 퀴즈를 만들 때 쓰는 링크이고 모두에게 보인다.
    `conversation_url`(`/c/`)도 결국 모두에게 줄 것이며, 지금 관리자에게만
    나가는 것은 그 링크가 아직 불안정해서다(`STUDYEZ_SHOW_CONVERSATION_URL`).
    """

    __tablename__ = "preview"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="chatgpt")
    share_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class UserPreview(Base):
    """사람마다 따로 가진 예습 대화.

    `preview`와 나눠 둔 이유는 **주인이 다르기 때문이다.** 그쪽은 강의당 하나이고
    반 전체가 같은 것을 읽는다(`share_url`). 이것은 사람당 하나이고 만든 사람만
    연다 — `/c/` 주소는 원래 만든 계정에서만 열리므로 남에게 주어도 죽은 링크다.

    프롬프트도 갈린다. 기본 링크는 문구가 고정이고, 개인 대화는 각자
    `profile.preview_prompt`로 묻는다.

    **관리자가 기본 링크를 만들면 그 `/c/`는 여기에도 함께 남는다.** 같은 대화가
    반에게는 `share_url`로, 만든 사람에게는 이어서 대화할 수 있는 자리로 쓰인다.
    """

    __tablename__ = "user_preview"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class PreItem(Base):
    """`pre_items.final.json`의 예습 카드 하나.

    **자유회상 플래시카드다.** 한동안 5지선다·단답이었고 서버가 문자열로 채점했는데,
    파이프라인이 pdf2anki로 갈리면서 카드가 Anki와 같은 앞면/뒷면이 되었다. 긴 산문
    답을 문자열로 맞히라고 하면 전원이 틀리므로, 채점은 **읽어 보고 본인이** 한다.

    `answer`와 `explanation`은 그래도 문항과 함께 안 내려보낸다. 답을 편 사람만
    `reveal`로 받아 가고, 그래야 `quiz_attempt`의 「맞았다」가 뜻을 갖는다.
    """

    __tablename__ = "pre_item"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "c001"
    ord: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # basic | cloze | ox. 푸는 방식은 셋 다 같고 화면이 꼴만 달리 그린다.
    qtype: Mapped[str] = mapped_column(String(16), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 왜 이것이 「꼭 반드시」인가. spine·vocabulary·mechanism·clinical·repeated.
    focus: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # 무엇을 막는 카드인가. term·abbrev·mechanism·taxonomy·clinical·number 등.
    card_type: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    exam_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="lecture")
    source_anchor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
        Index("ix_pre_item_lecture", "subject", "run_id"),
    )


class QuizAttempt(Base):
    """Pre-Quiz 웹 풀이의 결과. 사용자별로 쓰이는 유일한 표다.

    **`correct`는 본인이 찍은 것이다.** 서버가 판정한 것이 아니다. 자유회상
    카드라 대조할 문자열이 없고, 그래서 「답을 펴 보고 맞았다고 했다」가 여기
    남는 전부다. 화면이 이 값을 서버 판정처럼 그리면 안 된다.

    지금 Pre-Quiz는 apkg로 배급하는 것이 먼저이고 웹 풀이는 그 뒤에 있다.
    "오늘 놓친 것"이 여기서 나온다.
    """

    __tablename__ = "quiz_attempt"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (Index("ix_quiz_attempt_user_lecture", "user_id", "subject", "run_id"),)


class AssetGrab(Base):
    """이 사람이 이 강의의 이 종류를 받아 갔다.

    **덱이 "했다"를 처음으로 말하게 하는 표다.** apkg는 Anki에서 풀리므로 서버가
    풀이를 볼 방법이 없지만, 파일이 나가려면 `sign_file`에서 서명을 받아 가야
    하고 그 서명은 사용자가 버튼을 눌러야 나간다. 그래서 여기 있는 것은 정확히는
    *받아 갔다*지 *풀었다*가 아니다 — 화면에서 그 이상으로 읽히게 그리지 않는다.

    **파일이 아니라 종류로 센다.** 같은 종류가 여러 파일일 수 있고(필기가 두
    권으로 갈린 강의), 점은 "이 갈래를 손댔나"만 알면 된다.

    서명 URL은 TTL 동안 재사용되므로 `count`는 내려받은 횟수가 아니라 **버튼을
    누른 횟수**에 가깝다. 지금 화면은 안 쓰고, 나중에 "다시 받으러 온 강의"를
    볼 때를 위해 남긴다.
    """

    __tablename__ = "asset_grab"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)  # GRABBABLE_KINDS
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (Index("ix_asset_grab_user_lecture", "user_id", "subject", "run_id"),)


class LectureWaive(Base):
    """관리자가 "이 강의엔 해당 없음"으로 닫은 체크 칸.

    신설 강의에는 작년 필기가 없다. 그런 칸을 영영 미완으로 두면 관리자 화면이
    빨간 배경이 되고, 배경이 된 경고는 아무것도 못 막는다.

    **자료가 나중에 올라와도 지우지 않는다.** 올라온 것은 `asset`이 이미 알고
    있고, 체크 칸은 "올라왔거나, 닫혔거나"로 판정한다. 관리자가 직접 되돌리기
    전까지 이 줄은 그대로 남는다.
    """

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
