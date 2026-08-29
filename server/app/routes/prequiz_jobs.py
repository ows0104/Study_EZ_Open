"""러너의 덱 일감 큐. `/api/admin/prequiz-jobs` 와 강의별 일감 요청.

`routes/prequiz.py` 와 헷갈리지 마라 — 그쪽은 **학생이 푸는** 예습 문항
(`/api/lectures/.../prequiz`)이고, 여기는 **러너가 집어 가는 일감**이다.
소비자가 다르다. 웹의 관리자 화면이 일감을 걸고, 로컬 러너가 `claim` 으로
가져가 `PUT` 으로 진행을 알린다.

`admin.py` 에서 갈라 나왔다. 붙는 자리는 그대로 `/api/admin` 이라 주소는
바뀌지 않았다. `job_row`·`runner_row`·`RUNNER_NAME` 은 `/admin/overview` 도
쓰기 때문에 밑줄 없는 이름이다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_runner
from app.database import get_db
from app.models import (
    JOB_DONE,
    JOB_FAILED,
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


def job_row(job: PrequizJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "subject": job.subject,
        "runId": job.run_id,
        "kind": job.kind,
        "state": job.state,
        "stage": job.stage,
        "message": job.message,
        "requestedBy": job.requested_by,
        # 러너가 이것을 보고 이미 만든 편도 버리고 다시 만든다. 화면도 같은 값으로
        # 「만드는 중」과 「다시 만드는 중」을 가른다.
        "force": bool(job.force),
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

    open_job = db.scalars(
        select(PrequizJob)
        .where(
            PrequizJob.subject == lecture.subject,
            PrequizJob.run_id == lecture.run_id,
            PrequizJob.kind == kind,
            PrequizJob.state.in_(tuple(JOB_OPEN)),
        )
        .order_by(PrequizJob.created_at.desc())
    ).first()
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
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """러너가 일감 하나를 집어 간다. 없으면 `null`. **박동도 여기서 찍는다.**

    한 번에 하나만 준다. 한 편이 이미 빈 세션 넷을 띄우므로 겹쳐 돌릴 자리가
    아니다(`studyez.watch.build`와 같은 이유).

    이미 `running`인 것이 있으면 새 일감을 주지 않고 그것을 돌려준다 — 러너가
    끊겼다 붙었을 때 하던 일을 이어 잡으라는 뜻이다.
    """
    running = db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_RUNNING).order_by(PrequizJob.created_at)
    ).first()
    job = running or db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_QUEUED).order_by(PrequizJob.created_at)
    ).first()

    if job is not None and job.state == JOB_QUEUED:
        job.state = JOB_RUNNING
        job.stage = "시작"
        job.started_at = datetime.now(UTC)

    _touch_runner(db, busy=job is not None,
                  note=f"{job.subject}/{job.run_id}" if job is not None else "")
    db.commit()
    return {"job": job_row(job)}


class JobUpdate(BaseModel):
    state: Literal["running", "done", "failed"] | None = None
    stage: str | None = None
    message: str | None = None

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
    if job.state in (JOB_DONE, JOB_FAILED):
        # 끝난 뒤에 늦게 도착한 갱신. 조용히 무시하는 편이 안전하다 —
        # 다시 열면 화면이 끝난 편을 도는 중으로 보여 준다.
        return {"job": job_row(job), "applied": False}

    if payload.stage is not None:
        job.stage = payload.stage[:500]
    if payload.message is not None:
        job.message = payload.message[:2000]
    if payload.state is not None:
        job.state = payload.state
        if payload.state in (JOB_DONE, JOB_FAILED):
            job.finished_at = datetime.now(UTC)

    # 이 호출 자체가 박동이다(`_touch_runner`). 빈 몸으로 와도 마찬가지 —
    # 러너는 단계가 안 바뀌어도 여기를 두드려 살아 있다고 알린다.
    finished = job.state in (JOB_DONE, JOB_FAILED)
    _touch_runner(db, busy=not finished,
                  note="" if finished else f"{job.subject}/{job.run_id}")
    db.commit()
    return {"job": job_row(job), "applied": True}


@router.get("/prequiz-jobs")
def list_prequiz_jobs(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """최근 일감. `/overview`가 편마다 하나씩 들고 있지만, 흐름을 보려면 여기다."""
    jobs = db.scalars(select(PrequizJob).order_by(PrequizJob.created_at.desc()).limit(50)).all()
    return {
        "jobs": [job_row(job) for job in jobs],
        "runner": runner_row(db.get(RunnerBeat, RUNNER_NAME)),
    }
