"""Study_EZ 로컬 러너 CLI.

    python -m studyez match 병리학          작년 짝 붙이기 리포트
    python -m studyez match --all
    python -m studyez watch                 새 필기 스캔 (큐만 세움)
    python -m studyez watch --prep          스캔 + prep까지 (21:30 자동 실행용)
    python -m studyez watch --all-dates     블럭으로 안 좁힌다 (밀린 것 몰아 만들 때)
    python -m studyez prequeue              관리자가 저장한 예습 링크 → Pre-Quiz 자리
    python -m studyez prequeue --dry-run    무엇이 준비될지만 본다
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
import sys
import time
from datetime import date as Date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from studyez import (  # noqa: E402
    blocks, filenames, jokbo, matching, prequeue, preview, publish, watch,
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


def report_watch(args) -> int:
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
            if item.jokbo_pdf:
                print(f"        족보 ← 원본 {item.jokbo_label} (유사도 {item.jokbo_score})")
            for note in item.notes:
                print(f"        ⚠ {note}")

    for line in queue.skipped:
        print(f"  · 건너뜀 — {line}")

    if args.prep and queue.items:
        planned = len(queue.items)
        workers = args.workers or min(planned, max(1, (os.cpu_count() or 4) - 1))
        started = time.monotonic()
        print(f"\n  prep 실행 {planned}편 · 동시 {workers}개…")
        queue = watch.prepare(queue, runs_dir, REPO_ROOT, workers=workers)
        failed = planned - len(queue.items)
        elapsed = time.monotonic() - started
        print(f"  prep 완료 {len(queue.items)}편"
              + (f" · 실패 {failed}편" if failed else "")
              + f" · {elapsed / 60:.1f}분")
        for line in queue.skipped:
            if "prep 실패" in line:
                print(f"    ✗ {line}")

    queue_path = runs_dir / "queue.json"
    watch.save(queue, queue_path)
    print(f"\n  큐: {queue_path}")
    if queue.items:
        print("  이제 세션이 각 편마다 /quiz 를 돌린다 — 0.5단계부터 5단계까지.")
        print("  빌드가 끝나면 `python -m studyez done <run_id>` — 표시하고 그 편을 올린다.")
    return 0


def run_preview(args) -> int:
    """공유된 예습 대화를 내려받아 runs/<run_id>/preview.md로 만든다."""
    run_id = args.subject
    if not run_id or not args.url:
        print("쓰는 법: python -m studyez preview <run_id> --url https://chatgpt.com/share/...")
        return 2

    run_dir = Path(args.runs) / run_id
    if not (run_dir / "prep.json").exists():
        print(f"[preview] {run_dir}에 prep.json이 없다. 0단계를 먼저 돌려라.")
        return 2

    result = preview.fetch(args.url)
    path = preview.save(result, run_dir)
    print(f"[preview] {run_id} ← {args.url}")
    print(f"  발화 {len(result.turns)}개 · {result.chars:,}자 · 추출 {result.strategy}")
    print(f"  → {path}")
    print("  이제 /prequiz를 돌리면 1·2단계가 이걸 함께 읽는다")
    return 0


def run_source_pdf(runs_dir: Path, run_id: str) -> Path | None:
    """이 run이 실제로 무엇으로 만들어졌는지. `prep.json`이 답을 들고 있다.

    큐가 아니라 여기를 보는 이유는 **큐가 그 사이 다시 서기 때문**이다.
    그리고 이쪽이 더 참이다 — 큐는 지금 무엇을 만들 차례인지를 적고,
    `prep.json`은 이 run이 무엇으로 만들어졌는지를 적는다.
    """
    prep = runs_dir / run_id / "prep.json"
    if not prep.is_file():
        return None
    try:
        source = str(json.loads(prep.read_text(encoding="utf-8")).get("source_pdf", ""))
    except (OSError, ValueError):
        return None
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

    if args.no_publish:
        return 0

    # `subject` 위치 인자에 run_id가 들어와 있다. 업로드는 과목으로 도는 코드라
    # 자리를 제자리로 돌려놓고 넘긴다 — 못 알아냈으면 전 과목에서 찾게 둔다.
    args.run_id = run_id
    args.subject = subject
    print()
    return report_publish(args)


def run_jokbo(args) -> int:
    """과목 족보 PDF를 강의별로 자른다. 학기당 과목당 한 번이면 된다."""
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
        for p in pdfs:
            print(f"    {p.name} ({p.stat().st_size / 1024 / 1024:.1f}MB)")
        pdfs.sort(key=lambda p: p.stat().st_size, reverse=True)

    out_dir = Path(args.runs) / "_jokbo" / subject / args.this
    index = jokbo.split(pdfs[0], out_dir, body_start=args.body_start)

    sections = index["sections"]
    print(f"[jokbo] {pdfs[0].name} → {len(sections)}개 구간")
    for section in sections:
        pages = section["end_page"] - section["start_page"] + 1
        years = ",".join(str(y) for y in section["years"][:6]) or "-"
        print(f"  {section['block']:<3} {section['label']:<8} "
              f"p{section['start_page']:>3}-{section['end_page']:<3} ({pages:>2}쪽)  "
              f"{years:<26} {section['title'][:34]}")

    covered = sorted({int(n) for n in index["by_lecture"]})
    if covered:
        gaps = [n for n in range(covered[0], covered[-1] + 1) if n not in covered]
        print(f"\n  강의 {covered[0]}~{covered[-1]} 덮음"
              + (f" · 빈 번호 {gaps}" if gaps else " · 빠짐없음"))
    rows = index["professor_reference"]["rows"]
    print(f"  교수 매트릭스 {len(rows)}행 — 참고용. 담당이 바뀌면 틀리므로 단독 근거로 쓰지 마라")

    notes = filenames.scan(notes_dir(Path(args.root), subject, args.this),
                           expect_year=args.this)
    lectures = filenames.latest_versions(notes.files)
    if lectures:
        links = jokbo.link_lectures(index, lectures)
        ok = sum(1 for link in links if link["confident"])
        print(f"\n  올해 필기 {len(lectures)}편 ↔ 족보 연결 (확정 {ok})")
        for link in links:
            mark = "확정" if link["confident"] else ("확인" if link["jokbo_label"] else "없음")
            print(f"    {link['key']:<10} {mark:<4} {link['score']:>4}  "
                  f"{link['title'][:30]:<30} → {link['jokbo_label'] or '-'} "
                  f"{link['jokbo_title'] or ''}")
        (out_dir / "links.json").write_text(
            json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  → {out_dir}")
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


def report_prequeue(args) -> int:
    """관리자가 저장한 예습 링크를 받아 Pre-Quiz를 만들 자리까지 세운다.

    문항은 여기서 안 만든다. 만드는 것은 `/prequiz`이고 그건 모델이 하는
    일이다 — 여기서 하는 것은 그 앞의 결정적인 부분(짝 고르기·prep·대화
    내려받기)이고, 무엇이 남았는지를 `runs/prequeue.json`에 적어 넘긴다.
    """
    root, runs_dir = Path(args.root), Path(args.runs)
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")

    token = runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 "
              "STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
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
        print("\n  --dry-run — prep도 대화 내려받기도 하지 않았다\n")
        for target in targets:
            link = target.link
            if target.state == prequeue.BLOCKED:
                print(f"  {link.date} ✋ {link.run_id:<12} {link.title[:30]:<30}")
                print(f"      {target.reason}")
            else:
                print(f"  {link.date}    {link.run_id:<12} {link.title[:30]:<30} "
                      f"→ 작년 {target.prev_run_id}")
        return 0

    planned = [t for t in targets if t.state != prequeue.BLOCKED]
    if planned:
        started = time.monotonic()
        print(f"\n  자리 세우는 중 {len(planned)}편 (prep + 예습 대화)…")
        targets = prequeue.prepare(targets, runs_dir, REPO_ROOT, workers=args.workers)
        print(f"  {(time.monotonic() - started) / 60:.1f}분")

    print()
    ready: list[prequeue.Target] = []
    for target in targets:
        link = target.link
        mark = {prequeue.READY: "▶", prequeue.DONE: "✓",
                prequeue.STALE: "↻", prequeue.BLOCKED: "✋"}[target.state]
        print(f"  {link.date} {mark} {link.run_id:<12} {link.title[:30]:<30} "
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

    queue_path = runs_dir / prequeue.QUEUE_NAME
    prequeue.save(targets, queue_path)
    print(f"  큐: {queue_path}")
    if ready:
        print("\n  이제 세션이 각 편마다 /prequiz 를 돌린다 — 작년 run에서 만든다:")
        for target in ready:
            print(f"    /prequiz {target.prev_pdf}")
        print("  빌드가 끝나면 `python -m studyez done <작년 run_id>` — 덱·문항·링크가 함께 올라간다.")
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


def report_publish(args) -> int:
    """산출물을 서버로. 무엇이 올라갈지 먼저 다 적고 나서 민다."""
    root, runs_dir = Path(args.root), Path(args.runs)
    subjects = [args.subject] if args.subject else subjects_with_notes(root, args.this)
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")

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

    held = [p for p in plans if p.blocking]
    print(f"[publish] {api}")
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
    parser.add_argument("command", choices=["match", "watch", "done", "jokbo", "preview",
                                            "prequeue", "publish"])
    parser.add_argument("subject", nargs="?", help="과목 폴더명. --all이면 생략")
    parser.add_argument("--all", action="store_true", help="필기/올해 폴더가 있는 과목 전부")
    parser.add_argument("--this", default="2026", help="올해 폴더명")
    parser.add_argument("--prev", default="2025", help="작년 폴더명")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="자료 최상위 폴더")
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"), help="산출물 루트")
    parser.add_argument("--prep", action="store_true", help="watch: prep까지 실행")
    parser.add_argument("--workers", type=int, default=0,
                        help="watch·prequeue: 동시에 돌릴 prep 수 (기본: CPU-1)")
    parser.add_argument("--max", type=int, default=watch.DEFAULT_MAX_ITEMS,
                        help="watch: 하루 처리 상한")
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
    parser.add_argument("--body-start", type=int, default=4,
                        help="jokbo: 목차 다음, 본문이 시작하는 쪽 (기본 4)")
    parser.add_argument("--api", default=None,
                        help=f"publish: API 주소 (기본 {publish.DEFAULT_API_BASE})")
    parser.add_argument("--token", default=None,
                        help="publish: 러너 토큰 (기본 server/.env의 RUNNER_TOKEN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="publish: 무엇이 올라갈지만 적고 올리지 않는다. "
                             "prequeue: 어느 자리에 설지만 적고 prep·내려받기를 안 한다")
    parser.add_argument("--force", action="store_true",
                        help="publish: 이미 올린 표시를 무시하고 다시 올린다")
    parser.add_argument("--notes-only", action="store_true",
                        help="publish: 강의록만 올리고 덱·run-meta·예습 링크는 미룬다")
    parser.add_argument("--no-gate", action="store_true",
                        help="publish: 검문을 끄고 막힌 편도 민다 (사람이 보고 판단했을 때)")
    parser.add_argument("--run-id", default=None,
                        help="publish: 이 run을 쓰는 강의 한 편만 민다 (작년 run이면 그 짝). "
                             "prequeue: 이 강의의 예습 링크 하나만 (올해 run_id)")
    parser.add_argument("--no-ahead", action="store_true",
                        help="publish·prequeue: 아직 필기가 없는 강의는 세우지 않는다 "
                             "(예습용 작년 강의록도 안 붙는다)")
    parser.add_argument("--no-publish", action="store_true",
                        help="done: 표시만 하고 올리지 않는다")
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
