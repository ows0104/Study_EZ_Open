"""서버가 들고 있는 전부.

읽기 전용이 원칙이다. 로컬 러너가 채우고 웹이 읽는다. 사용자가 쓰는 표는 다섯뿐이다 —
웹 풀이의 채점과 일정(`quiz_attempt`·`main_attempt`), 그 되돌리기 기록
(`pre_review_log`·`main_review_log`), 그리고 `asset_grab`(파일을 받아 갔다).

**키는 언제나 `(subject, run_id)` 복합이다.** `run_id`는 `260813_03` 같은
날짜_교시라서 과목을 포함하지 않는다. 같은 교시에 여러 과목이 열리므로
`run_id` 단독은 학기 안에서 유일하지 않다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as Date

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Date as SADate,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


# 산출물 계약이 정한 다섯 가지. 여기 없는 종류가 필요해지면 계약을 먼저 고친다.
ASSET_KINDS = frozenset(
    {
        "notes_current",  # 올해 필기 PDF
        "notes_prev",  # 작년 필기 PDF (Pre-Quiz·예습용)
        "main_apkg",  # <강의>.apkg
        "pre_apkg",  # <강의>_예습.apkg
        "media",  # 예습 슬라이드 렌더. 이름이 갈래를 안 말하는 것은 역사다
        "main_media",  # 복습 슬라이드 렌더
    }
)

# 근거 슬라이드. **갈래를 갈라 둔다(2026-08-31).**
#
# 예습 슬라이드는 **작년** run 에서 와 놓고 올해 강의의 이름으로 올라간다. 복습
# 슬라이드를 같은 `media` 로 얹으면 `(subject, run_id, media, slide_no)` 가 둘이
# 되고, `prequiz.slide_url` 의 `db.scalar` 가 아무거나 집는다 — 예습 오답 해설이
# 조용히 엉뚱한 슬라이드를 띄운다. 아무 데서도 안 터지는 종류의 고장이다.
#
# 예습 쪽 이름을 `pre_media` 로 못 바꾼 것은 운영 DB 에 이미 `media` 로 쌓여
# 있어서다. 이 저장소의 마이그레이션은 칼럼을 붙일 뿐 값을 옮기지 않는다
# (`app/cli.py`). 이름이 갈래를 안 말하는 자리가 여기 하나 남는다.
SLIDE_KINDS = {"pre": "media", "main": "main_media"}

# 관리자가 강의마다 채우는 다섯 칸. 사용자 화면의 점 둘이 이것을 두 갈래로 묶는다 —
# 앞 셋이 예습, 뒤 둘이 복습이다.
CHECKLIST_ITEMS = ("notes_prev", "preview", "pre_apkg", "notes_current", "main_apkg")

# "받아 갔다"로 셀 종류. `media`는 뺀다 — 오답 해설이 근거 슬라이드를 띄울 때
# 서명이 자동으로 나가므로, 세면 사용자가 받은 것이 아니라 해설을 본 것이 된다.
GRABBABLE_KINDS = frozenset({"notes_prev", "notes_current", "pre_apkg", "main_apkg"})


class Profile(Base):
    """계정. **어느 앱을 쓸 수 있는지는 여기 없다** — `app_grant`가 든다.

    `is_admin`은 플랫폼 전체를 관리하는 사람이다. 앱마다 갈라지지 않으므로
    여기 남았다.

    `is_approved`는 **남아 있지만 아무도 안 읽는다.** 2026-09-06에 그 값이
    `app_grant(studyez)` 줄로 옮겨 갔고(`cli.backfill_app_grants`), 칼럼을 안 지운
    것은 되돌릴 일이 생겼을 때 값이 없으면 못 되돌리기 때문이다.
    한 학기쯤 지나고 떼면 된다.
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
    연다 — AI의 개인 대화 주소는 원래 만든 계정에서만 열리므로 남에게 주어도 죽은 링크다.

    프롬프트도 갈린다. 기본 링크는 문구가 고정이고, 개인 대화는 각자
    `profile.preview_prompt`로 묻는다.

    **관리자가 기본 링크를 만들면 그 `/c/`는 여기에도 함께 남는다.** 같은 대화가
    반에게는 `share_url`로, 만든 사람에게는 이어서 대화할 수 있는 자리로 쓰인다.
    """

    __tablename__ = "user_preview"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="chatgpt")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class _QuizItem:
    """웹에서 푸는 문항 한 장. **예습과 복습이 같은 모양이다.**

    **자유회상 플래시카드다.** 한동안 5지선다·단답이었고 서버가 문자열로 채점했는데,
    파이프라인이 pdf2anki(지금의 `quizgen/`)로 갈리면서 카드가 Anki와 같은 앞면/뒷면이 되었다. 긴 산문
    답을 문자열로 맞히라고 하면 전원이 틀리므로, 채점은 **읽어 보고 본인이** 한다.

    `answer`와 `explanation`은 그래도 문항과 함께 안 내려보낸다. 답을 편 사람만
    `reveal`로 받아 가고, 그래야 시도 기록의 「맞았다」가 뜻을 갖는다.

    **표를 둘로 나눈 이유는 모양이 달라서가 아니다.** `item_id`가 겹친다 — 두
    갈래 다 `c001`부터 센다. 한 표에 담으려면 갈래를 기본키에 넣어야 하는데, 이
    저장소의 마이그레이션은 칼럼을 붙일 뿐 기본키를 못 바꾼다(`app/cli.py`).
    칼럼은 그래서 여기 한 번만 적는다 — 두 곳에 적으면 한쪽에만 붙는 날이 온다.
    """

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "c001"
    ord: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # basic | cloze | ox. 푸는 방식은 셋 다 같고 화면이 꼴만 달리 그린다.
    qtype: Mapped[str] = mapped_column(String(16), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 예습은 **왜 이것이 「꼭 반드시」인가**(spine·vocabulary·mechanism·clinical·
    # repeated), 복습은 등급(`importance`)이 온다. 파이프라인이 그 갈림을 안다.
    focus: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # 무엇을 막는 카드인가. term·abbrev·mechanism·taxonomy·clinical·number 등.
    card_type: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    exam_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="lecture")
    source_anchor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            ForeignKeyConstraint(
                ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
            ),
            Index(f"ix_{cls.__tablename__}_lecture", "subject", "run_id"),
        )


class PreItem(_QuizItem, Base):
    """`pre_items.final.json`의 예습 카드 하나."""

    __tablename__ = "pre_item"


class MainItem(_QuizItem, Base):
    """`main_items.final.json`의 복습 카드 하나.

    **2026-08-31에 생겼고, 그 전에 구운 편에는 없다.** 파이프라인이 이 파일을 내기
    시작한 것이 그날이라 기존 39편은 다시 돌려야 채워진다. 비어 있는 강의에서는
    화면이 웹 풀이를 아예 안 그린다 — 덱만 있는 편과 같은 자리다.
    """

    __tablename__ = "main_item"


class _Attempt:
    """웹 풀이의 카드 한 장. **`correct`는 본인이 찍은 것이다.**

    서버가 판정한 것이 아니다. 자유회상 카드라 대조할 문자열이 없고, 그래서
    「답을 펴 보고 맞았다고 했다」가 여기 남는 전부다. 화면이 이 값을 서버
    판정처럼 그리면 안 된다.

    **2026-09-18에 「결과 한 줄」이 「카드 한 장」이 되었다.** 그 전까지 이 줄은
    `correct` 불리언 하나로 한 번의 채점만 들었고, 반복은 apkg를 받아 간 사람의
    안키가 들었다. 지금은 일정이 여기 있다 — `state`부터 `due_at`까지가 그것이고
    값을 정하는 것은 `app/srs.py` 하나다.

    `correct`는 남겨 두었다. 넷 중 `again`이면 거짓이고 나머지면 참이다.
    「오늘 놓친 것」과 진행 수가 그 값으로 서 있고, 일정이 없던 옛 줄에서도
    그 둘은 계속 나와야 한다.

    문항 표와 같은 이유로 갈래마다 표가 따로다 — `item_id`가 겹친다.
    """

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # ── 여기부터가 일정이다(2026-09-18). 값을 정하는 것은 `app/srs.py` 하나뿐이고,
    # 이름도 그쪽 `Card` 와 같다. **한 줄이 한 카드의 전부라 되돌리기가 이 일곱
    # 칼럼을 그대로 적어 두면 된다**(`_ReviewLog`).
    #
    # 옛 줄에는 이 칼럼이 없다. 기본값이 new·0·2.5 이므로 그런 줄은 「한 번
    # 찍었지만 일정은 아직 없다」로 읽힌다 — `correct` 는 그대로 있으므로
    # 「놓친 것」과 진행 수는 옛 줄에서도 계속 나온다.
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="new")
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 언제 다시 낼 것인가. `None` 이면 아직 일정이 없는 것이라 바로 낸다.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            Index(f"ix_{cls.__tablename__}_user_lecture", "user_id", "subject", "run_id"),
            # 「지금 낼 것」을 고르는 질의가 이 순서로 훑는다.
            Index(f"ix_{cls.__tablename__}_due", "user_id", "due_at"),
        )


class QuizAttempt(_Attempt, Base):
    """Pre-Quiz 웹 풀이의 결과. 사용자가 쓰는 몇 안 되는 표 중 하나다.

    2026-08-23부터 화면에서는 **웹 풀이가 먼저다** — Pre-Quiz를 누르면 전용 창이
    열리고 덱은 그 옆에서 받는다. 그래서 이 표는 전보다 더 차게 된다.
    "오늘 놓친 것"이 여기서 나온다.

    이름에 갈래가 안 붙어 있는 것은 역사다. 운영 DB에 이미 이 이름으로 쌓여 있다.
    """

    __tablename__ = "quiz_attempt"


class MainAttempt(_Attempt, Base):
    """Main-Quiz 웹 풀이의 결과.

    **덱과 진행이 갈린다.** 복습 덱은 Anki에서 3패스로 돌고 그 진행은 Anki가
    든다. 여기 쌓이는 것은 웹에서 푼 몫뿐이라, 둘을 더해 「몇 번 봤다」로 읽으면
    안 된다.
    """

    __tablename__ = "main_attempt"


class _ReviewLog:
    """찍은 한 번. **찍기 전의 일정을 그대로 적어 둔다.**

    되돌리기(2026-09-18 관리자 지시 — 「이전으로 돌아가는 기능」)를 위해 생겼다.
    안키의 undo 와 같은 자리이고, 같은 방식이다: 되돌릴 값을 **찍는 쪽이**
    남겨 둔다.

    ## 왜 다시 계산하지 않는가

    SM-2 는 한쪽으로만 간다. `interval_days` 를 쉬움도로 나누면 반올림한
    자리가 안 돌아오고, 잊어서 하루로 깎인 카드는 깎기 전 간격이 아예 사라진다.
    **되돌리기는 계산이 아니라 기억이다.**

    ## 되돌릴 것이 없던 자리까지 적는다

    `had_attempt` 가 거짓이면 그 찍기가 이 카드의 **첫 줄을 만든 것**이다.
    되돌릴 때 값을 되쓰는 것으로는 안 되고 줄을 지워야 한다 — 안 그러면
    「몇 장 봤다」가 안 본 카드를 센다.

    문항 표·시도 표와 같은 이유로 갈래마다 표가 따로다(`item_id` 가 겹친다).
    여기서는 대리키를 쓸 수 있으니 한 표에 `kind` 칼럼을 둘 수도 있었지만,
    그러면 이 파일에서 갈래를 가르는 방식이 두 가지가 된다.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    #: again | hard | good | easy. `srs.GRADES` 와 같다.
    grade: Mapped[str] = mapped_column(String(8), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    had_attempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prev_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prev_state: Mapped[str] = mapped_column(String(10), nullable=False, default="new")
    prev_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    prev_reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            # 되돌리기는 언제나 「이 사람 이 강의의 마지막 줄」을 집는다.
            Index(f"ix_{cls.__tablename__}_undo", "user_id", "subject", "run_id", "id"),
        )


class PreReviewLog(_ReviewLog, Base):
    """Pre-Quiz 웹 풀이의 되돌리기 기록."""

    __tablename__ = "pre_review_log"


class MainReviewLog(_ReviewLog, Base):
    """Main-Quiz 웹 풀이의 되돌리기 기록."""

    __tablename__ = "main_review_log"


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


# 일감의 상태. `queued`·`running`이 열린 것이고, 나머지는 끝난 것이다.
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
# 자동으로 세웠지만 그날의 상한을 넘어 사람을 기다리는 줄. **러너는 안 집어 간다.**
# 상한에 걸린 편을 아예 안 세우면 화면에 아무것도 안 남아서, 만들어지지 않은 것과
# 만들 생각이 없는 것이 같은 모양이 된다.
JOB_HELD = "held"
# 사람이 지우거나 멈춘 줄. **실패와 갈라 둔다** — 실패는 고칠 것이 있다는 뜻이고
# 이것은 사람이 안 만들기로 한 것이다. 같은 자리에 적으면 화면의 실패 수가
# 「고쳐야 할 것」을 못 세고, 다음 사람이 없는 고장을 찾으러 간다.
JOB_CANCELED = "canceled"
JOB_OPEN = frozenset({JOB_QUEUED, JOB_RUNNING, JOB_HELD})

# 자동으로 세우는 일감의 하루 상한(관리자 지시, 2026-09-01). 사람이 누른 것은
# 여기 안 든다 — 상한은 「아무도 안 봤는데 돈이 나가는 것」을 막는 장치다.
JOB_AUTO_DAILY_CAP = 6

# 어디서 온 일감인가. 버튼은 사람이 누른 것, 자동은 재료가 도착해서 선 것.
JOB_BUTTON = "button"
JOB_AUTO = "auto"

# 무엇을 만드는 일감인가. 예습(작년 필기 + 예습 대화)과 복습(올해 필기).
JOB_PRE = "pre"
JOB_MAIN = "main"
JOB_KINDS = frozenset({JOB_PRE, JOB_MAIN})


class PrequizJob(Base):
    """관리자가 「덱 만들기」를 누른 것. **여기도 방향이 반대다.**

    `preview`와 같은 이유다 — 누르는 것은 사람이고 사람은 `/admin` 화면에 있다.
    그런데 만드는 것은 노트북이다(`claude -p` 빈 세션 넷과 SynologyDrive의 PDF가
    거기 있다). 그래서 이 표가 둘 사이의 우편함이 된다.

    한동안 이 자리를 야간 스케줄러가 대신했는데, 조용히 실패하는 것이 문제였다 —
    쓸기가 2026-08-18부터 닷새 동안 「올릴 것이 없다」로 끝나면서 종료 코드 0을
    냈고, 아무도 몰랐다. **사람이 누른 일감은 끝나지 않으면 화면에 남는다.**

    `stage`는 사람이 읽는 한 줄이다. 러너가 하위 프로세스의 `── ` 줄을 그대로
    올려 준다 — 15분이 걸리는 일이라 "도는 중"만으로는 멈춘 것과 구별이 안 된다.

    **표 이름은 예습밖에 없던 때의 것이다.** 2026-08-24에 복습 덱도 같은 우편함을
    쓰게 되면서 `kind`가 붙었다. 이름을 안 바꾼 이유는 마이그레이션 도구가 없어서다
    (`app.cli` 첫머리) — 표를 갈아 끼우는 값이 이름 하나보다 크다.
    """

    __tablename__ = "prequiz_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    # **올해** run_id다. 예습은 작년 필기로 만들지만 누르는 자리는 올해 강의다.
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # `pre` | `main`. 나중에 붙은 칼럼이라 서버 기본값을 같이 준다 — 이미 서 있는
    # DB에 `app.cli`가 이 값으로 채워 넣는다.
    kind: Mapped[str] = mapped_column(
        String(8), nullable=False, default=JOB_PRE, server_default=JOB_PRE
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_QUEUED)
    stage: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 사람이 「다시 만들기」를 누른 것인가. **러너가 이걸 봐야 한다** — 안 넘기면
    # `runner.prequeue`가 이미 만든 편을 `done`으로 보고 건너뛰고, 그러면 화면에는
    # 「덱을 못 만들었다」가 적힌다. 만든 것이 있는데 안 만든 것처럼 보이는 자리다.
    force: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # `button` | `auto`. **상한이 자동에만 걸리므로 갈라 둔다** — 사람이 누른 것은
    # 몇 편째든 선다.
    origin: Mapped[str] = mapped_column(
        String(8), nullable=False, default=JOB_BUTTON, server_default=JOB_BUTTON
    )
    # 어느 일꾼이 집어 갔나(`w1`·`w2`). 러너가 여럿이 되면서 필요해졌다 — 끊겼다
    # 붙은 일꾼이 **자기가 잡고 있던 편**을 다시 잡아야 하고, 남의 편을 뺏으면
    # 같은 편을 둘이 만든다.
    worker: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    # 몇 단계 중 몇 번째인가. `stage`(사람이 읽는 한 줄)만으로는 얼마나 남았는지를
    # 화면이 말할 수 없다.
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stage_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 러너가 지난 편들의 실측으로 셈한 남은 시간(초). 0이면 아직 모른다.
    eta_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 이 시각 전에는 아무도 못 집어 간다. **모델 한도로 멈춘 편이 여기 선다** —
    # 러너가 「resets 1:40pm」을 읽어 적어 두면, 그때까지 큐에 서 있다가 저절로
    # 이어진다. 기다림을 러너 메모리가 아니라 큐가 드는 까닭은 러너가 재시작하면
    # 메모리가 날아가고, 그러면 풀리지도 않은 한도에 다시 부딪히기 때문이다.
    resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 사람이 줄에서 옮긴 자리. 작을수록 먼저다. **0이 안 건드린 것이고**, 그때는
    # 자동 순위가 정한다(`routes/prequiz_jobs.queue_priority` — 내일 예습 → 오늘
    # 복습 → 나머지). 사람이 옮긴 줄은 그 자동 순위보다 앞에서 갈리므로, 한 번
    # 맨 앞으로 보낸 편은 다음 날 순위가 바뀌어도 앞에 남는다.
    queue_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 사람이 「멈추기」를 눌렀다. **도는 편은 서버가 못 멈춘다** — 만드는 것은
    # 노트북의 하위 프로세스이고 서버는 그 프로세스를 모른다. 그래서 여기 적어
    # 두고, 러너가 진행을 적으러 올 때(20초마다) 받아 가 자기 자식을 죽인다.
    # 러너가 안 붙어 있으면 이 값은 그대로 남는다 — 그때는 사람이 한 번 더 눌러
    # 강제로 내린다(`move`가 아니라 `cancel`이 그것을 판정한다).
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 지금 단계가 언제 시작했나. 한 단계가 10분 넘게 이어지는 일이 정상이라,
    # **편 전체의 경과만으로는 멈춘 것과 오래 걸리는 것이 구별되지 않는다.**
    stage_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
        Index("ix_prequiz_job_state", "state", "created_at"),
        Index("ix_prequiz_job_lecture", "subject", "run_id"),
    )


class RunnerBeat(Base):
    """러너가 살아 있다고 알린 시각. 줄 하나짜리 표다.

    **일감이 `queued`인 채 안 움직이는 이유가 둘이라 가른다** — 러너가 안 떠
    있거나, 떠 있는데 앞의 편을 만드는 중이거나. 화면이 둘을 같은 모양으로
    보여 주면 사람이 노트북을 열어 봐야 한다.
    """

    __tablename__ = "runner_beat"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    busy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ─────────────────────────────────────────────────────────────────────
# 기생충학 땡시(Spotter_Quiz). 같은 계정, 다른 문.
#
# **이 앱은 `is_approved`를 보지 않는다.** Study_EZ가 내보내는 것은 남이 만든
# 강의 필기라서 「이 학년 학생인가」를 사람이 확인해야 하지만, 땡시는 우리가
# 만든 문항이고 사진도 실습 정리본이다. 가입만 하면 열린다 — 라우터가
# `require_approved_user` 대신 `get_current_user`를 쓰는 것이 그 차이의 전부다.
#
# 표 이름에 `spotter_`를 붙인 것은 DB를 함께 쓰기 때문이다. `quiz_attempt`는
# 이미 Study_EZ의 Pre-Quiz가 쓰고 있어서 이름이 겹치면 안 된다.
# ─────────────────────────────────────────────────────────────────────

# 제보의 갈래. 화면의 선택지와 같은 순서다.
SPOTTER_REPORT_KINDS = ("answer", "image", "explanation", "options", "other")

SPOTTER_REPORT_OPEN = "open"
SPOTTER_REPORT_RESOLVED = "resolved"
SPOTTER_REPORT_WONTFIX = "wontfix"
SPOTTER_REPORT_STATUSES = frozenset(
    {SPOTTER_REPORT_OPEN, SPOTTER_REPORT_RESOLVED, SPOTTER_REPORT_WONTFIX}
)

# 한 사람이 들고 다니는 기록의 수. 브라우저에 쌓던 시절과 같은 수다.
SPOTTER_RECORD_KEEP = 30

# **몇 명이 걸리면 「쌓였다」고 볼 것인가.** 선을 넘으면 세 가지가 한꺼번에
# 일어난다 — 관리자 화면에 빨간 줄이 서고, 그 문항이 새 세트에서 빠지고(격리),
# 진리탐구 게시판에 글타래가 선다.
#
# **한 명이면 넘은 것으로 본다.** 둘을 기다리던 시절의 생각은 「한 사람이 잘못
# 읽은 것과 둘이 같은 자리에서 멈춘 것은 다르다」였는데, 기다리는 값이 더
# 비쌌다. 문항은 자동 생성이라 실제로 틀린 것이 남아 있고, 그것을 알아본
# 첫 사람은 대개 맞게 본 사람이다. 둘째가 올 때까지 그 문항은 계속 나가고,
# 둘째가 영영 안 오는 문항도 있다 — 드물게 나오는 문항일수록 그렇다.
#
# 잘못 걸린 문항은 관리자가 글타래를 닫으면 그날로 돌아온다. 되돌리기 싼 쪽의
# 실수를 고르는 것이 맞다.
#
# 세는 것은 제보의 수가 아니라 **사람의 수**다. 한 사람이 한 문항에 한 줄이라
# (`uq_spotter_report_user_question`) 열린 줄을 세면 그대로 사람 수가 된다.
# 선을 옮기려면 이 한 줄만 고친다.
SPOTTER_ALERT_MIN = 1

# 글타래가 무엇에 걸렸는가. 문항 하나가 이상한 것과 사진 한 장이 이상한 것은
# 고치는 일이 달라서(보기를 고친다 / 사진을 다시 자른다) 따로 선다.
SPOTTER_THREAD_QUESTION = "question"
SPOTTER_THREAD_IMAGE = "image"
SPOTTER_THREAD_KINDS = (SPOTTER_THREAD_QUESTION, SPOTTER_THREAD_IMAGE)

# 댓글 한 줄의 길이. 게시판이지 논문이 아니다.
SPOTTER_COMMENT_MAX = 2000


class SpotterRecord(Base):
    """땡시 한 판의 결과. `localStorage`의 `para_records`가 여기로 왔다.

    **점수만 남기고 문항은 안 남긴다.** 화면이 쓰는 것은 「언제·무슨 모드·몇
    점」 세 가지뿐이고, 어느 문항을 틀렸는지는 `spotter_wrong`이 따로 든다 —
    오답노트는 판이 아니라 문항을 따라다니기 때문이다. 다음 판에 맞히면
    빠져야 하는데, 판마다 목록을 남기면 어느 판의 것이 참인지 알 수 없다.
    """

    __tablename__ = "spotter_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="exam")  # exam|study
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_spotter_record_user", "user_id", "created_at"),)


class SpotterWrong(Base):
    """아직 못 맞힌 문항. 맞히는 순간 줄이 사라진다.

    **문항 id는 내용에서 뽑은 해시다**(`scripts/build_web.py`의 `question_id`).
    사진이 늘거나 표본이 추가돼도 남은 문항의 id는 그대로라, 문항 DB를 다시
    구워도 이 표가 엉뚱한 문제를 가리키지 않는다. 순번을 썼다면 앞에 사진 한
    장만 끼어도 전부 밀렸을 것이다.

    그래도 문항이 정말 사라지는 경우(표본을 지웠다)는 남는다. 그때는 화면이
    DB에 없는 id를 그냥 버린다 — 서버가 청소하지 않는 것은, 청소하려면 서버가
    문항 DB의 내용을 알아야 하고 그러면 이 표가 DB 재빌드에 묶이기 때문이다.
    """

    __tablename__ = "spotter_wrong"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    missed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class SpotterReport(Base):
    """「이 문항 이상해요」. 문항이 자동 생성이라 반드시 필요한 표다.

    **한 사람이 한 문항에 한 줄이다**(unique). 같은 문항을 다시 제보하면 그
    줄을 고쳐 쓴다 — 목록에 같은 문항이 여러 줄로 늘어서면 몇 명이 걸렸는지가
    안 보이고, 그걸 세는 것이 이 표의 쓸모다.

    **`stem`·`answer`·`image`는 제보한 사람이 본 것을 그대로 뜬 것이다.**
    지금의 문항이 아니다. 문항 DB를 다시 구우면서 그 문항이 사라져도 제보는
    읽을 수 있어야 하고, 무엇보다 "고쳤다"를 판단하려면 제보 당시의 문면이
    있어야 한다. 화면이 이 값을 현재 문항처럼 그리면 안 된다.
    """

    __tablename__ = "spotter_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question_id: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 제보 당시의 문면. 위 설명을 보라 — 현재 문항이 아니다.
    stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 사진 파일명만, 쉼표로 이어서. 바로 위의 `image`는 **사람이 읽는 줄**이라
    # 출처가 괄호로 붙어 있고, 이것은 **묶어 세는 값**이다.
    #
    # 둘로 나눈 까닭은 한 사진이 여러 문항에 쓰이기 때문이다. 「이 사진이
    # 흐리다」는 제보는 그 사진을 쓰는 문항마다 흩어져 들어와서, 문항으로만
    # 세면 어느 쪽도 임계값을 못 넘은 채 사진 하나가 계속 돌아다닌다.
    # 표시용 문자열을 갈라 읽는 대신 칼럼을 하나 둔다 — 화면에 붙이는 글이
    # 바뀔 때마다 세는 쪽이 조용히 틀리면 안 된다.
    images: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_REPORT_OPEN)
    admin_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_spotter_report_user_question"),
        Index("ix_spotter_report_triage", "status", "created_at"),
        Index("ix_spotter_report_question", "question_id"),
    )


class SpotterThread(Base):
    """진리탐구 게시판의 글타래. **사람이 세우지 않는다.**

    제보가 선(`SPOTTER_ALERT_MIN`)을 넘는 순간 서버가 세운다. 글을 쓰는
    단추를 두지 않은 것은, 이 게시판이 아무 이야기나 하는 자리가 아니라
    **여럿이 같은 자리에서 멈춘 문항만 모이는 자리**이기 때문이다. 무엇을
    올릴지 사람이 고르기 시작하면 판정이 두 벌이 된다.

    `kind`가 둘인 까닭은 고치는 일이 다르기 때문이다. 문항이 이상하면 보기나
    정답을 고치고, 사진이 이상하면 사진을 다시 자른다. 사진 글타래는 그 사진을
    쓰는 문항 **전부**를 한꺼번에 가리킨다.

    **문면은 여기에도 뜬다.** 제보와 같은 이유다 — 문항 DB를 다시 구워 그
    문항이 사라져도 글타래는 읽을 수 있어야 하고, 무엇을 두고 이야기했는지가
    남아야 한다.

    글타래가 열려 있는 동안 그 문항은 새 세트에서 빠진다(`/flagged`). 닫는
    것이 곧 다시 내보내는 것이라, 닫기 전에 문항을 고쳐 다시 구워야 한다.
    """

    __tablename__ = "spotter_thread"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_THREAD_QUESTION)
    # 문항 글타래면 question_id, 사진 글타래면 파일명.
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    images: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_REPORT_OPEN)
    # 관리자가 내린 결론. 닫을 때 한 줄 적는 자리다.
    verdict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("kind", "subject", name="uq_spotter_thread_subject"),
        Index("ix_spotter_thread_status", "status", "updated_at"),
    )


class SpotterComment(Base):
    """글타래에 달린 의견 한 줄.

    **지운 줄은 남긴다**(`deleted`). 대화가 오간 자리에서 한 줄만 사라지면
    남은 줄들이 무엇에 답한 것인지 알 수 없게 된다. 화면은 「지운 글입니다」로
    그리고 내용만 안 보인다.
    """

    __tablename__ = "spotter_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_spotter_comment_thread", "thread_id", "created_at"),)


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
    """이 사람이 이 앱을 쓸 수 있다.

    **`profile.is_admin`을 대신하지 않는다.** 저것은 플랫폼 전체를 관리하는
    사람이고(부트스트랩이 `STUDYEZ_ADMIN_EMAILS`에서 온다), 이 표는 「어느 앱에
    들어갈 수 있나」다. 둘을 한 자리에 합치면 앱을 더할 때마다 관리자 개념이
    갈라진다.

    `role`은 지금 `member`뿐이고 `admin`은 자리만 잡아 뒀다 — 앱 안에서 역할이
    갈라지는 날(조교·출제자 같은) 값을 더하면 되고, 문자열이라 그때 마이그레이션이
    필요 없다.
    """

    __tablename__ = "app_grant"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    app: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_MEMBER)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_app_grant_app", "app", "role"),)
