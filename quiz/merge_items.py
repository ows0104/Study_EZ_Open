"""2단계 조각을 하나로 합친다.

    python quiz/merge_items.py runs/<lecture_id>

## 왜 쪼개나

한 번에 76장을 쓰게 하면 출력이 길어져 중간에 끊긴다. 실제로 `260812_02`에서
2단계가 **68분을 돌다 API 오류로 죽었고** 아무것도 남기지 못했다. 기준 강의의
19분과 견주면 3.5배다.

`structure.json`의 `chunks`가 이미 주제 경계를 들고 있다. 그 단위로 쪼개면
각 호출이 짧아지고, 강의록 덩어리끼리는 서로 독립이라 **동시에 돌릴 수 있다.**
한 조각이 죽어도 나머지는 남는다.

## 무엇을 합치나

`items.raw.<조각>.json` 을 전부 모아 `items.raw.json` 하나로 만든다. 조각마다
따로 매긴 `id`는 여기서 다시 매긴다 - 조각들은 서로를 모르므로 그대로 두면
`q001`이 여러 개 생긴다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _items(payload) -> list[dict]:
    if isinstance(payload, dict):
        return payload.get("items") or []
    return payload or []


def _skipped(payload) -> list[dict]:
    return (payload.get("skipped") or []) if isinstance(payload, dict) else []


def merge(run_dir: Path, out_name: str = "items.raw.json") -> dict:
    run_dir = Path(run_dir)
    parts = sorted(run_dir.glob("items.raw.*.json"))
    parts = [p for p in parts if p.name != out_name]
    if not parts:
        raise SystemExit(
            f"합칠 조각이 없다: {run_dir}/items.raw.<조각>.json\n"
            "2단계를 조각별로 먼저 돌려라.")

    merged: list[dict] = []
    skipped: list[dict] = []
    report: list[tuple[str, int, int]] = []
    seen_slides: dict[int, str] = {}
    collisions: list[str] = []

    for path in parts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = _items(payload)
        for item in items:
            item = dict(item)
            item["chunk"] = path.stem.split("items.raw.")[-1]
            merged.append(item)
        skipped.extend(_skipped(payload))
        report.append((path.name, len(items), len(_skipped(payload))))

    # 조각마다 1번부터 매기므로 그대로 두면 겹친다. 순서는 슬라이드 번호를 따른다 -
    # 학습자가 덱을 열었을 때 강의 흐름대로 나오는 편이 낫다.
    merged.sort(key=lambda i: (int(i.get("slide_no") or 0), str(i.get("id") or "")))
    for index, item in enumerate(merged, start=1):
        old = str(item.get("id") or "")
        item["id"] = f"q{index:03d}"
        if old:
            item.setdefault("source_id", old)

    # 조각 사이에 같은 슬라이드가 잡히면 중복 출제일 수 있다. 막지는 않고 알린다 -
    # 판단은 4단계 감사의 몫이다.
    for item in merged:
        slide = int(item.get("slide_no") or 0)
        chunk = item.get("chunk", "")
        if slide in seen_slides and seen_slides[slide] != chunk:
            collisions.append(f"슬라이드 {slide}: {seen_slides[slide]} · {chunk}")
        seen_slides.setdefault(slide, chunk)

    payload = {"items": merged, "skipped": skipped}
    (run_dir / out_name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"parts": report, "count": len(merged), "skipped": len(skipped),
            "collisions": sorted(set(collisions))}


def main() -> int:
    parser = argparse.ArgumentParser(description="2단계 조각 합치기")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--out", default="items.raw.json")
    args = parser.parse_args()

    result = merge(Path(args.run_dir), args.out)
    print(f"[merge] 조각 {len(result['parts'])}개 → {result['count']}장")
    for name, count, skips in result["parts"]:
        print(f"    {name:<28} {count:>3}장" + (f" · skipped {skips}" if skips else ""))
    if result["skipped"]:
        print(f"  skipped 합계 {result['skipped']}건")
    if result["collisions"]:
        print(f"  ⚠ 조각이 같은 슬라이드를 나눠 가졌다 {len(result['collisions'])}건 "
              "— 4단계에서 중복인지 보라")
        for line in result["collisions"][:8]:
            print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
