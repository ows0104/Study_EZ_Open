"""매일 21:30, 새로 올라온 올해 필기를 찾아 덱을 만든다.

## 가운데가 더 이상 뚫려 있지 않다

한동안 워처는 prep까지만 하고 `runs/queue.json`을 남겼다. 문항을 만드는 것은
사람이 연 Claude Code 세션의 `/quiz`였고, 그 한 편이 53~72분 동안 세션의 컨텍스트를
통째로 먹었다.

지금은 `pdf2anki`가 모델이 필요한 자리마다 **빈 세션을 스스로 띄운다**
(`pdf2anki/session.py`). 그래서 워처가 한 편을 끝까지 만든다.

    스캔 · 최신 판 고르기 · 큐 쓰기        watch
    prep → ①② → 검증 → 재현 → 빌드        pdf2anki.run (하위 프로세스)
    계약 모양으로 옮기기                    studyez.deck.contract

큐는 없어지지 않았다. `--build` 없이 부르면 **무엇을 만들지 보여 주기만** 한다 —
한 편이 수십 분이라 밤에 무엇이 돌지 먼저 보는 자리가 있어야 한다.

## 한 번에 한 편씩 만든다

pdf2anki 한 편이 이미 `--jobs 4`로 빈 세션 넷을 동시에 띄운다. 편을 겹쳐 돌리면
그 배수가 되어 노트북이 먼저 무릎을 꿇는다. prep만 돌리던 시절에는 편끼리 겹쳐
돌렸는데, 그때는 CPU 렌더가 전부였기 때문이다.

## 업로드는 여기서 하지 않는다

`publish`가 따로 한다. 두 자리에서 걸린다 — 편이 끝날 때 `studyez done`이 그
편을, 하루 한 번 `scripts/nightly-publish.ps1`이 `publish --all`로 놓친 것을.
무엇이 나갈지는 `studyez.gate`가 편마다 본다 — 막힌 편은 강의록만 나가고 덱은
미뤄진다. 무엇을 막고 무엇을 적기만 하는지는 그쪽 첫머리에 있다.

## 이미 만든 것을 다시 만들지 않는 방법

`runs/<run_id>/source.json`에 어느 파일의 몇 판으로 만들었는지 적어 둔다.
`runs/index.json`은 `lecture_id`로만 관리해서 v1으로 만든 뒤 v3이 올라온 경우를
구분하지 못한다 - 실제로 `260812_02`가 v1과 v3으로 두 번 올라왔다.

**그 표시를 찍는 길이 큐 밖에도 있어야 한다.** 예전에는 편이 끝날 무렵 `queue.json`이
이미 다시 쓰여 그 항목이 사라져 있는 일이 잦았고, 만든 13편 중 표시가 남은 것이 한
편뿐이었다. 지금은 `build_one()`이 끝나는 자리에서 바로 찍지만, `studyez done`이
부르는 길도 남겨 둔다 — 손으로 만든 편과 옆 저장소에서 옮겨 온 편이 그리로 온다.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import deck, filenames
from .filenames import LectureFile

DEFAULT_ROOT = Path.home() / "SynologyDrive"

# 동기화가 끝나기 전 파일을 잡으면 잘린 PDF로 덱을 만든다. 마지막 수정이 이만큼
# 지난 것만 건드린다. 21:30 기준으로 그날 올라온 필기는 대부분 이미 안정돼 있다.
MIN_AGE_SECONDS = 10 * 60

# 하루 처리 상한. 병리학은 하루 3~5편이 올라온다.
# 넘치는 분량은 다음 날 자동으로 다시 잡힌다 - source.json 기준이기 때문이다.
#
# 당분간 2다. 2026-08-19에 관리자가 토큰이 모자라 내렸다(6 → 3 → 2, 같은 날).
# 그날 큐는 6편을 잡고 7편을 상한으로 밀어냈는데, 그 6편을 다 돌릴 토큰이 없었다.
#
# **그 사정이 pdf2anki로 갈아탄 뒤 어떻게 바뀌었는지는 아직 안 쟀다.** 편당 비용은
# 이제 `runs/<run_id>/run.report.json`에 실제 값이 남으므로, 몇 편이 쌓이면 거기서
# 읽어 정하면 된다. 그 전까지 짐작으로 올리지 않는다.
DEFAULT_MAX_ITEMS = 2


@dataclass
class WorkItem:
    """한 편의 강의. 세션이 이걸 보고 스킬을 돌린다.

    작년 필기는 여기 없다. 올해 필기에도 족보가 붙어 있고 그게 작년 것을 포함하기
    때문이다(`260812_01` 실측: 작년 18문항이 올해 족보에 100% 포함). 작년 자료가
    필요한 곳은 Pre-Quiz뿐이고, 그건 다른 흐름이다.
    """

    subject: str
    run_id: str
    key: str
    date: str
    title: str
    this_pdf: str
    this_version: int
    reason: str                      # 'new' | 'newer_version'
    # 덱 나무의 가운데 마디. `title`과 달리 교수 괄호를 뗐다 — 그대로 쓰면
    # 교수가 바뀌는 해에 같은 강의가 두 노드로 갈린다.
    lecture: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class Queue:
    generated_at: str
    items: list[WorkItem]
    skipped: list[str]
    warnings: list[str]


def jokbo_ready(runs_dir: Path, subject: str) -> bool:
    """과목 족보가 잘려 있는가.

    어느 조각을 어느 강의에 물릴지는 **여기서 정하지 않는다.** pdf2anki가 목차
    제목으로 대조한다 — 카드를 만들 때 본 조각과 뒷면에 붙이는 조각이 갈리면 안
    되므로 그 판단은 한 곳에만 있어야 한다. 여기서는 자리가 섰는지만 본다.
    """
    return (deck.jokbo_dir(runs_dir, subject) / "index.json").is_file()


def _source_record(pdf: Path, item: LectureFile) -> dict:
    stat = pdf.stat()
    return {
        "path": str(pdf),
        "stem": pdf.stem,
        "version": item.version,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
    }


def _already_built(runs_dir: Path, run_id: str, item: LectureFile) -> str | None:
    """이미 만들었으면 None이 아닌 사유를 돌려준다."""
    source_path = runs_dir / run_id / "source.json"
    if not source_path.exists():
        return None
    try:
        recorded = json.loads(source_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if recorded.get("version", 0) >= item.version:
        return f"이미 v{recorded.get('version')}로 만듦"
    return None


def assign_run_ids(files: list[LectureFile]) -> dict[str, str]:
    """강의마다 겹치지 않는 run 디렉터리 이름을 준다.

    보통은 `260813_03`이면 되지만, 한 교시에 여러 강의가 열리면 그것만으로는
    서로를 덮어쓴다. 겹칠 때만 해시를 붙여 사람이 읽을 수 있는 이름을 지킨다.

    **해시는 `uid`로 뜬다.** 한동안 `stem`으로 떴는데, `stem`은 괄호를 떼고
    정규화한 값이라 조직학 2026의 두 강의가 통째로 겹쳤다.

        [260331_05] 조직학총론 실습 3(연골과 뼈)_심준선v1     stem 조직학총론실습3
        [260331_05]조직학총론 실습 3(근육)_신유빈v1           stem 조직학총론실습3

    둘 다 `260331_05-07f9`가 되어 run 디렉터리를 나눠 갖고, 서버는 (과목, run_id)로
    강의를 세므로 한 편이 다른 편을 덮는다. `LectureFile.uid`가 정확히 이 두 파일을
    예로 들며 괄호를 남겨 두는데, 여기서 그걸 안 쓰고 있었다.
    """
    by_key: dict[str, list[LectureFile]] = {}
    for item in files:
        by_key.setdefault(item.key, []).append(item)

    run_ids: dict[str, str] = {}
    for key, group in by_key.items():
        if len(group) == 1:
            run_ids[group[0].uid] = key
            continue
        for item in group:
            digest = hashlib.md5(item.uid.encode("utf-8")).hexdigest()[:4]
            run_ids[item.uid] = f"{key}-{digest}"
    return run_ids


def build_queue(
    root: Path,
    subjects: list[str],
    this_year: str,
    runs_dir: Path,
    max_items: int = DEFAULT_MAX_ITEMS,
    min_age_seconds: int = MIN_AGE_SECONDS,
    now: float | None = None,
    since: str | None = None,
    until: str | None = None,
) -> Queue:
    """`since`~`until`은 이번 블럭의 구간이다(`studyez.blocks`).

    이게 없으면 `필기/<올해>` 폴더가 있는 과목을 전부 훑고 날짜 오름차순으로
    자르기 때문에, 학기가 바뀌어도 지난 학기 필기가 먼저 걸린다.
    """
    now = time.time() if now is None else now
    items: list[WorkItem] = []
    skipped: list[str] = []
    warnings: list[str] = []
    outside: dict[str, int] = {}

    for subject in subjects:
        this_dir = root / subject / "필기" / this_year
        this_scan = filenames.scan(this_dir, expect_year=this_year)
        if not this_scan.files:
            continue

        for path in this_scan.conflicts:
            warnings.append(f"{subject}: 충돌 사본 제외 — {path.name}")
        for stray in this_scan.misfiled:
            warnings.append(f"{subject}: {this_year} 폴더에 {stray.date[:4]}년 파일 — {stray.title}")
        for path in this_scan.unparsed:
            warnings.append(f"{subject}: 파일명을 읽지 못함 — {path.name}")

        this_files = filenames.latest_versions(this_scan.files)
        run_ids = assign_run_ids(this_files)
        has_jokbo = jokbo_ready(runs_dir, subject)

        for item in this_files:
            run_id = run_ids[item.uid]
            pdf = item.path

            # 블럭 밖은 세기만 한다. 한 줄씩 적으면 지난 학기 수십 편이 보고를 덮는다.
            if (since and item.date < since) or (until and item.date > until):
                outside[subject] = outside.get(subject, 0) + 1
                continue

            done = _already_built(runs_dir, run_id, item)
            if done:
                continue

            age = now - pdf.stat().st_mtime
            if age < min_age_seconds:
                skipped.append(
                    f"{subject}/{run_id} {item.title[:26]} — 올라온 지 "
                    f"{int(age / 60)}분. 동기화 중일 수 있어 다음 차례로")
                continue

            reason = "newer_version" if (runs_dir / run_id / "source.json").exists() else "new"
            notes: list[str] = []
            if not has_jokbo:
                notes.append("과목 족보가 아직 안 잘려 있다 — 기출 카드 없이 만들어진다 "
                             f"(`python -m studyez jokbo {subject}`)")

            items.append(WorkItem(
                subject=subject, run_id=run_id, key=item.key, date=item.date,
                title=item.title, this_pdf=str(pdf), this_version=item.version,
                reason=reason,
                lecture=deck.deck_node(run_id, item.title, item.professors),
                notes=notes,
            ))

    for subject, count in sorted(outside.items()):
        skipped.append(f"{subject} {count}편 — 이번 블럭({since}~{until}) 밖")

    items.sort(key=lambda w: (w.date, w.run_id))
    if len(items) > max_items:
        for extra in items[max_items:]:
            skipped.append(
                f"{extra.subject}/{extra.run_id} {extra.title[:26]} — "
                f"하루 상한 {max_items}편 초과. 내일 다시 잡힌다")
        items = items[:max_items]

    return Queue(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        items=items, skipped=skipped, warnings=warnings,
    )


def build_one(item: WorkItem, runs_dir: Path, repo_root: Path, *,
              model: str = "", timeout: int = deck.DEFAULT_TIMEOUT,
              extra: list[str] | None = None) -> tuple[bool, str]:
    """한 편을 끝까지 만든다. (됐나, 사람이 볼 말)

    족보 조각을 손으로 물려 주지 않는다. `studyez jokbo <과목>`이 잘라 둔
    `runs/_jokbo/`를 pdf2anki가 목차 제목으로 스스로 대조한다 — 카드를 만들 때 본
    조각과 뒷면에 붙이는 조각이 갈리면 안 되기 때문에 그 판단이 한 곳에 있어야 한다.

    한 편이 죽어도 나머지는 계속 간다. 하룻밤 분량이 한 편 때문에 통째로
    날아가면 안 된다.
    """
    result = deck.run_main(
        pdf=item.this_pdf, run_id=item.run_id, subject=item.subject,
        lecture=item.lecture or item.title, title=item.title,
        runs_dir=runs_dir, repo_root=repo_root,
        model=model, timeout=timeout, extra=extra)
    if not result.ok:
        return False, f"{result.error} (로그: {result.log})"

    try:
        meta = deck.contract(result.run_dir, item.run_id, item.title, deck.MAIN)
    except (FileNotFoundError, OSError, ValueError) as cause:
        return False, f"산출물을 계약 모양으로 옮기지 못했다: {cause}"

    stamp_run(runs_dir, item.run_id, Path(item.this_pdf))
    return True, (f"{meta['item_count']}장 "
                  f"(강의록 {meta['sources'].get('lecture', 0)} · "
                  f"기출 {meta['sources'].get('jokbo', 0)})")


def build(queue: Queue, runs_dir: Path, repo_root: Path, *, model: str = "",
          timeout: int = deck.DEFAULT_TIMEOUT, extra: list[str] | None = None,
          announce=print) -> Queue:
    """큐대로 한 편씩 만든다. **겹쳐 돌리지 않는다.**

    pdf2anki 한 편이 이미 빈 세션 넷을 동시에 띄우므로, 편을 겹치면 그 배수가 된다.
    끝난 편만 `queue.items`에 남기고 실패한 편은 사유와 함께 `skipped`로 내린다.
    """
    survivors: list[WorkItem] = []
    for index, item in enumerate(queue.items, 1):
        announce(f"[{index}/{len(queue.items)}] {item.subject}/{item.run_id} "
                 f"{item.title[:34]} — 만드는 중")
        try:
            ok, note = build_one(item, runs_dir, repo_root,
                                 model=model, timeout=timeout, extra=extra)
        except Exception as exc:                        # noqa: BLE001
            ok, note = False, f"{type(exc).__name__}: {exc}"
        if ok:
            survivors.append(item)
            announce(f"    끝났다 — {note}")
        else:
            queue.skipped.append(f"{item.subject}/{item.run_id} — 빌드 실패: {note}")
            announce(f"    실패 — {note}")

    queue.items = survivors
    return queue


def stamp_run(runs_dir: Path, run_id: str, pdf: Path) -> bool:
    """한 편을 표시한다. 찍었으면 True.

    큐를 거치지 않는 길이 필요하다. 손으로 만든 편, 옆 저장소에서 옮겨 온 편,
    빌드가 끝난 뒤 사람이 확인하고 부르는 `studyez done`이 전부 여기로 온다.
    """
    if not pdf.exists():
        return False
    parsed = filenames.parse(pdf)
    if parsed is None:
        return False
    (runs_dir / run_id).mkdir(parents=True, exist_ok=True)
    (runs_dir / run_id / "source.json").write_text(
        json.dumps(_source_record(pdf, parsed), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return True


def stamp_sources(queue: Queue, runs_dir: Path) -> None:
    """빌드가 끝난 뒤 호출한다. 이 표시가 있어야 다음 스캔에서 빠진다."""
    for item in queue.items:
        stamp_run(runs_dir, item.run_id, Path(item.this_pdf))


def save(queue: Queue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at": queue.generated_at,
        "items": [asdict(i) for i in queue.items],
        "skipped": queue.skipped,
        "warnings": queue.warnings,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
