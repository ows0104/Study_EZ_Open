"""4단계 감사 결과를 반영한다. 감사는 **바뀐 것만** 쓴다.

    python quiz/apply_audit.py runs/<lecture_id>

## 왜 패치인가

감사가 최종 배열을 통째로 다시 쓰면 74장이면 74장을 전부 출력해야 한다. 그런데
이 파이프라인이 죽은 자리는 매번 **긴 JSON을 쓰기 시작하는 순간**이었다.

    통짜 2단계 76장   68분 돌다 죽음, 0장 남김
    족보 조각 13개    "Now I'll write the cards." 직후 죽음

감사가 실제로 손대는 것은 보통 전체의 2~3할이다. 나머지는 그대로 통과시킨다.
그러니 **바뀐 것만 쓰게** 하고 합치는 일은 코드가 한다.

## 패치 형식 (`audit_patch.json`)

```json
{
  "edit": [ { "id": "q012", "a": "고친 답", "explanation": "..." } ],
  "drop": [ { "id": "q034", "reason": "q031과 회상 목적이 같다" } ],
  "add":  [ { ...스키마를 갖춘 새 카드... } ],
  "notes": "판정 근거는 audit.md에"
}
```

`edit`은 **바꿀 필드만** 적는다. 안 적은 필드는 그대로 남는다.
언급되지 않은 카드는 전부 유지다 - "유지"를 일일이 적게 하면 패치의 뜻이 없다.
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

# 감사가 건드리면 안 되는 것. 슬라이드 번호와 출처는 2단계가 원본을 보고 적었고,
# 감사가 원본 없이 고치면 근거가 끊긴다. 정말 틀렸으면 drop하고 새로 add하라.
PROTECTED = {"id"}


def _items(payload) -> list[dict]:
    return payload.get("items", []) if isinstance(payload, dict) else (payload or [])


def apply_patch(run_dir: Path, base_name: str = "items.checked.json",
                patch_name: str = "audit_patch.json",
                out_name: str = "items.final.json") -> dict:
    run_dir = Path(run_dir)
    base = _items(json.loads((run_dir / base_name).read_text(encoding="utf-8")))
    patch_path = run_dir / patch_name
    if not patch_path.exists():
        raise SystemExit(
            f"패치가 없다: {patch_path}\n4단계 감사를 먼저 돌려라.")
    patch = json.loads(patch_path.read_text(encoding="utf-8"))

    by_id = {str(i.get("id")): dict(i) for i in base}
    unknown: list[str] = []
    edited: list[str] = []
    protected_hits: list[str] = []

    for change in patch.get("edit", []):
        key = str(change.get("id") or "")
        target = by_id.get(key)
        if target is None:
            unknown.append(f"edit {key}")
            continue
        for field, value in change.items():
            if field == "id":
                continue
            if field in PROTECTED:
                protected_hits.append(f"{key}.{field}")
                continue
            target[field] = value
        edited.append(key)

    dropped: list[tuple[str, str]] = []
    for change in patch.get("drop", []):
        key = str(change.get("id") or "")
        if by_id.pop(key, None) is None:
            unknown.append(f"drop {key}")
            continue
        dropped.append((key, str(change.get("reason") or "")))

    added: list[str] = []
    for index, item in enumerate(patch.get("add", []), start=1):
        item = dict(item)
        key = str(item.get("id") or f"add{index:03d}")
        if key in by_id:
            key = f"{key}_add"
        item["id"] = key
        by_id[key] = item
        added.append(key)

    final = sorted(by_id.values(),
                   key=lambda i: (int(i.get("slide_no") or 0), str(i.get("id") or "")))
    (run_dir / out_name).write_text(
        json.dumps({"items": final}, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"before": len(base), "after": len(final), "edited": edited,
            "dropped": dropped, "added": added, "unknown": unknown,
            "protected": protected_hits}


def main() -> int:
    parser = argparse.ArgumentParser(description="4단계 감사 패치 반영")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--base", default="items.checked.json")
    parser.add_argument("--patch", default="audit_patch.json")
    parser.add_argument("--out", default="items.final.json")
    args = parser.parse_args()

    result = apply_patch(Path(args.run_dir), args.base, args.patch, args.out)
    print(f"[audit] {result['before']}장 → {result['after']}장")
    print(f"  수정 {len(result['edited'])} · 삭제 {len(result['dropped'])} · 보충 {len(result['added'])}")
    for key, reason in result["dropped"]:
        print(f"    − {key}  {reason[:60]}")
    for key in result["added"]:
        print(f"    + {key}")
    if result["protected"]:
        print(f"  ⚠ 건드릴 수 없는 필드라 무시했다: {', '.join(result['protected'])}")
    if result["unknown"]:
        print(f"  ⚠ 없는 id를 가리켰다: {', '.join(result['unknown'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
