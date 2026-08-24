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
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date as Date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from studyez import (  # noqa: E402
    agent, blocks, deck, filenames, gate, matching, prequeue, preview, publish, watch,
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


def subjects_with_notes(root: Path, year: str) -> list[str]:
    """제외 대상(선택교과 등)은 여기서 이미 빠져 나온다."""
    return filenames.discover_subjects(root, year)


def resolve_window(args) -> tuple[str | None, str | None, int]:
    """이번 블럭의 구간. 못 정하면 큐를 세우지 않는다.

    `--since`/`--until`을 직접 주면 그게 이긴다. 아니면 오늘 날짜로 시간표에
    물어본다. 시간표가 대답을 못 하는 날에 창을 열어 두면 지난 학기 필기가
    통째로 딸려 오므로, 그럴 때는 아무것도 세우지 않고 사람을 부른다.
    """
    if args.all_dates:
        print("[block] --all-dates — 블럭으로 좁히지 않는다")
        return None, None, 0
    if args.since or args.until:
        print(f"[block] 손으로 준 구간 {args.since or '…'}~{args.until or '…'}")
        return args.since, args.until, 0

    today = Date.fromisoformat(args.today) if args.today else Date.today()
    try:
        found = blocks.find(today, Path(args.timetable) if args.timetable else None)
    except FileNotFoundError as missing:
        print(f"[block] 시간표를 찾지 못했다: {missing}\n"
              "  `python -m app.cli seed-timetable <시간표.json>`으로 넣거나 "
              "--timetable으로 준다. 큐를 세우지 않는다.")
        return None, None, 2

    if found.block is None:
        print(f"[block] {today} — 시간표({found.source.name}, 블럭 {len(found.table)}개)에서 "
              "오늘이 속한 블럭을 못 찾았다.\n"
              "  큐를 세우지 않는다. 필요하면 --since/--until로 구간을 준다.")
        return None, None, 2

    block = found.block
    print(f"[block] {today} — {block.label()} · {block.events}칸")
    if found.ended:
        # 블럭이 끝난 뒤 올라온 늦은 필기를 받으려고 물러난 것이다.
        print("  오늘은 이 블럭 밖이다. 늦게 올라온 필기를 받으려고 직전 블럭으로 물러났다.")
    return block.start.isoformat(), block.end.isoformat(), 0


def run_watch_one(args) -> int:
    """`watch --run-id` — 이 강의 하나만. 캘린더의 「Main-Quiz 덱 만들기」가 여기로 온다.

    쓸기와 다른 것이 셋이다. 셋 다 **사람이 그 편을 지목했다**는 한 가지에서 나온다 —
    블럭 창을 안 보고, 하루 상한을 안 보고, 이미 만들었다는 표시로 거르지 않는다
    (`watch.build_queue`의 `only_run_id`).

    **덱 파일이 있으면 안 만든다.** 그때 없는 것은 덱이 아니라 업로드이고, 그건
    이어서 `publish`가 한다. 15분과 빈 세션 넷을 다시 쓸 이유가 없다.
    `--force`면 그것도 버리고 다시 만든다.

    **큐 파일을 안 쓴다.** `runs/queue.json`은 밤에 무엇이 돌지 보는 자리인데,
    지목해서 만든 한 편으로 덮으면 그 자리가 없어진다.

    **실패하면 종료 코드로 말한다.** 쓸기는 한 편이 죽어도 0으로 끝난다(하룻밤
    분량이 한 편 때문에 날아가면 안 되므로). 여기서는 그 한 편이 전부다 —
    러너가 이 값으로 화면에 실패를 적는다.
    """
    runs_dir = Path(args.runs)
    run_dir = runs_dir / args.run_id
    made = deck.apkg_of(run_dir, deck.MAIN)
    if made and not args.force:
        print(f"[watch] {args.run_id} — 이미 덱이 있다: {made.name}\n"
              f"  안 올라간 것뿐이면 `python -m studyez publish --run-id {args.run_id}`가 민다.\n"
              "  덱 자체를 다시 만들려면 --force.")
        return 0

    root = Path(args.root)
    subjects = [args.subject] if args.subject else subjects_with_notes(root, args.this)
    queue = watch.build_queue(
        root=root, subjects=subjects, this_year=args.this, runs_dir=runs_dir,
        min_age_seconds=0 if args.now else watch.MIN_AGE_SECONDS,
        only_run_id=args.run_id,
    )
    for warning in queue.warnings:
        print(f"  ⚠ {warning}")

    if not queue.items:
        print(f"[watch] {args.run_id} — 만들 자리를 못 찾았다.")
        for line in queue.skipped:
            print(f"  · {line}")
        if not queue.skipped:
            # 걸러진 것도 없이 비었다면 그 run_id를 쓰는 올해 필기가 아예 없는 것이다.
            where = f"{args.subject} " if args.subject else ""
            print(f"  {where}필기/{args.this}에 이 run_id로 서는 강의가 없다 — "
                  "아직 안 올라왔거나 파일명이 바뀌었다.")
        return 1

    item = queue.items[0]
    for note in item.notes:
        print(f"  ⚠ {note}")
    if not args.build:
        print(f"[watch] {item.subject}/{item.run_id} {item.title[:38]}\n"
              f"  {Path(item.this_pdf).name}\n"
              "  `--build`를 붙이면 이대로 만든다.")
        return 0

    print(f"[watch] {item.subject}/{item.run_id} {item.title[:38]} — 만드는 중")
    started = time.monotonic()
    # **`--force`는 pdf2anki까지 내려가야 한다.** 여기서 「덱이 있어도 만든다」까지만
    # 하고 넘기면 pdf2anki가 이미 만든 단계를 건너뛰고 그 산출물로 덱만 다시 굽는다 —
    # 다시 만들라고 누른 사람은 「다시 만들었는데 그대로다」를 본다(`prequeue`도 같다).
    ok, note = watch.build_one(item, runs_dir, REPO_ROOT, model=args.model, timeout=args.timeout,
                               extra=["--force"] if args.force else None)
    minutes = (time.monotonic() - started) / 60
    if not ok:
        print(f"    실패 — {note} · {minutes:.1f}분")
        return 1
    print(f"    끝났다 — {note} · {minutes:.1f}분")
    print(f"  `python -m studyez publish --run-id {item.run_id}` — 검문을 지나면 나간다.")
    return 0


def report_watch(args) -> int:
    if args.run_id:
        return run_watch_one(args)
    if args.force:
        # 한 편이 빈 세션 넷이다. 좁히지 않은 --force는 이번 블럭을 통째로 다시
        # 만들라는 말이 되는데, 그걸 지나가듯 받으면 안 된다(`prequeue`와 같다).
        print("--force는 --run-id와 같이 준다 — 어느 편을 다시 만들지 정해야 한다.")
        return 2

    root = Path(args.root)
    runs_dir = Path(args.runs)
    subjects = [args.subject] if args.subject else subjects_with_notes(root, args.this)

    since, until, failed = resolve_window(args)
    if failed:
        return failed

    queue = watch.build_queue(
        root=root, subjects=subjects, this_year=args.this,
        runs_dir=runs_dir, max_items=args.max,
        min_age_seconds=0 if args.now else watch.MIN_AGE_SECONDS,
        since=since, until=until,
    )

    print(f"[watch] {queue.generated_at} — 과목 {len(subjects)}개")
    for warning in queue.warnings:
        print(f"  ⚠ {warning}")

    if not queue.items:
        print("\n  새로 만들 강의 없음")
    else:
        print(f"\n  만들 강의 {len(queue.items)}편")
        for item in queue.items:
            mark = "새로" if item.reason == "new" else f"v{item.this_version} 갱신"
            print(f"    {item.date}  {item.subject}/{item.run_id}  [{mark}]  {item.title[:38]}")
            for note in item.notes:
                print(f"        ⚠ {note}")

    for line in queue.skipped:
        print(f"  · 건너뜀 — {line}")

    if args.build and queue.items:
        planned = len(queue.items)
        started = time.monotonic()
        print(f"\n  덱 만드는 중 {planned}편 — 한 편씩 돈다\n")
        queue = watch.build(queue, runs_dir, REPO_ROOT,
                            model=args.model, timeout=args.timeout)
        failed = planned - len(queue.items)
        print(f"\n  완료 {len(queue.items)}편"
              + (f" · 실패 {failed}편" if failed else "")
              + f" · {(time.monotonic() - started) / 60:.1f}분")
        for line in queue.skipped:
            if "빌드 실패" in line:
                print(f"    ✗ {line}")

    queue_path = runs_dir / "queue.json"
    watch.save(queue, queue_path)
    print(f"\n  큐: {queue_path}")
    if queue.items and not args.build:
        print("  `python -m studyez watch --build` — 이대로 덱까지 만든다.")
    elif queue.items:
        print("  `python -m studyez publish --all` — 검문을 지난 편이 나간다.")
    return 0


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


def run_source_pdf(runs_dir: Path, run_id: str) -> Path | None:
    """이 run이 실제로 무엇으로 만들어졌는지.

    큐가 아니라 여기를 보는 이유는 **큐가 그 사이 다시 서기 때문**이다. 그리고
    이쪽이 더 참이다 — 큐는 지금 무엇을 만들 차례인지를 적고, 파이프라인의
    `run.config.json`은 이 run이 무엇으로 만들어졌는지를 적는다.
    """
    source = deck.source_pdf(runs_dir / run_id)
    return Path(source) if source else None


def subject_of(pdf: Path) -> str | None:
    """`.../{과목}/필기/{연도}/파일.pdf`에서 과목을 읽는다. 모양이 다르면 None."""
    parts = pdf.parts
    if "필기" in parts:
        index = parts.index("필기")
        if index >= 1:
            return parts[index - 1]
    return None


def stamp_source(runs_dir: Path, run_id: str, this_year: str, dry_run: bool = False) -> str | None:
    """빌드가 끝난 편을 표시한다. 알아낸 과목명을 돌려준다.

    **작년 run은 표시하지 않는다.** 표시는 "이 올해 필기는 이미 만들었다"는
    뜻으로 다음 스캔에서 빼는 장치인데, 스캔이 도는 곳은 올해 폴더뿐이다.
    `/prequiz`가 끝낸 작년 run에 찍으면 아무 데도 안 쓰이는 파일만 남는다.
    """
    pdf = run_source_pdf(runs_dir, run_id)
    if pdf is None:
        print(f"[done] {run_id}/prep.json에서 원본을 못 읽었다 — 표시를 건너뛴다")
        return None

    subject = subject_of(pdf)
    parsed = filenames.parse(pdf)
    if parsed is None or parsed.date[:4] != this_year:
        year = parsed.date[:4] if parsed else "?"
        print(f"[done] {run_id}은 {year} 필기로 돈 run이다 — 표시하지 않는다 "
              "(표시는 올해 필기를 다시 안 만들려는 장치다)")
        return subject

    if dry_run:
        print(f"[done] --dry-run — {run_id}을 표시하지 않았다")
        return subject

    if watch.stamp_run(runs_dir, run_id, pdf):
        print(f"[done] {run_id} 표시함 (v{parsed.version}) — 다음 스캔에서 빠진다")
    else:
        print(f"[done] {run_id}의 원본을 찾지 못했다 ({pdf.name[:50]}) — 표시를 건너뛴다")
    return subject


def report_cost(run_dir: Path) -> None:
    """이 편이 얼마나 들었는지 적는다. 세는 것은 파이프라인이 한다.

    예전에는 여기서 세션 트랜스크립트를 뒤져 토큰을 셈했다. 지금은 pdf2anki가
    `claude -p --output-format json` 봉투에 이미 실려 오는 값을 단계마다
    `usage.jsonl`에 적고 `run.report.json`으로 모으므로, 읽어 보여 주기만 한다.

    **`watch.DEFAULT_MAX_ITEMS`를 정할 근거가 여기서 쌓인다.**
    """
    report = run_dir / "run.report.json"
    if not report.is_file():
        return
    try:
        got = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    total = got.get("cumulative") or {}
    if not total:
        return
    print(f"  [비용] 누적 ${total.get('cost_usd', 0):.2f} · "
          f"{total.get('seconds', 0) / 60:.1f}분 · 세션 {total.get('sessions', 0)}개 · "
          f"토큰 {total.get('tokens_total', 0):,}")


def run_done(args) -> int:
    """빌드를 확인한 뒤 부른다. 표시하고, 이어서 그 편을 올린다.

    올리는 것까지 여기서 하는 이유는 **끝난 덱이 손을 기다리지 않게** 하려는
    것이다. `publish`는 멱등이고(ledger + 서버 HEAD) 편마다 `studyez.gate`가
    보므로, 여기서 불러도 검문에 걸린 편은 강의록만 나간다. 올리기 싫으면
    `--no-publish`.
    """
    runs_dir = Path(args.runs)
    run_id = args.subject
    if not run_id:
        print("쓰는 법: python -m studyez done 260814_05")
        return 2

    subject = stamp_source(runs_dir, run_id, args.this, dry_run=args.dry_run)

    if not args.dry_run:
        report_cost(runs_dir / run_id)

    if args.no_publish:
        return 0

    # `subject` 위치 인자에 run_id가 들어와 있다. 업로드는 과목으로 도는 코드라
    # 자리를 제자리로 돌려놓고 넘긴다 — 못 알아냈으면 전 과목에서 찾게 둔다.
    args.run_id = run_id
    args.subject = subject
    print()
    return report_publish(args)


def run_jokbo(args) -> int:
    """과목 족보 PDF를 강의별 조각으로 자른다. 학기당 과목당 한 번이면 된다.

    자르는 것은 `pdf2anki.jokbo`다. 여기서 하는 것은 **어느 PDF를 줄지 고르는
    것**뿐 — 과목 폴더에서 원본을 찾아 하위 프로세스에 넘긴다.

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
    done = subprocess.run(
        [sys.executable, "-m", "pdf2anki.jokbo", str(pdfs[0]), "-o", str(out_dir)],
        cwd=str(REPO_ROOT), env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if done.returncode != 0:
        print(f"  자르지 못했다 (코드 {done.returncode})")
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
        module = "pdf2anki.prequiz.build" if kind == deck.PRE else "pdf2anki.build"
        subject = cfg["deck"].split("::")[0]
        parsed = filenames.parse(deck.source_pdf(run_dir))
        title = parsed.title if parsed else run_dir.name
        professors = parsed.professors if parsed else ()
        name = deck.calendar_name(run_dir, run_dir.name, title, kind, professors)
        # **덱 이름도 다시 세운다.** `run.config.json`의 것을 그대로 쓰면 이름 규칙이
        # 바뀌어도 Anki 안에서 보이는 이름만 옛것으로 남는다 — 파일만 바뀌고 덱은
        # 그대로였던 것이 실제로 그 이유였다.
        deck_name = deck.calendar_deck(run_dir, run_dir.name, title, kind, subject, professors)
        argv = [sys.executable, "-m", module, str(run_dir),
                "--deck", deck_name, "--id", cfg.get("id") or deck.deck_id(run_dir.name),
                "--jokbo-dir", str(deck.jokbo_dir(runs_dir, subject)),
                "--apkg-name", name]
        if args.dry_run:
            moved = "" if deck_name == cfg["deck"] else f"\n      덱 {cfg['deck']} → {deck_name}"
            print(f"  → {run_dir.name} {kind}  {name}.apkg{moved}")
            continue
        marks = deck.reflag(run_dir) if args.reflag else {}
        result = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            print(f"  ✗ {run_dir.name} {kind} — {tail[-1] if tail else result.returncode}")
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


def runner_token(explicit: str | None) -> str:
    """러너 토큰. 인자 → 환경 변수 → `server/.env` 순으로 찾는다.

    같은 기계에서 도는 스크립트라 `.env`를 그대로 본다. 커밋되지 않는 파일이고,
    거기에도 없으면 Secret Manager의 `studyez-runner-token`에서 꺼내야 한다.
    """
    if explicit:
        return explicit.strip()
    value = os.getenv("STUDYEZ_RUNNER_TOKEN", "").strip()
    if value:
        return value
    env_file = REPO_ROOT / "server" / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("RUNNER_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def within_days_until(args) -> str:
    """`--within-days N` → 그날까지의 날짜. 0이면 빈 문자열(제한 없음).

    예습은 **강의 전날**에 값이 있는 것이라, 밀린 링크가 스무 개일 때 먼 강의까지
    밤새 만들 이유가 없다. 미룬 편은 다음 실행에서 다시 잡힌다.
    """
    if not args.within_days:
        return ""
    today = Date.fromisoformat(args.today) if args.today else Date.today()
    return (today + timedelta(days=args.within_days)).isoformat()


def report_prequeue(args) -> int:
    """관리자가 저장한 예습 링크를 받아 Pre-Quiz를 만들 자리까지 세운다.

    `--build` 없이 부르면 자리만 세운다 — 짝 고르기와 예습 대화 내려받기까지다.
    `--build`면 이어서 `pdf2anki.prequiz`가 덱을 만든다.
    """
    root, runs_dir = Path(args.root), Path(args.runs)
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")

    token = runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 "
              "STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
        return 2

    if args.force and not args.run_id:
        # 한 편이 빈 세션 넷이다. 좁히지 않은 --force는 저장된 링크 전부를 다시
        # 만들라는 뜻이 되는데, 그것을 누르려는 사람은 없다.
        print("--force는 --run-id와 같이 준다 — 어느 편을 다시 만들지 정해야 한다.")
        print("  안 그러면 저장된 예습 링크 전부를 다시 만든다 (한 편에 빈 세션 넷)")
        return 2

    print(f"[prequeue] {api}")
    try:
        links = prequeue.fetch_links(publish.Client(api, token))
    except publish.PublishError as cause:
        print(f"  예습 링크를 못 읽었다 — {cause}")
        return 1

    if args.subject:
        links = [link for link in links if link.subject == args.subject]
    if args.run_id:
        links = [link for link in links if link.run_id == args.run_id]

    print(f"  저장된 예습 링크 {len(links)}개")
    if not links:
        print("\n  /admin에서 예습 링크를 저장하면 여기에 잡힌다")
        return 0

    targets, warnings = prequeue.resolve(
        links, root, args.this, args.prev, runs_dir,
        timetable=None if args.no_ahead else Path(args.timetable or blocks.DEFAULT_SOURCE))
    for warning in warnings:
        print(f"  ⚠ {warning}")

    if args.dry_run:
        # 아직 아무것도 안 세웠으므로 state는 "막혔나 아닌가"까지만 참이다.
        print("\n  --dry-run — 대화 내려받기도 빌드도 하지 않았다\n")
        for target in targets:
            link = target.link
            # 서버에 저장된 제목이 아니라 **덱에 붙을 제목**을 보여 준다. 시간표
            # 칸에서 세운 강의는 그 사이 이름이 펴졌을 수 있다.
            title = target.this_title or link.title
            if target.state == prequeue.BLOCKED:
                print(f"  {link.date} ✋ {link.run_id:<12} {title[:30]:<30}")
                print(f"      {target.reason}")
            else:
                print(f"  {link.date}    {link.run_id:<12} {title[:30]:<30} "
                      f"→ 작년 {target.prev_run_id}")
        return 0

    planned = [target for target in targets if target.state != prequeue.BLOCKED]
    if planned:
        started = time.monotonic()
        print(f"\n  {'다시 만들 ' if args.force else ''}자리 세우는 중 {len(planned)}편 (예습 대화 내려받기)…")
        targets = prequeue.prepare(targets, runs_dir, force=args.force)
        print(f"  {(time.monotonic() - started) / 60:.1f}분")

    print()
    ready: list[prequeue.Target] = []
    for target in targets:
        link = target.link
        mark = {prequeue.READY: "▶", prequeue.DONE: "✓",
                prequeue.STALE: "↻", prequeue.BLOCKED: "✋"}[target.state]
        print(f"  {link.date} {mark} {link.run_id:<12} "
              f"{(target.this_title or link.title)[:30]:<30} "
              + (f"→ 작년 {target.prev_run_id}" if target.prev_run_id else ""))
        if target.reason:
            print(f"      {target.reason}")
        for note in target.notes:
            print(f"      · {note}"
                  + (f" ({target.turns}발화 {target.chars:,}자)"
                     if "새로 받음" in note and target.chars else ""))
        if target.state in (prequeue.READY, prequeue.STALE):
            ready.append(target)

    counts = {state: sum(1 for t in targets if t.state == state)
              for state in (prequeue.READY, prequeue.STALE, prequeue.DONE, prequeue.BLOCKED)}
    print(f"\n  만들 것 {counts[prequeue.READY]}편"
          f" · 다시 만들 것 {counts[prequeue.STALE]}편"
          f" · 이미 있는 것 {counts[prequeue.DONE]}편"
          f" · 막힌 것 {counts[prequeue.BLOCKED]}편")

    if args.build and ready:
        print(f"\n  예습 덱 만드는 중 {len(ready)}편 — 한 편씩, 강의 날짜가 이른 것부터\n")
        started = time.monotonic()
        targets = prequeue.build(targets, runs_dir, REPO_ROOT, model=args.model,
                                 timeout=args.timeout, limit=args.max,
                                 until=within_days_until(args))
        print(f"\n  {(time.monotonic() - started) / 60:.1f}분")

    queue_path = runs_dir / prequeue.QUEUE_NAME
    prequeue.save(targets, queue_path)
    print(f"  큐: {queue_path}")
    if ready and not args.build:
        print("\n  `python -m studyez prequeue --build` — 이대로 예습 덱까지 만든다:")
        for target in ready:
            print(f"    {target.prev_run_id}  {Path(target.prev_pdf).name[:52]}")
    elif args.build:
        print("  `python -m studyez publish --all` — 덱·문항·링크가 함께 올라간다.")
    return 0


def explain_missing_run(runs_dir: Path, run_id: str, prev_year: str) -> int:
    """`--run-id`가 붙을 강의를 못 찾았을 때. 무엇이 일어난 것인지 가려서 적는다.

    **작년 run이면 대개 정상이다.** Pre-Quiz를 진도보다 앞서 만들어 두면 올해
    필기가 아직 없어 붙일 자리가 없다. 산출물은 그대로 남고, 올해 필기가 올라온
    뒤 야간 `publish --all`이 그때 같이 민다. 그래서 이 경우만 0으로 끝낸다.
    """
    prep = runs_dir / run_id / "prep.json"
    source = ""
    if prep.is_file():
        try:
            source = str(json.loads(prep.read_text(encoding="utf-8")).get("source_pdf", ""))
        except (OSError, ValueError):
            source = ""
    parsed = filenames.parse(source) if source else None

    if parsed is not None and parsed.date[:4] == prev_year:
        print(f"[publish] {run_id}은 {prev_year} 필기로 돈 run이다 — {parsed.title[:40]}\n"
              "  올해 그 강의가 아직 안 올라와 붙일 자리가 없다. **올리지 않았다.**\n"
              "  산출물은 그대로 두면 된다 — 올해 필기가 올라오면 야간 publish가 같이 민다.")
        return 0

    print(f"[publish] {run_id} — 이 run을 쓰는 강의를 못 찾았다. **올리지 않았다.**\n"
          "  올해 필기가 지워졌거나 파일명이 바뀌었을 수 있다.\n"
          "  Pre-Quiz라면 작년 짝이 확정이 아니어서 안 붙은 것일 수도 있다 —\n"
          "  `python -m studyez match <과목>`으로 확인하라")
    return 1


def run_agent(args) -> int:
    """서버의 일감을 집어 와 만들고 올린다. **야간 스케줄러 자리에 선 것이다.**

    왜 크론을 걷어냈는지는 `studyez/agent.py` 첫머리에 있다. 요약하면 크론은
    닷새 동안 아무것도 안 올리면서 종료 코드 0을 냈고, 아무도 몰랐다.
    """
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")
    token = runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 "
              "STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
        return 2

    worker = agent.Agent(
        publish.Client(api, token), Path(args.runs), REPO_ROOT,
        subject=args.subject or "",
        sweep_seconds=0 if args.no_sweep else args.sweep_minutes * 60,
        timeout=args.timeout)
    if args.once:
        # 붙는지 보는 용도. 일감이 없으면 쓸기도 한 번 돌려 준다.
        worker.last_sweep = 0.0
        worker.tick()
        return 0
    return worker.loop(poll=args.poll)


def sync_previews(args, subjects: list[str], runs_dir: Path, api: str) -> set[tuple[str, str]]:
    """올리기 전에 예습 링크를 서버와 맞춘다. 돌려주는 것은 **어긋난 편**이다.

    이 저장소에서 방향이 반대인 것은 예습 링크 하나뿐이다 — 사람이 `/admin`에
    저장하므로 서버가 원본이다. `publish`는 `preview.md` 머리의 주소를 그대로
    다시 밀기 때문에, 당겨 오지 않으면 **관리자가 그 사이 바꾼 링크를 옛 것으로
    되돌린다.** 야간은 스크립트가 `prequeue`를 앞에 세워 막고 있었는데, 그러면
    손으로 `publish`·`done`을 부르는 길이 그대로 열려 있다. 그래서 여기로 옮겼다.

    맞춘 뒤에도 **덱은 옛 대화로 만든 것일 수 있다.** 그 편의 이름을 돌려주면
    `publish`가 Pre-Quiz만 미룬다(`publish.hold_pre`). 안 그러면 새 링크와 옛
    문항이 함께 나가서, 학생이 읽고 온 대화와 문항이 어긋난다.

    실패해도 올리기는 계속 간다 — 예습 링크 하나 때문에 강의록이 밀리면 안 된다.
    """
    token = runner_token(args.token)
    if not token:
        # 토큰이 없으면 어차피 아무것도 못 올린다. 그 말은 publish가 한다.
        return set()

    try:
        targets, warnings = prequeue.refresh(
            publish.Client(api, token), Path(args.root), args.this, args.prev, runs_dir,
            subjects=tuple(subjects),
            timetable=None if args.no_ahead else Path(args.timetable or blocks.DEFAULT_SOURCE))
    except publish.PublishError as cause:
        print(f"  ⚠ 예습 링크를 못 읽었다 — {cause}. 맞추지 못한 채로 올린다")
        return set()
    for warning in warnings:
        print(f"  ⚠ {warning}")

    fetched = [t for t in targets if any("새로 받음" in note for note in t.notes)]
    stale = {(t.link.subject, t.prev_run_id)
             for t in targets if t.state == prequeue.STALE and t.prev_run_id}
    print(f"  예습 링크 {len(targets)}개 · 새로 받은 대화 {len(fetched)}개"
          + (f" · 덱이 옛 대화로 만들어진 편 {len(stale)}개" if stale else ""))
    return stale


def report_publish(args) -> int:
    """산출물을 서버로. 무엇이 올라갈지 먼저 다 적고 나서 민다.

    **예습 링크를 먼저 서버에서 당겨 온다**(`sync_previews`). 순서가 반대면
    관리자가 방금 저장한 링크를 옛 것으로 덮어쓴다. `--no-prequeue`로 끈다.
    """
    root, runs_dir = Path(args.root), Path(args.runs)
    subjects = [args.subject] if args.subject else subjects_with_notes(root, args.this)
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")

    print(f"[publish] {api}")
    # 계획을 세우기 **전에** 맞춘다. 계획이 `preview.md`를 읽어 올릴 주소를 정하므로,
    # 뒤에 맞추면 이번 실행은 옛 주소를 그대로 민다.
    stale: set[tuple[str, str]] = set()
    if args.no_prequeue:
        print("  ⚠ --no-prequeue — 예습 링크를 안 맞춘다. 그 사이 바뀌었으면 옛 주소로 덮어쓴다")
    elif args.dry_run:
        print("  --dry-run — 예습 링크도 안 맞춘다 (남의 서비스를 두들기는 일이다)")
    else:
        stale = sync_previews(args, subjects, runs_dir, api)

    plans: list[publish.LecturePlan] = []
    warnings: list[str] = []
    for subject in subjects:
        subject_plans, subject_warnings = publish.plan_subject(
            root, subject, args.this, args.prev, runs_dir,
            notes_only=args.notes_only, gated=not args.no_gate,
            # 아직 필기가 없는 강의에도 작년 강의록을 붙인다. 예습이 필요한 쪽이
            # 그쪽이라 이게 기본이고, 시간표가 있어야 자리를 안다.
            timetable=None if args.no_ahead else Path(args.timetable or blocks.DEFAULT_SOURCE))
        plans.extend(subject_plans)
        warnings.extend(subject_warnings)

    if args.run_id:
        # 한 편만 민다. 과목을 안 줬으면 전 과목을 훑어 이 run을 쓰는 강의를 찾는다 —
        # Pre-Quiz는 작년 run에 산출물이 있어서 run_id만으로는 과목을 모른다.
        wanted = [p for p in plans if args.run_id in (p.run_id, p.prev_run_id)]
        if not wanted:
            return explain_missing_run(runs_dir, args.run_id, args.prev)
        # 남은 편의 과목 것만 남긴다. 다른 과목의 스캔 경고는 이 실행이 판단할
        # 자리가 아니다 — 야간 `--all`이 그걸 다 적는다.
        kept = {p.subject for p in wanted}
        warnings = [w for w in warnings if w.split(":", 1)[0] in kept]
        plans = wanted

    for plan in plans:
        if plan.prev_run_id and (plan.subject, plan.prev_run_id) in stale:
            publish.hold_pre(plan, "예습 링크가 바뀌었다 — 덱은 옛 대화로 만든 것이다")

    held = [p for p in plans if p.blocking]
    print(f"  과목 {len(subjects)}개 · 강의 {len(plans)}편"
          + (f" · 검문에 걸린 {len(held)}편" if held else ""))
    if args.no_gate:
        print("  ⚠ --no-gate — 검문을 끄고 민다. 무엇이 걸렸는지는 아래에 그대로 적는다")
    for warning in warnings:
        print(f"  ⚠ {warning}")

    if not plans:
        print("\n  올릴 것이 없다 — 올해 필기 폴더가 비어 있다")
        return 0

    total = 0
    print()
    for plan in plans:
        size = sum(upload.size for upload in plan.uploads)
        total += size
        extras = []
        if plan.run_meta:
            extras.append("run-meta " + "·".join(sorted(plan.run_meta)))
        if plan.pre_items:
            extras.append("pre-items")
        if plan.preview_url:
            extras.append("예습 링크")
        # 아직 필기가 없어 시간표에서 세운 자리. 진도보다 앞선 편이라 한눈에
        # 갈려야 한다.
        mark = "예습" if plan.ahead else "  "
        print(f"  {plan.item.date} {mark} {plan.run_id:<12} {plan.item.title[:32]:<32} "
              f"{publish.human(size):>8}  {plan.kinds()}"
              + (f"  + {' · '.join(extras)}" if extras else ""))
        for reason in plan.blocking:
            print(f"      ✋ {reason}")
        for note in plan.notes:
            print(f"      ⚠ {note}")

    ahead_plans = [p for p in plans if p.ahead]
    # 그중 몇 편이 실제로 Pre-Quiz를 들고 나가는가. 이 자리를 세운 이유가
    # 그것이라 개수만 적고 끝내면 아무것도 안 나가는 날을 못 알아본다.
    ahead_with_quiz = [p for p in ahead_plans if p.pre_items or "pre" in p.run_meta]
    print(f"\n  파일 {sum(len(p.uploads) for p in plans)}개 · {publish.human(total)}"
          + (f" · 그중 진도보다 앞선 자리 {len(ahead_plans)}편"
             f"(Pre-Quiz가 붙은 것 {len(ahead_with_quiz)}편)" if ahead_plans else ""))
    if held and not args.no_gate:
        # 미룬 것은 사라지지 않는다. 고치고 다시 부르면 그때 올라간다.
        print(f"  ✋ 검문에 걸린 {len(held)}편은 강의록만 나간다 — "
              f"{', '.join(p.run_id for p in held)}")
        print("     고친 뒤 다시 부르거나, 사람이 보고 괜찮으면 --no-gate로 민다")

    if args.dry_run:
        print("  --dry-run — 아무것도 올리지 않았다")
        return 0

    token = runner_token(args.token)
    if not token:
        print("\n  러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 "
              "STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
        return 2

    print()
    started = time.monotonic()
    report = publish.publish(plans, publish.Client(api, token), runs_dir, force=args.force)
    elapsed = time.monotonic() - started

    print(f"\n  올린 파일 {report.uploaded}개 ({publish.human(report.uploaded_bytes)}) · "
          f"그대로 둔 것 {report.skipped}개 · {elapsed / 60:.1f}분")
    print(f"  run-meta {report.run_meta} · pre-items {report.pre_items}문항 · "
          f"예습 링크 {report.previews}")
    if report.unlinked:
        # 안 붙은 강의는 캘린더에서 영영 안 보인다. 조용히 넘기지 않는다.
        print(f"  ⚠ 시간표에 못 붙은 강의 {report.unlinked}편 — /admin의 매칭 표에서 손으로 잇는다")
    for line in report.failures:
        print(f"  ✗ {line}")
    return 1 if report.failures else 0


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
        return report_watch(args)
    if args.command == "done":
        return run_done(args)
    if args.command == "jokbo":
        return run_jokbo(args)
    if args.command == "preview":
        return run_preview(args)
    if args.command == "prequeue":
        return report_prequeue(args)
    if args.command == "agent":
        return run_agent(args)
    if args.command == "import":
        return run_import(args)
    if args.command == "release":
        return run_release(args)
    if args.command == "rebuild":
        return run_rebuild(args)
    if args.command == "publish":
        if not args.subject and not args.all and not args.run_id:
            parser.error("과목명을 주거나 --all 또는 --run-id를 쓰세요")
        return report_publish(args)

    root = Path(args.root)
    if args.all:
        subjects = subjects_with_notes(root, args.this)
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
