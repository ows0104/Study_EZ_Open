"""덱 산출물 관리 명령: import, rebuild, release, chosen, promote."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from runner import attempts, chosen, deck, filenames, gate, rebuild, runlayout, watch

from . import REPO_ROOT

# quizgen 작업 폴더 이름. `pre_`가 예습, 뒤에 붙는 꼬리는 사람이 시험 삼아
# 갈라 둔 변형이다(`pre_p250825_01_note`). 꼬리가 달라도 같은 강의다.
RE_WORK_DIR = re.compile(r"^(?P<pre>pre_)?p(?P<run_id>\d{6}_\d{2}(?:-[0-9a-f]{4})?)(?P<variant>.*)$")

# 덮어쓸 때도 안 지우는 것. **파이프라인이 다시 만들 수 없는 것 전부**다.
#
# 2026-09-15 까지 여기 둘만 있었다(`preview.md`·`pre_target.json`). 그래서 이 자리를
# 비울 때 **`HOLD` 와 `source.json` 이 같이 지워졌다** — `.gitignore` 는 `HOLD` 를
# 두고 *"파이프라인이 다시 만들 수 없다 … 잃으면 막아 둔 이유를 아무도 모른 채 덱이
# 나간다"* 고 적고 있었고, 여기는 그것을 몰랐다. 09-15 에 `CHOSEN.json` 이 같은
# 자리에 하나 더 놓이면서 그 구멍이 커졌다 — 사람이 고른 판이 조용히 없어진다.
#
# **목록을 여기서 늘리지 마라.** 무엇이 강의 것인지는 `runlayout` 하나가 든다 —
# 두 곳에 적으면 다음에 파일이 늘 때 한쪽만 는다. 그게 이 주석의 사고였다.
KEEP_ON_IMPORT = runlayout.is_lecture_own


def import_dirs(source: Path) -> dict[str, list[tuple[str, Path]]]:
    """quizgen 작업 폴더를 훑어 `run_id`별로 모은다. `{run_id: [(kind, 폴더)]}`.

    폴더 이름이 곧 무엇인지 말한다 — `p260812_01`이 복습, `pre_p250825_01`이 예습이다.
    `_`로 시작하는 것(`_bundle`·`_image_check`)과 `jokbo`는 강의가 아니다.

    **꼬리가 붙은 변형을 같은 강의로 모은다.** 안 모으면 `pre_p250825_01_note`가
    `250825_01_note`라는 없는 강의가 되어 아무 데도 안 붙는 자리를 하나 만든다.
    """
    found: dict[str, list[tuple[str, Path]]] = {}
    for entry in sorted(source.iterdir() if source.is_dir() else []):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        match = RE_WORK_DIR.match(entry.name)
        if match is None:
            continue
        kind = deck.PRE if match.group("pre") else deck.MAIN
        if deck.apkg_of(entry, kind) is None:
            continue
        found.setdefault(match.group("run_id"), []).append((kind, entry))
    return found


def run_import(args) -> int:
    """다른 곳에서 만든 quizgen 덱을 `runs/`로 옮긴다. **올리지는 않는다.**

    옮긴 자리마다 `HOLD`를 놓는다. 이 사이트의 눈(계약·검문)으로 한 번도 본 적이
    없는 산출물이라, 사람이 보고 `python -m runner release <run_id>`로 풀기 전에는
    `publish`가 덱을 내보내지 않는다. 강의록 PDF는 그대로 나간다 — 그건 이 검토와
    무관한 자료다.
    """
    if not args.source_dir:
        print("쓰는 법: python -m runner import --from \"../PDF2ANKI/out\"")
        return 2
    source, runs_dir = Path(args.source_dir), Path(args.runs)
    if not source.is_dir():
        print(f"[import] {source} 가 없다")
        return 2

    found = import_dirs(source)
    if args.run_id:
        found = {k: v for k, v in found.items() if k == args.run_id}
    if not found:
        print(f"[import] {source} 에서 옮길 덱을 못 찾았다")
        return 1

    print(f"[import] {source} → {runs_dir}  ({len(found)}편)")
    moved = 0
    for run_id, entries in sorted(found.items()):
        # 한 강의에 같은 갈래가 여럿이면 (변형 폴더) 가장 새 것을 쓰되 **말은 한다.**
        # 이름이 `chosen` 이었는데 그게 `runner.chosen` 모듈을 가렸다. 지금은 이
        # 함수가 그 모듈을 안 쓰지만, 쓰려는 순간 UnboundLocalError 로 터진다.
        newest: list[tuple[str, Path]] = []
        for kind in (deck.MAIN, deck.PRE):
            same = sorted((pair for pair in entries if pair[0] == kind),
                          key=lambda pair: deck.apkg_of(pair[1], pair[0]).stat().st_mtime)
            if len(same) > 1:
                print(f"  ⚠ {run_id} {kind} — 후보가 {len(same)}개다. 가장 새 것을 쓴다: "
                      + " · ".join(folder.name for _, folder in same))
            newest += same[-1:]

        target = runs_dir / run_id
        for kind, folder in newest:
            source_name = Path(deck.source_pdf(folder)).name
            parsed = filenames.parse(source_name) if source_name else None
            label = f"{run_id} ← {folder.name}"
            if parsed is None:
                print(f"  ✗ {label} — 원본 파일명을 읽지 못했다")
                continue
            if target.exists() and not args.force:
                print(f"  · {label} — {target.name}이 이미 있다 (--force로 덮어쓴다)")
                continue
            if args.dry_run:
                print(f"  → {label} ({kind}, {parsed.title[:34]})")
                continue

            # 덮어쓰기는 **비우고 나서** 한다. 겹쳐 부으면 앞 파이프라인이 남긴
            # `.apkg`가 옆에 그대로 남고, `apkg_of`가 이름순으로 그걸 집을 수 있다.
            # 남기는 것은 사람이 만든 것뿐이다 — 예습 대화는 여기서 다시 못 만든다.
            if target.exists():
                for entry in target.iterdir():
                    if KEEP_ON_IMPORT(entry.name):
                        continue
                    shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
            shutil.copytree(folder, target, dirs_exist_ok=True)
            try:
                meta = deck.contract(target, run_id, parsed.title, kind)
            except (FileNotFoundError, OSError, ValueError) as cause:
                print(f"  ✗ {label} — 계약 모양으로 못 옮겼다: {cause}")
                continue
            (target / gate.HOLD_FILE).write_text(
                f"{source} 에서 옮겨 왔다. 이 사이트의 눈으로 본 적이 없다.\n"
                f"확인한 뒤 `python -m runner release {run_id}` 로 푼다.\n",
                encoding="utf-8")
            # 표시를 찍어 둔다. 안 찍으면 오늘 밤 워처가 옮겨 온 편을 처음부터
            # 다시 만들고, 사람이 보려던 그 덱이 그 자리에서 덮인다.
            stamped = ""
            source_path = Path(deck.source_pdf(target))
            if kind == deck.MAIN and parsed.date[:4] == args.this and source_path.exists():
                stamped = " · 표시함" if watch.stamp_run(runs_dir, run_id, source_path) else ""
            moved += 1
            print(f"  ✓ {label} — {meta['item_count']}장 · 보류 표시를 놓았다{stamped}")

    if not args.dry_run:
        print(f"\n  옮긴 것 {moved}편. 전부 보류 상태다 — `publish`가 덱을 안 내보낸다.")
        print("  확인한 편마다: python -m runner release <run_id>")
    return 0


def run_rebuild(args) -> int:
    """이미 만든 카드로 덱만 다시 굽는다. **모델을 부르지 않는다.**

    카드는 `items.reproduced.json`에 그대로 있고 여기서 하는 것은 그걸 `.apkg`로
    다시 싸는 것뿐이다 — 뒷면 배치나 CSS를 고쳤을 때 쓰는 자리다. 편당 몇 초이고
    돈이 들지 않는다.

    **guid는 안 바뀐다.** 씨앗이 `(강의 ID, 질문)`이고 둘 다 그대로이므로, 다시
    임포트하면 Anki가 같은 노트의 갱신으로 받아 복습 이력이 살아 있다.

    `--reflag`면 굽기 전에 소프트 표시를 다시 계산해 덧붙인다 — 검사 규칙이 늘었을 때
    이미 만든 덱에도 그 표시가 카드 뒷면 경고 박스로 뜨게 하는 길이다.
    """
    runs_dir = Path(args.runs)
    targets = rebuild.targets(runs_dir, args.run_id or "")
    if not targets:
        print("[rebuild] 다시 구울 것이 없다 (카드가 남아 있는 자리가 없다)")
        return 1

    print(f"[rebuild] {len(targets)}편")
    done, failed = 0, 0
    for t in targets:
        if args.dry_run:
            _, name, deck_name = rebuild.names(t)
            moved = "" if deck_name == t.cfg["deck"] else f"\n      덱 {t.cfg['deck']} → {deck_name}"
            print(f"  → {t.run_dir.name} {t.kind}  {name}.apkg{moved}")
            continue
        marks = deck.reflag(t.run_dir) if args.reflag else {}
        ok, got = rebuild.one(t, runs_dir)
        if not ok:
            print(f"  ✗ {t.run_dir.name} {t.kind} — {got[-1] if got else '실패'}")
            failed += 1
            continue
        done += 1
        added = (" · 새 표시 " + " ".join(f"{k} {v}장" for k, v in sorted(marks.items()))
                 if marks else "")
        print(f"  ✓ {t.run_dir.name} {t.kind} — {got['item_count']}장 · "
              f"미디어 {got['verified']['media']}개{added}")

    if not args.dry_run:
        print(f"\n  다시 구운 것 {done}편" + (f" · 실패 {failed}편" if failed else ""))
        print("  Anki에서 다시 임포트하면 같은 노트의 갱신으로 받는다 (guid가 그대로다).")
    return 1 if failed else 0


def run_release(args) -> int:
    """보류를 푼다. 사람이 그 편을 보고 괜찮다고 판단했을 때."""
    run_id = args.subject or args.run_id
    if not run_id:
        print("쓰는 법: python -m runner release 260812_01")
        return 2
    hold = Path(args.runs) / run_id / gate.HOLD_FILE
    if not hold.is_file():
        print(f"[release] {run_id}은 보류돼 있지 않다")
        return 0
    hold.unlink()
    print(f"[release] {run_id} 보류를 풀었다 — 다음 publish에서 덱이 나간다")
    return 0


def run_chosen(args) -> int:
    """어느 시도를 왜 골랐는지 적는다 (`docs/runs-layout.md` 4단계).

    `runs/<편>/CHOSEN.json` 이고 자세한 것은 `runner/chosen.py` 머리에 있다.
    **`--why` 없이는 적지 않는다** — 왜 골랐는지는 코드가 쓸 수 없다.

    인자를 안 주면 어느 편에 기록이 있고 어느 편에 없는지만 센다.
    """
    runs_dir = Path(args.runs)
    out_dir = REPO_ROOT / "out"
    run_id = args.subject or args.run_id

    if not run_id:
        ids = attempts.run_ids_with_alternatives(runs_dir, out_dir)
        if not ids:
            print("[chosen] 시도가 둘 이상인 편이 없다 — 고를 것이 없다")
            return 0
        have = [r for r in ids if chosen.read(runs_dir / r)]
        print(f"[chosen] 시도가 둘 이상인 편 {len(ids)}개 · 고른 기록이 있는 편 {len(have)}개")
        for rid in ids:
            mark = "▸" if rid in have else " "
            print(f"  {mark} {rid}  {chosen.summary(runs_dir / rid).splitlines()[0]}")
        if len(have) < len(ids):
            print("\n기록이 없는 편은 **지금 이 자리에 있는 것이 어쩌다 정본**인 상태다.")
            print('    python scripts/attempts.py <run_id>     먼저 재 보고')
            print('    python -m runner chosen <run_id> --keep --why "..."')
        return 0

    run_dir = runs_dir / run_id
    if not run_dir.is_dir():
        print(f"[chosen] {run_dir} 가 없다")
        return 1

    found = attempts.attempts_of(runs_dir, out_dir, run_id)
    if not found:
        print(f"[chosen] {run_id} 에 시도가 하나도 없다 — 카드 파일을 못 찾았다")
        return 1

    # 적지 않는 호출이면 지금 상태만 보여 준다.
    if not (args.keep or args.pick):
        print(f"[chosen] {run_id} — 시도 {sum(1 for a in found if a.fresh)}개")
        for a in found:
            where = a.path.name if a.path.parent != runs_dir else f"runs/{a.path.name}"
            print(f"  {'=' if not a.fresh else ' '} {where:<30} {a.cards:4}장  "
                  f"기출{a.exam_hit:3}  족보{a.jokbo_ref:3}  "
                  f"같음 {'—' if a.same_rate is None else f'{a.same_rate:.0%}'}"
                  + (f"  컷 {a.cut_id}" if a.cut_id else ""))
        print(f"  ▸ {chosen.summary(run_dir)}")
        if (mismatch := chosen.verdict(run_dir)):
            print(f"  ✋ {mismatch}")
        print("\n적으려면 --keep (지금 이 자리 것) 또는 --pick <경로> 와 --why 를 같이 주세요")
        return 0

    if args.keep and args.pick:
        print("[chosen] --keep 과 --pick 은 같이 못 쓴다")
        return 2
    if not (args.why or "").strip():
        print("[chosen] --why 가 필요하다. **왜 골랐는지는 코드가 쓰지 않는다**")
        print("         무엇이 좋은 시도인지가 아직 안 정해져 있어서다 "
              "(docs/runs-layout.md 「아직 안 정한 것」)")
        return 2

    want = run_dir if args.keep else Path(args.pick)
    pick = next((a for a in found if a.path.resolve() == want.resolve()), None)
    if pick is None:
        print(f"[chosen] {want} 는 이 편의 시도 목록에 없다. 있는 것은:")
        for a in found:
            print(f"    {a.path}")
        return 1

    record = chosen.build(run_id, pick, why=args.why, repo_root=REPO_ROOT,
                          considered=found, kind=chosen.MAIN,
                          previous=chosen.read(run_dir))
    path = chosen.write(run_dir, record)
    print(f"[chosen] {path}")
    print(f"  {chosen.summary(run_dir)}")
    if (mismatch := chosen.verdict(run_dir)):
        print(f"\n  ✋ {mismatch}")
        print("     **이 편의 덱은 다음 publish 에서 미뤄진다.** 강의록은 그대로 나간다.")
    return 0


def run_promote(args) -> int:
    """고른 시도를 강의 폴더로 올린다 (`docs/runs-layout.md` 5단계).

    강의 폴더의 루트는 「지금 나가는 것」만 들고 시도는 `main/<판>/` 에 산다. 그 둘을
    잇는 걸음이고, 올리는 일은 `deck.promote` + `deck.contract` 가 한다 —
    **빌드가 끝날 때 저절로 도는 것과 같은 걸음**이라 여기서 새로 만드는 것이 없다.

    쓸 자리는 둘이다 — 다른 시도를 골라 놓고 그것을 내보낼 때, 그리고 빌드가 계약
    단계에서 죽어 덱만 판 폴더에 남았을 때.
    """
    runs_dir = Path(args.runs)
    run_id = args.subject or args.run_id
    if not run_id:
        print("쓰는 법: python -m runner promote 260812_01")
        return 2
    run_dir = runs_dir / run_id
    if not run_dir.is_dir():
        print(f"[promote] {run_dir} 가 없다")
        return 1

    if not runlayout.attempt_dirs(run_dir):
        print(f"[promote] {run_id} 은 아직 옛 모양이다 — 시도가 강의 폴더에 그대로 있다.")
        print("          올릴 것이 없다. 접으려면 `python scripts/migrate_attempts.py "
              f"{run_id} --apply`")
        return 0

    print(f"[promote] {run_id}")
    done = 0
    for kind, layout_kind in ((deck.MAIN, runlayout.MAIN), (deck.PRE, runlayout.PREQUIZ)):
        want = args.version or None
        picked = runlayout.work_dir(run_dir, layout_kind, want)
        if picked == run_dir or not picked.is_dir():
            continue
        title = deck.calendar_node(runs_dir, run_id, "", kind) or run_id
        try:
            apkg = deck.promote(run_dir, kind, want)
            meta = deck.contract(run_dir, run_id, title, kind, want)
        except (FileNotFoundError, OSError, ValueError) as cause:
            print(f"  ✗ {kind} — 못 올렸다: {cause}")
            continue
        done += 1
        print(f"  {kind}  {picked.name} → {apkg.name}  ({meta['item_count']}장)")
    if not done:
        print("  올릴 시도가 없다")
        return 1

    # **올린 것과 고른 것이 어긋나면 여기서 말한다.** 문지기도 같은 것을 보지만
    # (`gate.inspect`), 사람이 방금 누른 명령의 자리에서 알아야 고칠 수 있다.
    if (mismatch := chosen.verdict(run_dir)):
        print(f"\n  ✋ {mismatch}")
        print("     **이 편의 덱은 다음 publish 에서 미뤄진다.**")
        return 1
    print(f"\n  이제 `python -m runner publish --run-id {run_id}` 로 나간다")
    return 0
