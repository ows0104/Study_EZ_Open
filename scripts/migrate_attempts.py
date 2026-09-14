"""시도 것을 `runs/<편>/<갈래>/<판>/` 으로 접는다. `out/` 도 같이 접는다.

    python scripts/migrate_attempts.py                  무엇이 어디로 갈지만 본다
    python scripts/migrate_attempts.py 260812_01        한 편만 본다
    python scripts/migrate_attempts.py 260812_01 --apply
    python scripts/migrate_attempts.py --all --apply    전부

`docs/runs-layout.md` 5단계다. 그 문서의 ③ 이 여기서 끝난다 — 강의 것과 시도 것이
한 폴더에 섞여 있어서 「다시 돌리기」가 위험하다는 것.

## 옮기는 것과 두는 것

무엇이 강의 것인지는 **`runner/runlayout.py` 하나가 든다.** 여기서 다시 적지 않는다 —
두 곳에 적으면 다음에 파일이 늘 때 한쪽만 늘고, 그게 `HOLD` 가 지워질 수 있었던
모양이다.

    둔다     run.meta.json · *.apkg · slides/ · source.json · HOLD · CHOSEN.json …
    옮긴다   prep.* · items.* · prompt.* · context.* · media/ · run.report.json …

## 판 이름은 산출물의 시각에서 딴다

`usage.jsonl` 첫 줄의 `t` 다 — 그 실행이 시작된 때이고 **파일을 복사해도 안 바뀐다.**
없으면 `items.raw.json` 의 mtime 으로 내려간다. **`index.json` 같은
나중에 다시 쓰이는 파일에서 따면 안 된다**: 3단계에서 그렇게 해서 판이 전부
「오늘」이 된 적이 있다(`scripts/backfill_cut.py` 머리).

카드 파일이 없는 폴더는 **시도가 아니다.** 옮기지 않는다.

## 한 번 더 돌려도 값이 같다

이미 판이 서 있는 편은 건너뛴다. 옮기다 끊기면 남은 것만 다시 옮긴다 —
`runlayout.find` 가 새 자리를 먼저 보고 없으면 옛 자리를 보기 때문에 **반쯤 옮긴
나무에서도 파이프라인이 돈다.**

## `--apply` 전에 세어 본다

되돌릴 수 없는 것은 먼저 본다(`CLAUDE.md`). 기본은 옮기지 않고 찍기만 한다.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runner import attempts as att  # noqa: E402
from runner import runlayout as L  # noqa: E402

RUNS = ROOT / "runs"
OUT = ROOT / "out"
RE_RUN_ID = re.compile(r"^\d{6}_\d{2}(-[0-9a-f]{4})?$")


def version_of(attempt_dir: Path) -> str | None:
    """그 시도의 판. 없으면 시도가 아니다(카드 파일이 없다).

    **파일 안의 시각을 먼저 본다.** `usage.jsonl` 의 첫 줄에 그 실행이 시작된
    epoch(`t`)가 적혀 있고, 그것은 파일을 복사해도 안 바뀐다. mtime 은 바뀐다 —
    이 저장소가 그것으로 이미 두 번 틀렸다(`runner/fingerprint.py` 의 「mtime 으로
    판정하지 않는다」, `scripts/backfill_cut.py` 의 「시각은 조각 파일에서 딴다」).

    2026-09-14 에 이 함수를 mtime 으로만 쓰고 실컷 시험을 해 봤더니, `cp -r` 로
    떠 놓은 사본에서 **판 셋이 전부 같은 분**이 됐다(`260914-2350`·`.2`·`.3`).
    원본 트리에서는 맞는 값이 나왔으므로 조용히 지나갈 수 있던 자리다.
    """
    stamp = attempt_dir / att.CARDS_FILE
    if not stamp.is_file():
        return None
    ledger = attempt_dir / "usage.jsonl"
    if ledger.is_file():
        try:
            first = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
            if isinstance(first.get("t"), int | float):
                return f"{dt.datetime.fromtimestamp(first['t']):%y%m%d-%H%M}"
        except (OSError, ValueError, IndexError, KeyError):
            pass
    return f"{dt.datetime.fromtimestamp(stamp.stat().st_mtime):%y%m%d-%H%M}"




class Plan:
    """한 편을 어떻게 접을지. 아무것도 안 옮긴 상태로 만들어진다."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.moves: list[tuple[Path, Path, list[str]]] = []   # (원본, 판폴더, 옮길 이름)
        self.skipped: list[str] = []

    def add(self, source: Path, kind: str, names: list[str]) -> None:
        root = L.attempt_root(self.run_dir, kind)
        want = version_of(source)
        if not want:
            self.skipped.append(f"{source.name} — 카드 파일이 없다. 시도가 아니다")
            return
        # **같은 분에 잘린 시도 둘이 실제로 있다**(`260820_02` 의 var1·var2 는 같은
        # 14:09 이다). 디스크에 있는 것과 **이 계획이 이미 잡아 둔 것**을 둘 다 피한다 —
        # 앞의 것만 보면 한 계획 안에서 둘이 같은 자리를 가리킨다.
        taken = {dest.name for _, dest, _ in self.moves if dest.parent == root}
        base, n = want, 1
        while want in taken or (root / want).exists():
            n += 1
            want = f"{base}.{n}"
        self.moves.append((source, root / want, names))

    @property
    def empty(self) -> bool:
        return not self.moves


def attempt_names(d: Path, at_lecture_root: bool) -> list[str]:
    """그 폴더에서 옮길 것의 이름.

    **`.apkg` 의 성격이 자리에 따라 다르다.** 강의 폴더의 덱은 *지금 나가는 것*이라
    남아야 하고(서버 계약이 그 자리를 본다), `out/` 시도 안의 덱은 **그 시도가 구운
    것**이라 시도와 같이 가야 한다. `runlayout.is_lecture_own` 은 이름만 보므로 둘을
    구별할 수 없다 — 자리를 아는 쪽이 여기라서 여기서 가른다.

    2026-09-14 실컷 시험에서 잡았다. 안 가르면 `out/redo_…/p260812_01.apkg` 만 남아
    **주인 없는 덱 껍데기**가 `out/` 에 남는다(그래서 폴더도 안 치워진다).
    """
    keep = L.is_lecture_own if at_lecture_root else (lambda n: n in L.HUMAN_FILES)
    return sorted(p.name for p in d.iterdir() if not keep(p.name))


def plan_for(run_dir: Path) -> Plan:
    plan = Plan(run_dir)
    if not run_dir.is_dir():
        return plan

    # ① 강의 폴더에 널려 있는 시도 것. 갈래는 설정 파일이 말한다.
    if not L.attempt_dirs(run_dir):
        names = attempt_names(run_dir, at_lecture_root=True)
        if att.CARDS_FILE in names:
            plan.add(run_dir, L.kind_of(run_dir), names)
        elif names:
            plan.skipped.append(
                f"강의 폴더의 시도 것 {len(names)}개 — 카드 파일이 없어 판을 못 딴다")
    else:
        plan.skipped.append("이미 판이 서 있다")

    # ② `out/` 에 흩어져 있는 시도. **이것이 `out/` 폐지다.**
    for d in sorted(p for p in OUT.glob(f"*{run_dir.name}*") if p.is_dir()):
        names = attempt_names(d, at_lecture_root=False)
        # 사람이 만든 것이 `out/` 시도 안에 있을 수 있다(`preview.md`). 시도 안으로
        # 묻으면 찾을 수 없게 되므로 **옮기지 않고 말한다** — 어디로 갈지는 사람이 정한다.
        for human in sorted(n for n in L.HUMAN_FILES if (d / n).exists()):
            plan.skipped.append(f"{d.name}/{human} — 사람이 만든 것이다. 안 옮긴다")
        plan.add(d, L.kind_of(d), names)
    return plan


def show(plan: Plan) -> None:
    rid = plan.run_dir.name
    if plan.empty and not plan.skipped:
        return
    print(f"{rid}")
    for source, dest, names in plan.moves:
        where = source.relative_to(ROOT).as_posix() if source != plan.run_dir else "(강의 폴더)"
        kept = [p.name for p in source.iterdir() if L.is_lecture_own(p.name)] \
            if source == plan.run_dir else []
        print(f"    {where:<32} → {dest.relative_to(ROOT).as_posix()}  ({len(names)}개)")
        if kept:
            print(f"      남는다: {' · '.join(sorted(kept))}")
    for note in plan.skipped:
        print(f"    · {note}")


def apply(plan: Plan) -> int:
    moved = 0
    for source, dest, names in plan.moves:
        dest.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = source / name
            if not src.exists():
                continue                    # 앞 단계가 이미 옮겼다
            shutil.move(str(src), str(dest / name))
            moved += 1
        # `out/` 쪽은 옮기고 나면 빈 껍데기가 남는다. 강의 것이 없으면 치운다.
        if source != plan.run_dir and not any(source.iterdir()):
            source.rmdir()
    return moved


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do = "--apply" in sys.argv
    everything = "--all" in sys.argv

    if args:
        ids = args
    elif everything or not do:
        ids = sorted(d.name for d in RUNS.iterdir()
                     if d.is_dir() and RE_RUN_ID.match(d.name))
    else:
        print("편을 주거나 --all 을 쓰세요")
        return 2

    plans = [plan_for(RUNS / rid) for rid in ids]
    todo = [p for p in plans if not p.empty]
    for p in plans:
        show(p)

    files = sum(len(n) for p in todo for _, _, n in p.moves)
    print(f"\n편 {len(ids)}개 중 접을 것 {len(todo)}개 · 시도 "
          f"{sum(len(p.moves) for p in todo)}개 · 파일 {files}개")
    if not do:
        print("\n정말 옮기려면 --apply. **되돌릴 수 없는 것은 먼저 본다** (CLAUDE.md)")
        print("반쯤 옮긴 나무에서도 파이프라인은 돈다 — 한 편씩 해도 된다")
        return 0

    # **쓰는 쪽이 아직 강의 폴더로 쓴다.** 지금 옮기면 그 편의 다음 실행이 낸
    # 산출물이 조용히 무시된다 — `runlayout.find` 가 판 폴더를 먼저 보기 때문이다.
    # 무엇이 갖춰져야 풀리는지는 `runlayout.WRITES_ATTEMPT_DIRS` 위 주석에 있다.
    if not L.WRITES_ATTEMPT_DIRS:
        print("\n✋ 아직 옮기지 않는다. **쓰는 쪽이 판 폴더를 모른다.**")
        print("   `deck.run_main` 이 `--out` 으로 강의 폴더를 그대로 넘기므로, 옮긴 편에")
        print("   새 실행이 쓰면 그 산출물이 판 폴더에 가려 조용히 무시된다.")
        print("   풀리는 조건은 `runner/runlayout.WRITES_ATTEMPT_DIRS` 위에 적혀 있다.")
        print("\n   위의 계획은 그대로 맞다 — 그 조건이 서면 이 명령이 그것을 한다.")
        return 3

    moved = sum(apply(p) for p in todo)
    print(f"\n파일 {moved}개를 옮겼다")
    print("`python scripts/attempts.py <편>` 으로 시도가 그대로 보이는지 확인해라")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
