"""사람별 이용현황이 맞는 수를 세는가.

2026-09-19에 생겼다 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」

**집계는 눈으로 안 틀린다.** 화면에 60이 떠 있으면 그게 60인지 6인지 볼 방법이
없고, 틀린 집계는 아무 데서도 안 터진다. 그래서 여기서는 **미리 아는 수**를
넣고 그 수가 그대로 나오는지만 본다.

    server/.venv/Scripts/python.exe -m tests.test_usage

넷을 잰다.

    ① 웹에서 푼 것과 받아 간 것이 각자 제 칸에서 세어지는가
    ② 손댄 편이 **합쳐서** 세어지는가 — 푼 편과 받기만 한 편이 둘 다 있다
    ③ 0이 갈라지는가 — 안 쓴 사람과 승인이 안 나 못 쓰는 사람
    ④ 자세한 내역이 강의마다 서고 최근 것이 먼저 오는가
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-usage-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'usage.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import LOCAL_TEST_EMAIL, LOCAL_TEST_USER_ID  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    APP_STUDYEZ,
    ROLE_MEMBER,
    AppGrant,
    AssetGrab,
    Lecture,
    MainAttempt,
    PreReviewLog,
    Profile,
    QuizAttempt,
)

ADMIN = {"Authorization": "Bearer local-test-token"}
SUBJECT = "기생충학"
SOLVED, GRABBED = "260918_02", "260917_01"  # 푼 편 · 받기만 한 편

# 세 사람. 이름이 그대로 이 검사가 가르려는 셋이다.
BUSY = "11111111-1111-1111-1111-111111111111"  # 쓰는 사람
IDLE = "22222222-2222-2222-2222-222222222222"  # 승인은 났는데 안 들어온 사람
WAITING = "33333333-3333-3333-3333-333333333333"  # 승인을 기다리는 사람

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def a_lecture(run_id: str, day: int, title: str) -> Lecture:
    return Lecture(
        subject=SUBJECT,
        run_id=run_id,
        uid=f"{run_id}#{title}",
        date=datetime.date(2026, 9, day),
        slot=2,
        slot_end=2,
        start_time="10:00",
        title=title,
        professors=["홍성태"],
        author="박주항",
        version=1,
    )


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(a_lecture(SOLVED, 18, "말라리아(1)"))
        db.add(a_lecture(GRABBED, 17, "아메바"))
        # 관리자 자신. `local-test` 토큰이 이 줄로 들어온다.
        db.add(Profile(id=LOCAL_TEST_USER_ID, email=LOCAL_TEST_EMAIL, is_admin=True))
        db.add(Profile(id=BUSY, email="busy@studyez.test"))
        db.add(Profile(id=IDLE, email="idle@studyez.test"))
        db.add(Profile(id=WAITING, email="waiting@studyez.test"))
        for uid in (LOCAL_TEST_USER_ID, BUSY, IDLE):
            db.add(AppGrant(user_id=uid, app=APP_STUDYEZ, role=ROLE_MEMBER))

        # 예습 3장(둘은 본인이 맞다고 했다) · 복습 1장. 찍은 횟수는 5번이다.
        #
        # **시각을 지금에서 재서 넣는다.** 날짜를 박아 두면 「최근 7일」 칸이
        # 다음 주에 저절로 0이 되고, 그때 이 검사는 고장을 찾은 것이 아니라
        # 자기가 낡은 것이다. 루트 `CLAUDE.md` 의 함정 ⑤ 가 그것이다.
        now = datetime.datetime.now(datetime.UTC)
        early = now - datetime.timedelta(days=2)
        late = now - datetime.timedelta(hours=1)
        for ord_, correct in enumerate((True, True, False), start=1):
            db.add(
                QuizAttempt(
                    user_id=BUSY,
                    subject=SUBJECT,
                    run_id=SOLVED,
                    item_id=f"c00{ord_}",
                    correct=correct,
                    answered_at=late,
                )
            )
        db.add(
            MainAttempt(
                user_id=BUSY,
                subject=SUBJECT,
                run_id=SOLVED,
                item_id="m001",
                correct=True,
                answered_at=early,
            )
        )
        for ord_ in range(5):
            db.add(
                PreReviewLog(
                    user_id=BUSY,
                    subject=SUBJECT,
                    run_id=SOLVED,
                    item_id=f"c00{ord_ % 3 + 1}",
                    grade="good",
                    reviewed_at=late,
                )
            )
        # **다른 편이다.** 받기만 하고 웹에서는 안 푼 편 — 손댄 편이 둘이 되어야 한다.
        for kind, clicks in (("pre_apkg", 2), ("notes_prev", 1)):
            db.add(
                AssetGrab(
                    user_id=BUSY,
                    subject=SUBJECT,
                    run_id=GRABBED,
                    kind=kind,
                    count=clicks,
                    first_at=early,
                    last_at=early,
                )
            )
        db.commit()


def main() -> None:
    seed()
    client = TestClient(app)

    payload = client.get("/api/admin/usage", headers=ADMIN).json()
    rows = {row["id"]: row for row in payload["users"]}
    busy, idle, waiting = rows.get(BUSY, {}), rows.get(IDLE, {}), rows.get(WAITING, {})

    print("\n[1] 웹에서 푼 것과 받아 간 것이 제 칸에서 세어진다")
    check("가입한 넷이 다 온다", len(payload["users"]) == 4, sorted(rows))
    check("예습 3장", busy.get("pre", {}).get("cards") == 3, busy.get("pre"))
    check("복습 1장", busy.get("main", {}).get("cards") == 1, busy.get("main"))
    check("찍은 횟수 5번", busy.get("pre", {}).get("grades") == 5, busy.get("pre"))
    check("받아 간 갈래 2", busy.get("grabs", {}).get("kinds") == 2, busy.get("grabs"))
    # 누른 횟수다. 내려받은 횟수가 아니다 — 이름이 그렇게 말한다.
    check("누른 횟수 3", busy.get("grabs", {}).get("clicks") == 3, busy.get("grabs"))
    check("최근 7일 찍기 5", busy.get("recentGrades") == 5, busy.get("recentGrades"))

    print("\n[2] 손댄 편은 세 표를 합쳐서 센다")
    # 푼 편 하나 + 받기만 한 편 하나. 한쪽만 세면 1이 나온다.
    check("2편", busy.get("lectures") == 2, busy.get("lectures"))

    print("\n[3] 0이 갈라진다 — 안 쓴 사람과 못 쓰는 사람")
    check("둘 다 활동이 없다", not idle.get("lastAt") and not waiting.get("lastAt"))
    check("안 쓴 사람은 문이 열려 있다", idle.get("hasAccess") is True, idle)
    check("못 쓰는 사람은 문이 닫혀 있다", waiting.get("hasAccess") is False, waiting)
    check("쓰는 사람이 맨 위", payload["users"][0]["id"] == BUSY, payload["users"][0].get("email"))
    check("창의 크기를 같이 준다", payload.get("recentDays") == 7, payload.get("recentDays"))

    print("\n[4] 자세한 내역은 강의마다 서고 최근 것이 먼저다")
    detail = client.get(f"/api/admin/usage/{BUSY}", headers=ADMIN).json()
    lectures = detail["lectures"]
    check("2편", len(lectures) == 2, [row["runId"] for row in lectures])
    first = lectures[0] if lectures else {}
    check("최근에 손댄 편이 먼저", first.get("runId") == SOLVED, [row["runId"] for row in lectures])
    check("제목이 온다", first.get("title") == "말라리아(1)", first.get("title"))
    check("본인이 맞다고 한 것 2장", first.get("pre", {}).get("selfCorrect") == 2, first.get("pre"))
    check("찍은 횟수도 편에 붙는다", first.get("pre", {}).get("grades") == 5, first.get("pre"))
    grabbed = next((row for row in lectures if row["runId"] == GRABBED), {})
    check("받기만 한 편도 선다", grabbed.get("grabs") == ["notes_prev", "pre_apkg"], grabbed.get("grabs"))
    check("그 편은 푼 것이 0이다", grabbed.get("pre", {}).get("cards") == 0, grabbed.get("pre"))

    print("\n[5] 없는 계정은 404")
    check("404", client.get("/api/admin/usage/nobody", headers=ADMIN).status_code == 404)

    print(f"\n{'실패 ' + str(len(failures)) if failures else '모두 통과'}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
