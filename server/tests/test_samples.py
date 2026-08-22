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
    pre_meta = json.loads((SAMPLES / "pre_run.meta.sample.json").read_text(encoding="utf-8"))

    run_id = pre_items["lecture_id"]
    base = f"/api/admin/lectures/병리학/{run_id}"
    quiz_base = f"/api/lectures/병리학/{run_id}/prequiz"

    print(f"\n[1] pre_items.sample.json — {len(pre_items['items'])}장이 그대로 들어가는가")
    register(client, run_id, "종양의 분자생물학(1)")
    stored = client.put(f"{base}/pre-items", headers=RUNNER, json=pre_items)
    check("200", stored.status_code == 200, stored.text)
    check("장수가 같다", stored.json().get("itemCount") == len(pre_items["items"]),
          (stored.json(), len(pre_items["items"])))

    print("\n[2] qtype이 계약의 셋 안에 드는가")
    kinds = {item["qtype"] for item in pre_items["items"]}
    check("basic·cloze·ox 밖이 없다", kinds <= {"basic", "cloze", "ox"}, kinds)
    check("보기가 실려 오지 않는다", not any("choices" in item for item in pre_items["items"]))

    print("\n[3] 답이 문항과 함께 나가지 않는가 — 실물로")
    quiz = client.get(quiz_base, headers=USER).json()
    check("장수가 같다", len(quiz["items"]) == len(pre_items["items"]), len(quiz["items"]))
    leaked = sorted({"answer", "explanation"} & {key for item in quiz["items"] for key in item})
    check("answer·explanation 필드가 없다", not leaked, leaked)
    body = json.dumps(quiz, ensure_ascii=False)
    # 답이나 해설 본문이 통째로 새면 펴 보기 전에 정답이 보인다. 실물 문장으로 확인한다.
    escaped = [item for item in pre_items["items"]
               if item["answer"][:30] in body or item["explanation"][:40] in body]
    check("답·해설 본문이 어디에도 없다", not escaped, [item["id"] for item in escaped])

    print("\n[4] 빈칸 카드가 Anki 문법인 채로 나가지 않는가")
    clozes = [item for item in pre_items["items"] if item["qtype"] == "cloze"]
    check("표본에 빈칸 카드가 있다", bool(clozes), len(clozes))
    check("`{{c1::`이 앞면에 없다", not any("{{c" in item["stem"] for item in clozes),
          [item["id"] for item in clozes if "{{c" in item["stem"]])
    check("빈칸이 그려져 있다", all("[" in item["stem"] for item in clozes),
          [item["id"] for item in clozes if "[" not in item["stem"]])

    print("\n[5] 펴야 답이 오는가 — 전 문항")
    missing = []
    for item in pre_items["items"]:
        opened = client.post(f"{quiz_base}/reveal", headers=USER,
                             json={"itemId": item["id"]}).json()
        if opened.get("answer") != item["answer"]:
            missing.append(item["id"])
    check("펴면 선언된 답이 그대로 온다", not missing, missing)

    print("\n[6] 펴 보기만 해서는 기록이 안 남는가")
    after_reveal = client.get(quiz_base, headers=USER).json()
    check("전부 폈는데 푼 것은 0", after_reveal["answered"] == 0, after_reveal["answered"])

    print("\n[7] 본인이 찍은 것이 그대로 남는가")
    first, second = pre_items["items"][0], pre_items["items"][1]
    client.post(f"{quiz_base}/grade", headers=USER, json={"itemId": first["id"], "correct": True})
    client.post(f"{quiz_base}/grade", headers=USER, json={"itemId": second["id"], "correct": False})
    graded = client.get(quiz_base, headers=USER).json()
    check("푼 것 2 · 맞은 것 1", (graded["answered"], graded["correct"]) == (2, 1),
          (graded["answered"], graded["correct"]))

    print("\n[8] 틀렸다고 찍은 것이 「놓친 것」으로 오는가")
    detail = client.get(f"/api/lectures/병리학/{run_id}", headers=USER).json()
    missed = [entry["itemId"] for entry in (detail["prequiz"] or {}).get("missed", [])]
    # 다 풀어야 나온다. 두 장만 찍었으므로 아직 비어 있는 것이 맞다.
    check("아직 안 나온다 (다 풀지 않았다)", not missed, missed)
    for item in pre_items["items"][2:]:
        client.post(f"{quiz_base}/grade", headers=USER, json={"itemId": item["id"], "correct": True})
    detail = client.get(f"/api/lectures/병리학/{run_id}", headers=USER).json()
    missed = [entry["itemId"] for entry in (detail["prequiz"] or {}).get("missed", [])]
    check("틀렸다고 찍은 그 장이 온다", missed == [second["id"]], missed)

    print("\n[9] 다시 풀기가 기록을 지우는가")
    client.delete(f"{quiz_base}/attempts", headers=USER)
    check("0으로 돌아온다", client.get(quiz_base, headers=USER).json()["answered"] == 0)

    print("\n[10] run.meta — 관리자 판단에 쓰는 값이 뽑히는가")
    register(client, run_meta["lecture_id"], run_meta["lecture_title"])
    meta_response = client.put(
        f"/api/admin/lectures/병리학/{run_meta['lecture_id']}/run-meta/main",
        headers=RUNNER, json=run_meta)
    check("200", meta_response.status_code == 200, meta_response.text)
    check(
        f"review_flagged {run_meta['review_flagged']} · slides_unused {len(run_meta['slides_unused'])}",
        meta_response.json() == {"reviewFlagged": run_meta["review_flagged"],
                                 "slidesUnused": len(run_meta["slides_unused"])},
        meta_response.json())

    stored_pre = client.put(f"{base}/run-meta/pre", headers=RUNNER, json=pre_meta)
    check("예습 run.meta도 받는다", stored_pre.status_code == 200, stored_pre.text)

    overview = client.get("/api/admin/overview", headers=USER).json()
    row = next(item for item in overview["lectures"] if item["runId"] == run_meta["lecture_id"])
    check("관리자 목록이 경고를 든다",
          row["runMeta"]["main"]["reviewFlagged"] == run_meta["review_flagged"], row["runMeta"])
    check(f"item_count {run_meta['item_count']}",
          row["runMeta"]["main"]["itemCount"] == run_meta["item_count"], row["runMeta"])
    check("built_at을 읽었다", row["runMeta"]["main"]["builtAt"] is not None,
          row["runMeta"]["main"]["builtAt"])

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
