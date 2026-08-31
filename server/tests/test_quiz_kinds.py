"""웹 풀이 두 갈래가 서로를 안 건드리는가.

2026-08-31에 복습도 웹에서 풀 수 있게 되면서 생긴 검사다. 두 갈래가 표를 나눠
쓰는 이유가 여기 있다 — **`item_id`가 겹친다.** 파이프라인이 두 갈래 다 `c001`
부터 세므로, 한 표에 담으면 복습에서 찍은 것이 예습 기록을 덮어쓴다.

슬라이드도 같은 함정이다. 예습 슬라이드는 **작년** run 에서 오고 복습 슬라이드는
**올해** run 에서 오는데 붙는 자리는 같은 강의다. kind 로 안 가르면 같은
`slide_no` 가 둘이 되고 `db.scalar` 가 아무거나 집는다 — 아무 데서도 안 터지고
예습 해설이 조용히 엉뚱한 슬라이드를 띄운다.

    server/.venv/Scripts/python.exe -m tests.test_quiz_kinds
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-quizkind-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'kinds.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Asset, Lecture, TimetableEvent  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "병리학", "260825_01"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"
ADMIN = f"/api/admin/lectures/{SUBJECT}/{RUN}"

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def an_item(item_id: str, stem: str, answer: str, slide_no: int) -> dict:
    return {
        "id": item_id,
        "qtype": "basic",
        "stem": stem,
        "answer": answer,
        "explanation": "",
        "focus": "spine",
        "card_type": "term",
        "exam_hit": False,
        "slide_no": slide_no,
        "source_type": "lecture",
        "source_anchor": "",
        "flags": [],
    }


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(
            TimetableEvent(
                id="official-kind-1",
                date=datetime.date(2026, 8, 25),
                start_time="09:00",
                end_time="09:50",
                title="질병의 병리학적 이해 25",
                details="",
                professor="이혜승",
                category="lecture",
                course="질병의 병리학적 이해",
                course_key="질병의병리학적이해",
                slot=1,
            )
        )
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
                timetable_event_id="official-kind-1",
            )
        )
        # 슬라이드 12번이 갈래마다 하나씩. **여기가 이 파일의 요점이다.**
        for index, (kind, key) in enumerate(
            (("media", "lectures/x/pre_s012.png"), ("main_media", "lectures/x/main_s012.png"))
        ):
            db.add(
                Asset(
                    id=f"asset-{index}",
                    subject=SUBJECT,
                    run_id=RUN,
                    kind=kind,
                    filename=Path(key).name,
                    object_key=key,
                    size_bytes=1,
                    content_type="image/png",
                    slide_no=12,
                )
            )
        db.commit()

    client = TestClient(app)

    # ── 같은 id 로 두 갈래를 채운다.
    pre = client.put(
        f"{ADMIN}/pre-items",
        json={"items": [an_item("c001", "예습 문항", "예습 답", 12)]},
        headers=RUNNER,
    )
    main_ = client.put(
        f"{ADMIN}/main-items",
        json={"items": [an_item("c001", "복습 문항", "복습 답", 12)]},
        headers=RUNNER,
    )
    check("두 갈래를 같은 id로 넣을 수 있다", (pre.status_code, main_.status_code) == (200, 200),
          (pre.status_code, main_.status_code))

    detail = client.get(BASE, headers=USER).json()
    check("강의 상세가 둘을 따로 센다",
          detail["prequiz"]["itemCount"] == 1 and detail["mainquiz"]["itemCount"] == 1,
          (detail.get("prequiz"), detail.get("mainquiz")))

    # ── 문항이 안 섞인다.
    pre_stem = client.get(f"{BASE}/prequiz", headers=USER).json()["items"][0]["stem"]
    main_stem = client.get(f"{BASE}/mainquiz", headers=USER).json()["items"][0]["stem"]
    check("문항이 갈래를 안 넘어간다", (pre_stem, main_stem) == ("예습 문항", "복습 문항"),
          (pre_stem, main_stem))

    # ── 답도 안 섞인다. **여기가 섞이면 오답 해설이 남의 답을 편다.**
    pre_answer = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c001"}, headers=USER).json()
    main_answer = client.post(f"{BASE}/mainquiz/reveal", json={"itemId": "c001"}, headers=USER).json()
    check("답이 갈래를 안 넘어간다",
          (pre_answer["answer"], main_answer["answer"]) == ("예습 답", "복습 답"),
          (pre_answer["answer"], main_answer["answer"]))

    # ── 근거 슬라이드가 제 갈래의 것을 집는다.
    check("슬라이드가 갈래를 안 넘어간다",
          "pre_s012" in (pre_answer["slideUrl"] or "") and "main_s012" in (main_answer["slideUrl"] or ""),
          (pre_answer["slideUrl"], main_answer["slideUrl"]))

    # ── 채점이 안 섞인다. 같은 id 라 표가 하나였으면 뒤엣것이 앞엣것을 덮는다.
    client.post(f"{BASE}/prequiz/grade", json={"itemId": "c001", "correct": False}, headers=USER)
    client.post(f"{BASE}/mainquiz/grade", json={"itemId": "c001", "correct": True}, headers=USER)
    detail = client.get(BASE, headers=USER).json()
    check("채점이 갈래를 안 덮는다",
          (detail["prequiz"]["correct"], detail["mainquiz"]["correct"]) == (0, 1),
          (detail["prequiz"], detail["mainquiz"]))

    # ── 한쪽을 지워도 다른 쪽은 산다.
    client.delete(f"{BASE}/mainquiz/attempts", headers=USER)
    detail = client.get(BASE, headers=USER).json()
    check("한 갈래의 기록을 지워도 다른 갈래는 남는다",
          (detail["prequiz"]["answered"], detail["mainquiz"]["answered"]) == (1, 0),
          (detail["prequiz"]["answered"], detail["mainquiz"]["answered"]))

    # ── 문항이 없는 갈래는 `null` 이다. 화면이 그 자리를 아예 안 그린다.
    client.put(f"{ADMIN}/main-items", json={"items": []}, headers=RUNNER)
    detail = client.get(BASE, headers=USER).json()
    check("문항이 없으면 null이다", detail["mainquiz"] is None, detail["mainquiz"])

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        raise SystemExit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()
