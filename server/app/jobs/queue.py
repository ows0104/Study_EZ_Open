"""일감의 공통 정책: 자동 등록, 하루 상한, 처리 순서.

claim과 관리자 목록은 같은 queue_order를 사용한다. 커밋은 호출자가 한다."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as Date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    JOB_AUTO,
    JOB_AUTO_DAILY_CAP,
    JOB_BANK,
    JOB_CANCELED,
    JOB_HELD,
    JOB_KINDS,
    JOB_MAIN,
    JOB_OPEN,
    JOB_PRE,
    JOB_QUEUED,
    Lecture,
    PrequizJob,
)

# 러너는 지금 한 대뿐이다. 여러 대가 되면 이름을 나눠야 하는데, 그때는 일감을
# 집어 가는 쪽도 같이 고쳐야 하므로 상수 하나로 묶어 둔다.
RUNNER_NAME = "local"

# 한 번에 몇 편까지 도는가(관리자 지시, 2026-09-01). **러너의 일꾼 수와 같은 값을
# 여기도 든다** — 러너가 몇이든 서버가 이보다 많이 내주지 않으면 겹쳐 도는 편이
# 이 수를 넘지 않는다. 편당 비용은 안 변하고 벽시계만 줄어든다.
MAX_RUNNING = 2

# 하루가 언제 바뀌는가. 표는 UTC로 적히고 사람은 한국 시각으로 센다.
KST_OFFSET = timedelta(hours=9)


def _kst_day_start() -> datetime:
    """오늘(한국 시각) 0시를 UTC로. 자동 상한을 세는 창이다."""
    now_kst = datetime.now(UTC) + KST_OFFSET
    return now_kst.replace(hour=0, minute=0, second=0, microsecond=0) - KST_OFFSET


# 큐가 세는 하루는 **새벽 5시에 바뀐다.** 자정으로 두면, 01시에 도는 러너에게는
# 몇 시간 뒤 강의의 예습이 「오늘 예습」(= 늦은 것)이 되어 뒤로 밀리고, 그 자리를
# 하루 더 남은 편이 가져간다. 5시로 두면 그 편이 새벽 내내 「내일 예습」으로 남는다.
#
# **이 값이 서는 근거는 짐작이 아니라 자리다** — 러너가 밤새 돈다는 것과, 강의가
# 아무리 일러도 9시라는 것. 그 사이 어디를 잘라도 같지만 5시를 골랐다.
QUEUE_DAY_START_HOUR = 5

# 자동 순위(관리자 지시, 2026-09-03). **작을수록 먼저다.**
#
#   ① 내일 예습 — 강의 전에 없으면 그 편의 쓸모가 통째로 없어진다
#   ② 오늘 복습 — 강의 직후 한 바퀴가 3패스의 첫 패스다
#   ③ 나머지  — 선 순서대로(id)
#
# 사람이 옮긴 자리(`queue_rank`)가 이보다 먼저 갈린다.
RANK_PRE_TOMORROW = 0
RANK_MAIN_TODAY = 1
RANK_REST = 2

# 화면이 「왜 이게 앞인가」를 그대로 말하는 자리. 없는 것은 빈 문자열이다 —
# 「보통」이라고 적으면 세 갈래가 다 뭔가 정해진 것처럼 보인다.
PRIORITY_LABELS = {RANK_PRE_TOMORROW: "내일 예습", RANK_MAIN_TODAY: "오늘 복습", RANK_REST: ""}


def auto_used_today(db: Session) -> int:
    """오늘 자동으로 **돌린** 일감 수. 상한이 무는 값이다.

    사람이 누른 것은 안 센다. 상한에 걸려 `held`로 선 것도 안 센다 — 그것은 아직
    아무것도 안 쓴 줄이고, 세어 버리면 일곱 번째 필기부터는 화면에 아무 자국도
    안 남는다.
    """
    rows = db.scalars(
        select(PrequizJob.id).where(
            PrequizJob.origin == JOB_AUTO,
            PrequizJob.state != JOB_HELD,
            PrequizJob.created_at >= _kst_day_start(),
        )
    ).all()
    return len(rows)


def study_today(now: datetime | None = None) -> Date:
    """큐가 세는 「오늘」. 한국 시각이고, 하루가 새벽 `QUEUE_DAY_START_HOUR`에 바뀐다."""
    now = now or datetime.now(UTC)
    return ((now + KST_OFFSET) - timedelta(hours=QUEUE_DAY_START_HOUR)).date()


def queue_priority(kind: str, lecture_date: Date | None, today: Date) -> int:
    """이 일감의 자동 순위. 강의 날짜를 모르면 나머지로 친다.

    **날짜만 본다.** 「내일 예습」은 내일 열리는 강의의 예습이지, 내일 만들 예습이
    아니다 — 만드는 것은 오늘 밤이다.
    """
    if lecture_date is None:
        return RANK_REST
    if kind == JOB_PRE and lecture_date == today + timedelta(days=1):
        return RANK_PRE_TOMORROW
    if kind in (JOB_MAIN, JOB_BANK) and lecture_date == today:
        return RANK_MAIN_TODAY
    return RANK_REST


def _lecture_days(db: Session, jobs: list[PrequizJob]) -> dict[tuple[str, str], tuple[Date, int]]:
    """일감이 가리키는 강의의 (날짜, 교시). 순위를 매기려면 이 둘이 있어야 한다."""
    if not jobs:
        return {}
    rows = db.execute(
        select(Lecture.subject, Lecture.run_id, Lecture.date, Lecture.slot).where(
            Lecture.run_id.in_({job.run_id for job in jobs})
        )
    ).all()
    return {(row.subject, row.run_id): (row.date, row.slot) for row in rows}


def queue_order(
    db: Session, jobs: list[PrequizJob], today: Date | None = None
) -> list[tuple[PrequizJob, int]]:
    """사람이 정한 queue_rank → 자동 순위 → 교시 → id 순으로 정렬한다.

    claim과 관리자 목록이 함께 사용한다. 나머지 순위(RANK_REST)는 교시를 무시하고
    먼저 요청한 순서를 유지한다."""
    today = today or study_today()
    days = _lecture_days(db, jobs)
    ranked = []
    for job in jobs:
        day, slot = days.get((job.subject, job.run_id), (None, 0))
        rank = queue_priority(job.kind, day, today)
        ranked.append((job, rank, slot if rank != RANK_REST else 0))
    ranked.sort(key=lambda row: (row[0].queue_rank, row[1], row[2], row[0].id))
    return [(job, rank) for job, rank, _slot in ranked]


def open_job_of(db: Session, subject: str, run_id: str, kind: str) -> PrequizJob | None:
    """이 편·이 갈래에 아직 안 끝난 일감. **중복을 막는 자리는 여기 하나다.**"""
    return db.scalars(
        select(PrequizJob)
        .where(
            PrequizJob.subject == subject,
            PrequizJob.run_id == run_id,
            PrequizJob.kind == kind,
            PrequizJob.state.in_(tuple(JOB_OPEN)),
        )
        .order_by(PrequizJob.created_at.desc())
    ).first()


def ensure_auto_job(db: Session, subject: str, run_id: str, kind: str, why: str) -> PrequizJob | None:
    """자료 업로드·예습 링크 저장에 따라 일감을 등록한다. 이미 열렸거나 취소된 편은 건너뛴다.

    자동 상한을 넘으면 held로 기록해 관리자에게 표시한다. 등록된 행은 flush만 하고
    업로드·링크와 한 트랜잭션이 되도록 호출자가 commit한다."""
    # Main Quiz는 ChatGPT 답을 저장할 때 bank 작업으로 접수한다.
    if kind not in JOB_KINDS or kind == JOB_MAIN:
        return None
    if open_job_of(db, subject, run_id, kind) is not None:
        return None
    # **사람이 지운 편은 다시 안 세운다.** 재료가 도착했다는 신호는 쓸기마다
    # 다시 온다(`publish`가 회차마다 `uploads/complete`를 두드린다) — 그러면
    # 지운 줄이 10분 뒤에 되살아나고, 지운 사람은 자기가 뭘 잘못 눌렀는지
    # 알 길이 없다. 다시 만들려면 그 덱 칸의 버튼을 누른다(그 길은 여기를
    # 안 지난다).
    canceled = db.scalars(
        select(PrequizJob.id).where(
            PrequizJob.subject == subject,
            PrequizJob.run_id == run_id,
            PrequizJob.kind == kind,
            PrequizJob.state == JOB_CANCELED,
        )
    ).first()
    if canceled:
        return None

    over = auto_used_today(db) >= JOB_AUTO_DAILY_CAP
    job = PrequizJob(
        subject=subject,
        run_id=run_id,
        kind=kind,
        state=JOB_HELD if over else JOB_QUEUED,
        stage=(f"오늘 자동 상한 {JOB_AUTO_DAILY_CAP}편을 다 썼다 — 만들려면 눌러라"
               if over else f"{why} — 러너를 기다리는 중"),
        requested_by="",
        origin=JOB_AUTO,
    )
    db.add(job)
    # **부르는 쪽이 이 줄을 그대로 응답에 싣는다.** flush 를 안 하면 id 도 기본값도
    # 아직 없어서 `{"id": null}` 이 화면까지 간다.
    db.flush()
    return job
