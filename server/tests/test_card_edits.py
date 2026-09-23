"""사이트에서 고친 카드가 웹 풀이에 닿고, 다음 쓸기에 안 덮이는가.

2026-09-23 에 섰다 — 문지기가 결함 카드를 막는 대신 올리고, 관리자가 사이트에서
고치거나 빼게 하라는 지시였다(`app/routes/cards.py`).

**요점은 「다음 쓸기」다.** 러너는 문항을 통째로 갈아 끼운다. 고친 것을 문항 표에만
쓰면 화면에서는 고쳐진 것이 보이다가 다음 날 아침 쓸기에 조용히 되돌아간다 — 아무
데서도 안 터진다. 그래서 갈아 끼우기를 한 번 더 지나게 해서 잰다.

    server/.venv/Scripts/python.exe -m tests.test_card_edits
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-cardedit-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'cards.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Lecture  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "미생물학", "260921_03"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"
ADMIN = f"/api/admin/lectures/{SUBJECT}/{RUN}"

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def an_item(item_id: str, stem: str, answer: str, flags: list[str] | None = None) -> dict:
    return {
        "id": item_id, "qtype": "basic", "stem": stem, "answer": answer,
        "explanation": f"{item_id} 해설", "focus": "detail", "card_type": "mechanism",
        "exam_hit": False, "slide_no": 8, "source_type": "lecture",
        "source_anchor": "", "flags": flags or [],
    }


ITEMS = [
    an_item("c001", "첫 질문", "첫 답"),
    an_item("c002", "변이 기전으로 꼽은 것은?", "morphology alteration"),
    an_item("c003", "빈칸 ___", "축"),
]

META = {
    "item_count": 3,
    "verified": {"notes": 3, "missing_media": []},
    "reproduce_defects": ["c002"],
    "reproduce_defect_notes": {
        "c002": {"reason": "needs_options", "note": "분류 체계가 질문에 없다",
                 "reproduced": "gene reassortment"},
    },
    "axis_unresolved": ["c003"],
}


def pre_ids(client: TestClient) -> list[str]:
    return [i["itemId"] for i in client.get(f"{BASE}/prequiz", headers=USER).json()["items"]]


def stem(client: TestClient, item_id: str) -> str:
    items = client.get(f"{BASE}/prequiz", headers=USER).json()["items"]
    return next(i["stem"] for i in items if i["itemId"] == item_id)


def reveal(client: TestClient, item_id: str) -> dict:
    return client.post(f"{BASE}/prequiz/reveal", json={"itemId": item_id}, headers=USER).json()


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(
            subject=SUBJECT, run_id=RUN, uid=f"{RUN}#인수공통", date=datetime.date(2026, 9, 21),
            slot=3, slot_end=3, start_time="11:00", title="인수공통감염 전파경로",
            professors=["염진기"], author="", version=1,
        ))
        db.commit()
    client = TestClient(app)

    # ── 러너가 올린다. 결함 카드가 있어도 올라간다(문지기는 이제 적기만 한다).
    check("문항이 올라간다",
          client.put(f"{ADMIN}/pre-items", json={"items": ITEMS}, headers=RUNNER).status_code == 200)
    client.put(f"{ADMIN}/main-items", json={"items": [an_item("c002", "복습 질문", "복습 답")]},
               headers=RUNNER)
    client.put(f"{ADMIN}/run-meta/pre", json=META, headers=RUNNER)

    review = client.get("/api/admin/card-review", headers=USER).json()
    got = {c["itemId"]: c for c in review["cards"]}
    check("걸린 카드 둘이 목록에 뜬다", sorted(got) == ["c002", "c003"], sorted(got))
    check("결함과 축을 갈라 적는다",
          (got["c002"]["flag"]["why"], got["c003"]["flag"]["why"]) == ("defect", "axis"))
    check("결함 사유와 재현 답이 실린다",
          got["c002"]["flag"]["reason"] == "needs_options"
          and got["c002"]["flag"]["reproduced"] == "gene reassortment", got["c002"]["flag"])
    check("검토 목록에는 답까지 있다", got["c002"]["answer"] == "morphology alteration")
    check("아직 아무도 안 봤다", (review["open"], review["done"]) == (2, 0))
    check("run-meta 가 없는 복습 갈래는 목록에 안 든다",
          all(c["kind"] == "pre" for c in review["cards"]))

    # ── 고친다.
    edited = client.put(f"{ADMIN}/cards/pre/c002",
                        json={"action": "edit", "stem": "gene recombination·mutation과 함께 "
                              "강의가 꼽은 세 번째 기전은? (강의 분류)",
                              "answer": "morphology alteration"},
                        headers=USER)
    check("고친다", edited.status_code == 200, edited.text)
    check("웹 풀이의 질문이 바뀐다", "강의 분류" in stem(client, "c002"), stem(client, "c002"))
    check("원본을 들고 있다", edited.json()["original"]["stem"] == "변이 기전으로 꼽은 것은?")
    check("같은 id 의 복습 카드는 안 바뀐다",
          client.post(f"{BASE}/mainquiz/reveal", json={"itemId": "c002"}, headers=USER)
          .json()["answer"] == "복습 답")

    blank = client.put(f"{ADMIN}/cards/pre/c001", json={"action": "edit", "answer": "  "},
                       headers=USER)
    check("답을 비우지는 못한다", blank.status_code == 422, blank.status_code)
    nothing = client.put(f"{ADMIN}/cards/pre/c001", json={"action": "edit", "answer": "첫 답"},
                         headers=USER)
    check("아무것도 안 고친 edit 은 받지 않는다", nothing.status_code == 422, nothing.status_code)

    # ── 뺀다.
    check("뺀다", client.put(f"{ADMIN}/cards/pre/c003", json={"action": "delete"},
                             headers=USER).status_code == 200)
    check("웹 풀이에서 빠진다", pre_ids(client) == ["c001", "c002"], pre_ids(client))
    listed = client.get(f"{ADMIN}/cards/pre", headers=USER).json()["cards"]
    check("한 편 목록에는 뺀 카드도 남는다(되돌리려고)",
          [(c["itemId"], (c["edit"] or {}).get("action")) for c in listed]
          == [("c001", None), ("c002", "edit"), ("c003", "delete")], listed)
    check("또 빼도 된다", client.put(f"{ADMIN}/cards/pre/c003", json={"action": "delete"},
                                    headers=USER).status_code == 200)

    review = client.get("/api/admin/card-review", headers=USER).json()
    check("둘 다 본 것으로 센다", (review["open"], review["done"]) == (0, 2))

    # ── **다음 쓸기.** 같은 파일을 다시 올린다.
    again = client.put(f"{ADMIN}/pre-items", json={"items": ITEMS}, headers=RUNNER).json()
    check("다시 올려도 판정이 얹힌다",
          (again["itemCount"], again["edited"], again["deleted"]) == (2, 1, 1), again)
    check("뺀 카드가 도로 서지 않는다", pre_ids(client) == ["c001", "c002"], pre_ids(client))
    check("고친 질문이 도로 덮이지 않는다", "강의 분류" in stem(client, "c002"), stem(client, "c002"))

    # 표시만 바뀌어 올라온 것은 같은 카드다.
    reflagged = [dict(i, flags=["missing_explanation"]) if i["id"] == "c002" else i for i in ITEMS]
    kept = client.put(f"{ADMIN}/pre-items", json={"items": reflagged}, headers=RUNNER).json()
    check("표시만 바뀌면 판정을 지킨다", kept["editsDropped"] == 0 and kept["edited"] == 1, kept)

    # 파이프라인이 그 카드를 바꿔 올렸다 — 같은 id 의 다른 카드다.
    rebuilt = [an_item("c002", "새로 만든 질문", "새 답") if i["id"] == "c002" else i
               for i in ITEMS]
    fresh = client.put(f"{ADMIN}/pre-items", json={"items": rebuilt}, headers=RUNNER).json()
    check("바꿔 올린 카드의 판정은 버린다", fresh["editsDropped"] == 1, fresh)
    check("새 카드가 그대로 선다", reveal(client, "c002")["answer"] == "새 답")
    check("안 바뀐 카드의 판정은 남는다", pre_ids(client) == ["c001", "c002"], pre_ids(client))
    review = client.get("/api/admin/card-review", headers=USER).json()
    check("새 카드는 다시 「안 봄」으로 뜬다",
          [(c["itemId"], c["edit"] is None) for c in review["cards"]]
          == [("c002", True), ("c003", False)], review["cards"])

    # ── 되돌린다.
    undone = client.delete(f"{ADMIN}/cards/pre/c003", headers=USER)
    check("판정을 거둔다", undone.status_code == 200, undone.text)
    check("뺀 카드가 제자리로 돌아온다", pre_ids(client) == ["c001", "c002", "c003"],
          pre_ids(client))
    check("거둘 것이 없으면 404", client.delete(f"{ADMIN}/cards/pre/c003",
                                              headers=USER).status_code == 404)

    # 고쳤다가 「괜찮다」로 돌아서면 원본으로 선다.
    client.put(f"{ADMIN}/cards/pre/c001", json={"action": "edit", "answer": "고친 답"},
               headers=USER)
    check("고친 답이 보인다", reveal(client, "c001")["answer"] == "고친 답")
    client.put(f"{ADMIN}/cards/pre/c001", json={"action": "ok"}, headers=USER)
    check("괜찮다로 돌아서면 원본이다", reveal(client, "c001")["answer"] == "첫 답")

    check("없는 카드는 404", client.put(f"{ADMIN}/cards/pre/c999", json={"action": "ok"},
                                       headers=USER).status_code == 404)

    덱으로_가는_길(client)


def 덱으로_가는_길(client: TestClient) -> None:
    """2026-09-23 둘째 지시 — 「사이트에서 고친 카드가 apkg에도 반영되게 해줘.」

    러너가 판정을 당겨 가 덱을 다시 굽고, **얹어 구운 문항을 다시 올린다.** 그때
    서버가 그것을 「파이프라인이 바꿨다」로 읽으면 판정이 사라진다 — 여기가 요점이다.
    """
    print("\n  ── 덱으로 가는 길")
    cloze = dict(an_item("c004", "먼저 [____]의 이동을 부른다", "동물"),
                 qtype="cloze", source_stem="먼저 {{c1::동물}}의 이동을 부른다")
    base = [i for i in ITEMS if i["id"] != "c002"] + [cloze]
    client.put(f"{ADMIN}/pre-items", json={"items": base}, headers=RUNNER)

    bad = client.put(f"{ADMIN}/cards/pre/c004", json={"action": "edit", "stem": "딴 문장"},
                     headers=USER)
    check("빈칸 카드는 편 질문을 못 고친다", bad.status_code == 422, bad.status_code)
    noblank = client.put(f"{ADMIN}/cards/pre/c004",
                         json={"action": "edit", "sourceStem": "빈칸 없는 문장"}, headers=USER)
    check("빈칸이 없는 원문은 받지 않는다", noblank.status_code == 422, noblank.status_code)
    good = client.put(f"{ADMIN}/cards/pre/c004",
                      json={"action": "edit", "sourceStem": "댐 건설은 먼저 {{c1::동물}}의 이동을 부른다",
                            "answer": "동물"}, headers=USER)
    check("빈칸 카드는 원문을 고친다", good.status_code == 200, good.text)
    check("웹 질문은 서버가 편다", stem(client, "c004") == "댐 건설은 먼저 [____]의 이동을 부른다",
          stem(client, "c004"))

    listed = client.get("/api/admin/card-edits", headers=RUNNER).json()["edits"]
    mine = {(e["kind"], e["itemId"]): e for e in listed}
    check("러너가 고침·뺌만 받는다 (괜찮음은 덱에 할 일이 없다)",
          sorted(mine) == [("pre", "c004")],
          sorted(mine))
    c004 = mine.get(("pre", "c004")) or {}
    check("원문과 원본을 같이 준다",
          c004.get("sourceStem") == "댐 건설은 먼저 {{c1::동물}}의 이동을 부른다"
          and c004.get("original", {}).get("stem") == "먼저 [____]의 이동을 부른다", c004)

    # 러너가 얹어 구운 문항 — 질문이 고친 모양으로 올라온다.
    baked = [dict(cloze, stem="댐 건설은 먼저 [____]의 이동을 부른다",
                  source_stem="댐 건설은 먼저 {{c1::동물}}의 이동을 부른다") if i["id"] == "c004" else i
             for i in base]
    again = client.put(f"{ADMIN}/pre-items", json={"items": baked}, headers=RUNNER).json()
    check("얹어 구운 것이 올라와도 판정을 지킨다", again["editsDropped"] == 0, again)
    undone = client.delete(f"{ADMIN}/cards/pre/c004", headers=USER)
    check("그 뒤에 되돌려도 파이프라인 원본으로 간다",
          undone.status_code == 200 and stem(client, "c004") == "먼저 [____]의 이동을 부른다",
          stem(client, "c004"))

    print(f"\n{'모두 통과' if not failures else f'실패 {len(failures)}'}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
