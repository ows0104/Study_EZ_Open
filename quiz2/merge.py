"""조각 결과를 합쳐 v1 뒷단이 읽을 수 있는 꼴로 낸다.

v2 조각은 `{"learning_plan": [...], "cards": [...]}`를 쓰고, v1의
`validate.py`·`build.py`는 `{"items": [...]}`를 읽는다. 여기서 갈아 끼운다.

**v1 코드를 안 고치는 이유**: `quiz/`는 `pre-rewrite-agentic` 태그로 보존한
기준선이다. 같은 강의록으로 두 판을 나란히 돌려 견주려면 그쪽이 그대로여야 한다.

## learning_plan은 버리지 않는다

카드로 안 만든 것을 `rejected_candidates`에 남기게 한 것이 인터뷰 ②의 결정이다.
그걸 합쳐 `plan.json`으로 따로 뽑아 둔다 - 어느 슬라이드가 왜 비었는지가 거기 있고,
`coverage_gaps`를 볼 때 근거가 된다(우선순위는 낮지만 계속 센다 - ①⃝).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def merge(run_dir: str | Path, out_name: str = "items.raw.json") -> dict:
    run_dir = Path(run_dir)
    parts = sorted(p for p in run_dir.glob("items.raw.*.json")
                   if p.name != out_name)
    if not parts:
        raise SystemExit(f"합칠 조각이 없다: {run_dir}/items.raw.<조각>.json")

    items: list[dict] = []
    plans: list[dict] = []
    report: list[tuple[str, int, int]] = []
    # 같은 슬라이드를 여러 조각이 나눠 가졌으면 중복 의심이다. 판정은 안 한다 -
    # 세어서 표시만 하고 지울지는 사람이나 감사가 정한다.
    slide_owner: dict[int, str] = {}
    overlaps: list[str] = []

    for path in parts:
        chunk = path.stem.split("items.raw.")[-1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        cards = payload.get("cards") or []
        plan = payload.get("learning_plan") or []

        for card in cards:
            card = dict(card)
            card["chunk"] = chunk
            card["id"] = f"q{len(items) + 1:03d}"
            items.append(card)
            slide = card.get("slide_no")
            if isinstance(slide, int):
                owner = slide_owner.setdefault(slide, chunk)
                if owner != chunk:
                    overlaps.append(f"slide {slide}: {owner} ↔ {chunk}")

        rejected = sum(len(o.get("rejected_candidates") or []) for o in plan)
        plans.append({"chunk": chunk, "learning_plan": plan})
        report.append((chunk, len(cards), rejected))

    (run_dir / out_name).write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "plan.json").write_text(
        json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"items": items, "report": report, "overlaps": sorted(set(overlaps))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    result = merge(args.run_dir)
    items = result["items"]

    print(f"[merge] {len(items)}장 → items.raw.json")
    print(f"{'조각':<8}{'카드':>5}{'제외기록':>8}")
    for chunk, count, rejected in result["report"]:
        print(f"{chunk:<8}{count:>5}{rejected:>8}")

    for key in ("card_type", "card_format", "importance", "source_type"):
        counts = Counter(str(i.get(key)) for i in items)
        print(f"  {key}: " + ", ".join(f"{k}={v}" for k, v in counts.most_common()))
    hits = sum(1 for i in items if i.get("exam_hit"))
    print(f"  exam_hit: {hits} / {len(items)}")

    if result["overlaps"]:
        print(f"  조각이 나눠 가진 슬라이드 {len(result['overlaps'])}건 "
              f"(중복 의심, 판정은 사람이): {', '.join(result['overlaps'][:6])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
