"""2단계 조각을 하나로 합친다. **세어서 표시만 하고 판정하지 않는다.**

    python prequiz/merge_items.py runs/<lecture_id>

## 조각의 단위가 quiz와 다르다

`quiz/merge_items.py`는 `structure.json`의 `chunks`로 쪼갠다. 여기서는
**청사진의 `objective`로 쪼갠다.** 이유는 배분이다.

Pre-Quiz는 **30문항 상한**이 있어서 조각들이 서로를 모르는 채로 "정보량대로"
쓰면 합이 상한을 넘는다. quiz에는 그 상한이 없어서 이 문제가 없고, 대신 조각
크기를 `plan_chunks.py`가 회귀로 맞춘다.

그런데 Pre-Quiz는 **청사진이 이미 배분을 들고 있다.** 실측한 편(`250820_01`)에서
`check_point` 총합이 30이고 나온 문항이 29였다. objective별로도 거의 1:1이었다.

    obj_1  cp 3 → 문항 3      obj_4  cp 7 → 문항 7
    obj_2  cp 4 → 문항 4      obj_5  cp 5 → 문항 4
    obj_3  cp 4 → 문항 4      obj_6  cp 7 → 문항 7

그래서 조각의 몫은 **그 objective의 `check_point` 수**다. 계산할 것이 없다.

## 순서를 objective 순서로 되돌린다

Pre-Quiz는 슬라이드 순이 아니라 **작성 순서가 곧 푸는 순서**다
(`PreItem.ord`, `prequiz/apply_audit.py` 참고). 실측한 편의 통짜 2단계가
obj_1 → obj_6 순으로 썼으므로, 여기서도 objective 순으로 이어 붙이면 조각화
전과 같은 순서가 나온다.

`id`는 **여기서 매기지 않는다.** quiz는 작성자가 조각별로 매겨서 병합이 다시
매기는데, Pre-Quiz는 작성자가 아예 안 쓰고 3단계가 매긴다
(`prequiz/validate.py`의 `setdefault("id", f"p{idx+1:03d}")`, 스키마에서도
`required`가 아니다). 실측한 편의 `pre_items.raw.json`도 28문항 전부 id가 없었다.

그래서 여기서는 **조각이 적어 왔으면 버린다.** 안 버리면 조각마다 `p001`이 생기고
`setdefault`가 그 중복을 그대로 통과시킨다. 배열 순서만 objective 순으로 세워 두면
3단계가 그 순서대로 번호를 매긴다.

## 한 조각이 죽어도 나머지는 남는다

조각화의 값은 시간보다 여기에 있다. 실측한 통짜 2단계는 12.5분이었고, 그 안에서
죽으면 그때까지의 32분이 통째로 날아간다. 조각 파일이 없으면 **그 사실을 적고
나머지로 합친다.** 조용히 빼면 다음 사람이 "이 강의는 원래 그 부분이 없다"고 읽는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz import timings  # noqa: E402

# preview-rules가 정한 상한. 넘으면 세어서 표시한다 — 자르는 것은 4단계 몫이다.
MAX_ITEMS = 30


def _items(payload) -> list[dict]:
    return payload.get("items", []) if isinstance(payload, dict) else (payload or [])


def merge(run_dir: Path, blueprint_name: str = "pre_blueprint.json",
          out_name: str = "pre_items.raw.json") -> dict:
    run_dir = Path(run_dir)
    blueprint = json.loads((run_dir / blueprint_name).read_text(encoding="utf-8"))
    objectives = blueprint.get("objectives", [])

    merged: list[dict] = []
    skipped: list[dict] = []
    missing: list[str] = []
    per_chunk: list[dict] = []
    owns: dict[str, set] = {}

    for objective in objectives:
        obj_id = str(objective.get("id") or "")
        owns[obj_id] = set(objective.get("slides") or [])
        quota = len(objective.get("check_points") or [])

        path = run_dir / f"pre_items.raw.{obj_id}.json"
        if not path.is_file():
            missing.append(obj_id)
            per_chunk.append({"objective_id": obj_id, "quota": quota,
                              "items": 0, "missing": True})
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        chunk_items = _items(payload)
        for item in chunk_items:
            item = dict(item)
            # 조각이 자기 objective를 안 적었어도 어느 조각에서 왔는지는 안다.
            item.setdefault("objective_id", obj_id)
            merged.append(item)
        for row in (payload.get("skipped") or []) if isinstance(payload, dict) else []:
            row = dict(row) if isinstance(row, dict) else {"note": str(row)}
            row.setdefault("objective_id", obj_id)
            skipped.append(row)
        per_chunk.append({"objective_id": obj_id, "quota": quota,
                          "items": len(chunk_items), "missing": False})

    # id는 3단계가 매긴다 (위 「순서를 objective 순서로 되돌린다」). 조각이 적어
    # 온 것은 여기서 버려 중복을 만들지 않는다.
    stripped = 0
    for item in merged:
        if item.pop("id", None) is not None:
            stripped += 1

    # ── 세기만 한다 ───────────────────────────────────────────────
    slide_owner: dict[int, set] = {}
    for item in merged:
        slide = item.get("slide_no")
        if slide is None:
            continue
        slide_owner.setdefault(int(slide), set()).add(str(item.get("objective_id")))
    overlaps = sorted(slide for slide, who in slide_owner.items() if len(who) > 1)

    outside = [
        {"at": index, "objective_id": item.get("objective_id"),
         "slide_no": item.get("slide_no")}
        for index, item in enumerate(merged, start=1)
        if item.get("slide_no") is not None
        and item.get("slide_no") not in owns.get(str(item.get("objective_id")), set())
    ]

    out = {"lecture_id": blueprint.get("lecture_id", ""), "items": merged}
    if skipped:
        out["skipped"] = skipped
    (run_dir / out_name).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"total": len(merged), "chunks": per_chunk, "missing": missing,
            "overlaps": overlaps, "outside": outside, "skipped": len(skipped),
            "stripped_ids": stripped,
            "qtypes": Counter(str(i.get("qtype")) for i in merged)}


def main() -> int:
    parser = argparse.ArgumentParser(description="예습퀴즈 2단계 조각 병합")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--blueprint", default="pre_blueprint.json")
    parser.add_argument("--out", default="pre_items.raw.json")
    args = parser.parse_args()

    with timings.stage(Path(args.run_dir), "2-merge"):
        result = merge(Path(args.run_dir), args.blueprint, args.out)

    print(f"[pre-merge] 조각 {len(result['chunks'])}개 → {result['total']}문항")
    for row in result["chunks"]:
        mark = "✗ 없음" if row["missing"] else f"{row['items']:>2}문항"
        note = "" if row["missing"] or row["items"] == row["quota"] else \
            f"  (check_point {row['quota']}개와 다르다)"
        print(f"    {row['objective_id']:<8} {mark}{note}")

    if result["missing"]:
        print(f"  ✗ 조각이 없다: {', '.join(result['missing'])} — "
              "그 objective의 문항이 통째로 빠졌다. 그 조각만 다시 돌려라")
    if result["total"] > MAX_ITEMS:
        print(f"  ! {result['total']}문항으로 상한 {MAX_ITEMS}을 넘었다 — "
              "4단계가 context부터 잘라야 한다")
    if result["overlaps"]:
        print(f"  ! 두 조각이 같이 다룬 슬라이드: {result['overlaps']} — "
              "회상 목적이 겹치는지는 4단계가 본다")
    for row in result["outside"]:
        print(f"  ! {row['at']}번째 문항이 {row['objective_id']} 밖의 s{row['slide_no']}를 썼다")
    if result["stripped_ids"]:
        print(f"  조각이 적어 온 id {result['stripped_ids']}개를 버렸다 — 번호는 3단계가 매긴다")
    if result["skipped"]:
        print(f"  조각들이 남긴 skipped {result['skipped']}건 — 4단계의 coverage 판단 입력이다")
    print(f"  유형: {dict(result['qtypes'])}")
    return 1 if result["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
