"""족보 컷을 `runs/_materials/<과목>/<판>/` 으로 옮긴다.

    python scripts/migrate_materials.py            무엇이 어디로 갈지만 본다
    python scripts/migrate_materials.py --apply    옮긴다

`docs/runs-layout.md` 의 3′ 다. 그 문서가 「옮길 배치」로 적어 둔 자리이고, 3단계
(판 기록)와 5단계(시도를 판 폴더로)를 하고 나서야 값이 생겼다.

## 무엇이 달라지나

    전  runs/_jokbo/기생충학/L1-2_….json          지금 컷이 과목 폴더에 널려 있다
        runs/_jokbo/기생충학/_previous/<판>/…      밀려난 컷은 따로
    후  runs/_materials/기생충학/260908-0130/…    판이 서로 **형제**다
        runs/_materials/기생충학/current          어느 판이 지금 것인가

**`_previous` 가 필요 없어지는 것이 요점이다.** 지금 컷만 특별한 자리에 있어서,
다시 자르면 그 컷이 `_previous/` 로 **이사를 갔다** — 그 컷으로 만든 덱이 적어 둔
`cut_id` 로 폴더를 찾으면 거기 없다. 판이 형제면 아무것도 움직이지 않는다.

## 판 이름은 `cut.json` 이 든다

3단계에서 적어 둔 `cut_id` 다. 없는 컷은 `scripts/backfill_cut.py` 가 되짚어 채운다 —
**여기서 새로 짓지 않는다.** 지으면 같은 컷이 두 이름을 갖는다.

## 한 번 더 돌려도 값이 같다

이미 판 폴더가 선 과목은 건너뛴다. `current` 도 이미 맞으면 안 건드린다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quizgen import cutmark  # noqa: E402
from runner import deck  # noqa: E402

RUNS = ROOT / "runs"
OLD = RUNS / deck.LEGACY_MATERIALS       # _jokbo
NEW = RUNS / deck.MATERIALS              # _materials


class Plan:
    def __init__(self, subject: str):
        self.subject = subject
        self.moves: list[tuple[Path, Path]] = []
        self.current: str = ""
        self.notes: list[str] = []

    @property
    def empty(self) -> bool:
        return not self.moves and not self.current


def cut_id_of(cut_dir: Path) -> str | None:
    """그 컷의 판. `cut.json` 이 든다 — **여기서 새로 짓지 않는다**(모듈 머리)."""
    mark = cutmark.read(cut_dir)
    return str(mark["cut_id"]) if mark and mark.get("cut_id") else None


def plan_for(subject: str) -> Plan:
    plan = Plan(subject)
    src = OLD / subject
    dest_root = NEW / subject
    if not src.is_dir():
        return plan

    # ① 지금 컷 — 과목 폴더에 널려 있다
    if (src / "index.json").is_file():
        cid = cut_id_of(src)
        if not cid:
            plan.notes.append("판이 안 적혀 있다 — `scripts/backfill_cut.py --apply` 먼저")
            return plan
        plan.moves.append((src, dest_root / cid))
        plan.current = cid

    # ② 밀려난 컷 — `_previous/<판>/`. **형제로 끌어올린다.**
    prev = src / cutmark.PREVIOUS
    if prev.is_dir():
        for d in sorted(p for p in prev.iterdir() if p.is_dir()):
            plan.moves.append((d, dest_root / d.name))
    return plan


def show(plan: Plan) -> None:
    if plan.empty and not plan.notes:
        return
    print(f"{plan.subject}")
    for src, dest in plan.moves:
        where = src.relative_to(RUNS).as_posix()
        n = len(list(src.glob("*.json"))) + len(list(src.glob("*.md")))
        print(f"    {where:<42} → {dest.relative_to(RUNS).as_posix()}  ({n}개)")
    if plan.current:
        print(f"    current = {plan.current}")
    for note in plan.notes:
        print(f"    · {note}")


def apply(plan: Plan) -> int:
    moved = 0
    for src, dest in plan.moves:
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name == cutmark.PREVIOUS:
                continue                      # 그것은 따로 계획에 들어 있다
            shutil.move(str(item), str(dest / item.name))
            moved += 1
        # `_previous` 만 남았으면 껍데기다. 비었으면 치운다.
        if src.is_dir() and not any(src.iterdir()):
            src.rmdir()
    if plan.current:
        cutmark.set_current(NEW / plan.subject, plan.current)
    return moved


def main() -> int:
    do = "--apply" in sys.argv
    if not OLD.is_dir():
        print(f"{OLD.relative_to(ROOT).as_posix()} 가 없다 — 이미 옮겼거나 컷이 없다")
        for subject in sorted(d.name for d in NEW.iterdir() if d.is_dir()) if NEW.is_dir() else []:
            got = cutmark.resolve(NEW / subject)
            print(f"  {subject:10} 판 {cutmark.cuts(NEW / subject)} · 지금 {got.name}")
        return 0

    plans = [plan_for(d.name) for d in sorted(OLD.iterdir()) if d.is_dir()]
    todo = [p for p in plans if not p.empty]
    for p in plans:
        show(p)
    print(f"\n과목 {len(plans)}개 중 옮길 것 {len(todo)}개 · 컷 "
          f"{sum(len(p.moves) for p in todo)}개")
    if not do:
        print("\n정말 옮기려면 --apply. **되돌릴 수 없는 것은 먼저 본다** (CLAUDE.md)")
        print("옛 이름도 계속 읽힌다(`deck.subject_dir`) — 한 과목씩 해도 된다")
        return 0

    total = sum(apply(p) for p in todo)
    print(f"\n파일 {total}개를 옮겼다")
    # 껍데기가 남았으면 치운다. **비어 있을 때만** — 안 옮긴 것이 있으면 남겨 둔다.
    if OLD.is_dir() and not any(OLD.iterdir()):
        OLD.rmdir()
        print(f"{OLD.relative_to(ROOT).as_posix()} 를 치웠다")
    else:
        print(f"⚠ {OLD.relative_to(ROOT).as_posix()} 에 무엇이 남아 있다 — 보고 정해라")
    for p in todo:
        got = cutmark.resolve(NEW / p.subject)
        print(f"  {p.subject:10} 판 {cutmark.cuts(NEW / p.subject)} · 지금 {got.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
