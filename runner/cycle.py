"""야간 러너 한 사이클. `__main__` 이 얹는 CLI 껍데기와 갈라 둔다.

`runner` 의 서브커맨드는 성격이 둘로 갈린다 — **스케줄러가 돌리는 것**과
**사람이 한 번씩 치는 것**이다. 이 모듈은 앞쪽이다.

    watch     새 필기를 스캔해 덱을 만든다            (21:30)
    prequeue  예습 링크를 받아 자리를 세운다          (04:00)
    publish   끝난 편을 서버로 민다                   (야간 쓸어담기)
    done      한 편의 빌드가 끝났음을 표시하고 올린다
    agent     러너 자신을 띄운다

이 다섯이 서로를 부른다 — `done` 이 `report_publish` 를 부르고 `report_watch` 가
`run_watch_one` 을 돌리는 식이다. **묶여 있어서 한 덩어리다**(호출 그래프에서
연결 성분 하나였다). 반대로 `import`·`rebuild`·`jokbo`·`match`·`preview`·
`release` 는 이쪽을 한 번도 부르지 않아 `__main__` 에 남겼다.

이 모듈은 `__main__` 을 부르지 않는다. 화살표는 한 방향이다.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date as Date
from datetime import timedelta
from pathlib import Path

from runner import agent, blocks, deck, filenames, prequeue, publish, site_edits, watch

REPO_ROOT = Path(__file__).resolve().parent.parent


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
              "  `python -m app.cli seed-timetable`으로 넣거나 "
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

    # **자를 수 있는 족보를 안 자른 채로는 안 만든다.**
    #
    # 여기서 막는 이유는 뒤에서 막혀 봤기 때문이다. 2026-09-12 에 `260911_03` 이
    # 22.9분·$8.53 을 다 쓰고 `build.py` 의 마지막 검사에서 죽었다 — 모델이 강의록
    # 뒤의 족보 부록에서 기출 카드 3장을 뽑았는데 물릴 조각이 없었다. 같은 날 같은
    # 과목의 다른 세 편은 기출 카드를 안 뽑아서 살았다. **모델이 무엇을 뽑느냐로
    # 생사가 갈리는 자리였다.**
    #
    # 그 세 편도 무사한 것은 아니다. 미생물학 족보는 반복률이 32~74%인데 기출 0
    # 으로 나갔고, 다시 구우면 편당 ~30분·$12 이다. 자르는 것은 몇 분이고 LLM 을
    # 안 쓴다.
    #
    # **원본이 없는 과목은 막지 않는다**(`JOKBO_ABSENT`). 사람이 어찌할 수 없는
    # 것을 막으면 그 과목은 영영 안 만들어진다. `--no-jokbo` 로도 넘어간다.
    jokbo = watch.jokbo_state(runs_dir, item.subject, root, args.this)
    if jokbo == watch.JOKBO_UNCUT and not getattr(args, "no_jokbo", False):
        print(f"[watch] {args.run_id} — 과목 족보를 먼저 자른다.\n"
              f"  `python -m runner jokbo {item.subject}`  (몇 분 · LLM 안 씀)\n"
              "  그 뒤에 이 명령을 다시 부르면 조각이 스스로 물린다.\n"
              "  족보 없이 만들려면 --no-jokbo.")
        return 1

    # **덱이 있어도 원본이 갈렸으면 만든다.** 예전에는 여기서 무조건 멈추고 `--force` 를
    # 안내했는데, 그러면 새 판이 온 편은 사람이 손으로 부르기 전에는 안 고쳐졌다.
    # 갈렸는지는 `fingerprint` 가 판정한다(`item.reason`).
    made = deck.apkg_of(run_dir, deck.MAIN)
    changed = item.reason in watch.UPDATED or bool(getattr(args, "slides", ""))
    if made and not args.force and not changed:
        print(f"[watch] {args.run_id} — 이미 덱이 있다: {made.name}\n"
              f"  안 올라간 것뿐이면 `python -m runner publish --run-id {args.run_id}`가 민다.\n"
              "  덱 자체를 다시 만들려면 --force. 어느 슬라이드가 고쳐졌는지 알면 "
              "`--slides 37` 로 그 자리만 갈아 끼운다.")
        return 0
    if made and changed:
        why = ("사람이 슬라이드를 지목했다" if getattr(args, "slides", "")
               else "원본이 갈렸다")
        print(f"[watch] {args.run_id} — 덱은 있는데 {why}. "
              "갈린 슬라이드의 카드만 갈아 끼운다 (통째로는 --force).")

    if not args.build:
        print(f"[watch] {item.subject}/{item.run_id} {item.title[:38]}\n"
              f"  {Path(item.this_pdf).name}\n"
              "  `--build`를 붙이면 이대로 만든다.")
        return 0

    print(f"[watch] {item.subject}/{item.run_id} {item.title[:38]} — 만드는 중")
    started = time.monotonic()
    # **`--force`는 quizgen까지 내려가야 한다.** 여기서 「덱이 있어도 만든다」까지만
    # 하고 넘기면 quizgen가 이미 만든 단계를 건너뛰고 그 산출물로 덱만 다시 굽는다 —
    # 다시 만들라고 누른 사람은 「다시 만들었는데 그대로다」를 본다(`prequeue`도 같다).
    extra = (["--force"] if args.force else [])
    if args.strategy != "auto":
        extra += ["--strategy", args.strategy]
    if getattr(args, "slides", ""):
        # 사람이 「37p 를 고쳤다」고 알려준 것. 갈아 끼우기가 그 슬라이드를 무조건 다시 쓴다.
        # 판이 안 갈렸다고 판정된 편에도 붙여 준다 — 코드가 못 보는 갈림이 그것이다.
        extra += ["--slides", args.slides]
        if "--force" not in extra and "--revise" not in extra:
            extra.append("--revise")
    ok, note = watch.build_one(item, runs_dir, REPO_ROOT, model=args.model, timeout=args.timeout,
                               extra=extra or None)
    minutes = (time.monotonic() - started) / 60
    if not ok:
        print(f"    실패 — {note} · {minutes:.1f}분")
        return 1
    print(f"    끝났다 — {note} · {minutes:.1f}분")
    print(f"  `python -m runner publish --run-id {item.run_id}` — 검문을 지나면 나간다.")
    return 0


def report_watch(args) -> int:
    if args.run_id:
        return run_watch_one(args)
    if args.strategy != "auto":
        print("[watch] --strategy는 --run-id로 한 강의를 지정할 때만 쓸 수 있다. "
              "사진 중심을 전체 강의에 실수로 적용하지 않게 막았다.")
        return 2
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
            # **「갱신」은 한동안 화면에만 있었다.** `reason` 을 읽는 곳이 여기 하나뿐이고
            # `watch.build` 는 `extra` 를 안 받아서 깃발이 갈 길이 없었다. 그러면
            # `quizgen.run` 이 산출물이 있는 단계를 전부 건너뛰어(`runbase.step`)
            # **아무것도 안 만들고 `source.json` 에만 새 판이 찍힌다.** 그 편은
            # 쓸기에는 「이미 만듦」, 문지기에는 「옛 판이라 못 내보낸다」가 되어 갇혔다
            # (2026-09-03 에 세 편이 그랬다).
            #
            # 2026-09-04 에 둘 다 고쳤다 — 판정은 `cycle.fingerprint` 한 곳에서
            # 나오고(쓸기·문지기가 같은 값을 본다), 갱신된 편에는 `watch.build_extra`
            # 가 `--revise` 를 실어 보낸다(갈린 슬라이드의 카드만 갈아 끼운다).
            mark = ("새로" if item.reason == "new"
                    else "내용 갈림" if item.reason == "content_changed"
                    else f"v{item.this_version} 갱신")
            print(f"    {item.date}  {item.subject}/{item.run_id}  [{mark}]  {item.title[:38]}")
            for note in item.notes:
                print(f"        ⚠ {note}")

    for line in queue.skipped:
        print(f"  · 건너뜀 — {line}")

    # **밀린 것을 센다.** 한 줄씩은 위에 이미 적혀 있는데, 그 줄들이 다른 사유와
    # 섞여 있어서 「줄고 있는가」가 안 보였다. 2026-09-12 에 기생충학 7편이 상한
    # 뒤에 줄 서 있었고 제일 오래된 것이 12일째였다 — 상한(2)보다 하루 들어오는
    # 양이 많으면 큐는 원리상 안 줄어든다. 그 사실이 로그 어디에도 없었다.
    if queue.backlog:
        oldest = queue.backlog[0]
        print(f"\n  ✋ 밀린 것 {len(queue.backlog)}편 — 가장 오래된 것은 "
              f"{oldest.date} {oldest.subject}/{oldest.run_id}."
              f" 하루 상한은 {args.max}편이다 (--max 로 올린다)")

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
        print("  `python -m runner watch --build` — 이대로 덱까지 만든다.")
    elif queue.items:
        print("  `python -m runner publish --all` — 검문을 지난 편이 나간다.")
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

    예전에는 여기서 세션 트랜스크립트를 뒤져 토큰을 셈했다. 지금은 quizgen가
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
    것이다. `publish`는 멱등이고(ledger + 서버 HEAD) 편마다 `cycle.gate`가
    보므로, 여기서 불러도 검문에 걸린 편은 강의록만 나간다. 올리기 싫으면
    `--no-publish`.
    """
    runs_dir = Path(args.runs)
    run_id = args.subject
    if not run_id:
        print("쓰는 법: python -m runner done 260814_05")
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
    `--build`면 이어서 `quizgen.prequiz`가 덱을 만든다.
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
    # 판정은 편마다 자기 자리에도 적는다. 큐 파일은 한 파일이라 다음 실행이
    # 지우고, 그것을 되읽던 러너가 「덱을 못 만들었다」를 잘못 적었다.
    for target in targets:
        prequeue.save_state(target, runs_dir)
    print(f"  큐: {queue_path}")
    if ready and not args.build:
        print("\n  `python -m runner prequeue --build` — 이대로 예습 덱까지 만든다:")
        for target in ready:
            print(f"    {target.prev_run_id}  {Path(target.prev_pdf).name[:52]}")
    elif args.build:
        print("  `python -m runner publish --all` — 덱·문항·링크가 함께 올라간다.")
    return 0


def explain_missing_run(runs_dir: Path, run_id: str, prev_year: str) -> int:
    """`--run-id`가 붙을 강의를 못 찾았을 때. 무엇이 일어난 것인지 가려서 적는다.

    **작년 run이면 대개 정상이다.** Pre-Quiz를 진도보다 앞서 만들어 두면 올해
    필기가 아직 없어 붙일 자리가 없다. 산출물은 그대로 남고, 올해 필기가 올라온
    뒤 야간 `publish --all`이 그때 같이 민다. 그래서 이 경우만 0으로 끝낸다.
    """
    # **`prep.json` 을 직접 읽지 않는다.** 한동안 여기서 `source_pdf` 키를 찾았는데
    # `374071a`(pdf2anki 이관 — 지금의 `quizgen/`)에서 `prep.py` 가 `source` 로 이름을 바꿨다. 그래서 이
    # 함수가 원본을 영영 못 읽었고, 아래 「작년 run 이라 정상」 분기가 통째로 죽어
    # 있었다 — 작년 run 인데도 「필기가 지워졌다」고 찍고 1 로 끝냈다.
    # `run_source_pdf` 가 `run.config.json` 까지 보고 두 키를 다 안다.
    source = run_source_pdf(runs_dir, run_id)
    parsed = filenames.parse(source) if source else None

    if parsed is not None and parsed.date[:4] == prev_year:
        print(f"[publish] {run_id}은 {prev_year} 필기로 돈 run이다 — {parsed.title[:40]}\n"
              "  올해 그 강의가 아직 안 올라와 붙일 자리가 없다. **올리지 않았다.**\n"
              "  산출물은 그대로 두면 된다 — 올해 필기가 올라오면 야간 publish가 같이 민다.")
        return 0

    print(f"[publish] {run_id} — 이 run을 쓰는 강의를 못 찾았다. **올리지 않았다.**\n"
          "  올해 필기가 지워졌거나 파일명이 바뀌었을 수 있다.\n"
          "  Pre-Quiz라면 작년 짝이 확정이 아니어서 안 붙은 것일 수도 있다 —\n"
          "  `python -m runner match <과목>`으로 확인하라")
    return 1


def run_agent(args) -> int:
    """서버의 일감을 집어 와 만들고 올린다. **야간 스케줄러 자리에 선 것이다.**

    왜 크론을 걷어냈는지는 `runner/agent.py` 첫머리에 있다. 요약하면 크론은
    닷새 동안 아무것도 안 올리면서 종료 코드 0을 냈고, 아무도 몰랐다.
    """
    api = (args.api or os.getenv("STUDYEZ_API_BASE_URL") or publish.DEFAULT_API_BASE).rstrip("/")
    token = runner_token(args.token)
    if not token:
        print("러너 토큰이 없다. server/.env의 RUNNER_TOKEN이나 "
              "STUDYEZ_RUNNER_TOKEN 환경 변수, 또는 --token으로 준다")
        return 2

    runner = agent.Agent(
        publish.Client(api, token), Path(args.runs), REPO_ROOT,
        subject=args.subject or "",
        sweep_seconds=0 if args.no_sweep else args.sweep_minutes * 60,
        timeout=args.timeout, workers=args.workers)
    if args.once:
        # 붙는지 보는 용도. 일감이 없으면 쓸기도 한 번 돌려 준다 — 쓸기가 이제
        # 따로 도는 실이라(`agent.sweep_loop`) `tick`이 안 부른다.
        if not runner.tick() and runner.sweep_seconds:
            runner.sweep()
        return 0
    return runner.loop(poll=args.poll)


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


def sync_site_edits(args, subjects: list[str], runs_dir: Path, api: str) -> None:
    """사이트 「카드 검토」의 판정을 당겨 덱을 다시 굽는다(`runner/site_edits.py`).

    실패해도 올리기는 계속 간다 — 그 편은 옛 덱으로 나가고, 웹 풀이는 서버가 이미
    고쳐 두었다. `--run-id` 로 한 편만 밀 때도 과목 전체를 본다: 판정 몇 건에 편당
    몇 초라 좁힐 값이 없다.
    """
    token = runner_token(args.token)
    if not token:
        return
    try:
        lines = site_edits.sync(publish.Client(api, token), runs_dir,
                                subjects=tuple(subjects), dry_run=args.dry_run)
    except publish.PublishError as cause:
        print(f"  ⚠ 사이트 판정을 못 읽었다 — {cause}. 덱은 판정 없이 나간다")
        return
    for index, line in enumerate(lines):
        print(f"  {'' if index == 0 else '  '}{line}")


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
    # 사이트에서 고친 카드를 덱에 얹는다(2026-09-23). **계획보다 먼저다** — 계획이
    # 덱 파일의 크기·시각을 읽으므로, 뒤에 구우면 이번 실행은 옛 덱을 민다.
    sync_site_edits(args, subjects, runs_dir, api)

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
