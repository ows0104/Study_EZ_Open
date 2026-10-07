"""덱·Quiz Bank 생성 일감 API (/api/admin).

학생 풀이 API는 prequiz.py에 있다. 큐 정책은 app.jobs.queue, 응답은 app.jobs.views.
running 취소는 cancel_requested로 러너에게 전달한다. 서버는 러너 프로세스를 종료하지 않는다."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_runner
from app.database import get_db
from app.jobs.queue import MAX_RUNNING, RUNNER_NAME, open_job_of, queue_order
from app.jobs.views import board, job_row, runner_row
from app.models import (
    JOB_BANK,
    JOB_BUTTON,
    JOB_CANCELED,
    JOB_DONE,
    JOB_FAILED,
    JOB_HELD,
    JOB_KINDS,
    JOB_MAIN,
    JOB_PRE,
    JOB_QUEUED,
    JOB_RUNNING,
    Asset,
    Lecture,
    PrequizJob,
    Preview,
    QuizBank,
    RunnerBeat,
)
from app.routes.common import lecture_or_404

router = APIRouter()


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
    if kind == JOB_BANK:
        bank = db.get(QuizBank, (lecture.subject, lecture.run_id))
        return "" if bank is not None and (bank.raw_response or bank.responded_at) else (
            "ChatGPT 응답이 아직 없습니다. Quiz Bank는 캘린더 패널에서 ChatGPT로 만들고 시작합니다.")
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
    if kind == JOB_MAIN:
        raise HTTPException(410, "Main Quiz는 Quizbank로 전환되었습니다. 강의 패널에서 ChatGPT 답을 저장하세요.")
    lecture = lecture_or_404(db, subject, run_id)
    blocked = _no_material(db, lecture, kind)
    if blocked:
        raise HTTPException(400, blocked)

    open_job = open_job_of(db, lecture.subject, lecture.run_id, kind)
    if open_job is not None and open_job.state == JOB_HELD and open_job.ask:
        # 러너가 물어 놓은 줄이다. 여기서 풀면 답 없이 다시 줄에 서고, 러너가
        # 집자마자 같은 것을 또 묻는다 — 누른 사람에게는 아무 일도 안 난 것으로 보인다.
        raise HTTPException(409, f"러너가 먼저 묻고 있습니다 — {open_job.ask} "
                                 "관리 화면의 퀴즈 탭에서 전략을 고르세요.")
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

    # 전환 전에 남은 대기 작업은 기록을 보존하며 종료한다.
    db.execute(update(PrequizJob).where(
        PrequizJob.kind == JOB_MAIN,
        PrequizJob.state.in_([JOB_QUEUED, JOB_HELD]),
    ).values(state=JOB_CANCELED, stage="", finished_at=now,
             message="Main Quiz를 Quizbank로 전환하여 기존 생성 대기를 종료했습니다."))
    # 이미 실행 중인 구버전 러너는 다음 진행 보고에서 중단 요청을 받는다.
    db.execute(update(PrequizJob).where(
        PrequizJob.kind == JOB_MAIN, PrequizJob.state == JOB_RUNNING,
    ).values(cancel_requested=True))

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
    # `held`는 **러너가 사람에게 물을 때** 쓴다 — 그때 `ask`가 같이 온다.
    state: Literal["running", "done", "failed", "queued", "canceled", "held"] | None = None
    ask: str | None = None
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

    if job.kind == JOB_MAIN:
        # claim 호출이 없어도 기존 러너의 다음 박동에서 전환을 알린다.
        job.cancel_requested = True

    if payload.stage is not None:
        # **단계가 바뀔 때만 시계를 다시 잡는다.** 러너는 단계가 그대로여도
        # 20초마다 두드리는데(박동), 그때마다 잡으면 「이 단계에서 12분째」가
        # 영영 0분으로 보인다.
        if payload.stage[:500] != job.stage:
            job.stage_started_at = datetime.now(UTC)
        job.stage = payload.stage[:500]
    if payload.message is not None:
        job.message = payload.message[:2000]
    if payload.ask is not None:
        job.ask = payload.ask[:2000]
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
        if payload.state in (JOB_QUEUED, JOB_HELD):
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


class JobChoice(BaseModel):
    # `runner watch --strategy` 가 받는 이름 그대로다.
    strategy: Literal["기본", "족보", "필기", "사진"]


@router.post("/prequiz-jobs/{job_id}/choose")
def choose_strategy(
    job_id: int,
    payload: JobChoice,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """러너가 물어 놓은 줄에 답한다. 고른 전략을 싣고 **다시 줄에 선다.**

    2026-09-24 관리자 지시 — 「표시해뒀다가 돌리게 될 때 알림이 뜨고 선택하게」.
    무엇을 물을지는 러너가 정하고(`runner.watch.strategy_question`), 여기는 답을
    받아 적을 뿐이다. 러너는 다음에 이 줄을 집을 때 `strategy` 가 차 있으면
    묻지 않고 그대로 `--strategy` 로 넘긴다.
    """
    job = db.get(PrequizJob, job_id)
    if job is None:
        raise HTTPException(404, "그런 일감이 없습니다.")
    if job.state != JOB_HELD or not job.ask:
        raise HTTPException(400, "묻고 있는 일감이 아닙니다.")
    job.strategy = payload.strategy
    job.ask = ""
    job.state = JOB_QUEUED
    job.stage = f"러너를 기다리는 중 — 고른 전략: {payload.strategy}"
    job.requested_by = user.email
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
