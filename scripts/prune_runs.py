"""`runs/` 에서 다시 만들 수 있는 것과 지나간 블럭의 안 쓰는 판을 지운다.

    python scripts/prune_runs.py            지울 것을 세기만 한다
    python scripts/prune_runs.py --apply    지운다. 지운 경로는 runs/_pruned_<날짜>.txt

규칙은 2026-10-03 관리자 결정이다(`docs/runs-layout.md` 「아직 안 정한 것 ②」).

    작업물          `_bundle/` · `_image_check/` · 판 안의 `*_image_check.pdf`
                    — 다시 읽는 코드가 없고 다시 만들 수 있다
    지나간 블럭의 판  지금 블럭이 시작하기 전 강의의, **안 쓰는** 판
                    — 남기는 것: 지금 쓰는 판(`runlayout.work_dir`) · 계약이 가리키는 판 ·
                      `CHOSEN.json` 이 고른 판. 지금 블럭의 옛 판은 비교 재료라 안 건드린다

작년 편(`25…`)은 `pre_target.json` 의 날짜(그 예습이 향하는 올해 강의)로 가르고,
그 파일이 없으면 날짜를 모르므로 남긴다.

**지우기 전후로 편마다 `work_dir` 과 `chosen.verdict` 를 맞댄다.** 하나라도 달라지면
2로 끝난다 — 그때는 지운 목록을 보고 무엇이 그 판을 기대고 있었는지 찾는다.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from runner import blocks, chosen  # noqa: E402
from runner import runlayout as rl  # noqa: E402

GB = 1024 ** 3


def size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for dp, _, fns in os.walk(p):
        for f in fns:
            with contextlib.suppress(OSError):
                total += os.path.getsize(os.path.join(dp, f))
    return total


def lecture_date(run_dir: Path) -> datetime.date | None:
    name = run_dir.name
    if name.startswith("26"):
        return datetime.date(2000 + int(name[:2]), int(name[2:4]), int(name[4:6]))
    target = run_dir / "pre_target.json"
    if target.exists():
        try:
            return datetime.date.fromisoformat(json.loads(target.read_text(encoding="utf-8"))["date"])
        except (ValueError, KeyError, json.JSONDecodeError):
            return None
    return None


def lecture_dirs(runs: Path) -> list[Path]:
    return [d for d in sorted(runs.iterdir()) if d.is_dir() and not d.name.startswith("_")]


def snapshot(runs: Path) -> dict[str, list[str]]:
    out = {}
    for d in lecture_dirs(runs):
        for kind in (rl.MAIN, rl.PREQUIZ):
            if not rl.versions(d, kind):
                continue
            try:
                verdict = chosen.verdict(d, kind)
            except Exception as e:  # 판정이 죽는 것도 그대로 맞댄다
                verdict = f"ERR {type(e).__name__}"
            out[f"{d.name}/{kind}"] = [rl.work_dir(d, kind).name, verdict]
    return out


def work_products(runs: Path) -> list[Path]:
    found = [p for p in (runs / "_bundle", runs / "_image_check") if p.exists()]
    for dp, _, fns in os.walk(runs):
        if "_image_check" in Path(dp).parts:
            continue
        found += [Path(dp) / f for f in fns if f.lower().endswith("_image_check.pdf")]
    return found


def stale_attempts(runs: Path, block_start: datetime.date) -> tuple[list[Path], int, int]:
    drop, kept_current, kept_unknown = [], 0, 0
    for d in lecture_dirs(runs):
        for kind in (rl.MAIN, rl.PREQUIZ):
            found = rl.versions(d, kind)
            if len(found) < 2:
                continue
            when = lecture_date(d)
            if when is None:
                kept_unknown += len(found) - 1
                continue
            if when >= block_start:
                kept_current += len(found) - 1
                continue
            keep = {rl.work_dir(d, kind).name}
            for pick in (rl._published_version, rl._chosen_version):
                v = pick(d, kind, found)
                if v:
                    keep.add(v)
            drop += [rl.attempt_root(d, kind) / v for v in found if v not in keep]
    return drop, kept_current, kept_unknown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="정말 지운다")
    ap.add_argument("--runs", default=str(REPO / "runs"))
    args = ap.parse_args(argv)
    runs = Path(args.runs)

    today = datetime.date.today()
    found = blocks.find(today)
    if found.block is None:
        print("오늘의 블럭을 시간표에서 못 찾았다 — 아무것도 안 지운다")
        return 2
    block_start = found.block.start
    print(f"지금 블럭  {found.block.name} ({found.block.start} ~ {found.block.end})")

    work = work_products(runs)
    drop, kept_current, kept_unknown = stale_attempts(runs, block_start)
    print(f"작업물               {len(work):4d}개  {sum(size(p) for p in work) / GB:6.2f} GB")
    print(f"지나간 블럭의 옛 판   {len(drop):4d}개  {sum(size(p) for p in drop) / GB:6.2f} GB  (작업물과 겹치는 몫 포함)")
    print(f"남김  지금 블럭의 옛 판 {kept_current}개 · 날짜를 모르는 편의 옛 판 {kept_unknown}개")
    if not args.apply:
        print("세기만 했다. 지우려면 --apply")
        return 0

    before = snapshot(runs)
    log = runs / f"_pruned_{today.isoformat()}.txt"
    with open(log, "a", encoding="utf-8") as fh:
        for p in work + drop:
            if not p.exists():
                continue
            fh.write(f"{p}\n")
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    after = snapshot(runs)
    changed = [k for k in before if before[k] != after.get(k)]
    print(f"지웠다. 목록: {log}")
    if changed:
        print(f"✋ 지운 뒤 판정이 달라진 편 {len(changed)}개: {', '.join(changed[:10])}")
        return 2
    print(f"편 {len(before)}개의 work_dir · verdict 가 지우기 전과 같다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
