"""사람별 이용현황이 맞는 수를 세는가.

2026-09-19에 생겼다 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」
같은 날 관리자가 **기간을 잘라 달라고** 했다(「너무 오래된 것까지 영향을 주지
않게. 이번 블럭, 지난 블럭 정도 기준으로」).

**집계는 눈으로 안 틀린다.** 화면에 60이 떠 있으면 그게 60인지 6인지 볼 방법이
없고, 틀린 집계는 아무 데도 안 터진다. 그래서 여기서는 **미리 아는 수**를 넣고
그 수가 그대로 나오는지만 본다.

    server/.venv/Scripts/python.exe -m tests.test_usage

씨앗은 **블럭 둘**이다 — 지난 블럭(기생충학)에서 한 것과 이번 블럭(미생물학)에서
한 것을 갈라 두었다. 창을 바꾸면 그 둘이 서로 바뀌어야 한다. 그것이 안 되면
「오래된 것이 영향을 준다」는 바로 그 상태다.

    ① 기본은 이번 블럭이고, 그 창 안의 것만 세어지는가
    ② 지난 블럭으로 바꾸면 **그때 한 것만** 세어지는가
    ③ 최근 7일이 블럭과 따로 서는가 · 없는 기간은 422인가
    ④ 0이 갈라지는가 — 안 쓴 사람과 승인이 안 나 못 쓰는 사람
    ⑤ 기본 링크와 개인 링크가 갈려서 세어지는가
    ⑥ 자세한 내역이 강의마다 서고 **기간을 안 자르는가**
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
    Preview,
    PreviewOpen,
    Profile,
    QuizAttempt,
    UserPreview,
)

ADMIN = {"Authorization": "Bearer local-test-token"}

# 블럭 둘. **이 저장소에서 블럭은 과목이고 범위는 강의 날짜다.**
#
# 날짜를 박아 두어도 안 낡는다 — 「이번 블럭」은 *이미 시작한 것 중 가장 늦게
# 끝나는 것*이라, 오늘이 언제든 미생물학이 이번 블럭이다.
PREV_SUBJECT, PREV_RUN = "기생충학", "260903_02"
NOW_SUBJECT, NOW_RUN = "미생물학", "260915_01"
PREV_DAY = datetime.date(2026, 9, 3)
NOW_DAY = datetime.date(2026, 9, 15)
#: 지난 블럭 안의 시각. 이번 블럭 창에는 안 들어와야 한다.
PREV_AT = datetime.datetime(2026, 9, 3, 5, 0, tzinfo=datetime.UTC)

BUSY = "11111111-1111-1111-1111-111111111111"  # 쓰는 사람
IDLE = "22222222-2222-2222-2222-222222222222"  # 승인은 났는데 안 들어온 사람
WAITING = "33333333-3333-3333-3333-333333333333"  # 승인을 기다리는 사람

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def a_lecture(subject: str, run_id: str, day: datetime.date, title: str) -> Lecture:
    return Lecture(
        subject=subject,
        run_id=run_id,
        uid=f"{run_id}#{title}",
        date=day,
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
    # **이번 블럭 쪽 시각은 지금에서 잰다.** 날짜를 박아 두면 「이번 블럭」 칸이
    # 다음 달에 저절로 0이 되고, 그때 이 검사는 고장을 찾은 것이 아니라 자기가
    # 낡은 것이다(루트 CLAUDE.md 함정 ⑤).
    now = datetime.datetime.now(datetime.UTC)
    late = now - datetime.timedelta(hours=1)

    with SessionLocal() as db:
        db.add(a_lecture(PREV_SUBJECT, PREV_RUN, PREV_DAY, "아메바"))
        db.add(a_lecture(NOW_SUBJECT, NOW_RUN, NOW_DAY, "그람양성막대균"))
        db.add(Profile(id=LOCAL_TEST_USER_ID, email=LOCAL_TEST_EMAIL, is_admin=True))
        db.add(Profile(id=BUSY, email="busy@studyez.test", preview_prompt="내 방식대로 물어봐"))
        db.add(Profile(id=IDLE, email="idle@studyez.test"))
        db.add(Profile(id=WAITING, email="waiting@studyez.test"))
        for uid in (LOCAL_TEST_USER_ID, BUSY, IDLE):
            db.add(AppGrant(user_id=uid, app=APP_STUDYEZ, role=ROLE_MEMBER))

        # ── 이번 블럭에서 한 것. 예습 3장 + 복습 1장 = 4장.
        for ord_, correct in enumerate((True, True, False), start=1):
            db.add(
                QuizAttempt(
                    user_id=BUSY, subject=NOW_SUBJECT, run_id=NOW_RUN,
                    item_id=f"c00{ord_}", correct=correct, answered_at=late,
                )
            )
        db.add(
            MainAttempt(
                user_id=BUSY, subject=NOW_SUBJECT, run_id=NOW_RUN,
                item_id="m001", correct=True, answered_at=late,
            )
        )
        for kind in ("pre_apkg", "notes_prev"):
            db.add(
                AssetGrab(
                    user_id=BUSY, subject=NOW_SUBJECT, run_id=NOW_RUN,
                    kind=kind, count=2, first_at=late, last_at=late,
                )
            )
        for kind, times in (("share", 3), ("mine", 1)):
            db.add(
                PreviewOpen(
                    user_id=BUSY, subject=NOW_SUBJECT, run_id=NOW_RUN,
                    kind=kind, count=times, first_at=late, last_at=late,
                )
            )

        # ── 지난 블럭에서 한 것. **이번 블럭 창에는 안 들어와야 한다.**
        for ord_ in (1, 2):
            db.add(
                QuizAttempt(
                    user_id=BUSY, subject=PREV_SUBJECT, run_id=PREV_RUN,
                    item_id=f"p00{ord_}", correct=True, answered_at=PREV_AT,
                )
            )
        db.add(
            AssetGrab(
                user_id=BUSY, subject=PREV_SUBJECT, run_id=PREV_RUN,
                kind="main_apkg", count=1, first_at=PREV_AT, last_at=PREV_AT,
            )
        )

        # 개인 예습 대화 하나. **빈 줄도 하나 넣는다** — 저장했다 지운 자리이고,
        # 그것까지 세면 「만든 적 있다」가 거짓으로 부풀어 오른다.
        db.add(UserPreview(user_id=BUSY, subject=NOW_SUBJECT, run_id=NOW_RUN,
                           provider="chatgpt", conversation_url="https://chatgpt.com/c/abc",
                           updated_at=late))
        db.add(UserPreview(user_id=BUSY, subject=PREV_SUBJECT, run_id=PREV_RUN,
                           provider="chatgpt", conversation_url="", updated_at=PREV_AT))
        # 기본 링크. 강의당 하나이고 **사람별 수에 섞이면 안 된다.**
        db.add(Preview(subject=NOW_SUBJECT, run_id=NOW_RUN, provider="chatgpt",
                       share_url="https://chatgpt.com/share/xyz", conversation_url=""))
        db.commit()


def main() -> None:
    seed()
    client = TestClient(app)

    print("\n[1] 기본은 이번 블럭이고, 그 창 안의 것만 센다")
    payload = client.get("/api/admin/usage", headers=ADMIN).json()
    rows = {row["id"]: row for row in payload["users"]}
    busy, idle, waiting = rows.get(BUSY, {}), rows.get(IDLE, {}), rows.get(WAITING, {})
    check("가입한 넷이 다 온다", len(payload["users"]) == 4, sorted(rows))
    check("창이 이번 블럭이다", payload["window"]["key"] == "block", payload["window"])
    check("어느 블럭인지 적는다", NOW_SUBJECT in payload["window"]["label"], payload["window"])
    # 이번 블럭 4장 + 지난 블럭 2장 = 6장. **4가 나와야 창이 일을 한 것이다.**
    check("푼 카드 4장", busy.get("cards") == 4, busy.get("cards"))
    check("받은 덱 1편", busy.get("decks") == 1, busy.get("decks"))
    check("무엇을 쟀는지 같이 온다", bool(payload["window"]["from"]), payload["window"])
    check("이번 블럭은 끝이 열려 있다", payload["window"]["to"] is None, payload["window"])

    print("\n[2] 지난 블럭으로 바꾸면 그때 한 것만 센다")
    prev = client.get("/api/admin/usage?window=prev", headers=ADMIN).json()
    prev_busy = {row["id"]: row for row in prev["users"]}[BUSY]
    check("창이 지난 블럭이다", prev["window"]["key"] == "prev", prev["window"])
    check("어느 블럭인지 적는다", PREV_SUBJECT in prev["window"]["label"], prev["window"])
    check("푼 카드 2장", prev_busy["cards"] == 2, prev_busy["cards"])
    check("받은 덱 1편", prev_busy["decks"] == 1, prev_busy["decks"])
    # **끝이 닫혀 있어야 한다.** 안 닫으면 지난 블럭이 이번 블럭까지 먹는다.
    check("지난 블럭은 끝이 닫혀 있다", bool(prev["window"]["to"]), prev["window"])
    check("이번 블럭 링크는 안 센다", prev_busy["opens"]["share"] == 0, prev_busy["opens"])

    print("\n[3] 최근 7일은 블럭과 따로 선다")
    week = client.get("/api/admin/usage?window=week", headers=ADMIN).json()
    week_busy = {row["id"]: row for row in week["users"]}[BUSY]
    check("창이 최근 7일이다", week["window"]["key"] == "week", week["window"])
    check("이번 블럭 것만 든다", week_busy["cards"] == 4, week_busy["cards"])
    check(
        "고를 수 있는 창 셋",
        [row["key"] for row in week["windows"]] == ["block", "prev", "week"],
        week["windows"],
    )
    check("없는 기간은 422", client.get("/api/admin/usage?window=nope", headers=ADMIN).status_code == 422)

    print("\n[4] 0이 갈라진다 — 안 쓴 사람과 못 쓰는 사람")
    check("둘 다 활동이 없다", not idle.get("lastAt") and not waiting.get("lastAt"))
    check("안 쓴 사람은 문이 열려 있다", idle.get("hasAccess") is True, idle)
    check("못 쓰는 사람은 문이 닫혀 있다", waiting.get("hasAccess") is False, waiting)
    check("쓰는 사람이 맨 위", payload["users"][0]["id"] == BUSY, payload["users"][0].get("email"))
    # **마지막 활동은 창을 안 탄다.** 창을 자르면 「마지막으로 언제 왔나」가 뜻이 없다.
    check("지난 블럭 창에서도 마지막은 그대로", prev_busy["lastAt"] == busy["lastAt"], prev_busy["lastAt"])

    print("\n[5] 기본 링크와 개인 링크가 갈린다")
    check("기본 1편", busy["opens"]["share"] == 1, busy["opens"])
    check("개인 1편", busy["opens"]["mine"] == 1, busy["opens"])
    # 기본 링크(`preview`)는 강의당 하나라 사람별 수에 없다. 섞였으면 2가 됐을 것이다.
    check("개인 대화 1개 — 빈 줄은 안 센다", busy["previews"] == 1, busy["previews"])
    check("언제부터 남았는지 온다", bool(payload["opensSince"]), payload["opensSince"])
    check("프롬프트를 고쳤다", busy["prompt"]["custom"] is True, busy["prompt"])
    check("안 고친 사람은 기본", idle["prompt"]["custom"] is False, idle["prompt"])

    print("\n[6] 자세한 내역은 강의마다 서고 기간을 안 자른다")
    detail = client.get(f"/api/admin/usage/{BUSY}", headers=ADMIN).json()
    lectures = detail["lectures"]
    # **두 블럭이 다 온다.** 여기서까지 자르면 「예전에 뭘 했나」를 볼 자리가 없다.
    check("2편", len(lectures) == 2, [row["runId"] for row in lectures])
    first = lectures[0] if lectures else {}
    check("최근에 손댄 편이 먼저", first.get("runId") == NOW_RUN, [row["runId"] for row in lectures])
    check("제목이 온다", first.get("title") == "그람양성막대균", first.get("title"))
    check("본인이 맞다고 한 것 2장", first.get("pre", {}).get("selfCorrect") == 2, first.get("pre"))
    check("받아 간 것이 편에 붙는다", first.get("grabs") == ["notes_prev", "pre_apkg"], first.get("grabs"))
    check("편마다 링크도 갈린다", first.get("opens") == {"share": 3, "mine": 1}, first.get("opens"))
    check("고친 프롬프트가 온다", detail["user"].get("previewPrompt") == "내 방식대로 물어봐", detail["user"])

    print("\n[7] 없는 계정은 404")
    check("404", client.get("/api/admin/usage/nobody", headers=ADMIN).status_code == 404)

    print(f"\n{'실패 ' + str(len(failures)) if failures else '모두 통과'}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
