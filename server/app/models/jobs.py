"""러너 일감의 상태, 큐, 진행 보고와 heartbeat."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now

# queued·running·held는 열린 일감이며 나머지는 종료 상태다.
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

# Quiz Bank(2026-10-04). 재료는 관리자가 ChatGPT 에서 받아 온 응답이고(`quiz_bank.raw_response`),
# 러너는 그것을 정리·검증·검토만 한다 — 만드는 것은 ChatGPT 다.
JOB_BANK = "bank"
JOB_KINDS = frozenset({JOB_PRE, JOB_MAIN, JOB_BANK})


class PrequizJob(Base):
    """관리자의 생성 요청과 로컬 러너의 진행 보고를 연결하는 일감.

    예습·복습·Quiz Bank를 kind로 구분하며 운영 테이블 이름 prequiz_job을 유지한다.
    stage는 러너가 보내는 진행 설명이고, 서버는 생성 프로세스를 직접 실행하지 않는다."""

    __tablename__ = "prequiz_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    # **올해** run_id다. 예습은 작년 필기로 만들지만 누르는 자리는 올해 강의다.
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # `pre` | `main` | `bank`. 기존 행을 위해 서버 기본값을 같이 준다 — 이미 서 있는
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
    # 자동 순위가 정한다(`jobs/queue.queue_priority` — 내일 예습 → 오늘
    # 복습 → 나머지). 사람이 옮긴 줄은 그 자동 순위보다 앞에서 갈리므로, 한 번
    # 맨 앞으로 보낸 편은 다음 날 순위가 바뀌어도 앞에 남는다.
    queue_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 사람이 「멈추기」를 눌렀다. **도는 편은 서버가 못 멈춘다** — 만드는 것은
    # 노트북의 하위 프로세스이고 서버는 그 프로세스를 모른다. 그래서 여기 적어
    # 두고, 러너가 진행을 적으러 올 때(20초마다) 받아 가 자기 자식을 죽인다.
    # 러너가 안 붙어 있으면 이 값은 그대로 남는다 — 그때는 사람이 한 번 더 눌러
    # 강제로 내린다(`move`가 아니라 `cancel`이 그것을 판정한다).
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 러너가 만들기 전에 사람에게 묻는 말. **비어 있지 않으면 이 줄은 `held` 로 서서
    # 사람의 답을 기다린다.** 2026-09-24 관리자 지시 — 「표시해뒀다가 돌리게 될 때
    # 알림이 뜨고 선택하게」. 무엇을 물을지는 러너가 안다(`runner.watch.strategy_question`)
    # — 족보·교수 분석이 노트북에 있어서다.
    ask: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 사람이 고른 전략(`기본`·`족보`·`필기`·`사진`). 빈 문자열이면 자동 판정이다.
    # 러너가 이 값을 `--strategy` 로 넘긴다.
    strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
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
    """러너의 마지막 응답 시각과 작업 상태. claim과 진행 갱신 양쪽에서 기록한다."""

    __tablename__ = "runner_beat"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    busy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
