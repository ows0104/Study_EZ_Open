"""Study_EZ 로컬 러너 CLI.

    python -m runner match 병리학          작년 짝 붙이기 리포트
    python -m runner match --all
    python -m runner watch                 새 필기 스캔 (무엇을 만들지 보여준다)
    python -m runner watch --build         스캔 + 덱까지 (21:30 자동 실행용)
    python -m runner watch --all-dates     블럭으로 안 좁힌다 (밀린 것 몰아 만들 때)
    python -m runner watch <과목> --run-id <올해> --build
                                            그 강의 하나만 만든다 (캘린더 버튼이 이리로 온다)
    python -m runner prequeue              예습 링크 → 자리 세우기
    python -m runner prequeue --build      자리 세우고 예습 덱까지 (04:00 자동 실행용)
    python -m runner prequeue --dry-run    무엇이 준비될지만 본다
    python -m runner prequeue <과목> --run-id <올해> --build --force
                                            이미 만든 편도 버리고 다시 만든다
    python -m runner jokbo 병리학           과목 족보를 강의별로 자른다 (학기당 1회)
    python -m runner import --from <폴더>   다른 곳에서 만든 덱을 옮긴다 (보류로 들어온다)
    python -m runner release <run_id>       보류를 푼다
    python -m runner chosen                 어느 편에 고른 기록이 있나
    python -m runner chosen <run_id>         그 편의 시도와 고른 기록을 본다
    python -m runner chosen <run_id> --keep --why "..."
                                            지금 이 자리 것을 쓴다고 적는다
    python -m runner chosen <run_id> --pick out/redo_<id> --why "..."
                                            다른 시도를 골랐다고 적는다 (문지기가 막는다)
    python -m runner promote <run_id>        고른 시도를 강의 폴더로 올린다
    python -m runner promote <run_id> --version 260827-2300   판을 지목해서
    python -m runner rebuild                이미 만든 카드로 덱만 다시 굽는다
    python -m runner done <run_id>          빌드 끝. 표시하고 그 편을 올린다
    python -m runner publish 병리학 --dry-run   무엇이 올라갈지 본다
    python -m runner publish 병리학             서버로 밀어 넣는다
    python -m runner publish --run-id <run_id>  그 run을 쓰는 한 편만 올린다
    python -m runner publish --all              전부 훑는다 (야간 쓸어담기)

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

from runner import (  # noqa: E402
    agent,
    attempts,
    blocks,
    chosen,
    cycle,
    deck,
    filenames,
    gate,
    matching,
    preview,
    publish,
    rebuild,
    runlayout,
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
        print("쓰는 법: python -m runner preview <run_id> --url https://chatgpt.com/share/...")
        return 2

    # 자리가 비어 있어도 받는다. 대화가 먼저 오고 덱이 나중에 오는 순서라,
    # 여기서 prep을 요구하면 예습이 정작 필요한 편에서 막힌다.
    run_dir = Path(args.runs) / run_id
    result = preview.fetch(args.url)
    path = preview.save(result, run_dir)
    print(f"[preview] {run_id} ← {args.url}")
    print(f"  발화 {len(result.turns)}개 · {result.chars:,}자 · 추출 {result.strategy}")
    print(f"  → {path}")
    print("  이제 `python -m runner prequeue --build`가 이걸 예습 설명본으로 읽는다")
    return 0


def practical_pdfs(spec: str | None) -> list[Path]:
    """`--practical` 로 받은 폴더나 파일을 PDF 목록으로 편다.

    **실습 족보는 과목 족보와 다른 자리에 산다.** 과목 족보는 해마다 한 권이라
    `족보/<올해>/` 에서 집으면 되지만, 실습 족보는 회차가 여러 해에 걸쳐
    누적본 여러 권으로 흩어져 있고(2026-09-07 실측 — 2025 회차는 올해 족보 안,
    2023~2015 회차는 별도 누적본 한 권) 어느 것이 정본인지 코드가 모른다.
    그래서 사람이 지목한다.
    """
    if not spec:
        return []
    p = Path(spec)
    if p.is_dir():
        return sorted(p.glob("*.pdf"))
    return [p] if p.is_file() else []


def remembered_practical(index: Path) -> tuple[list[Path], list[str]]:
    """지난번에 쓴 실습 족보를 되살린다. (아직 있는 것, 없어진 것의 이름)

    **안 되살리면 다음 절단이 조용히 되돌아간다.** 실습 조각은 `--practical` 을
    줬을 때만 서고, 안 주면 과목 족보 안의 실습 구역(한 회차)만 남는다. 그러면
    문항이 277개에서 40개로 줄어드는데 화면에는 아무 말도 안 뜬다 — 그리고 그
    차이는 다음에 굽는 실습 편의 기출 카드에서야 드러난다.
    """
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    found, lost = [], []
    for src in data.get("practical_sources") or []:
        path = Path(src.get("path", ""))
        (found if path.is_file() else lost).append(path if path.is_file() else src.get("name", "?"))
    return found, lost


def run_jokbo(args) -> int:
    """과목 족보 PDF를 강의별 조각으로 자른다. 학기당 과목당 한 번이면 된다.

    자르는 것은 `quizgen.jokbo`다. 여기서 하는 것은 **어느 PDF를 줄지 고르는
    것**뿐 — 과목 폴더에서 원본을 찾아 `deck.cut_jokbo`에 넘긴다.

    강의와 조각을 짝지어 `links.json`을 쓰던 자리가 여기 있었는데 없앴다.
    지금은 어느 조각을 물릴지 quizgen가 카드를 만들 때 목차 제목으로 대조한다.
    두 곳에서 각각 짝지으면 **카드가 본 조각과 뒷면에 붙는 조각이 갈릴 수 있다.**
    """
    subject = args.subject
    if not subject:
        print("과목명을 주세요: python -m runner jokbo 병리학")
        return 2

    # 경로는 `watch` 가 들고 있다 — 「잘렸는가」를 묻는 쪽과 자르는 쪽이 같은 곳을
    # 봐야 한다(`watch.jokbo_state` 가 이 폴더를 보고 UNCUT 을 가른다).
    folder = watch.jokbo_source_dir(Path(args.root), subject, args.this)
    pdfs = sorted(folder.glob("*.pdf")) if folder.is_dir() else []
    if not pdfs:
        print(f"[jokbo] {folder} 에 PDF가 없습니다")
        return 1
    if len(pdfs) > 1:
        print(f"[jokbo] PDF가 {len(pdfs)}개입니다. 가장 큰 것을 씁니다:")
        for candidate in pdfs:
            print(f"    {candidate.name} ({candidate.stat().st_size / 1024 / 1024:.1f}MB)")
        pdfs.sort(key=lambda candidate: candidate.stat().st_size, reverse=True)

    practical = practical_pdfs(args.practical)
    if args.practical and not practical:
        print(f"[jokbo] --practical {args.practical} 에 PDF가 없습니다")
        return 1

    # **자르는 쪽에는 과목 폴더를 준다.** 판 폴더는 `quizgen.jokbo` 가 그 아래에
    # 만든다 — 과목 이름을 폴더 이름에서 읽기 때문에 판을 직접 주면 실습 조각이
    # 「260915-0130 실습」이라는 이름으로 나온다(`deck.jokbo_dir` 주석).
    out_dir = deck.subject_dir(Path(args.runs), subject)
    if not practical:
        # 지난번 실습 족보는 **지금 판**의 색인에 적혀 있다.
        practical, lost = remembered_practical(
            deck.jokbo_dir(Path(args.runs), subject) / "index.json")
        for p in practical:
            print(f"[jokbo] 지난번에 쓴 실습 족보를 그대로 씁니다: {p.name}")
        for name in lost:
            print(f"[jokbo] ⚠ 지난번 실습 족보 {name} 이 그 자리에 없습니다")
        if lost:
            print("        이대로 자르면 그 회차 문항이 빠집니다. --practical 로 새 자리를 주세요.")
    print(f"[jokbo] {pdfs[0].name} → {out_dir}")
    for p in practical:
        print(f"        실습 족보: {p.name}")
    # 자르는 쪽은 자기 출력을 화면으로 바로 흘린다(`cut_jokbo`). 여기 것을 안 밀어내면
    # 어느 PDF를 골랐는지가 그 뒤에 찍혀 순서가 뒤집힌다.
    sys.stdout.flush()
    code = deck.cut_jokbo(pdfs[0], out_dir, REPO_ROOT, practical=practical)
    if code != 0:
        print(f"  자르지 못했다 (코드 {code})")
        return 1

    # 방금 만들어진 판을 찾는다. `cut_id` 는 자르는 쪽이 정하므로 여기서는 모른다.
    cut_dir = deck.jokbo_dir(Path(args.runs), subject)
    index = cut_dir / "index.json"
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

    # **판을 화면에 적는다.** 자른 쪽(`quizgen.cutmark`)이 `cut.json` 에 남긴 것이고,
    # 이 줄이 있어야 사람이 「방금 자른 것이 무엇인가」를 그 자리에서 본다.
    print(f"\n  → {index}")
    print(f"  {deck.cut_line(cut_dir)}")
    print("  이제 `python -m runner watch --build`가 이 조각을 스스로 물린다")
    return 0


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Study_EZ 로컬 러너")
    parser.add_argument("command", choices=["match", "watch", "done", "jokbo", "preview", "agent",
                                            "prequeue", "publish", "import", "release", "rebuild",
                                            "chosen", "promote"])
    parser.add_argument("subject", nargs="?", help="과목 폴더명. --all이면 생략")
    parser.add_argument("--all", action="store_true", help="필기/올해 폴더가 있는 과목 전부")
    parser.add_argument("--this", default="2026", help="올해 폴더명")
    parser.add_argument("--prev", default="2025", help="작년 폴더명")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="자료 최상위 폴더")
    parser.add_argument("--practical", default="",
                        help="jokbo: 실습 족보 PDF 또는 그 PDF들이 든 폴더. "
                             "주면 실습 조각(PRAC)을 이것으로만 만든다")
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
    parser.add_argument("--slides", default="",
                        help="watch --run-id: 새 판에서 고쳐졌다고 **사람이 알려준** 슬라이드 "
                             "(쉼표 구분). 코드가 못 보는 갈림(그림 픽셀만 바뀐 것)이 여기로 들어온다")
    parser.add_argument("--timeout", type=int, default=deck.DEFAULT_TIMEOUT,
                        help=f"watch·prequeue: 한 편의 제한 시간(초). 기본 {deck.DEFAULT_TIMEOUT}")
    parser.add_argument("--max", type=int, default=watch.DEFAULT_MAX_ITEMS,
                        help="watch·prequeue: 한 번에 만들 상한")
    parser.add_argument("--within-days", type=int, default=0,
                        help="prequeue: 강의가 오늘부터 이 날짜 안에 있는 것만 만든다")
    parser.add_argument("--now", action="store_true",
                        help="watch: 방금 올라온 파일도 포함 (동기화 대기 생략)")
    parser.add_argument("--no-jokbo", action="store_true",
                        help="watch --run-id: 과목 족보가 안 잘려 있어도 그냥 만든다. "
                             "기본은 멈추고 `runner jokbo <과목>`을 안내한다")
    parser.add_argument("--since", default=None,
                        help="watch: 이 날짜부터의 강의만 (YYYY-MM-DD). 주면 시간표를 안 본다")
    parser.add_argument("--until", default=None, help="watch: 이 날짜까지의 강의만")
    parser.add_argument("--all-dates", action="store_true",
                        help="watch: 블럭으로 좁히지 않는다. 지난 학기까지 전부 잡힌다")
    parser.add_argument("--today", default=None,
                        help="watch: 오늘을 이 날짜로 친다 (블럭 판정 확인용)")
    parser.add_argument("--timetable", default=None,
                        help=f"watch: 시간표 (기본 {blocks.DEFAULT_SOURCE})")
    parser.add_argument("--version", default="",
                        help="promote: 올릴 판 (예: 260827-2300). 생략하면 CHOSEN 이 고른 것")
    parser.add_argument("--keep", action="store_true",
                        help="chosen: 지금 runs/<편>/ 에 있는 시도를 쓴다고 적는다")
    parser.add_argument("--pick", default="",
                        help="chosen: 다른 시도를 골랐다고 적는다 (예: out/redo_260812_01)")
    parser.add_argument("--why", default="",
                        help="chosen: 왜 그것을 골랐는가. **없으면 안 적는다**")
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
    parser.add_argument("--workers", type=int, default=agent.WORKERS,
                        help=f"agent: 겹쳐 만들 편 수. 기본 {agent.WORKERS} "
                             "(서버도 같은 상한을 든다 — 둘 중 작은 쪽이 실제 상한이다)")
    parser.add_argument("--no-prequeue", action="store_true",
                        help="publish·done: 올리기 전에 예습 링크를 서버와 맞추는 단계를 "
                             "건너뛴다 (그 사이 링크가 바뀌었으면 옛 주소로 덮어쓴다)")
    parser.add_argument("--reflag", action="store_true",
                        help="rebuild: 검사 규칙이 늘었을 때 소프트 표시를 다시 계산해 덧붙인다")
    parser.add_argument("--from", dest="source_dir", default=None,
                        help="import: 덱을 옮겨 올 quizgen 작업 폴더 (예: ../PDF2ANKI/out)")
    args = parser.parse_args()

    # 이름을 직접 대도 막는다. 실수로 한 번 돌리면 재고에 섞여 들어가고,
    # 그 뒤로는 왜 거기 있는지 아무도 모른다.
    if args.subject and filenames.is_excluded(args.subject):
        print(f"[{args.subject}] 학생마다 듣는 것이 달라 파이프라인에서 뺀 과목이다.\n"
              "  강의록 연결·예습·복습 어느 것도 만들지 않는다.\n"
              "  정말 필요하면 runner/filenames.py의 EXCLUDED_SUBJECTS·"
              "EXCLUDED_PREFIXES를 고쳐라.")
        return 0

    if args.command == "watch":
        return cycle.report_watch(args)
    if args.command == "done":
        return cycle.run_done(args)
    if args.command == "jokbo":
        return run_jokbo(args)
    if args.command == "preview":
        return run_preview(args)
    if args.command == "prequeue":
        return cycle.report_prequeue(args)
    if args.command == "agent":
        return cycle.run_agent(args)
    if args.command == "import":
        return run_import(args)
    if args.command == "chosen":
        return run_chosen(args)
    if args.command == "promote":
        return run_promote(args)
    if args.command == "release":
        return run_release(args)
    if args.command == "rebuild":
        return run_rebuild(args)
    if args.command == "publish":
        if not args.subject and not args.all and not args.run_id:
            parser.error("과목명을 주거나 --all 또는 --run-id를 쓰세요")
        return cycle.report_publish(args)

    root = Path(args.root)
    if args.all:
        subjects = cycle.subjects_with_notes(root, args.this)
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
