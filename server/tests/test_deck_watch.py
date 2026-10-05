"""학생의 덱 칸이 진행을 읽는 자리(`GET /api/lectures/…/deck-job`).

2026-09-21 관리자 지시 — 「퀴즈를 만들고 있을 때 관리자가 아닌 사용자도
사이드패널 현황을 볼 수 있게. 몇 단계 몇 분 남았는지.」

**이 검사가 보는 것은 진행이 오는가가 아니라 그것만 오는가다.** 관리자 경로
(`/api/admin/…/prequiz-job`)를 학생에게 열어 주는 길도 있었는데, 그쪽은 같은
일감 줄에 **누가 눌렀는지(이메일)** · 어느 일꾼이 잡았는지 · 왜 실패했는지 ·
줄에서 몇 번째인지까지 싣는다. 그래서 주는 칸을 덜어 낸 경로를 따로 세웠고
(`jobs/views.watch_row`), 덜어 냈다는 것은 **세어 봐야 사실이 된다** —
화면에서 안 그리는 것과 응답에 안 싣는 것은 다른 일이다.

같은 이유로 러너도 `lastSeen` 하나뿐이어야 한다. `note`는 **다른 편의 이름**
이라(「기생충학/260910_03 외 1편」) 이 편을 보러 온 사람에게 갈 자리가 아니다.

    server/.venv/Scripts/python.exe -m tests.test_deck_watch
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-deckwatch-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'watch.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402
from datetime import UTC, timedelta  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Lecture, PrequizJob, RunnerBeat  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
SUBJECT, RUN = "병리학", "260825_01"
WATCH = f"/api/lectures/{SUBJECT}/{RUN}/deck-job"

# 학생에게 절대 가면 안 되는 칸. 관리자 줄(`job_row`)에는 전부 있다.
FORBIDDEN = ("requestedBy", "worker", "message", "priority", "queueRank", "cancelRequested", "origin", "id")

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def put_job(**fields) -> None:
    """이 편·이 갈래의 일감을 하나로 갈아 끼운다."""
    with SessionLocal() as db:
        for row in db.query(PrequizJob).all():
            db.delete(row)
        db.add(PrequizJob(subject=SUBJECT, run_id=RUN, **fields))
        db.commit()


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(
            Lecture(
                subject=SUBJECT,
                run_id=RUN,
                uid=f"{RUN}#종양",
                date=datetime.date(2026, 8, 25),
                slot=1,
                slot_end=1,
                start_time="09:00",
                title="종양의 분자생물학(1)",
                professors=["전윤경"],
                author="박주항",
                version=1,
            )
        )
        db.add(RunnerBeat(name="local", busy=True, note="기생충학/260910_03 외 1편"))
        db.commit()

    client = TestClient(app)
    now = datetime.datetime.now(UTC)

    # ── ① 도는 편. 여기가 이 경로가 생긴 이유다.
    print("\n[1] 만드는 중이면 단계와 남은 시간이 온다")
    put_job(
        kind="main",
        state="running",
        stage="② 카드",
        stage_index=6,
        stage_total=17,
        eta_seconds=1320,
        started_at=now - timedelta(minutes=12),
        stage_started_at=now - timedelta(minutes=4),
        requested_by="someone@example.com",
        worker="w2",
        message="옛 실패 사유",
        queue_rank=3,
    )
    answer = client.get(f"{WATCH}?kind=main", headers=USER)
    check("200", answer.status_code == 200, answer.status_code)
    job = answer.json()["job"]
    check("일감이 온다", job is not None)
    check("단계 이름", job["stage"] == "② 카드", job["stage"])
    check("몇 단계 중 몇 번째", (job["stageIndex"], job["stageTotal"]) == (6, 17), job)
    check("남은 시간", job["etaSeconds"] == 1320, job["etaSeconds"])
    check("몇 분째", 11 * 60 <= job["elapsedSeconds"] <= 13 * 60, job["elapsedSeconds"])
    check("이 단계 몇 분째", 3 * 60 <= job["stageSeconds"] <= 5 * 60, job["stageSeconds"])

    print("\n[2] 운영의 칸은 한 줄도 안 온다")
    for key in FORBIDDEN:
        check(f"{key} 없다", key not in job, job.get(key))
    runner = answer.json()["runner"]
    check("러너는 lastSeen 하나뿐", set(runner) == {"lastSeen"}, runner)
    check("남의 편 이름이 안 샌다", "기생충학" not in answer.text)
    check("남의 이메일이 안 샌다", "someone@example.com" not in answer.text)

    # ── ③ 갈래를 섞으면 안 만드는 것을 기다리게 된다.
    print("\n[3] 갈래를 안 섞는다")
    other = client.get(f"{WATCH}?kind=pre", headers=USER).json()
    check("예습 자리는 비어 있다", other["job"] is None, other["job"])
    bad = client.get(f"{WATCH}?kind=side", headers=USER)
    check("모르는 갈래는 400", bad.status_code == 400, bad.status_code)

    # ── ④ 줄 서 있는 일감의 `stage`는 진행이 아니다.
    print("\n[4] 줄만 서 있으면 단계를 안 적는다")
    put_job(kind="main", state="queued", stage="러너를 기다리는 중", stage_index=6, stage_total=17,
            eta_seconds=1320, started_at=now - timedelta(minutes=12))
    job = client.get(f"{WATCH}?kind=main", headers=USER).json()["job"]
    check("줄에 서 있다", job["state"] == "queued", job)
    check("안내문을 단계로 안 내보낸다", job["stage"] == "", job["stage"])
    check("남은 시간도 안 적는다", (job["stageIndex"], job["etaSeconds"], job["elapsedSeconds"]) == (0, 0, 0), job)

    # ── ⑤ 한도로 멈춘 편은 이어지는 시각이 있어야 「기다리면 된다」가 된다.
    print("\n[5] 한도로 멈춘 편은 시각을 준다")
    put_job(kind="main", state="queued", resume_at=now + timedelta(hours=1))
    job = client.get(f"{WATCH}?kind=main", headers=USER).json()["job"]
    check("이어지는 시각이 온다", bool(job["resumeAt"]), job)

    # ── ⑥ 끝난 일감은 안 나간다. 덱이 그 자리에 있거나, 학생이 할 일이 없다.
    print("\n[6] 열린 일감만 나간다")
    for state in ("done", "failed", "canceled"):
        put_job(kind="main", state=state, message="세션 한도로 죽었다")
        body = client.get(f"{WATCH}?kind=main", headers=USER)
        check(f"{state}는 안 나간다", body.json()["job"] is None, body.json()["job"])
        check(f"{state}의 사유도 안 샌다", "세션 한도로 죽었다" not in body.text)
    put_job(kind="main", state="held", stage="오늘 자동 상한을 다 썼다 — 만들려면 눌러라")
    held = client.get(f"{WATCH}?kind=main", headers=USER).json()["job"]
    check("held는 나간다", held is not None and held["state"] == "held", held)
    check("held의 안내문은 단계가 아니다", held and held["stage"] == "", held)

    print("\n실패 " + str(len(failures)) if failures else "\n모두 통과")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
