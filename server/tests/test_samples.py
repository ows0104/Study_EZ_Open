"""실물 표본이 서버를 그대로 통과하는가.

`docs/samples/`는 파이프라인이 실제로 뱉은 것이다. 내가 상상한 모양이 아니라
이것으로 확인해야 계약을 지켰다고 말할 수 있다.

    server/.venv/Scripts/python.exe -m tests.test_samples
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-samples-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'samples.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "samples"
USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def register(client: TestClient, run_id: str, title: str) -> None:
    client.post(
        "/api/admin/lectures",
        headers=RUNNER,
        json=[
            {
                "subject": "병리학",
                "runId": run_id,
                "uid": f"{run_id}#{title}",
                "date": f"20{run_id[:2]}-{run_id[2:4]}-{run_id[4:6]}",
                "slot": int(run_id[7:9]),
                "startTime": f"{int(run_id[7:9]) + 8:02d}:00",
                "title": title,
                "professors": [],
            }
        ],
    )


def main() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)

    pre_items = json.loads((SAMPLES / "pre_items.sample.json").read_text(encoding="utf-8"))
    run_meta = json.loads((SAMPLES / "run.meta.sample.json").read_text(encoding="utf-8"))

    print("\n[1] pre_items.sample.json — 17문항이 그대로 들어가는가")
    register(client, pre_items["lecture_id"], "멘델법칙을 따르지 않는 유전자 질환")
    base = f"/api/admin/lectures/병리학/{pre_items['lecture_id']}"
    stored = client.put(f"{base}/pre-items", headers=RUNNER, json=pre_items)
    check("200", stored.status_code == 200, stored.text)
    check(
        "문항 수가 같다",
        stored.json().get("itemCount") == len(pre_items["items"]),
        (stored.json(), len(pre_items["items"])),
    )

    print("\n[2] 세 가지 qtype이 다 있고, mcq는 보기가 5개다")
    kinds = {item["qtype"] for item in pre_items["items"]}
    check("mcq·short·ox가 다 있다", kinds == {"mcq", "short", "ox"}, kinds)

    print("\n[3] 정답이 문항과 함께 나가지 않는가 — 실물로")
    quiz = client.get(f"/api/lectures/병리학/{pre_items['lecture_id']}/prequiz", headers=USER).json()
    check("문항 수가 같다", len(quiz["items"]) == len(pre_items["items"]), len(quiz["items"]))
    leaked = sorted({"answer", "explanation"} & {key for item in quiz["items"] for key in item})
    check("answer·explanation 필드가 없다", not leaked, leaked)
    body = json.dumps(quiz, ensure_ascii=False)
    # 해설 본문이 통째로 새면 정답도 같이 샌다. 실제 해설 문장으로 확인한다.
    escaped = [item for item in pre_items["items"] if item["explanation"][:40] in body]
    check("해설 본문이 어디에도 없다", not escaped, [item["id"] for item in escaped])

    print("\n[4] `**강조**`가 살아 있는가")
    emphasised = [item for item in pre_items["items"] if "**" in item["stem"]]
    check("표본에 강조 발문이 있다", bool(emphasised), len(emphasised))
    served = {item["itemId"]: item["stem"] for item in quiz["items"]}
    check(
        "서버가 별표를 지우지 않았다",
        all(served[item["id"]] == item["stem"] for item in emphasised),
    )

    print("\n[5] 실물 정답으로 채점이 되는가 — 전 문항")
    graded_wrong = []
    for item in pre_items["items"]:
        response = client.post(
            f"/api/lectures/병리학/{pre_items['lecture_id']}/prequiz/grade",
            headers=USER,
            json={"itemId": item["id"], "answered": item["answer"]},
        ).json()
        if not response.get("correct"):
            graded_wrong.append((item["id"], item["qtype"], item["answer"]))
    check("선언된 정답이 전부 정답 처리된다", not graded_wrong, graded_wrong)

    print("\n[6] 단답의 허용 표기가 실제로 읽히는가")
    from app.models import PreItem
    from app.database import SessionLocal
    from app.routes.prequiz import accepted_answers

    # 표본의 단답 셋은 전부 "…어느 표기든 정답이다"로 허용 표기를 밝힌다.
    # 하나라도 안 늘어나면 규칙을 못 읽고 있다는 뜻이므로 개수로 넘기지 않는다.
    with SessionLocal() as db:
        shorts = db.query(PreItem).filter(PreItem.qtype == "short").all()
        widened = {item.item_id: accepted_answers(item) for item in shorts}
    check("단답 3문항", len(shorts) == 3, len(shorts))
    check("셋 다 허용 표기가 늘었다", all(len(value) > 1 for value in widened.values()), widened)

    # 실물에서 골라낸 표기들. 학생이 이렇게 써도 정답이어야 한다.
    for item_id, typed in [
        ("p012", "LHON"),
        ("p012", "Leber 유전성 시신경병증"),
        ("p013", "모성 각인"),          # answer는 "Maternal imprinting(모성 각인)"이다
        ("p013", "maternal imprinting"),
        ("p016", "안젤만 증후군"),
    ]:
        graded = client.post(
            f"/api/lectures/병리학/{pre_items['lecture_id']}/prequiz/grade",
            headers=USER,
            json={"itemId": item_id, "answered": typed},
        ).json()
        check(f"{item_id} ← {typed!r}", graded.get("correct") is True, graded.get("answer"))

    print("\n[6-2] 해설 문장을 별칭으로 오해하지 않는가")
    # "/"가 들어 있어도 "정답이다" 표시가 없으면 별칭 목록이 아니다.
    from app.models import PreItem as _PreItem

    decoy = _PreItem(
        subject="병리학", run_id="x", item_id="x", qtype="short", answer="상염색체 우성",
        explanation="AD/AR 구분은 가계도에서 먼저 본다. 부모 중 한쪽만 이환되면 우성을 의심한다.",
    )
    check("별칭이 늘지 않는다", len(accepted_answers(decoy)) == 1, accepted_answers(decoy))

    print("\n[7] run.meta.sample.json — 관리자 판단에 쓰는 값이 뽑히는가")
    register(client, run_meta["lecture_id"], run_meta["lecture_title"])
    meta_response = client.put(
        f"/api/admin/lectures/병리학/{run_meta['lecture_id']}/run-meta/main",
        headers=RUNNER,
        json=run_meta,
    )
    check("200", meta_response.status_code == 200, meta_response.text)
    check(
        "review_flagged 2 · slides_unused 11",
        meta_response.json() == {"reviewFlagged": 2, "slidesUnused": 11},
        meta_response.json(),
    )

    overview = client.get("/api/admin/overview", headers=USER).json()
    row = next(item for item in overview["lectures"] if item["runId"] == run_meta["lecture_id"])
    check("관리자 목록이 경고를 든다", row["runMeta"]["main"]["reviewFlagged"] == 2, row["runMeta"])
    check("item_count 80", row["runMeta"]["main"]["itemCount"] == 80, row["runMeta"])
    check(
        "built_at을 읽었다",
        row["runMeta"]["main"]["builtAt"] is not None and row["runMeta"]["main"]["builtAt"].startswith("2026-08-16"),
        row["runMeta"]["main"]["builtAt"],
    )

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
