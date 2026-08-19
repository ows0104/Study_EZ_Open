"""1단계 조각 청사진을 하나로 합친다.

    python quiz/merge_blueprint.py runs/<lecture_id>

## 왜 쪼개나

1단계는 오래 걸리는데 혼자 돈다 — `260814_05` 14.8분 · `260812_03` 13.9분으로 두 편
모두 직렬 단계 중 가장 컸다. 그런데 나온 결과를 0.5단계의 chunk 경계에 대고 세어 보면
**objective 78개 중 경계를 넘는 것이 하나도 없었다**(두 편 합쳐 35 + 43). 66쪽을 통째로
읽고 만든 것이 실은 조각 단위로 완결돼 있었다는 뜻이다.

그래서 chunk마다 하나씩 돌린다. 전역이던 것 중 큰 것(`exam_focus`)은 **0.5단계로
옮겼다** — 경계를 찾느라 족보를 어차피 전부 읽는 자리라, 그 읽기를 버리고 1단계가 같은
쪽을 다시 읽던 것을 없앴다.

## 무엇을 합치나

`blueprint.<조각>.json`을 모아 `blueprint.json` 하나로 만든다. `objective`의 `id`는
여기서 다시 매긴다 — 조각들은 서로를 몰라 그대로 두면 `obj_1`이 여러 개 생긴다.

전역 필드는 이렇게 채운다.

- `exam_focus` — `structure.json`에서 가져온다 (0.5단계가 냈다)
- `skip_slides` — 조각들이 낸 것을 합집합으로
- `estimated_item_count` — 조각들의 합
- `summary` — 조각 요약을 잇는다

**커버리지는 세어서 표시만 한다.** 강의록 슬라이드 중 어느 조각도 안 덮고 `skip_slides`
에도 없는 것이 있으면 알린다. 지울지 채울지는 사람이 정한다 — 조각이 서로를 못 봐서
흘린 것일 수도 있고 정말 뺄 자리일 수도 있다.
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


def _objectives(payload) -> list[dict]:
    if isinstance(payload, dict):
        return payload.get("objectives") or []
    return payload or []


def merge(run_dir: Path, out_name: str = "blueprint.json") -> dict:
    run_dir = Path(run_dir)
    parts = sorted(p for p in run_dir.glob("blueprint.*.json")
                   if p.name != out_name)
    if not parts:
        raise SystemExit(
            f"합칠 조각이 없다: {run_dir}/blueprint.<조각>.json\n"
            "1단계를 조각별로 먼저 돌려라.")

    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))

    merged: list[dict] = []
    report: list[tuple[str, int, int]] = []
    skip: set[int] = set()
    estimated = 0
    summaries: list[str] = []

    for path in parts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunk = path.stem.split("blueprint.")[-1]
        objs = _objectives(payload)
        for obj in objs:
            obj = dict(obj)
            obj["chunk"] = chunk
            merged.append(obj)
        skip.update(int(s) for s in (payload.get("skip_slides") or []))
        estimated += int(payload.get("estimated_item_count") or 0)
        if isinstance(payload, dict) and payload.get("summary"):
            summaries.append(str(payload["summary"]).strip())
        report.append((path.name, len(objs),
                       sum(len(o.get("retrieval_targets") or []) for o in objs)))

    # 조각마다 obj_1부터 매기므로 그대로 두면 겹친다. 순서는 슬라이드를 따른다.
    merged.sort(key=lambda o: (min(o.get("slides") or [0]), str(o.get("id") or "")))
    for index, obj in enumerate(merged, start=1):
        old = str(obj.get("id") or "")
        obj["id"] = f"obj_{index}"
        if old:
            obj.setdefault("source_id", old)

    blueprint = {
        "lecture_id": prep["lecture_id"],
        "summary": " ".join(summaries),
        "estimated_item_count": estimated,
        "skip_slides": sorted(skip),
        "objectives": merged,
    }
    if structure.get("exam_focus"):
        blueprint["exam_focus"] = structure["exam_focus"]

    (run_dir / out_name).write_text(
        json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")

    lo, hi = structure.get("lecture_range") or [1, 1]
    covered = {s for o in merged for s in (o.get("slides") or [])}
    gaps = [s for s in range(lo, hi + 1) if s not in covered and s not in skip]
    # 두 조각이 같은 슬라이드에 objective를 세웠나. 막지 않고 알린다 - 한 슬라이드에
    # 여러 주제가 있을 수 있고, 정말 중복이면 §16b가 본다.
    owner: dict[int, str] = {}
    overlap: list[str] = []
    for obj in merged:
        for s in (obj.get("slides") or []):
            prev = owner.setdefault(s, obj.get("chunk", ""))
            if prev != obj.get("chunk", ""):
                overlap.append(f"슬라이드 {s}: {prev} · {obj.get('chunk')}")

    return {
        "parts": report,
        "objectives": len(merged),
        "targets": sum(len(o.get("retrieval_targets") or []) for o in merged),
        "skip_slides": sorted(skip),
        "coverage_gaps": gaps,
        "overlap": sorted(set(overlap)),
        "has_exam_focus": bool(structure.get("exam_focus")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="1단계 조각 청사진 합치기")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--out", default="blueprint.json")
    args = parser.parse_args()

    result = merge(Path(args.run_dir), args.out)
    print(f"[merge-blueprint] 조각 {len(result['parts'])}개 → "
          f"objective {result['objectives']}개 · target {result['targets']}개")
    for name, objs, tgts in result["parts"]:
        print(f"    {name:<30} objective {objs:>3} · target {tgts:>3}")
    if not result["has_exam_focus"]:
        print("  ⚠ `structure.json`에 exam_focus가 없다 — 0.5단계가 안 냈다")
    if result["skip_slides"]:
        print(f"  skip_slides {len(result['skip_slides'])}장: {result['skip_slides']}")
    if result["coverage_gaps"]:
        print(f"  ⚠ 어느 조각도 안 덮고 skip에도 없는 슬라이드 "
              f"{len(result['coverage_gaps'])}장: {result['coverage_gaps']}\n"
              "      조각이 서로를 못 봐서 흘린 것일 수도, 정말 뺄 자리일 수도 있다. "
              "직접 열어 보라")
    if result["overlap"]:
        print(f"  조각이 같은 슬라이드에 objective를 세웠다 {len(result['overlap'])}건 "
              "— 중복이면 덱 감사가 본다")
        for line in result["overlap"][:8]:
            print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
