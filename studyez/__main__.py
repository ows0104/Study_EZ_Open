"""Study_EZ 로컬 러너 CLI.

    python -m studyez match 병리학          작년 짝 붙이기 리포트
    python -m studyez match --all
    python -m studyez watch                 새 필기 스캔 (무엇을 만들지 보여준다)
    python -m studyez watch --build         스캔 + 덱까지 (21:30 자동 실행용)
    python -m studyez watch --all-dates     블럭으로 안 좁힌다 (밀린 것 몰아 만들 때)
    python -m studyez watch <과목> --run-id <올해> --build
                                            그 강의 하나만 만든다 (캘린더 버튼이 이리로 온다)
    python -m studyez prequeue              예습 링크 → 자리 세우기
    python -m studyez prequeue --build      자리 세우고 예습 덱까지 (04:00 자동 실행용)
    python -m studyez prequeue --dry-run    무엇이 준비될지만 본다
    python -m studyez prequeue <과목> --run-id <올해> --build --force
                                            이미 만든 편도 버리고 다시 만든다
    python -m studyez jokbo 병리학           과목 족보를 강의별로 자른다 (학기당 1회)
    python -m studyez import --from <폴더>   다른 곳에서 만든 덱을 옮긴다 (보류로 들어온다)
    python -m studyez release <run_id>       보류를 푼다
    python -m studyez rebuild                이미 만든 카드로 덱만 다시 굽는다
    python -m studyez done <run_id>          빌드 끝. 표시하고 그 편을 올린다
    python -m studyez publish 병리학 --dry-run   무엇이 올라갈지 본다
    python -m studyez publish 병리학             서버로 밀어 넣는다
    python -m studyez publish --run-id <run_id>  그 run을 쓰는 한 편만 올린다
    python -m studyez publish --all              전부 훑는다 (야간 쓸어담기)

업로드는 두 자리에서 걸린다 — 편이 끝날 때 `done`이 그 편을, 하루 한 번
`scripts/nightly-publish.ps1`이 `publish --all`로 놓친 것을 쓸어담는다.
`publish`는 멱등이라 겹쳐 돌아도 다시 안 민다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from studyez import (  # noqa: E402
    agent,
    blocks,
    deck,
    filenames,
    gate,
    matching,
    preview,
    publish,
    runner,
    watch,
)

DEFAULT_ROOT = Path.home() / "SynologyDrive"
REPO_ROOT = Path(__file__).resolve().parent.parent


def notes_dir(root: Path, subject: str, year: str) -> Path:
    return root / subject / "필기" / year


def report_subject(root: Path, subject: str, this_year: str, prev_year: str) -> int:
    this_dir, prev_dir = notes_dir(root, subject, this_year), notes_dir(root, subject, prev_year)
    if not this_dir.is_dir():
        print(f"[{subject}] {this_year} 폴더 없음 — 건너뜀")
        return 0

    this_scan = filenames.scan(this_dir, expect_year=this_year)
    prev_scan = filenames.scan(prev_dir, expect_year=prev_year)
    this_files = filenames.latest_versions(this_scan.files)
    prev_files = filenames.latest_versions(prev_scan.files)

    print(f"\n=== {subject} — {this_year} {len(this_files)}편 ↔ {prev_year} {len(prev_files)}편 ===")

    for scan, label in ((this_scan, this_year), (prev_scan, prev_year)):
        for path in scan.conflicts:
            print(f"  [충돌 사본] {label}/ {path.name[:60]} — 제목 오염, 제외")
        for item in scan.misfiled:
            print(f"  [연도 어긋남] {label}/ 폴더에 {item.date[:4]}년 파일 — {item.title[:40]}")
        for path in scan.unparsed:
            print(f"  [읽지 못함] {label}/ {path.name[:60]}")

    for old, new in filenames.superseded(this_scan.files):
        if old.version == new.version:
            # 같은 강의를 두 사람이 각각 올렸다. 무엇을 쓸지는 사람이 정해야 한다.
            print(f"  [판 충돌] {old.key} {old.title[:28]} — "
                  f"{old.author}·{new.author} 판이 같은 v{new.version}. {new.author} 사용")
        else:
            print(f"  [판 중복] {old.key} {old.title[:28]} — v{old.version} 버리고 v{new.version} 사용")

    for key, group in sorted(filenames.parallel_lectures(this_files).items()):
        print(f"  [병렬 강의] {key}에 {len(group)}편이 나란히 열림")
        for item in group:
            print(f"             · {item.title[:56]}")

    matches = matching.match_years(this_files, prev_files)
    counts = {"확정": 0, "확인": 0, "없음": 0}

    print(f"\n  {'올해':<10} {'상태':<4} {'점수':>5} {'작년':<10}  제목")
    print(f"  {'-' * 10} {'-' * 4} {'-' * 5} {'-' * 10}  {'-' * 44}")
    for match in matches:
        counts[match.status] += 1
        prev = match.prev_year
        print(
            f"  {match.this_year.key:<10} {match.status:<4} "
            f"{match.score:>5.2f} {(prev.key if prev else '-'):<10}  "
            f"{match.this_year.title[:44]}"
        )
        if prev and match.this_year.stem != prev.stem:
            print(f"  {'':>32}  ↳ 작년: {prev.title[:44]}")
        if match.status == "확인" and match.runner_up:
            print(f"  {'':>32}  ⚠ 경쟁: {match.runner_up.title[:40]}")

    matched_prev = {m.prev_year.uid for m in matches if m.prev_year}
    leftovers = [p for p in prev_files if p.uid not in matched_prev]

    print(f"\n  확정 {counts['확정']} · 확인 필요 {counts['확인']} · 짝 없음 {counts['없음']}")
    if leftovers:
        print(f"  작년에만 있는 강의 {len(leftovers)}편 (아직 안 나간 진도로 보임)")

    return counts["확인"] + counts["없음"]


def run_preview(args) -> int:
    """공유된 예습 대화를 내려받아 runs/<run_id>/preview.md로 만든다."""
    run_id = args.subject
    if not run_id or not args.url:
        print("쓰는 법: python -m studyez preview <run_id> --url https://chatgpt.com/share/...")
        return 2

    # 자리가 비어 있어도 받는다. 대화가 먼저 오고 덱이 나중에 오는 순서라,
    # 여기서 prep을 요구하면 예습이 정작 필요한 편에서 막힌다.
    run_dir = Path(args.runs) / run_id
    result = preview.fetch(args.url)
    path = preview.save(result, run_dir)
    print(f"[preview] {run_id} ← {args.url}")
    print(f"  발화 {len(result.turns)}개 · {result.chars:,}자 · 추출 {result.strategy}")
    print(f"  → {path}")
    print("  이제 `python -m studyez prequeue --build`가 이걸 예습 설명본으로 읽는다")
    return 0


def run_jokbo(args) -> int:
    """과목 족보 PDF를 강의별 조각으로 자른다. 학기당 과목당 한 번이면 된다.

    자르는 것은 `pdf2anki.jokbo`다. 여기서 하는 것은 **어느 PDF를 줄지 고르는
    것**뿐 — 과목 폴더에서 원본을 찾아 `deck.cut_jokbo`에 넘긴다.

    강의와 조각을 짝지어 `links.json`을 쓰던 자리가 여기 있었는데 없앴다.
    지금은 어느 조각을 물릴지 pdf2anki가 카드를 만들 때 목차 제목으로 대조한다.
    두 곳에서 각각 짝지으면 **카드가 본 조각과 뒷면에 붙는 조각이 갈릴 수 있다.**
    """
    subject = args.subject
    if not subject:
        print("과목명을 주세요: python -m studyez jokbo 병리학")
        return 2

    folder = Path(args.root) / subject / "족보" / args.this
    pdfs = sorted(folder.glob("*.pdf")) if folder.is_dir() else []
    if not pdfs:
        print(f"[jokbo] {folder} 에 PDF가 없습니다")
        return 1
    if len(pdfs) > 1:
        print(f"[jokbo] PDF가 {len(pdfs)}개입니다. 가장 큰 것을 씁니다:")
        for candidate in pdfs:
            print(f"    {candidate.name} ({candidate.stat().st_size / 1024 / 1024:.1f}MB)")
        pdfs.sort(key=lambda candidate: candidate.stat().st_size, reverse=True)

    out_dir = deck.jokbo_dir(Path(args.runs), subject)
    print(f"[jokbo] {pdfs[0].name} → {out_dir}")
    code = deck.cut_jokbo(pdfs[0], out_dir, REPO_ROOT)
    if code != 0:
        print(f"  자르지 못했다 (코드 {code})")
        return 1

    index = out_dir / "index.json"
    if not index.is_file():
        print("  index.json이 안 나왔다 — 다음 빌드가 이 조각을 못 찾는다")
        return 1

    # 원본 족보가 어디 있는지 적어 둔다. 빌드가 기출 카드 뒷면에 **지면 이미지**를
    # 붙이려면 원본 PDF가 필요한데, 그건 SynologyDrive에 있어 저장소 안을 훑어서는
    # 못 찾는다. 안 적어 두면 카드는 멀쩡히 나오고 뒷면만 비어서 티가 안 난다.
    try:
        recorded = json.loads(index.read_text(encoding="utf-8"))
        recorded["source_path"] = str(pdfs[0].resolve())
        index.write_text(json.dumps(recorded, ensure_ascii=False, indent=1), encoding="utf-8")
    except (OSError, ValueError) as cause:
        print(f"  ⚠ index.json에 원본 경로를 못 적었다 ({cause}) — 지면 이미지가 빠진다")

    print(f"\n  → {index}")
    print("  이제 `python -m studyez watch --build`가 이 조각을 스스로 물린다")
    return 0


# pdf2anki 작업 폴더 이름. `pre_`가 예습, 뒤에 붙는 꼬리는 사람이 시험 삼아
# 갈라 둔 변형이다(`pre_p250825_01_note`). 꼬리가 달라도 같은 강의다.
RE_WORK_DIR = re.compile(r"^(?P<pre>pre_)?p(?P<run_id>\d{6}_\d{2}(?:-[0-9a-f]{4})?)(?P<variant>.*)$")

# 덮어쓸 때도 안 지우는 것. **사람이 만든 것과 남의 서비스에서 받아 온 것**이다 —
# 파이프라인은 이 둘을 다시 만들 수 없다.
KEEP_ON_IMPORT = {"preview.md", "pre_target.json"}


def import_dirs(source: Path) -> dict[str, list[tuple[str, Path]]]:
    """pdf2anki 작업 폴더를 훑어 `run_id`별로 모은다. `{run_id: [(kind, 폴더)]}`.

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
    """다른 곳에서 만든 pdf2anki 덱을 `runs/`로 옮긴다. **올리지는 않는다.**

    옮긴 자리마다 `HOLD`를 놓는다. 이 사이트의 눈(계약·검문)으로 한 번도 본 적이
    없는 산출물이라, 사람이 보고 `python -m studyez release <run_id>`로 풀기 전에는
    `publish`가 덱을 내보내지 않는다. 강의록 PDF는 그대로 나간다 — 그건 이 검토와
    무관한 자료다.
    """
    if not args.source_dir:
        print("쓰는 법: python -m studyez import --from \"../PDF2ANKI/out\"")
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
        chosen: list[tuple[str, Path]] = []
        for kind in (deck.MAIN, deck.PRE):
            same = sorted((pair for pair in entries if pair[0] == kind),
                          key=lambda pair: deck.apkg_of(pair[1], pair[0]).stat().st_mtime)
            if len(same) > 1:
                print(f"  ⚠ {run_id} {kind} — 후보가 {len(same)}개다. 가장 새 것을 쓴다: "
                      + " · ".join(folder.name for _, folder in same))
            chosen += same[-1:]

        target = runs_dir / run_id
        for kind, folder in chosen:
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
                    if entry.name in KEEP_ON_IMPORT:
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
                f"확인한 뒤 `python -m studyez release {run_id}` 로 푼다.\n",
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
        print("  확인한 편마다: python -m studyez release <run_id>")
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
    targets = []
    for entry in sorted(runs_dir.iterdir() if runs_dir.is_dir() else []):
        if not entry.is_dir() or (args.run_id and entry.name != args.run_id):
            continue
        for kind in (deck.MAIN, deck.PRE):
            cfg = deck.config_of(entry, kind)
            if cfg and cfg.get("deck") and (entry / "items.reproduced.json").is_file():
                targets.append((entry, kind, cfg))
    if not targets:
        print("[rebuild] 다시 구울 것이 없다 (카드가 남아 있는 자리가 없다)")
        return 1

    print(f"[rebuild] {len(targets)}편")
    done, failed = 0, 0
    for run_dir, kind, cfg in targets:
        subject = cfg["deck"].split("::")[0]
        parsed = filenames.parse(deck.source_pdf(run_dir))
        title = parsed.title if parsed else run_dir.name
        professors = parsed.professors if parsed else ()
        name = deck.calendar_name(run_dir, run_dir.name, title, kind, professors)
        # **덱 이름도 다시 세운다.** `run.config.json`의 것을 그대로 쓰면 이름 규칙이
        # 바뀌어도 Anki 안에서 보이는 이름만 옛것으로 남는다 — 파일만 바뀌고 덱은
        # 그대로였던 것이 실제로 그 이유였다.
        deck_name = deck.calendar_deck(run_dir, run_dir.name, title, kind, subject, professors)
        if args.dry_run:
            moved = "" if deck_name == cfg["deck"] else f"\n      덱 {cfg['deck']} → {deck_name}"
            print(f"  → {run_dir.name} {kind}  {name}.apkg{moved}")
            continue
        marks = deck.reflag(run_dir) if args.reflag else {}
        ok, tail = deck.rebuild(
            run_dir=run_dir, kind=kind, deck_name=deck_name,
            id=cfg.get("id") or deck.deck_id(run_dir.name),
            jokbo_dir=deck.jokbo_dir(runs_dir, subject), apkg_name=name,
            repo_root=REPO_ROOT)
        if not ok:
            print(f"  ✗ {run_dir.name} {kind} — {tail[-1] if tail else '실패'}")
            failed += 1
            continue
        # 이름 규칙이 바뀌면 옛 이름의 덱이 옆에 남는다. 같은 갈래의 낡은 것은
        # 지우고 간다 — 남겨 두면 어느 것이 참인지 파일만 봐서는 모른다.
        #
        # **굽기가 성공한 뒤에 지운다.** 먼저 지우던 때가 있었는데, 빌드가 결함을
        # 이유로 거부하면 그 편에 덱이 하나도 안 남았다. `runs/` 는 gitignore 라
        # 되돌릴 데가 없다 — 2026-08-23 에 `260821_05` 가 실제로 그렇게 날아갔다.
        for stale in run_dir.glob("*.apkg"):
            if deck.is_pre(stale) == (kind == deck.PRE) and stale.stem != name:
                stale.unlink()
        # 폴더가 기억하는 이름도 새것으로 바꾼다. 안 바꾸면 `--resume`이나 다음
        # rebuild가 옛 이름으로 되돌린다 — 그 자리가 정본이기 때문이다.
        if deck_name != cfg["deck"]:
            cfg["deck"] = deck_name
            (run_dir / ("prequiz.config.json" if kind == deck.PRE else "run.config.json")
             ).write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

        meta = deck.contract(run_dir, run_dir.name, title, kind)
        done += 1
        added = (" · 새 표시 " + " ".join(f"{k} {v}장" for k, v in sorted(marks.items()))
                 if marks else "")
        print(f"  ✓ {run_dir.name} {kind} — {meta['item_count']}장 · "
              f"미디어 {meta['verified']['media']}개{added}")

    if not args.dry_run:
        print(f"\n  다시 구운 것 {done}편" + (f" · 실패 {failed}편" if failed else ""))
        print("  Anki에서 다시 임포트하면 같은 노트의 갱신으로 받는다 (guid가 그대로다).")
    return 1 if failed else 0


def run_release(args) -> int:
    """보류를 푼다. 사람이 그 편을 보고 괜찮다고 판단했을 때."""
    run_id = args.subject or args.run_id
    if not run_id:
        print("쓰는 법: python -m studyez release 260812_01")
        return 2
    hold = Path(args.runs) / run_id / gate.HOLD_FILE
    if not hold.is_file():
        print(f"[release] {run_id}은 보류돼 있지 않다")
        return 0
    hold.unlink()
    print(f"[release] {run_id} 보류를 풀었다 — 다음 publish에서 덱이 나간다")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Study_EZ 로컬 러너")
    parser.add_argument("command", choices=["match", "watch", "done", "jokbo", "preview", "agent",
                                            "prequeue", "publish", "import", "release", "rebuild"])
    parser.add_argument("subject", nargs="?", help="과목 폴더명. --all이면 생략")
    parser.add_argument("--all", action="store_true", help="필기/올해 폴더가 있는 과목 전부")
    parser.add_argument("--this", default="2026", help="올해 폴더명")
    parser.add_argument("--prev", default="2025", help="작년 폴더명")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="자료 최상위 폴더")
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"), help="산출물 루트")
    parser.add_argument("--build", action="store_true",
                        help="watch·prequeue: 자리만 세우지 말고 덱까지 만든다")
    parser.add_argument("--model", default="",
                        help="watch·prequeue: 빈 세션에 쓸 모델 (기본: CLI 기본값)")
    parser.add_argument("--strategy", default="auto",
                        choices=("auto", "기본", "필기", "필기 중심", "족보", "족보 중심",
                                 "사진", "사진 중심",
                                 "base", "annotation", "jokbo", "image", "photo"),
                        help="watch --run-id: 복습 덱 전략. 실습 사진 중심은 '사진'")
    parser.add_argument("--timeout", type=int, default=deck.DEFAULT_TIMEOUT,
                        help=f"watch·prequeue: 한 편의 제한 시간(초). 기본 {deck.DEFAULT_TIMEOUT}")
    parser.add_argument("--max", type=int, default=watch.DEFAULT_MAX_ITEMS,
                        help="watch·prequeue: 한 번에 만들 상한")
    parser.add_argument("--within-days", type=int, default=0,
                        help="prequeue: 강의가 오늘부터 이 날짜 안에 있는 것만 만든다")
    parser.add_argument("--now", action="store_true",
                        help="watch: 방금 올라온 파일도 포함 (동기화 대기 생략)")
    parser.add_argument("--since", default=None,
                        help="watch: 이 날짜부터의 강의만 (YYYY-MM-DD). 주면 시간표를 안 본다")
    parser.add_argument("--until", default=None, help="watch: 이 날짜까지의 강의만")
    parser.add_argument("--all-dates", action="store_true",
                        help="watch: 블럭으로 좁히지 않는다. 지난 학기까지 전부 잡힌다")
    parser.add_argument("--today", default=None,
                        help="watch: 오늘을 이 날짜로 친다 (블럭 판정 확인용)")
    parser.add_argument("--timetable", default=None,
                        help=f"watch: 시간표 (기본 {blocks.DEFAULT_SOURCE})")
    parser.add_argument("--url", default=None,
                        help="preview: 공유된 예습 대화 주소")
    parser.add_argument("--api", default=None,
                        help=f"publish: API 주소 (기본 {publish.DEFAULT_API_BASE})")
    parser.add_argument("--token", default=None,
                        help="publish: 러너 토큰 (기본 server/.env의 RUNNER_TOKEN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="publish: 무엇이 올라갈지만 적고 올리지 않는다. "
                             "prequeue: 어느 자리에 설지만 적고 내려받기·빌드를 안 한다. "
                             "import: 무엇을 옮길지만 본다")
    parser.add_argument("--force", action="store_true",
                        help="publish: 이미 올린 표시를 무시하고 다시 올린다. "
                             "prequeue·watch: 이미 만든 편도 버리고 다시 만든다 (--run-id 필요)")
    parser.add_argument("--notes-only", action="store_true",
                        help="publish: 강의록만 올리고 덱·run-meta·예습 링크는 미룬다")
    parser.add_argument("--no-gate", action="store_true",
                        help="publish: 검문을 끄고 막힌 편도 민다 (사람이 보고 판단했을 때)")
    parser.add_argument("--run-id", default=None,
                        help="publish: 이 run을 쓰는 강의 한 편만 민다 (작년 run이면 그 짝). "
                             "prequeue: 이 강의의 예습 링크 하나만 (올해 run_id). "
                             "watch: 이 강의 하나만 만든다 — 블럭 창·하루 상한·이미 만든 "
                             "표시를 지난다 (올해 run_id)")
    parser.add_argument("--no-ahead", action="store_true",
                        help="publish·prequeue: 아직 필기가 없는 강의는 세우지 않는다 "
                             "(예습용 작년 강의록도 안 붙는다)")
    parser.add_argument("--no-publish", action="store_true",
                        help="done: 표시만 하고 올리지 않는다")
    parser.add_argument("--once", action="store_true",
                        help="agent: 한 바퀴만 돌고 끝낸다 (붙는지 볼 때)")
    parser.add_argument("--poll", type=int, default=agent.POLL_SECONDS,
                        help=f"agent: 일감을 물어보는 간격(초). 기본 {agent.POLL_SECONDS}")
    parser.add_argument("--sweep-minutes", type=int, default=agent.SWEEP_SECONDS // 60,
                        help=f"agent: 일감이 없을 때 남은 것을 쓸어 올리는 간격(분). "
                             f"기본 {agent.SWEEP_SECONDS // 60}")
    parser.add_argument("--no-sweep", action="store_true",
                        help="agent: 쓸기를 하지 않는다. 일감만 받는다")
    parser.add_argument("--no-prequeue", action="store_true",
                        help="publish·done: 올리기 전에 예습 링크를 서버와 맞추는 단계를 "
                             "건너뛴다 (그 사이 링크가 바뀌었으면 옛 주소로 덮어쓴다)")
    parser.add_argument("--reflag", action="store_true",
                        help="rebuild: 검사 규칙이 늘었을 때 소프트 표시를 다시 계산해 덧붙인다")
    parser.add_argument("--from", dest="source_dir", default=None,
                        help="import: 덱을 옮겨 올 pdf2anki 작업 폴더 (예: ../PDF2ANKI/out)")
    args = parser.parse_args()

    # 이름을 직접 대도 막는다. 실수로 한 번 돌리면 재고에 섞여 들어가고,
    # 그 뒤로는 왜 거기 있는지 아무도 모른다.
    if args.subject and filenames.is_excluded(args.subject):
        print(f"[{args.subject}] 학생마다 듣는 것이 달라 파이프라인에서 뺀 과목이다.\n"
              "  강의록 연결·예습·복습 어느 것도 만들지 않는다.\n"
              "  정말 필요하면 studyez/filenames.py의 EXCLUDED_SUBJECTS·"
              "EXCLUDED_PREFIXES를 고쳐라.")
        return 0

    if args.command == "watch":
        return runner.report_watch(args)
    if args.command == "done":
        return runner.run_done(args)
    if args.command == "jokbo":
        return run_jokbo(args)
    if args.command == "preview":
        return run_preview(args)
    if args.command == "prequeue":
        return runner.report_prequeue(args)
    if args.command == "agent":
        return runner.run_agent(args)
    if args.command == "import":
        return run_import(args)
    if args.command == "release":
        return run_release(args)
    if args.command == "rebuild":
        return run_rebuild(args)
    if args.command == "publish":
        if not args.subject and not args.all and not args.run_id:
            parser.error("과목명을 주거나 --all 또는 --run-id를 쓰세요")
        return runner.report_publish(args)

    root = Path(args.root)
    if args.all:
        subjects = runner.subjects_with_notes(root, args.this)
    elif args.subject:
        subjects = [args.subject]
    else:
        parser.error("과목명을 주거나 --all을 쓰세요")

    needs_review = 0
    for subject in subjects:
        needs_review += report_subject(root, subject, args.this, args.prev)

    print(f"\n손봐야 할 강의 {needs_review}편")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
