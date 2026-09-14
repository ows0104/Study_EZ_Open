"""판이 안 적힌 옛 컷에 `cut.json` 을 되짚어 채운다.

    python scripts/backfill_cut.py            무엇이 채워질지만 본다
    python scripts/backfill_cut.py --apply    채운다

2026-09-14 에 판 기록을 붙였다(`quizgen/cutmark.py`). 그 전에 자른 컷은 판이 없고,
**그 컷으로 만든 덱이 306편 중 대부분이다.** 그 편들이 무엇을 봤는지는 이제 와서
알 수 없지만, 컷 자체가 언제 무엇으로 잘렸는지는 남아 있는 파일에서 되짚을 수 있다.

## 시각은 조각 파일에서 딴다 — `index.json` 이 아니다

처음에 `index.json` 의 mtime 으로 떴다가 **한 번 틀렸다.** 채우면서 그 파일에
`cut_id` 를 심는데, 그 쓰기가 mtime 을 오늘로 바꾼다. 그래서 두 번째로 돌리면
세 과목 전부 판이 「오늘」이 됐다(260908-0130 → 260914-2312).

조각 파일(`L1-2_….json`)은 이 스크립트가 손대지 않으므로 자른 시각을 그대로 든다.
세 과목에서 조각 18·19·17개의 mtime 이 **각각 같은 분으로 모여 있었고**, 그 값이
처음 `index.json` 에서 뜬 값과 정확히 일치했다.

**되짚은 판에는 `backfilled: true` 가 붙는다.** 자른 코드의 판은 되짚을 수 없어
`cutter` 에 「기록되지 않았다」가 들어간다 — 지금 코드를 적으면 거짓이 된다.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quizgen import cutmark  # noqa: E402  (경로를 세운 뒤에 불러야 한다)


def cut_time(cut_dir: Path) -> dt.datetime | None:
    """그 컷이 잘린 시각. **조각 파일에서 딴다**(모듈 머리)."""
    slices = [p for p in cut_dir.glob("*.json")
              if p.name not in ("index.json", cutmark.CUT_FILE)]
    if not slices:
        return None
    return dt.datetime.fromtimestamp(max(p.stat().st_mtime for p in slices))


def main() -> int:
    apply = "--apply" in sys.argv
    # 옛 이름(`_jokbo`)과 새 이름(`_materials`) 둘 다 본다. 개명은
    # `scripts/migrate_materials.py` 가 한다.
    base = next((ROOT / "runs" / n for n in ("_materials", "_jokbo")
                 if (ROOT / "runs" / n).is_dir()), ROOT / "runs" / "_materials")
    if not base.is_dir():
        print(f"{base} 가 없다")
        return 1

    todo = 0
    for cut_dir in sorted(base.iterdir()):
        index = cut_dir / "index.json"
        if not index.is_file():
            continue
        if cutmark.read(cut_dir):
            print(f"{cut_dir.name:10} 이미 판이 있다 — {cutmark.describe(cut_dir)}")
            continue
        when = cut_time(cut_dir)
        if when is None:
            print(f"{cut_dir.name:10} 조각이 없어 시각을 못 딴다 — 건너뛴다")
            continue

        got = json.loads(index.read_text(encoding="utf-8"))
        src = Path(got.get("source_path") or got.get("source", ""))
        cid = cutmark.new_cut_id(when)
        todo += 1
        print(f"{cut_dir.name:10} 판 {cid} · {src.name}"
              f" · 원본 {'있다' if src.is_file() else '없다'}")
        if not apply:
            continue
        cutmark.write(cut_dir, source=src, pages=got.get("pages"),
                      practical=got.get("practical_sources"),
                      cut_id=cid, cut_at=when, backfilled=True,
                      counts={"lectures": len(got.get("lectures", [])),
                              "questions": sum(e.get("n_questions", 0)
                                               for e in got.get("lectures", []))})
        # `index.json` 에도 심는다 — 그 파일을 이미 읽는 쪽이 여럿이다.
        # **이 쓰기가 mtime 을 바꾼다.** 그래서 시각을 여기서 따지 않는다(모듈 머리).
        got["cut_id"] = cid
        index.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
        if (stale := cutmark.stale_source(cut_dir)):
            print(f"{'':10}   ⚠ {stale} — 다시 자를지는 사람이 정한다")

    if todo and not apply:
        print(f"\n채울 컷 {todo}개. 정말 채우려면 --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
