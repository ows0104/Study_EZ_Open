"""모아받기 — 하루치·블럭 전체를 한 파일로 받을 때 서버가 하는 세 가지.

**여기서 지키려는 것은 하나다: 「안 받은 것만」이 거짓말을 하지 않는가.**

그 말이 서려면 둘이 맞아야 한다 — 덱을 **종류로** 세는 것(`marks`·`grabbed` 는
자리 하나에 여러 종류를 묶어서 못 쓴다)과, **파일이 나간 뒤에** 적는 것. 뒤의
것이 이 갈래에서 새로 생긴 자리다. 한 편짜리 내려받기는 서명하면서 같이 적는데,
모아받기는 서명과 저장 사이가 몇 분이라 그 사이에 깨질 수 있다. 너무 일찍 적으면
**받은 적 없는 덱이 목록에서 빠진다.**

    server/.venv/Scripts/python.exe -m tests.test_bundles
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bundles-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'bundles.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import LOCAL_TEST_USER_ID  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Asset, AssetGrab, Lecture  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


# (과목, run_id, 날짜, 교시). 하루 둘 · 과목 둘로 잡는다 — 「하루」와 「블럭」이
# 서로 다른 묶음이라는 것을 이 배치 하나가 보인다.
LECTURES = [
    ("병리학", "260812_01", date(2026, 8, 12), 1),
    ("병리학", "260812_02", date(2026, 8, 12), 2),
    ("병리학", "260813_01", date(2026, 8, 13), 1),
    ("기생충학", "260812_03", date(2026, 8, 12), 3),
]
UPLOADED_AT = datetime(2026, 8, 13, tzinfo=UTC)


def seed() -> None:
    Base.metadata.create_all(engine)
    storage = Path(os.environ["STUDYEZ_LOCAL_STORAGE_DIR"])
    with SessionLocal() as db:
        for subject, run_id, day, slot in LECTURES:
            db.add(
                Lecture(
                    subject=subject, run_id=run_id, uid=f"{run_id}#{subject}", date=day,
                    slot=slot, slot_end=slot, start_time="09:00", title=f"{run_id} 편",
                    professors=[], author="", version=1,
                )
            )
            for kind in ("pre_apkg", "main_apkg"):
                key = f"lectures/{subject}/{run_id}/{kind}/deck.apkg"
                path = storage / key
                path.parent.mkdir(parents=True, exist_ok=True)
                # 내용은 아무래도 좋다. 이 검사가 보는 것은 **바이트가 나오는가**와
                # **몇 바이트라고 말하는가**이지 apkg 의 속이 아니다(속을 보는 것은
                # `quizgen.build.verify` 이고, 합치는 쪽은 브라우저에 있다).
                path.write_bytes(kind.encode() * 4)
                db.add(
                    Asset(
                        id=f"{subject}-{run_id}-{kind}", subject=subject, run_id=run_id,
                        kind=kind, filename=f"{run_id} {kind}.apkg", object_key=key,
                        size_bytes=path.stat().st_size, content_type="application/octet-stream",
                        uploaded_at=UPLOADED_AT,
                    )
                )
        # **같은 자리에 파일이 둘.** 이름이 달라진 채로 다시 구워지면 표에 두 줄이
        # 남는다(`uq_asset_slot` 이 파일명까지 본다). 한 줄로 접히지 않으면 화면이
        # 「12편」이라 적고 같은 덱을 두 번 받는다.
        twin_key = "lectures/병리학/260813_01/main_apkg/다시 구운 것.apkg"
        twin = storage / twin_key
        twin.parent.mkdir(parents=True, exist_ok=True)
        twin.write_bytes(b"newer deck")
        db.add(
            Asset(
                id="병리학-260813_01-main_apkg-2", subject="병리학", run_id="260813_01",
                kind="main_apkg", filename="다시 구운 것.apkg", object_key=twin_key,
                size_bytes=twin.stat().st_size, content_type="application/octet-stream",
                # 같은 flush의 기본 시각은 같을 수 있다. 시계 해상도에 의존하지 않는다.
                uploaded_at=UPLOADED_AT,
            )
        )
        # 덱이 아닌 자산도 하나 둔다. 목록에 섞여 들면 「12편」이 거짓이 된다.
        db.add(
            Asset(
                id="notes-1", subject="병리학", run_id="260812_01", kind="notes_current",
                filename="노트.pdf", object_key="lectures/병리학/260812_01/notes_current/n.pdf",
                size_bytes=3, content_type="application/pdf",
            )
        )
        db.commit()


def main() -> None:
    seed()
    client = TestClient(app)

    print("\n[1] 목록 — 덱만, 그리고 아직 아무것도 안 받은 상태")
    decks = client.get("/api/bundles/decks", headers=USER).json()["decks"]
    check("덱 8개(편 4 × 갈래 2)", len(decks) == 8, len(decks))
    check("필기는 안 섞인다", {d["kind"] for d in decks} == {"pre", "main"}, {d["kind"] for d in decks})
    check("아무것도 안 받았다", not any(d["grabbed"] for d in decks))
    check("크기를 말한다", all(d["sizeBytes"] > 0 for d in decks))
    twin = [d for d in decks if d["runId"] == "260813_01" and d["kind"] == "main"]
    check("한 자리에 파일이 둘이어도 한 줄이다", len(twin) == 1, twin)
    check("업로드 시각이 같으면 ID로 순서를 정한다", twin and twin[0]["filename"] == "다시 구운 것.apkg", twin)
    served = client.get("/api/bundles/decks/병리학/260813_01/main", headers=USER)
    check("바이트도 같은 것을 준다", served.content == b"newer deck", served.content)
    check("센 크기와 실제 길이가 같다", twin and twin[0]["sizeBytes"] == len(served.content),
          (twin[0]["sizeBytes"] if twin else None, len(served.content)))
    check(
        "날짜와 과목이 같이 온다 — 하루로도 과목으로도 갈라야 한다",
        {(d["date"], d["subject"]) for d in decks}
        == {("2026-08-12", "병리학"), ("2026-08-13", "병리학"), ("2026-08-12", "기생충학")},
    )

    print("\n[2] 하루와 블럭은 다른 묶음이다")
    day = [d for d in decks if d["date"] == "2026-08-12" and d["kind"] == "pre"]
    block = [d for d in decks if d["subject"] == "병리학" and d["kind"] == "pre"]
    check("8-12 예습은 3편 — 두 과목이 같이 선다", len(day) == 3, [d["runId"] for d in day])
    check("병리학 예습은 3편 — 이틀에 걸쳐 선다", len(block) == 3, [d["runId"] for d in block])
    check(
        "둘은 같은 묶음이 아니다",
        {d["runId"] for d in day} != {d["runId"] for d in block},
    )

    print("\n[3] 바이트 — 받아도 「받았다」가 안 적힌다")
    got = client.get("/api/bundles/decks/병리학/260812_01/pre", headers=USER)
    check("200", got.status_code == 200, got.text)
    check("내용이 그대로 나온다", got.content == b"pre_apkg" * 4, got.content[:40])
    check("길이를 실어 보낸다", got.headers.get("content-length") == str(len(got.content)))
    with SessionLocal() as db:
        check("아직 아무것도 안 적혔다", db.query(AssetGrab).count() == 0)

    check(
        "모르는 갈래는 404",
        client.get("/api/bundles/decks/병리학/260812_01/notes", headers=USER).status_code == 404,
    )
    check(
        "다른 과목의 같은 run_id는 404 — 키는 (subject, run_id)다",
        client.get("/api/bundles/decks/기생충학/260812_01/pre", headers=USER).status_code == 404,
    )
    check("로그인 없이는 안 나간다", client.get("/api/bundles/decks/병리학/260812_01/pre").status_code == 401)

    print("\n[4] 파일이 손에 들어간 뒤에 적는다")
    body = {"decks": [{"subject": "병리학", "runId": d["runId"], "kind": "pre"} for d in block]}
    recorded = client.post("/api/bundles/grabs", headers=USER, json=body)
    check("200", recorded.status_code == 200, recorded.text)
    check("3편이 적혔다", recorded.json()["recorded"] == 3, recorded.json())

    after = client.get("/api/bundles/decks", headers=USER).json()["decks"]
    grabbed = {(d["subject"], d["runId"], d["kind"]) for d in after if d["grabbed"]}
    check(
        "받은 것만 표시된다 — 같은 편의 복습은 그대로 남는다",
        grabbed == {("병리학", d["runId"], "pre") for d in block},
        grabbed,
    )
    fresh = [d for d in after if d["subject"] == "병리학" and d["kind"] == "pre" and not d["grabbed"]]
    check("병리학 예습에 안 받은 것이 없다", not fresh, [d["runId"] for d in fresh])

    print("\n[5] 새 편이 구워지면 그것만 남는다 — 이 기능의 요점")
    with SessionLocal() as db:
        db.add(
            Lecture(
                subject="병리학", run_id="260814_01", uid="260814_01#병리학",
                date=date(2026, 8, 14), slot=1, slot_end=1, start_time="09:00",
                title="나중에 구워진 편", professors=[], author="", version=1,
            )
        )
        key = "lectures/병리학/260814_01/pre_apkg/deck.apkg"
        path = Path(os.environ["STUDYEZ_LOCAL_STORAGE_DIR"]) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"new!")
        db.add(
            Asset(
                id="late-pre", subject="병리학", run_id="260814_01", kind="pre_apkg",
                filename="늦게 나온 덱.apkg", object_key=key, size_bytes=4,
                content_type="application/octet-stream",
            )
        )
        db.commit()

    later = client.get("/api/bundles/decks", headers=USER).json()["decks"]
    still_fresh = [
        d for d in later if d["subject"] == "병리학" and d["kind"] == "pre" and not d["grabbed"]
    ]
    check("안 받은 것은 새 편 하나뿐이다", [d["runId"] for d in still_fresh] == ["260814_01"], still_fresh)

    print("\n[6] 다시 받아도 표는 안 부서진다")
    again = client.post("/api/bundles/grabs", headers=USER, json=body)
    check("200", again.status_code == 200, again.text)
    with SessionLocal() as db:
        row = db.get(AssetGrab, (LOCAL_TEST_USER_ID, "병리학", block[0]["runId"], "pre_apkg"))
        check(
            "줄이 늘지 않고 센 수만 오른다",
            row is not None and row.count == 2 and db.query(AssetGrab).count() == 3,
            (row.count if row else None, db.query(AssetGrab).count()),
        )

    print("\n[7] 없는 편을 섞어 보내도 나머지는 적힌다")
    mixed = client.post(
        "/api/bundles/grabs",
        headers=USER,
        json={
            "decks": [
                {"subject": "병리학", "runId": "260814_01", "kind": "pre"},
                {"subject": "병리학", "runId": "없는편", "kind": "pre"},
            ]
        },
    )
    check("있는 것만 적힌다", mixed.json()["recorded"] == 1, mixed.json())

    print("\n[8] 못 쓰는 요청은 막는다")
    check(
        "빈 목록은 422",
        client.post("/api/bundles/grabs", headers=USER, json={"decks": []}).status_code == 422,
    )
    check(
        "모르는 갈래는 422",
        client.post(
            "/api/bundles/grabs",
            headers=USER,
            json={"decks": [{"subject": "병리학", "runId": "260812_01", "kind": "notes"}]},
        ).status_code == 422,
    )
    too_many = client.post(
        "/api/bundles/grabs",
        headers=USER,
        json={"decks": [{"subject": "병리학", "runId": f"r{i}", "kind": "pre"} for i in range(401)]},
    )
    check("한 번에 받을 수 있는 수를 넘기면 422", too_many.status_code == 422, too_many.text)

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
