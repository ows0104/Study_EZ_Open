"""자료 준비 명령: 강의 짝 비교(match), 예습 링크(preview), 족보 자르기(jokbo)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from runner import ahead, deck, filenames, matching, preview, watch

from . import REPO_ROOT


def notes_dir(root: Path, subject: str, year: str) -> Path:
    return root / subject / "필기" / year


def report_subject(root: Path, subject: str, this_year: str, prev_year: str,
                   runs_dir: Path | None = None) -> int:
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

    # 사람이 확인한 짝(`_pairs`)을 먼저 앉힌다 — `publish` 가 올리는 짝과 같아야 한다.
    confirmed = ahead.load_pairs(runs_dir, subject) if runs_dir else {}
    matches = matching.match_with_confirmed(this_files, prev_files, confirmed)
    from runner.preview_sources import History
    history = History(root, subject, this_year, prev_year, prev_files, runs_dir or REPO_ROOT / 'runs',
                      current_files=this_files)
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
        choice = history.select(match.this_year, prev if match.confident else None)
        selected = choice.metadata['selected']
        labels = [label for label, yes in [('교수 변경', choice.metadata['changed']),
                                           ('신규 교수', choice.metadata['newProfessor'])] if yes]
        print(f"  {'':>32}  예습: {str(selected['year']) + '년 ' + selected['filename'] if selected else '확인 필요'}"
              + (f" · {', '.join(labels)}" if labels else ''))

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


# 옛 판 과목 족보. 2026-10-05 관리자 — *"족보를 2026, 2020년꺼를 써서, 2026-2015까지를
# 커버할 수 있도록 하자."* 2026판이 2020~2025 시험을, 2020판이 2015~2019 시험을 싣는다.
OLDER_JOKBO_YEARS = ("2020",)


def older_pdfs(root: Path, subject: str, years: str) -> list[Path]:
    """옛 판 과목 족보를 해 폴더마다 하나씩 고른다. 실습 족보·표지는 뺀다.

    폴더에 PDF 가 여럿이면 가장 큰 것이다 — 올해 판을 고르는 규칙과 같다. 병리학·
    기생충학 2020 폴더는 본문과 `_실습` 이 따로 있다.
    """
    picked = []
    for year in [y.strip() for y in (years or "").split(",") if y.strip()]:
        folder = watch.jokbo_source_dir(root, subject, year)
        pdfs = [p for p in (sorted(folder.glob("*.pdf")) if folder.is_dir() else [])
                if "실습" not in p.stem and "표지" not in p.stem]
        if not pdfs:
            print(f"[jokbo] ⚠ 옛 판 {folder} 에 과목 족보 PDF가 없다 — {year}판 없이 자른다")
            continue
        picked.append(max(pdfs, key=lambda p: p.stat().st_size))
    return picked


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
    older = older_pdfs(Path(args.root), subject,
                       getattr(args, "older", ",".join(OLDER_JOKBO_YEARS)))
    print(f"[jokbo] {pdfs[0].name} → {out_dir}")
    for p in older:
        print(f"        옛 판: {p.name}")
    for p in practical:
        print(f"        실습 족보: {p.name}")
    # 자르는 쪽은 자기 출력을 화면으로 바로 흘린다(`cut_jokbo`). 여기 것을 안 밀어내면
    # 어느 PDF를 골랐는지가 그 뒤에 찍혀 순서가 뒤집힌다.
    sys.stdout.flush()
    code = deck.cut_jokbo(pdfs[0], out_dir, REPO_ROOT, practical=practical, older=older)
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
