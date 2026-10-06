"""웹 풀이가 망각곡선으로 돌고, 찍은 것이 되돌아가는가.

2026-09-18에 생겼다 — 「웹 퀴즈를 안키처럼 해줘. 망각곡선에 기반해서. 그리고
이전으로 돌아가는 기능도 만들어줘.」

사다리 자체는 `tests/test_srs.py`가 순수 함수로 잰다. **여기서는 그것이 표와
경로를 지나 오는지를 본다** — 다른 검사가 있어야 하는 이유가 넷이다.

    ① 찍은 일정이 정말 표에 남는가(다시 받아 봐서 확인한다)
    ② 되돌리기가 **찍기 전 그 값**으로 돌아가는가 — 다시 계산하면 안 돌아온다
    ③ 첫 찍기를 되돌리면 줄이 **사라지는가** — 값만 되쓰면 「몇 장 봤다」가 안 본 것을 센다
    ④ 옛 화면의 `{correct: bool}`이 계속 통하는가 — API를 먼저 배포하므로

    server/.venv/Scripts/python.exe -m tests.test_quiz_srs
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-srs-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'srs.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import srs  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Lecture, TimetableEvent  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "기생충학", "260918_02"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"
ADMIN = f"/api/admin/lectures/{SUBJECT}/{RUN}"

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def an_item(item_id: str, ord_: int) -> dict:
    return {
        "id": item_id,
        "qtype": "basic",
        "stem": f"{item_id} 발문",
        "answer": f"{item_id} 답",
        "explanation": "",
        "focus": "spine",
        "card_type": "term",
        "exam_hit": False,
        "slide_no": ord_,
        "source_type": "lecture",
        "source_anchor": "",
        "flags": [],
    }


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(
            TimetableEvent(
                id="official-srs-1",
                date=datetime.date(2026, 9, 18),
                start_time="10:00",
                end_time="10:50",
                title="감염의 기초 18",
                details="",
                professor="홍성태",
                category="lecture",
                course="감염의 기초",
                course_key="감염의기초",
                slot=2,
            )
        )
        db.add(
            Lecture(
                subject=SUBJECT,
                run_id=RUN,
                uid=f"{RUN}#말라리아",
                date=datetime.date(2026, 9, 18),
                slot=2,
                slot_end=2,
                start_time="10:00",
                title="말라리아(1)",
                professors=["홍성태"],
                author="박주항",
                version=1,
                timetable_event_id="official-srs-1",
            )
        )
        db.commit()

    client = TestClient(app)
    client.put(
        f"{ADMIN}/main-items",
        json={"items": [an_item("c001", 1), an_item("c002", 2), an_item("c003", 3)]},
        headers=RUNNER,
    )

    print("\n[1] 안 찍은 카드는 전부 새 카드다")
    payload = client.get(f"{BASE}/mainquiz", headers=USER).json()
    check("셋 다 왔다", len(payload["items"]) == 3, payload["items"])
    check("일정이 아직 없다", all(row["attempt"] is None for row in payload["items"]))
    check("서버 시각이 온다", bool(payload.get("now")), payload.get("now"))
    check("되돌릴 것이 없다", payload["undoable"] is False, payload["undoable"])

    print("\n[2] 답을 펴면 네 버튼의 결과가 같이 온다")
    revealed = client.post(f"{BASE}/mainquiz/reveal", json={"itemId": "c001"}, headers=USER).json()
    check("답이 온다", revealed["answer"] == "c001 답", revealed["answer"])
    check("넷 다 온다", sorted(revealed["next"]) == sorted(srs.GRADES), revealed.get("next"))
    check("새 카드의 Good 은 10분", revealed["next"]["good"] == {"days": 0, "seconds": 600},
          revealed["next"]["good"])
    # 펴는 것만으로는 아무것도 안 남는다. 그 규칙은 일정이 생긴 뒤에도 그대로다.
    check("펴는 것은 기록하지 않는다",
          client.get(f"{BASE}/mainquiz", headers=USER).json()["answered"] == 0)

    print("\n[3] 찍으면 일정이 표에 남는다")
    graded = client.post(
        f"{BASE}/mainquiz/grade", json={"itemId": "c001", "grade": "easy"}, headers=USER
    ).json()
    check("Easy 는 바로 익은 것이 된다", graded["attempt"]["state"] == srs.STATE_REVIEW,
          graded["attempt"])
    check("간격이 나흘이다", graded["attempt"]["intervalDays"] == 4, graded["attempt"])
    check("다음 때가 박혔다", bool(graded["attempt"]["dueAt"]), graded["attempt"])
    check("이제 되돌릴 것이 있다", graded["undoable"] is True, graded)

    payload = client.get(f"{BASE}/mainquiz", headers=USER).json()
    first = next(row for row in payload["items"] if row["itemId"] == "c001")
    check("다시 받아 봐도 그대로다", first["attempt"]["intervalDays"] == 4, first["attempt"])
    check("나머지는 아직 새 카드다",
          [row["attempt"] for row in payload["items"] if row["itemId"] != "c001"] == [None, None])

    print("\n[4] Again 은 분 단위로 다시 낸다")
    again = client.post(
        f"{BASE}/mainquiz/grade", json={"itemId": "c002", "grade": "again"}, headers=USER
    ).json()
    check("익히는 중이 된다", again["attempt"]["state"] == srs.STATE_LEARNING, again["attempt"])
    check("본인 판정은 틀렸다로 남는다", again["correct"] is False, again)
    check("간격은 아직 0이다", again["attempt"]["intervalDays"] == 0, again["attempt"])

    print("\n[5] 되돌리기가 찍기 전으로 돌린다")
    # c001 을 한 번 더 찍어서 4일 → 더 늘려 놓고, 되돌려 4일로 돌아오는지 본다.
    client.post(f"{BASE}/mainquiz/grade", json={"itemId": "c001", "grade": "good"}, headers=USER)
    grown = next(
        row for row in client.get(f"{BASE}/mainquiz", headers=USER).json()["items"]
        if row["itemId"] == "c001"
    )
    check("간격이 늘었다", grown["attempt"]["intervalDays"] > 4, grown["attempt"])

    undone = client.post(f"{BASE}/mainquiz/undo", headers=USER).json()
    check("되돌린 것이 그 카드다", undone["itemId"] == "c001", undone["itemId"])
    check("답이 같이 온다 — 펴진 채로 다시 선다", undone["answer"] == "c001 답", undone["answer"])
    check("간격이 찍기 전으로 돌아왔다", undone["attempt"]["intervalDays"] == 4, undone["attempt"])
    check("아직 더 되돌릴 것이 있다", undone["undoable"] is True, undone)

    payload = client.get(f"{BASE}/mainquiz", headers=USER).json()
    first = next(row for row in payload["items"] if row["itemId"] == "c001")
    check("표에도 돌아갔다", first["attempt"]["intervalDays"] == 4, first["attempt"])
    check("본 장수는 그대로 둘이다", payload["answered"] == 2, payload["answered"])

    print("\n[6] 첫 찍기를 되돌리면 줄이 사라진다")
    # **값만 되쓰면 안 된다.** 「몇 장 봤다」가 안 본 카드를 세게 된다.
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c002 의 again
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c001 의 easy
    payload = client.get(f"{BASE}/mainquiz", headers=USER).json()
    check("전부 새 카드로 돌아갔다", all(row["attempt"] is None for row in payload["items"]),
          [row["attempt"] for row in payload["items"]])
    check("본 장수가 0이다", payload["answered"] == 0, payload["answered"])
    check("되돌릴 것이 없어졌다", payload["undoable"] is False, payload)

    print("\n[7] 되돌릴 것이 없으면 404 — 조용히 아무 일도 안 하지 않는다")
    empty = client.post(f"{BASE}/mainquiz/undo", headers=USER)
    check("404 다", empty.status_code == 404, empty.status_code)

    print("\n[8] 옛 화면의 꼴도 계속 받는다")
    # API 를 먼저 배포하므로, 그 사이 열려 있는 탭이 보내는 것이 이 꼴이다.
    legacy = client.post(
        f"{BASE}/mainquiz/grade", json={"itemId": "c003", "correct": True}, headers=USER
    ).json()
    check("Pass 는 good 으로 받는다", legacy["grade"] == "good", legacy)
    check("일정도 똑같이 선다", legacy["attempt"]["state"] == srs.STATE_LEARNING, legacy["attempt"])
    legacy_again = client.post(
        f"{BASE}/mainquiz/grade", json={"itemId": "c003", "correct": False}, headers=USER
    ).json()
    check("Again 도 그대로다", legacy_again["grade"] == "again", legacy_again)

    print("\n[9] 모르는 채점은 받지 않는다")
    bad = client.post(
        f"{BASE}/mainquiz/grade", json={"itemId": "c003", "grade": "perfect"}, headers=USER
    )
    check("422 다", bad.status_code == 422, bad.status_code)
    naked = client.post(f"{BASE}/mainquiz/grade", json={"itemId": "c003"}, headers=USER)
    check("아무것도 안 보내도 422 다", naked.status_code == 422, naked.status_code)

    print("\n[10] 강의 상세가 「오늘 낼 카드」를 센다")
    detail = client.get(BASE, headers=USER).json()["mainquiz"]
    check("카드가 셋이다", detail["itemCount"] == 3, detail)
    # c003 은 방금 Again 을 눌러 익히는 중(1분 뒤)이고 나머지 둘은 새 카드다.
    check("새 카드 둘", detail["new"] == 2, detail)
    # **익히는 중인 카드는 「나중」이 아니다.** 1분 뒤로 잡혀 있어도 오늘 안에
    # 나온다 — 화면이 미리 낸다(`web/src/lecture/queue.ts` 의 ④). 여기서 나중으로
    # 세면 「오늘 낼 것 0」이라고 적으면서 카드를 내미는 화면이 된다.
    check("익히는 중 하나", detail["learning"] == 1, detail)
    check("나중으로 밀린 것은 없다", detail["later"] == 0, detail)
    check("오늘 낼 것은 셋", detail["due"] == 3, detail)
    check("다음 때가 없다 — 익은 카드가 아직 없다", detail["nextDueAt"] is None, detail)

    print("\n[11] 일정을 지우면 되돌리기 기록도 같이 지워진다")
    # 남겨 두면 없는 줄을 되살리려는 되돌리기가 남는다.
    client.delete(f"{BASE}/mainquiz/attempts", headers=USER)
    payload = client.get(f"{BASE}/mainquiz", headers=USER).json()
    check("전부 새 카드다", all(row["attempt"] is None for row in payload["items"]))
    check("되돌릴 것도 없다", payload["undoable"] is False, payload)
    check("되돌리기가 404 다", client.post(f"{BASE}/mainquiz/undo", headers=USER).status_code == 404)

    print("\n[12] 갈래가 서로의 일정을 안 건드린다")
    # `item_id` 가 겹치는 표라 기록 표도 갈래마다 따로다(`tests/test_quiz_kinds.py`).
    client.put(f"{ADMIN}/pre-items", json={"items": [an_item("c001", 1)]}, headers=RUNNER)
    client.post(f"{BASE}/prequiz/grade", json={"itemId": "c001", "grade": "easy"}, headers=USER)
    pre = client.get(f"{BASE}/mainquiz", headers=USER).json()
    main_ = client.get(f"{BASE}/prequiz", headers=USER).json()
    check("예습만 찍혔다", pre["answered"] == 0 and main_["answered"] == 1,
          (pre["answered"], main_["answered"]))
    check("복습은 되돌릴 것이 없다", pre["undoable"] is False, pre["undoable"])
    check("예습은 되돌릴 것이 있다", main_["undoable"] is True, main_["undoable"])
    check("복습 되돌리기가 예습 것을 안 집는다",
          client.post(f"{BASE}/mainquiz/undo", headers=USER).status_code == 404)

    print("\n[13] 「오늘 놓친 것」이 다시 맞힌 카드도 센다")
    # **`attempt.correct` 로 고르면 이 목록은 영영 빈다.** Again 을 누른 카드는
    # 큐에 남아 있고(때가 안 돼도 미리 낸다), 그래서 「다 했다」에 닿는 순간에는
    # 거짓인 줄이 하나도 없다. 지금은 **오늘 Again 을 누른 기록**으로 고른다.
    client.delete(f"{BASE}/mainquiz/attempts", headers=USER)
    client.post(f"{BASE}/mainquiz/grade", json={"itemId": "c001", "grade": "again"}, headers=USER)
    client.post(f"{BASE}/mainquiz/grade", json={"itemId": "c001", "grade": "easy"}, headers=USER)
    for item_id in ("c002", "c003"):
        client.post(f"{BASE}/mainquiz/grade", json={"itemId": item_id, "grade": "easy"}, headers=USER)
    detail = client.get(BASE, headers=USER).json()["mainquiz"]
    check("세 장 다 찍혔다", detail["answered"] == 3, detail["answered"])
    check("전부 「맞았다」로 남았다", detail["correct"] == 3, detail["correct"])
    missed = [row["itemId"] for row in detail["missed"]]
    check("그래도 막혔던 카드가 목록에 있다", missed == ["c001"], missed)

    # 되돌리면 그 기록도 사라진다 — 잘못 누른 Again 이 목록에 남으면 안 된다.
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c003 easy
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c002 easy
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c001 easy
    client.post(f"{BASE}/mainquiz/undo", headers=USER)  # c001 again
    detail = client.get(BASE, headers=USER).json()["mainquiz"]
    check("되돌린 Again 은 목록에서 빠진다", detail["missed"] == [], detail["missed"])

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        raise SystemExit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()
