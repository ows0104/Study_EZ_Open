"""4단계 감사 결과를 반영한다. 감사는 **바뀐 것만** 쓴다.

    python prequiz/apply_audit.py runs/<lecture_id>

## 왜 패치인가

`quiz/apply_audit.py`와 같은 이유다. 감사가 최종 배열을 통째로 다시 쓰면 손대지
않기로 한 문항까지 전부 다시 타이핑해야 한다.

2026-08-18 무인 실행이 그 낭비를 그대로 보여줬다 — 감사가 실제로 한 일은
**수정 11건 · 삭제 0 · 보충 0**인데, `pre_items.final.json` 40KB에 27문항을 전부
썼다. **16문항을 손 안 대고 베껴 쓴 것이다.**

quiz 쪽에서는 그 베끼기가 실제로 죽음을 불렀다(76장 2단계가 68분 돌다 죽고 0장을
남겼다). Pre-Quiz는 20문항 상한이라 죽을 위험은 그보다 작다. **여기서 진짜 위험은
조용한 변형이다** — 안 고치기로 한 문항이 다시 타이핑되는 동안 무엇이 바뀌어도
아무도 모른다.

## quiz판과 다른 한 곳 — 순서를 지킨다

`quiz/apply_audit.py`는 마지막에 `(slide_no, id)`로 정렬한다. 그쪽 카드가 이미
슬라이드 순이라 정렬이 사실상 제자리걸음이기 때문이다.

**Pre-Quiz는 슬라이드 순이 아니다.** 실측한 편의 `slide_no`가 9, 12, 8, 11, 8, 16…
이었다. 작성 단계가 정한 순서이고, 그것이 학생이 푸는 순서다 — 서버가
`PreItem.ord`로 들고 있고(`admin.py`가 배열 순서로 매긴다) 웹이 그 순으로 낸다
(`routes/prequiz.py`의 `order_by(PreItem.ord)`).

그래서 여기서는 **base의 순서를 그대로 지키고, 보충한 문항만 뒤에 붙인다.**
정렬하면 덱 순서가 통째로 뒤집힌다.

## 패치 형식 (`pre_audit_patch.json`)

```json
{
  "edit": [ { "id": "p012", "answer": "3", "explanation": "..." } ],
  "drop": [ { "id": "p019", "reason": "p014와 회상 목적이 같다" } ],
  "add":  [ { ...item.schema.json을 갖춘 새 문항... } ],
  "notes": "판정 근거는 pre_audit.md에"
}
```

`edit`은 **바꿀 필드만** 적는다. 안 적은 필드는 그대로 남는다.
언급되지 않은 문항은 전부 유지다 — "유지"를 일일이 적게 하면 패치의 뜻이 없다.

`add`의 `id`는 비워 둬도 된다. 코드가 남은 번호에 이어 매긴다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz import timings  # noqa: E402

# 감사가 못 바꾸는 것. id가 바뀌면 패치가 무엇을 가리켰는지 알 수 없게 된다.
#
# `slide_no`와 `source_type`은 **일부러 열어 뒀다.** 4단계 지시가
# `source_type_range_mismatch`를 두고 "어느 쪽이 틀렸는지 원본 라벨로 가려라"라고
# 시키는 자리라, 막으면 그 지시를 따를 방법이 없어진다.
PROTECTED = {"id"}

_ID_RE = re.compile(r"^p(\d+)$")


def _items(payload) -> list[dict]:
    return payload.get("items", []) if isinstance(payload, dict) else (payload or [])


def _next_ids(existing: list[str], count: int) -> list[str]:
    """`p001` 다음 번호부터. 지운 자리는 다시 쓰지 않는다 — 같은 번호가 두 뜻을
    갖게 되면 `pre_audit.md`의 근거가 어느 문항을 가리키는지 흐려진다."""
    top = 0
    for key in existing:
        found = _ID_RE.match(key)
        if found:
            top = max(top, int(found.group(1)))
    return [f"p{top + n:03d}" for n in range(1, count + 1)]


def apply_patch(run_dir: Path, base_name: str = "pre_items.checked.json",
                patch_name: str = "pre_audit_patch.json",
                out_name: str = "pre_items.final.json") -> dict:
    run_dir = Path(run_dir)
    raw = json.loads((run_dir / base_name).read_text(encoding="utf-8"))
    base = _items(raw)

    patch_path = run_dir / patch_name
    if not patch_path.exists():
        raise SystemExit(f"패치가 없다: {patch_path}\n4단계 감사를 먼저 돌려라.")
    patch = json.loads(patch_path.read_text(encoding="utf-8"))

    order = [str(i.get("id")) for i in base]
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
        order.remove(key)
        dropped.append((key, str(change.get("reason") or "")))

    incoming = patch.get("add", [])
    minted = _next_ids(list(by_id) + [str(i.get("id")) for i in base], len(incoming))
    added: list[str] = []
    for item, key in zip(incoming, minted):
        item = dict(item)
        item["id"] = key
        by_id[key] = item
        order.append(key)
        added.append(key)

    # 순서는 base 그대로. 보충한 것만 뒤에 붙는다 (위 「quiz판과 다른 한 곳」).
    final = [by_id[key] for key in order]

    out = dict(raw) if isinstance(raw, dict) else {}
    out.pop("skipped", None)          # raw 단계의 기록이라 확정본에 실을 것이 아니다
    out["items"] = final
    (run_dir / out_name).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"before": len(base), "after": len(final), "edited": edited,
            "dropped": dropped, "added": added, "unknown": unknown,
            "protected": protected_hits}


def main() -> int:
    parser = argparse.ArgumentParser(description="예습퀴즈 4단계 감사 패치 반영")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--base", default="pre_items.checked.json")
    parser.add_argument("--patch", default="pre_audit_patch.json")
    parser.add_argument("--out", default="pre_items.final.json")
    args = parser.parse_args()

    # quiz는 이 구간을 `5-apply`로 찍는다. 여기서는 4단계가 낸 것을 반영하는
    # 자리이고 SKILL.md도 4단계 안에 두므로 `4-apply`다. 오타가 아니다.
    with timings.stage(Path(args.run_dir), "4-apply"):
        result = apply_patch(Path(args.run_dir), args.base, args.patch, args.out)

    print(f"[pre-audit] {result['before']}문항 → {result['after']}문항")
    print(f"  수정 {len(result['edited'])} · 삭제 {len(result['dropped'])} · "
          f"보충 {len(result['added'])} · 그대로 "
          f"{result['before'] - len(result['edited']) - len(result['dropped'])}")
    for key, reason in result["dropped"]:
        print(f"    − {key}  {reason[:60]}")
    for key in result["added"]:
        print(f"    + {key}  (맨 뒤에 붙었다)")
    if result["protected"]:
        print(f"  ⚠ 건드릴 수 없는 필드라 무시했다: {', '.join(result['protected'])}")
    if result["unknown"]:
        print(f"  ⚠ 없는 id를 가리켰다: {', '.join(result['unknown'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
