"""러너의 덱 일감 큐. `/api/admin/prequiz-jobs` 와 강의별 일감 요청.

`routes/prequiz.py` 와 헷갈리지 마라 — 그쪽은 **학생이 푸는** 예습 문항
(`/api/lectures/.../prequiz`)이고, 여기는 **러너가 집어 가는 일감**이다.
소비자가 다르다. 웹의 관리자 화면이 일감을 걸고, 로컬 러너가 `claim` 으로
가져가 `PUT` 으로 진행을 알린다.

`admin.py` 에서 갈라 나왔다. 붙는 자리는 그대로 `/api/admin` 이라 주소는
바뀌지 않았다. `job_row`·`runner_row`·`RUNNER_NAME` 은 `/admin/overview` 도
쓰기 때문에 밑줄 없는 이름이다.

## 줄은 선 순서가 아니라 급한 순서다 (2026-09-03)

한동안 `created_at` 순이었다. 그러면 **낮에 올라온 필기의 복습이 밤에 저장된
내일 예습 링크를 앞지른다** — 복습은 하루 늦어도 되지만 예습은 강의가 끝나면
쓸모가 없어지는데.

    ① 내일 예습   ② 오늘 복습   ③ 나머지는 선 순서대로

관리자 지시(2026-09-03)이고, `queue_priority`가 그 셋을 매긴다. 그 위에 사람이
옮긴 자리(`queue_rank`)가 한 겹 더 있다 — 날짜에 안 적힌 사정은 자동 순위가
모른다. **집어 가는 쪽(`claim`)과 보여 주는 쪽(`board`)이 같은 함수로 줄을
세운다**(`queue_order`). 갈라 두면 화면의 「차례 1번째」와 러너가 집는 편이
어긋나고, 둘 다 그럴듯해 보여서 아무도 그 어긋남을 못 본다.

## 지우는 것과 멈추는 것은 다른 일이다 (2026-09-03)

버튼은 하나지만(`cancel`) 상태에 따라 하는 일이 갈린다.

    queued·held   그 자리에서 끝난다. 아직 아무도 안 만들었다
    running       표에 「멈춰라」를 적고, **러너가 받아 가 자기 자식을 죽인다**

둘째 줄이 이 파일에서 제일 조심할 자리다 — **서버는 그 프로세스를 모른다.**
만드는 것은 노트북이고, 여기서 상태만 `canceled`로 바꾸면 화면은 멈췄는데
빈 세션 넷은 그대로 돈다. 그래서 표시(`cancel_requested`)를 두고 러너가
20초마다 진행을 적으러 올 때 받아 가게 했다.
"""

from __future__ import annotations

from datetime import UTC, date as Date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_runner
from app.database import get_db
from app.models import (
    JOB_AUTO,
    JOB_AUTO_DAILY_CAP,
    JOB_BUTTON,
    JOB_CANCELED,
    JOB_DONE,
    JOB_FAILED,
    JOB_HELD,
    JOB_KINDS,
    JOB_MAIN,
    JOB_OPEN,
    JOB_PRE,
    JOB_QUEUED,
    JOB_RUNNING,
    Asset,
    Lecture,
    PrequizJob,
    Preview,
    RunnerBeat,
)
from app.routes.common import lecture_or_404

router = APIRouter()


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


def _seconds_since(when: datetime | None) -> int:
    if when is None:
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - when).total_seconds()))


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
    if kind == JOB_MAIN and lecture_date == today:
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
    """집어 갈 순서대로. 줄마다 자동 순위를 같이 준다.

    **집어 가는 쪽과 보여 주는 쪽이 이 한 함수를 같이 쓴다.** 갈라 두면 화면이
    말하는 「차례 1번째」와 러너가 실제로 집는 편이 어긋나고, 그 어긋남은 아무도
    안 본다 — 둘 다 그럴듯하게 보이기 때문이다.

    가르는 값은 넷이다.

        queue_rank   사람이 옮긴 자리. 0이 안 건드린 것
        rank         자동 순위(내일 예습 → 오늘 복습 → 나머지)
        slot         같은 순위 안에서는 이른 교시부터. 나머지 갈래에서는 안 본다
        id           그래도 같으면 선 순서대로

    `slot`을 나머지 갈래에서 빼는 까닭은 그쪽이 **「순서대로」**이기 때문이다 —
    거기서 교시를 보면 어제 3교시가 오늘 1교시를 앞지른다.
    """
    today = today or study_today()
    days = _lecture_days(db, jobs)
    ranked = []
    for job in jobs:
        day, slot = days.get((job.subject, job.run_id), (None, 0))
        rank = queue_priority(job.kind, day, today)
        ranked.append((job, rank, slot if rank != RANK_REST else 0))
    ranked.sort(key=lambda row: (row[0].queue_rank, row[1], row[2], row[0].id))
    return [(job, rank) for job, rank, _slot in ranked]


def job_row(job: PrequizJob | None, priority: str = "") -> dict[str, Any] | None:
    if job is None:
        return None
    running = job.state == JOB_RUNNING
    return {
        "id": job.id,
        "subject": job.subject,
        "runId": job.run_id,
        "kind": job.kind,
        "state": job.state,
        "stage": job.stage,
        "message": job.message,
        "requestedBy": job.requested_by,
        # 버튼인가 자동인가. 화면이 「내가 누른 것」과 「저절로 선 것」을 갈라
        # 보여 주지 않으면, 누른 적 없는 편이 도는 것을 보고 사람이 놀란다.
        "origin": job.origin,
        "worker": job.worker,
        # **서버가 셈해서 준다.** 화면마다 시계를 맞추면 시차만큼 어긋난다.
        "elapsedSeconds": _seconds_since(job.started_at) if running else 0,
        "stageSeconds": _seconds_since(job.stage_started_at) if running else 0,
        "stageIndex": job.stage_index,
        "stageTotal": job.stage_total,
        # 러너가 지난 편들의 실측으로 셈한 남은 시간. 0이면 아직 모른다.
        "etaSeconds": job.eta_seconds if running else 0,
        # 러너가 이것을 보고 이미 만든 편도 버리고 다시 만든다. 화면도 같은 값으로
        # 「만드는 중」과 「다시 만드는 중」을 가른다.
        "force": bool(job.force),
        # 이 시각까지 줄에서 기다린다(모델 한도). 화면이 「멈춰 있다」와 「기다리는
        # 중이다」를 갈라 말하려면 이 값이 필요하다.
        "resumeAt": job.resume_at.isoformat() if job.resume_at else "",
        # **왜 이 줄이 거기 섰나.** 「내일 예습」·「오늘 복습」이거나 빈 문자열이다.
        # 줄 세우는 쪽만 아는 값이라 여기서 실어 보낸다 — 화면이 날짜를 다시
        # 세면 하루가 바뀌는 시각이 두 자리에서 갈린다(`QUEUE_DAY_START_HOUR`).
        "priority": priority,
        # 사람이 옮긴 자리. 0이 아니면 자동 순위를 덮고 있다는 뜻이고, 화면은
        # 그 사실을 적어야 한다 — 안 적으면 왜 이게 앞인지 아무도 모른다.
        "queueRank": job.queue_rank,
        # 사람이 「멈추기」를 눌렀고 러너가 아직 안 받아 갔다. **러너가 이 값을
        # 보고 자기 자식을 죽인다**(`runner.agent`). 화면도 같은 값으로
        # 「만드는 중」과 「멈추는 중」을 가른다.
        "cancelRequested": bool(job.cancel_requested),
        "createdAt": job.created_at.isoformat() if job.created_at else "",
        "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
    }


def runner_row(beat: RunnerBeat | None) -> dict[str, Any] | None:
    if beat is None:
        return None
    return {
        "lastSeen": beat.last_seen.isoformat() if beat.last_seen else "",
        "busy": beat.busy,
        "note": beat.note,
    }


def _busy_note(running: list[PrequizJob]) -> str:
    """지금 무엇을 만들고 있는지 한 줄로. 화면 맨 위가 이걸 읽는다."""
    if not running:
        return ""
    head = f"{running[0].subject}/{running[0].run_id}"
    return head if len(running) == 1 else f"{head} 외 {len(running) - 1}편"


def _touch_runner(db: Session, *, busy: bool, note: str) -> None:
    """러너가 살아 있다고 적는다. **러너가 말을 걸 때마다 지나가는 자리다.**

    물어보는 것(`claim`)만으로는 모자란다. 한 편을 집어 가면 러너는 15분 동안
    `claim`을 안 부르므로(`agent.tick`이 `handle` 안에 머문다), 진행을 적는
    `PUT`도 여기를 지나야 한다. 안 그러면 2분 뒤부터 화면이 멀쩡히 만드는 중인
    러너를 「안 붙어 있습니다」라고 말한다.
    """
    beat = db.get(RunnerBeat, RUNNER_NAME)
    if beat is None:
        beat = RunnerBeat(name=RUNNER_NAME)
        db.add(beat)
    beat.busy = busy
    beat.note = note[:500]
    beat.last_seen = datetime.now(UTC)


class JobRequest(BaseModel):
    """「다시 만들기」인가. 몸이 없으면 처음 만드는 것이다."""

    force: bool = False


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
    """재료가 도착해서 저절로 서는 일감. 이미 서 있으면 아무것도 안 한다.

    **버튼은 이제 안전장치다**(관리자 지시, 2026-09-01). 필기가 올라오면 복습이,
    예습 링크가 저장되면 예습이 여기서 큐로 들어간다 — 사람이 누르기를 기다리는
    동안 노트북이 놀고 있었다.

    하루 상한(`JOB_AUTO_DAILY_CAP`)을 넘으면 `held`로 세운다. 만들지는 않지만
    **화면에는 남는다** — 안 세우면 「자동이 안 걸린 편」과 「상한에 걸린 편」이
    같은 모양이 되고, 그 둘을 가르려면 사람이 노트북을 열어 봐야 한다.

    커밋은 부르는 쪽이 한다. 업로드·링크 저장과 **한 트랜잭션에 묶여야** 해서다 —
    따로 커밋하면 링크는 저장됐는데 일감은 안 선 상태가 남을 수 있다.
    """
    if kind not in JOB_KINDS:
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


def _job_kind(kind: str) -> str:
    if kind not in JOB_KINDS:
        raise HTTPException(400, f"모르는 일감 종류입니다: {kind}")
    return kind


def _no_material(db: Session, lecture: Lecture, kind: str) -> str:
    """재료가 없어서 지금 못 만드는 이유. 만들 수 있으면 빈 문자열.

    **여기서 가르지 않으면 러너가 15분 뒤에 가른다.** 그때는 사람이 화면을 이미
    닫았고, 노트북만 헛돈 뒤 「만들 자리를 못 찾았다」가 남는다.

    재료가 갈래마다 다르다 — 예습은 관리자가 만든 예습 대화로 만들고(그 대화가
    Pre-Quiz의 본체다), 복습은 **올해 필기**로 만든다. 올해 필기는 러너가 쓸기마다
    올리므로 서버에 없으면 노트북에도 아직 없다.
    """
    if kind == JOB_MAIN:
        notes = db.scalars(
            select(Asset.id).where(
                Asset.subject == lecture.subject,
                Asset.run_id == lecture.run_id,
                Asset.kind == "notes_current",
            )
        ).first()
        return "" if notes else "올해 강의록이 아직 없습니다. Main-Quiz는 올해 필기로 만듭니다."

    preview = db.get(Preview, (lecture.subject, lecture.run_id))
    if preview is None or not preview.share_url:
        return "예습 링크를 먼저 저장하세요. Pre-Quiz는 그 대화로 만듭니다."
    return ""


@router.post("/lectures/{subject}/{run_id}/prequiz-job")
def request_prequiz(
    subject: str,
    run_id: str,
    kind: str = JOB_PRE,
    payload: JobRequest | None = None,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """「덱 만들기」·「다시 만들기」. 일감 한 줄을 적고, 만드는 것은 러너가 한다.

    **두 번 눌러도 두 번 만들지 않는다.** 열려 있는 일감이 있으면 그것을 그대로
    돌려준다 — 15분짜리 일이라 사람이 반응이 없다고 다시 누르는 일이 잦다.

    `kind`가 두 갈래를 가른다(`pre` 기본, `main`). **한 갈래가 다른 갈래를 막지
    않는다** — 열린 일감을 셀 때도 같은 갈래만 본다. 같은 편의 예습을 만드는 중에
    복습을 눌러도 줄이 따로 선다. 러너가 한 번에 하나씩 집어 갈 뿐이다.

    `force`는 **덱이 이미 있는데도 다시 만들라**는 뜻이다. 이것을 표에 적어 두는
    까닭은 러너가 판정할 수 없기 때문이다 — 노트북에 산출물이 남아 있으면
    `prequeue`는 그 편을 `done`으로 보고 건너뛴다. 사람이 누른 것을 러너가 알
    길은 이 값뿐이다.

    **덱이 있는지는 여기서 안 본다.** 서버에 파일이 없어도(검문에 걸려 덱만
    미뤄진 편이 그렇다) 사람은 다시 만들라고 할 수 있고, 그때 다시 만들어야 하는
    것은 노트북에 있는 그 산출물이다.

    **재료가 없으면 거절한다.** 그 재료가 무엇인지는 갈래마다 다르다(`_no_material`).
    """
    kind = _job_kind(kind)
    force = bool(payload and payload.force)
    lecture = lecture_or_404(db, subject, run_id)
    blocked = _no_material(db, lecture, kind)
    if blocked:
        raise HTTPException(400, blocked)

    open_job = open_job_of(db, lecture.subject, lecture.run_id, kind)
    if open_job is not None and open_job.state == JOB_HELD:
        # 상한에 걸려 서 있던 줄을 사람이 푼 것이다. **새 줄을 세우지 않는다** —
        # 세우면 같은 편이 두 줄이 되고, 하나는 영영 `held`로 남는다.
        open_job.state = JOB_QUEUED
        open_job.stage = "다시 만들려고 러너를 기다리는 중" if force else "러너를 기다리는 중"
        open_job.requested_by = user.email
        open_job.force = open_job.force or force
        db.commit()
        return {"job": job_row(open_job), "created": False}
    if open_job is not None:
        # **누른 뜻은 덧붙는다.** 아직 안 집어 간 일감에 「다시 만들기」가 겹치면
        # 그 일감이 다시 만드는 일이 된다 — 새 줄을 세우면 같은 편을 두 번 만든다.
        #
        # 이미 집어 간 뒤라면 늦었다. 러너는 그 편을 이어 만들고 있고, 여기서
        # 값만 바꿔도 그 프로세스는 안 본다. 그래서 **바꾸지 않는다** — 돌려주는
        # 일감의 `force`가 거짓이면 누른 사람이 그 사실을 본다.
        if force and not open_job.force and open_job.state == JOB_QUEUED:
            open_job.force = True
            open_job.stage = "다시 만들려고 러너를 기다리는 중"
            db.commit()
        return {"job": job_row(open_job), "created": False}

    job = PrequizJob(
        subject=lecture.subject,
        run_id=lecture.run_id,
        kind=kind,
        state=JOB_QUEUED,
        stage="다시 만들려고 러너를 기다리는 중" if force else "러너를 기다리는 중",
        requested_by=user.email,
        force=force,
        origin=JOB_BUTTON,
    )
    db.add(job)
    db.commit()
    return {"job": job_row(job), "created": True}


@router.get("/lectures/{subject}/{run_id}/prequiz-job")
def lecture_prequiz_job(
    subject: str,
    run_id: str,
    kind: str = JOB_PRE,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """이 강의에서 그 갈래의 가장 최근 일감. 없으면 `null`.

    캘린더 패널이 「… 덱 — 아직 없습니다」 자리에서 부른다. `/overview`로
    갈음할 수 있지만 그쪽은 학기 전체를 그리는 응답이라, 패널 하나 여는 값으로는
    비싸다.

    **갈래를 섞어 주지 않는다.** 한 자리가 두 갈래를 같이 말하면, 복습을 만드는
    중이라는 말이 예습 자리에 떠서 사람이 누르지 않은 것을 기다리게 된다.

    러너 상태를 같이 준다. **일감이 안 움직이는 이유가 둘이라 가른다** — 러너가
    안 떠 있거나, 떠 있는데 앞의 편을 만드는 중이거나.
    """
    kind = _job_kind(kind)
    lecture = lecture_or_404(db, subject, run_id)
    job = db.scalars(
        select(PrequizJob)
        .where(
            PrequizJob.subject == lecture.subject,
            PrequizJob.run_id == lecture.run_id,
            PrequizJob.kind == kind,
        )
        .order_by(PrequizJob.created_at.desc())
    ).first()
    return {"job": job_row(job), "runner": runner_row(db.get(RunnerBeat, RUNNER_NAME))}


@router.post("/prequiz-jobs/claim")
def claim_prequiz_job(
    worker: str = "",
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """일꾼 하나가 일감 하나를 집어 간다. 없으면 `null`. **박동도 여기서 찍는다.**

    **한 대의 러너에 일꾼이 여럿이다**(2026-09-01). 그 전에는 도는 편이 하나라도
    있으면 그것을 돌려주고 끝이었는데, 그러면 한 편이 막힌 동안 뒤의 편이 전부
    같이 멈춘다 — 2026-08-31에 한 편이 45분을 잠들어 있는 동안 큐가 통째로 섰다.

    갈라 주는 규칙은 셋이다.

    ① **자기가 잡고 있던 편이 먼저다.** 끊겼다 붙은 일꾼은 그 편을 이어 만든다.
    ② **남의 편은 안 준다.** 주면 같은 편을 둘이 만든다 — 편당 빈 세션 넷이다.
    ③ **같은 강의는 겹쳐 안 돈다.** 예습과 복습이 한 편에서 동시에 도는 것까지는
       재료가 달라 되지만, 그 둘이 같은 자리에 올리므로 순서가 엉킨다.

    `worker`를 안 주면 옛 러너다. 그때는 이름 없는 일꾼 하나로 친다.
    """
    slot = (worker or "w1")[:16]
    now = datetime.now(UTC)

    running = db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_RUNNING).order_by(PrequizJob.created_at)
    ).all()

    mine = next((job for job in running if job.worker == slot), None)
    if mine is not None:
        _touch_runner(db, busy=True, note=_busy_note(running))
        db.commit()
        return {"job": job_row(mine)}

    if len(running) >= MAX_RUNNING:
        _touch_runner(db, busy=True, note=_busy_note(running))
        db.commit()
        return {"job": None}

    busy_lectures = {(job.subject, job.run_id) for job in running}
    waiting = db.scalars(
        select(PrequizJob).where(
            PrequizJob.state == JOB_QUEUED,
            # **아직 때가 안 된 편은 안 준다.** 모델 한도로 멈춘 편이 여기 선다 —
            # 러너가 「resets 1:40pm」을 읽어 적어 두면 그때까지 줄에서 기다린다.
            # 이 기다림을 러너 메모리에 두면 재시작에 날아가고, 그러면 풀리지도
            # 않은 한도에 다시 부딪힌다.
            or_(PrequizJob.resume_at.is_(None), PrequizJob.resume_at <= now),
        )
    ).all()
    # **선 순서가 아니라 급한 순서다**(`queue_order`). 화면도 같은 함수로 줄을
    # 세우므로, 거기 적힌 「차례 1번째」가 여기서 집는 편이다.
    queued = [job for job, _rank in queue_order(db, list(waiting))]
    # **읽고 나서 쓰는 사이가 비어 있으면 둘이 같은 줄을 집는다.** 일꾼 둘이 같은
    # 초에 물어보는 일이 실제로 생긴다(둘 다 15초마다 깨어난다). 조건부 UPDATE 한
    # 방으로 집고, **뺏겼으면 다음 줄로 넘어간다** — 여기서 빈손으로 돌아가면 그
    # 일꾼이 다음 회차까지(15초) 논다.
    job = None
    for row in queued:
        if (row.subject, row.run_id) in busy_lectures:
            continue
        taken = db.execute(
            update(PrequizJob)
            .where(PrequizJob.id == row.id, PrequizJob.state == JOB_QUEUED)
            .values(state=JOB_RUNNING, stage="시작", worker=slot,
                    started_at=now, stage_started_at=now)
        )
        if taken.rowcount == 1:
            db.refresh(row)
            job = row
            running = [*running, row]
            break

    _touch_runner(db, busy=bool(running), note=_busy_note(running))
    db.commit()
    return {"job": job_row(job)}


class JobUpdate(BaseModel):
    # `queued`는 **러너가 물러설 때** 쓴다 — 모델 한도처럼 이 편의 잘못이 아니고
    # 기다리면 풀리는 것. 실패로 적으면 사람이 다시 눌러야 하는데, 누를 사람이
    # 자는 시각에 걸리는 일이 잦다(2026-09-02에 01:32과 10:17 두 번).
    # `canceled`는 **러너가 멈춤을 받아 갔다고 알리는 자리다** — 사람이 누른 것을
    # 서버가 표에 적어 두면(`cancel_requested`) 러너가 자식을 죽이고 여기로 온다.
    state: Literal["running", "done", "failed", "queued", "canceled"] | None = None
    # 그때까지는 아무도 못 집어 간다. ISO 시각.
    resume_at: str | None = Field(default=None, alias="resumeAt")
    stage: str | None = None
    message: str | None = None
    # 어디까지 왔나·얼마나 남았나. 러너만 아는 값이라 여기로 올라온다
    # (`runner.eta`가 지난 편들의 실측으로 셈한다).
    stage_index: int | None = Field(default=None, alias="stageIndex")
    stage_total: int | None = Field(default=None, alias="stageTotal")
    eta_seconds: int | None = Field(default=None, alias="etaSeconds")

    model_config = {"populate_by_name": True}


@router.put("/prequiz-jobs/{job_id}")
def update_prequiz_job(
    job_id: int,
    payload: JobUpdate,
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """러너가 진행을 적는다. 끝난 일감은 다시 열지 않는다.

    **몸이 비어 있어도 된다.** 그때는 아무것도 안 바꾸고 박동만 찍는다 — 한
    단계가 2분 넘게 이어지는 동안 러너가 죽은 것으로 보이지 않게.
    """
    job = db.get(PrequizJob, job_id)
    if job is None:
        raise HTTPException(404, "그런 일감이 없습니다.")
    if job.state in (JOB_DONE, JOB_FAILED, JOB_CANCELED):
        # 끝난 뒤에 늦게 도착한 갱신. 조용히 무시하는 편이 안전하다 —
        # 다시 열면 화면이 끝난 편을 도는 중으로 보여 준다. **사람이 강제로
        # 내린 줄도 여기서 막힌다** — 러너가 그 뒤에 올리는 진행이 그 줄을
        # 되살리면, 사람이 멈춘 편이 화면에서 다시 돌기 시작한다.
        return {"job": job_row(job), "applied": False}

    if payload.stage is not None:
        # **단계가 바뀔 때만 시계를 다시 잡는다.** 러너는 단계가 그대로여도
        # 20초마다 두드리는데(박동), 그때마다 잡으면 「이 단계에서 12분째」가
        # 영영 0분으로 보인다.
        if payload.stage[:500] != job.stage:
            job.stage_started_at = datetime.now(UTC)
        job.stage = payload.stage[:500]
    if payload.message is not None:
        job.message = payload.message[:2000]
    if payload.stage_index is not None:
        job.stage_index = max(0, payload.stage_index)
    if payload.stage_total is not None:
        job.stage_total = max(0, payload.stage_total)
    if payload.eta_seconds is not None:
        job.eta_seconds = max(0, payload.eta_seconds)
    if payload.resume_at is not None:
        try:
            job.resume_at = datetime.fromisoformat(payload.resume_at)
        except ValueError:
            raise HTTPException(400, "resumeAt은 ISO 시각이어야 합니다.") from None
    if payload.state is not None:
        job.state = payload.state
        if payload.state in (JOB_DONE, JOB_FAILED, JOB_CANCELED):
            job.finished_at = datetime.now(UTC)
        if payload.state == JOB_CANCELED:
            # 러너가 받아 갔다. 표시를 지운다 — 남겨 두면 화면이 끝난 줄을
            # 「멈추는 중」으로 읽는다.
            job.cancel_requested = False
        if payload.state == JOB_QUEUED:
            # **줄 앞으로 되돌린다.** 일꾼 이름을 지우지 않으면 그 일꾼만 다시
            # 집을 수 있고(claim ①), 러너가 재시작해 이름이 바뀌면 아무도 못 집는다.
            job.worker = ""
            job.started_at = None
            job.finished_at = None

    # 이 호출 자체가 박동이다(`_touch_runner`). 빈 몸으로 와도 마찬가지 —
    # 러너는 단계가 안 바뀌어도 여기를 두드려 살아 있다고 알린다.
    #
    # **한 편이 끝났다고 러너가 논다는 뜻이 아니다.** 일꾼이 둘이라 옆에서 다른
    # 편이 돌고 있을 수 있다 — 도는 것을 세어서 적는다.
    db.flush()
    running = db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_RUNNING).order_by(PrequizJob.created_at)
    ).all()
    _touch_runner(db, busy=bool(running), note=_busy_note(list(running)))
    db.commit()
    return {"job": job_row(job), "applied": True}


def board(db: Session) -> dict[str, Any]:
    """지금 큐가 어떻게 서 있나. **화면 하나가 통째로 이 응답으로 그려진다.**

    도는 것과 기다리는 것을 여기서 갈라 준다 — 화면이 50줄을 받아 스스로 갈라도
    되지만, 「지금 몇 편이 돌고 몇 편이 남았나」는 화면마다 같은 답이어야 한다.

    순서를 바꾸는 자리도 이걸 그대로 돌려준다. 바꾼 뒤에 다시 읽게 하면 그 사이에
    러너가 한 편 집어 가고, 화면은 자기가 방금 옮긴 줄이 어디로 갔는지 못 말한다.
    """
    jobs = db.scalars(select(PrequizJob).order_by(PrequizJob.created_at.desc()).limit(50)).all()
    rows = [job_row(job) for job in jobs]
    # 기다리는 줄은 **집어 갈 순서대로** 준다(`queue_order`). 화면이 「차례 2번째」라고
    # 말하려면 최신순이 아니라 이 순서여야 하고, 그 순서가 러너의 것과 같아야 한다.
    waiting = [
        job_row(job, priority=PRIORITY_LABELS[rank])
        for job, rank in queue_order(db, [job for job in jobs if job.state == JOB_QUEUED])
    ]
    return {
        "jobs": rows,
        "running": [row for row in rows if row and row["state"] == JOB_RUNNING],
        "waiting": waiting,
        "held": [row for row in rows if row and row["state"] == JOB_HELD],
        # 자동이 오늘 몇 편을 썼나. 상한에 걸린 이유를 화면이 그대로 말할 수 있게.
        "autoUsedToday": auto_used_today(db),
        "autoDailyCap": JOB_AUTO_DAILY_CAP,
        "maxRunning": MAX_RUNNING,
        "runner": runner_row(db.get(RunnerBeat, RUNNER_NAME)),
    }


@router.get("/prequiz-jobs")
def list_prequiz_jobs(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """최근 일감. `/overview`가 편마다 하나씩 들고 있지만, 흐름을 보려면 여기다."""
    return board(db)


class JobMove(BaseModel):
    """줄에서 어디로 옮기나. 사이에 끼우는 자리는 두지 않았다 — 아래 설명 참고."""

    to: Literal["front", "back"] = "front"


@router.post("/prequiz-jobs/{job_id}/move")
def move_prequiz_job(
    job_id: int,
    payload: JobMove,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """기다리는 줄 하나를 맨 앞이나 맨 뒤로. **자동 순위를 사람이 덮는 자리다.**

    자동 순위(`queue_priority`)는 날짜만 보므로, 날짜에 안 적힌 사정을 모른다 —
    시험이 앞이라 이 편부터 필요하다거나, 강의가 취소돼서 급하지 않다거나.
    그래서 사람이 옮긴 자리를 표에 적어 두고(`queue_rank`) 그것을 먼저 본다.

    **끼워 넣기는 두지 않았다.** 줄이 서너 개짜리라 맨 앞과 맨 뒤면 어느 순서든
    몇 번으로 만들어진다. 가운데를 지정하게 하면 그 값을 화면이 들고 있어야 하고,
    러너가 그 사이에 한 편을 집어 가면 화면이 든 값이 틀린다.

    **도는 편은 못 옮긴다.** 이미 러너가 만들고 있고, 여기서 값을 바꿔도 그
    프로세스는 안 본다.
    """
    job = db.get(PrequizJob, job_id)
    if job is None:
        raise HTTPException(404, "그런 일감이 없습니다.")
    if job.state != JOB_QUEUED:
        raise HTTPException(400, "기다리는 중인 일감만 순서를 바꿀 수 있습니다.")

    others = db.scalars(
        select(PrequizJob.queue_rank).where(
            PrequizJob.state == JOB_QUEUED, PrequizJob.id != job.id
        )
    ).all()
    # 0을 같이 넣는다. **안 건드린 줄이 전부 0이라** 그것보다 앞이거나 뒤여야 한다.
    ranks = [0, *others]
    job.queue_rank = min(ranks) - 1 if payload.to == "front" else max(ranks) + 1
    db.commit()
    return board(db)


@router.post("/prequiz-jobs/{job_id}/cancel")
def cancel_prequiz_job(
    job_id: int,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """줄에서 지우거나, 도는 편을 멈춘다. **누르는 자리는 하나고 하는 일이 둘이다.**

    기다리는 줄(`queued`·`held`)은 여기서 끝난다 — 아무도 아직 만들지 않았으므로
    상태만 바꾸면 된다.

    **도는 편은 서버가 못 멈춘다.** 만드는 것은 노트북의 하위 프로세스이고 서버는
    그 프로세스를 모른다. 그래서 표에 「멈춰라」를 적어 두고(`cancel_requested`),
    러너가 진행을 적으러 올 때 받아 가 자기 자식을 죽인다. 그동안 화면에는
    **「멈추는 중」**이 뜬다 — 이 갈래를 안 만들고 바로 `canceled`로 적으면, 노트북은
    계속 만들고 있는데 화면만 멈춘 것으로 보인다(빈 세션 넷이 그대로 돈다).

    **한 번 더 누르면 강제로 내린다.** 러너가 안 붙어 있으면 그 표시를 아무도
    받아 가지 않아 영영 「멈추는 중」으로 남는다. 그때 사람에게 남는 길이 없으면
    그 줄이 `running` 자리를 하나 먹은 채로 굳는다(동시 2편이 1편이 된다).

    지운 줄은 **다시 만들 수 있다.** 끝난 일감이라 캘린더의 그 덱 칸에서 누르면
    새 줄이 선다.
    """
    job = db.get(PrequizJob, job_id)
    if job is None:
        raise HTTPException(404, "그런 일감이 없습니다.")
    if job.state in (JOB_DONE, JOB_FAILED, JOB_CANCELED):
        raise HTTPException(400, "이미 끝난 일감입니다.")

    if job.state == JOB_RUNNING and not job.cancel_requested:
        job.cancel_requested = True
        job.stage = "멈추는 중 — 러너가 이 편을 놓기를 기다린다"
        db.commit()
        return board(db)

    # 기다리던 줄이거나, 러너가 안 받아 가서 사람이 한 번 더 누른 것.
    forced = job.state == JOB_RUNNING
    job.state = JOB_CANCELED
    job.cancel_requested = False
    job.stage = ""
    job.message = ("러너가 안 받아 강제로 내렸다 — 노트북에서 아직 돌고 있을 수 있다"
                   if forced else "사람이 줄에서 지웠다")
    job.finished_at = datetime.now(UTC)
    db.commit()
    return board(db)
