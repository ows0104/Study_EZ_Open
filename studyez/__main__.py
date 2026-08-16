"""Study_EZ 로컬 러너 CLI.

    python -m studyez match 병리학          작년 짝 붙이기 리포트
    python -m studyez match --all
    python -m studyez watch                 새 필기 스캔 (큐만 세움)
    python -m studyez watch --prep          스캔 + prep까지 (21:30 자동 실행용)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from studyez import filenames, jokbo, matching, preview, watch  # noqa: E402

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


def report_watch(args) -> int:
    root = Path(args.root)
    runs_dir = Path(args.runs)
    subjects = [args.subject] if args.subject else subjects_with_notes(root, args.this)

    queue = watch.build_queue(
        root=root, subjects=subjects, this_year=args.this,
        runs_dir=runs_dir, max_items=args.max,
        min_age_seconds=0 if args.now else watch.MIN_AGE_SECONDS,
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
        print("  빌드가 끝나면 studyez.watch.stamp_sources()로 표시해야 다음 스캔에서 빠진다.")
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


def run_done(args) -> int:
    """빌드를 확인한 뒤 부른다. 이 표시가 있어야 다음 스캔에서 빠진다."""
    runs_dir = Path(args.runs)
    run_id = args.subject
    queue_path = runs_dir / "queue.json"
    if not run_id or not queue_path.exists():
        print("run_id와 runs/queue.json이 필요합니다")
        return 2
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    entry = next((i for i in raw["items"] if i["run_id"] == run_id), None)
    if entry is None:
        print(f"[done] 큐에 {run_id}가 없다")
        return 1
    queue = watch.Queue(raw["generated_at"], [watch.WorkItem(**entry)], [], [])
    watch.stamp_sources(queue, runs_dir)
    print(f"[done] {run_id} 표시함 — 다음 스캔에서 빠진다")
    return 0


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Study_EZ 로컬 러너")
    parser.add_argument("command", choices=["match", "watch", "done", "jokbo", "preview"])
    parser.add_argument("subject", nargs="?", help="과목 폴더명. --all이면 생략")
    parser.add_argument("--all", action="store_true", help="필기/올해 폴더가 있는 과목 전부")
    parser.add_argument("--this", default="2026", help="올해 폴더명")
    parser.add_argument("--prev", default="2025", help="작년 폴더명")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="자료 최상위 폴더")
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"), help="산출물 루트")
    parser.add_argument("--prep", action="store_true", help="watch: prep까지 실행")
    parser.add_argument("--workers", type=int, default=0,
                        help="watch: 동시에 돌릴 prep 수 (기본: CPU-1)")
    parser.add_argument("--max", type=int, default=watch.DEFAULT_MAX_ITEMS,
                        help="watch: 하루 처리 상한")
    parser.add_argument("--now", action="store_true",
                        help="watch: 방금 올라온 파일도 포함 (동기화 대기 생략)")
    parser.add_argument("--url", default=None,
                        help="preview: 공유된 예습 대화 주소")
    parser.add_argument("--body-start", type=int, default=4,
                        help="jokbo: 목차 다음, 본문이 시작하는 쪽 (기본 4)")
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
