"""관리자·학생에게 보내는 일감 응답과 큐 현황.

학생용 watch_* 응답은 운영 정보와 다른 사용자의 식별 정보를 포함하지 않는다."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.queue import (
    MAX_RUNNING,
    PRIORITY_LABELS,
    RUNNER_NAME,
    auto_used_today,
    queue_order,
)
from app.models import (
    JOB_AUTO_DAILY_CAP,
    JOB_HELD,
    JOB_OPEN,
    JOB_QUEUED,
    JOB_RUNNING,
    PrequizJob,
    RunnerBeat,
)


def _seconds_since(when: datetime | None) -> int:
    if when is None:
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - when).total_seconds()))


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
        # 러너가 만들기 전에 사람에게 묻는 말. 비어 있지 않으면 이 줄은 `held` 로
        # 서서 답을 기다린다(`choose_strategy`). 화면은 이 값으로 버튼을 그린다.
        "ask": job.ask,
        # 사람이 고른 전략. 빈 문자열이면 자동 판정이다.
        "strategy": job.strategy,
        "createdAt": job.created_at.isoformat() if job.created_at else "",
        "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
    }


def watch_row(job: PrequizJob | None) -> dict[str, Any] | None:
    """학생에게 보이는 열린 일감. 개인 식별자·실패 사유·작업자·큐 조작 정보는 제외한다.

    done·failed·canceled는 노출하지 않는다. 단계와 시간은 running일 때만 채운다."""
    if job is None or job.state not in JOB_OPEN:
        return None
    running = job.state == JOB_RUNNING
    return {
        "kind": job.kind,
        "state": job.state,
        "stage": job.stage if running else "",
        "stageIndex": job.stage_index if running else 0,
        "stageTotal": job.stage_total if running else 0,
        "elapsedSeconds": _seconds_since(job.started_at) if running else 0,
        "stageSeconds": _seconds_since(job.stage_started_at) if running else 0,
        "etaSeconds": job.eta_seconds if running else 0,
        # 받아 간 덱이 곧 새것으로 바뀐다는 뜻이다. 학생에게도 뜻이 있다 —
        # 덱이 이미 있는데 「만드는 중」만 뜨면 무엇이 만들어지는지 모른다.
        "force": bool(job.force),
        # 모델 한도로 멈춘 편. 시각을 안 주면 「차례를 기다립니다」와 같은
        # 모양이 되고, 그러면 기다려도 안 오는 줄로 읽힌다.
        "resumeAt": job.resume_at.isoformat() if job.resume_at else "",
    }


def watch_runner_row(beat: RunnerBeat | None) -> dict[str, Any] | None:
    """러너가 마지막으로 응답한 시각만 제공한다. 다른 강의명이 담긴 note는 제외한다."""
    if beat is None:
        return None
    return {"lastSeen": beat.last_seen.isoformat() if beat.last_seen else ""}


def runner_row(beat: RunnerBeat | None) -> dict[str, Any] | None:
    if beat is None:
        return None
    return {
        "lastSeen": beat.last_seen.isoformat() if beat.last_seen else "",
        "busy": beat.busy,
        "note": beat.note,
    }


def board(db: Session) -> dict[str, Any]:
    """최근 일감을 실행·대기·보류로 나누고 대기는 claim과 같은 순서로 응답한다."""
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
