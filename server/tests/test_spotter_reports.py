"""제보가 쌓이는 것을 서버가 알아채는가.

세는 규칙이 둘이고 둘 다 조용히 틀릴 수 있어서 따로 잡아 둔다.

  * 문항 묶음은 **사람**을 센다. 한 사람이 같은 문항을 두 번 눌러도 한 명이다.
  * 사진 묶음은 **여러 문항에 걸친 것만** 낸다. 한 문항에만 걸린 사진은 문항
    묶음이 이미 말한 것이라 두 번 적지 않는다.

SQLite로 돈다.

    server/.venv/Scripts/python.exe -m tests.test_spotter_reports
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-reports-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'reports.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import SPOTTER_ALERT_MIN, SpotterReport  # noqa: E402
from app.routes.spotter import ensure_threads  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def add(user: str, question: str, images: str) -> None:
    """제보 한 줄. 로컬 테스트는 사람이 하나뿐이라 나머지는 직접 놓는다.

    놓고 나서 `ensure_threads`를 부르는 것은 **제보가 들어오는 길이 그렇기
    때문이다** — 화면에서 온 제보는 `create_report`가 저장한 직후에 같은 것을
    부른다. 여기서 안 부르면 글타래가 서는 자리를 안 지나고 넘어간다.
    """
    with SessionLocal() as db:
        db.add(
            SpotterReport(
                user_id=user,
                question_id=question,
                kind="image",
                note="흐립니다",
                stem=f"{question}의 문면",
                answer="Ascaris lumbricoides",
                image=f"{images} (실습 정리본)",
                images=images,
            )
        )
        db.commit()
        ensure_threads(db)


def reports() -> dict:
    response = client.get("/api/spotter/admin/reports", headers=USER)
    assert response.status_code == 200, response.text
    return response.json()


def group(data: dict, question: str) -> dict:
    return next(g for g in data["groups"] if g["questionId"] == question)


client = TestClient(app)


def main() -> None:
    Base.metadata.create_all(engine)

    print("\n[1] 화면이 보낸 제보에 사진 이름이 남는가")
    made = client.post(
        "/api/spotter/reports",
        headers=USER,
        json={
            "questionId": "q-two-photos",
            "kind": "image",
            "note": "둘째 사진이 흐립니다",
            "stem": "다음 충란은?",
            "answer": "Ascaris lumbricoides",
            "image": "a.jpg, b.jpg (실습 정리본 · 실제실습본)",
            "images": ["a.jpg", "b.jpg"],
        },
    )
    check("제보 200", made.status_code == 200, made.text)
    check("사진 둘이 남았다", made.json().get("images") == ["a.jpg", "b.jpg"], made.json())

    print("\n[2] 한 사람이 두 번 눌러도 한 명이다")
    client.post(
        "/api/spotter/reports",
        headers=USER,
        json={"questionId": "q-two-photos", "note": "다시 보니 정답도 이상합니다",
              "kind": "answer", "images": ["a.jpg", "b.jpg"]},
    )
    data = reports()
    check("문항 한 줄", group(data, "q-two-photos")["open"] == 1, data["groups"])
    check("아직 조용하다", data["alert"]["questions"] == 0, data["alert"])

    print(f"\n[3] {SPOTTER_ALERT_MIN}명이 같은 문항에 걸리면 뜬다")
    for i in range(SPOTTER_ALERT_MIN - 1):
        add(f"user-{i}", "q-two-photos", "a.jpg, b.jpg")
    data = reports()
    hot = group(data, "q-two-photos")
    check(f"{SPOTTER_ALERT_MIN}명", hot["open"] == SPOTTER_ALERT_MIN, hot["open"])
    check("빨갛다", hot["hot"] is True, hot)
    check("배지가 1을 든다", data["alert"]["questions"] == 1, data["alert"])
    check("선을 함께 낸다", data["alert"]["min"] == SPOTTER_ALERT_MIN, data["alert"])

    print("\n[4] 한 문항에만 걸린 사진은 사진 묶음에 안 낸다")
    check("사진 묶음 없음", data["images"] == [], data["images"])

    print("\n[5] 흩어져 들어온 같은 사진은 사진 묶음이 잡는다")
    # 세 사람이 **다른 문항**을 제보했지만 사진은 같다. 문항으로만 세면
    # 셋 다 한 명씩이라 아무 데도 안 걸린다.
    for i in range(SPOTTER_ALERT_MIN):
        add(f"scatter-{i}", f"q-scatter-{i}", "blurry.jpg")
    data = reports()
    check(
        "문항 쪽은 조용하다",
        all(group(data, f"q-scatter-{i}")["hot"] is False for i in range(SPOTTER_ALERT_MIN)),
        [group(data, f"q-scatter-{i}")["open"] for i in range(SPOTTER_ALERT_MIN)],
    )
    spot = next((g for g in data["images"] if g["image"] == "blurry.jpg"), None)
    check("사진 쪽이 잡았다", spot is not None, data["images"])
    if spot:
        check(f"{SPOTTER_ALERT_MIN}명", spot["open"] == SPOTTER_ALERT_MIN, spot)
        check("문항 셋을 짚는다", len(spot["questionIds"]) == SPOTTER_ALERT_MIN, spot)
    check("배지가 사진 1을 든다", data["alert"]["images"] == 1, data["alert"])

    print("\n[6] 한 사람이 같은 사진의 두 문항을 제보해도 한 명이다")
    add("dupe", "q-dupe-a", "twice.jpg")
    add("dupe", "q-dupe-b", "twice.jpg")
    data = reports()
    spot = next((g for g in data["images"] if g["image"] == "twice.jpg"), None)
    check("한 명뿐이라 안 뜬다", spot is None, spot)

    print("\n[7] 닫은 제보는 안 센다")
    client.post("/api/spotter/admin/reports/q-two-photos/close", headers=USER)
    data = reports()
    check("문항이 식었다", group(data, "q-two-photos")["hot"] is False, group(data, "q-two-photos"))
    check("배지도 내려갔다", data["alert"]["questions"] == 0, data["alert"])

    # 콘솔이 cp949라 찍는 글에는 줄표를 안 쓴다. 설명은 주석에 둔다.
    print("\n[8] 옛 줄: `images`가 비어 있어도 `image`에서 이름을 뽑는다")
    for i in range(SPOTTER_ALERT_MIN):
        with SessionLocal() as db:
            db.add(
                SpotterReport(
                    user_id=f"legacy-{i}",
                    question_id=f"q-legacy-{i}",
                    kind="image",
                    image="old.jpg, old2.jpg (실습 정리본 · 실제실습본)",
                )
            )
            db.commit()
    data = reports()
    check(
        "옛 줄도 사진으로 묶인다",
        any(g["image"] == "old.jpg" for g in data["images"]),
        data["images"],
    )

    print("\n[9] 선을 넘으면 글타래가 저절로 선다")
    threads = client.get("/api/spotter/threads", headers=USER).json()
    seats = {(t["kind"], t["subject"]) for t in threads["threads"]}
    check("문항 글타래", ("question", "q-two-photos") in seats, sorted(seats))
    check("사진 글타래", ("image", "blurry.jpg") in seats, sorted(seats))
    check("한 명짜리는 안 선다", ("question", "qsolo") not in seats, sorted(seats))
    hot = next(t for t in threads["threads"] if t["subject"] == "blurry.jpg")
    check("사진 글타래가 걸린 문항을 다 안는다", len(hot["questionIds"]) == SPOTTER_ALERT_MIN, hot)
    check("걸린 사람 수를 든다", hot["reports"] == SPOTTER_ALERT_MIN, hot)

    print("\n[10] 열린 글타래의 문항은 새 세트에서 빠진다")
    flagged = client.get("/api/spotter/flagged", headers=USER).json()
    check("문항이 격리됐다", "q-two-photos" in flagged["questions"], flagged)
    check("사진이 격리됐다", "blurry.jpg" in flagged["images"], flagged)

    print("\n[11] 의견을 달고 지운다")
    posted = client.post(
        "/api/spotter/threads/image/blurry.jpg/comments",
        headers=USER,
        json={"body": "제 화면에서도 초점이 안 맞습니다. 원본을 다시 자르는 게 좋겠습니다."},
    )
    check("댓글 200", posted.status_code == 200, posted.text)
    body = posted.json()
    check("한 줄 달렸다", len(body["comments"]) == 1, body["comments"])
    check("이름은 앞부분만", "@" not in body["comments"][0]["who"], body["comments"][0])
    check("빈 글은 막는다",
          client.post("/api/spotter/threads/image/blurry.jpg/comments",
                      headers=USER, json={"body": "   "}).status_code == 400)
    gone = client.delete(f"/api/spotter/comments/{body['comments'][0]['id']}", headers=USER)
    check("지움 200", gone.status_code == 200, gone.text)
    after = client.get("/api/spotter/threads/image/blurry.jpg", headers=USER).json()
    check("줄은 남고 내용만 빈다",
          after["comments"][0]["deleted"] and after["comments"][0]["body"] == "",
          after["comments"][0])

    print("\n[12] 닫으면 격리가 풀린다")
    closed = client.patch(
        "/api/spotter/admin/threads/image/blurry.jpg",
        headers=USER,
        json={"status": "resolved", "verdict": "사진을 다시 잘라 올렸습니다."},
    )
    check("닫힘 200", closed.status_code == 200, closed.text)
    flagged = client.get("/api/spotter/flagged", headers=USER).json()
    check("사진이 풀렸다", "blurry.jpg" not in flagged["images"], flagged)
    check("문항은 그대로 잠겨 있다", "q-two-photos" in flagged["questions"], flagged)

    print("\n[13] 닫은 글타래는 제보가 더 들어와도 안 되살아난다")
    add("late", "qblur9", "blurry.jpg")
    threads = client.get("/api/spotter/threads", headers=USER).json()["threads"]
    spot = next(t for t in threads if t["subject"] == "blurry.jpg")
    check("닫힌 채로 있다", spot["status"] == "resolved", spot)
    check("결론이 남아 있다", spot["verdict"].startswith("사진을"), spot)

    print()
    if failures:
        print(f"실패 {len(failures)}건: " + ", ".join(failures))
        raise SystemExit(1)
    print("모두 통과")


if __name__ == "__main__":
    main()
