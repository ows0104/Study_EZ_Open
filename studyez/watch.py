"""매일 21:30, 새로 올라온 올해 필기를 찾아 퀴즈 만들 거리를 세운다.

## 워처가 하는 일과 하지 않는 일

`/quiz`는 Opus 5를 세 번 부른다. 그건 Claude Code 세션 안에서만 되는 일이라
워처가 대신할 수 없다. 그래서 여기서는 **결정적인 부분만** 한다.

    워처(코드)          스캔 · 최신 판 고르기 · 작년 짝 붙이기 · prep 실행 · 큐 쓰기
    세션(모델)          0.5단계 구조 판별 · 1·2단계 · 4단계 감사
    워처(코드)          validate · build

세션은 `runs/queue.json`을 읽어 한 편씩 처리한다. 워처가 에이전트 흉내를 내려
들면 둘 다 망가진다.

## 업로드는 여기서 하지 않는다

`/quiz`는 족보 경계가 틀리면 뒤가 전부 어긋나고, `run.meta.json`에
`review_flagged`·`slides_unused`가 남는다. 생성까지 자동, 배포는 사람이 본 뒤다.
무인으로 두면 틀린 덱이 조용히 배포된다.

## 이미 만든 것을 다시 만들지 않는 방법

`runs/<run_id>/source.json`에 어느 파일의 몇 판으로 만들었는지 적어 둔다.
`runs/index.json`은 `lecture_id`로만 관리해서 v1으로 만든 뒤 v3이 올라온 경우를
구분하지 못한다 - 실제로 `260812_02`가 v1과 v3으로 두 번 올라왔다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import filenames
from .filenames import LectureFile

DEFAULT_ROOT = Path.home() / "SynologyDrive"

# 동기화가 끝나기 전 파일을 잡으면 잘린 PDF로 덱을 만든다. 마지막 수정이 이만큼
# 지난 것만 건드린다. 21:30 기준으로 그날 올라온 필기는 대부분 이미 안정돼 있다.
MIN_AGE_SECONDS = 10 * 60

# 하루 처리 상한. 병리학은 하루 3~5편이 올라오고 편당 Opus 5 호출이 3회다.
# 넘치는 분량은 다음 날 자동으로 다시 잡힌다 - source.json 기준이기 때문이다.
DEFAULT_MAX_ITEMS = 6


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
    jokbo_pdf: str | None = None     # 과목 족보에서 잘라온 원본. 있으면 이쪽이 낫다
    jokbo_label: str | None = None
    jokbo_score: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class Queue:
    generated_at: str
    items: list[WorkItem]
    skipped: list[str]
    warnings: list[str]


def _jokbo_links(runs_dir: Path, subject: str, year: str) -> dict[str, dict]:
    """`studyez jokbo <과목>`이 남긴 필기↔족보 연결. 없으면 빈 사전."""
    path = runs_dir / "_jokbo" / subject / year / "links.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return {row["key"]: row for row in rows if row.get("key")}


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
    서로를 덮어쓴다. 겹칠 때만 어간 해시를 붙여 사람이 읽을 수 있는 이름을 지킨다.
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
            digest = hashlib.md5(item.stem.encode("utf-8")).hexdigest()[:4]
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
) -> Queue:
    now = time.time() if now is None else now
    items: list[WorkItem] = []
    skipped: list[str] = []
    warnings: list[str] = []

    for subject in subjects:
        this_dir = root / subject / "필기" / this_year
        this_scan = filenames.scan(this_dir, expect_year=this_year)
        if not this_scan.files:
            continue

        # 과목 족보를 이미 잘라 뒀으면 그 연결을 쓴다(`studyez jokbo <과목>`).
        links = _jokbo_links(runs_dir, subject, this_year)

        for path in this_scan.conflicts:
            warnings.append(f"{subject}: 충돌 사본 제외 — {path.name}")
        for stray in this_scan.misfiled:
            warnings.append(f"{subject}: {this_year} 폴더에 {stray.date[:4]}년 파일 — {stray.title}")
        for path in this_scan.unparsed:
            warnings.append(f"{subject}: 파일명을 읽지 못함 — {path.name}")

        this_files = filenames.latest_versions(this_scan.files)
        run_ids = assign_run_ids(this_files)

        for item in this_files:
            run_id = run_ids[item.uid]
            pdf = item.path

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
            link = links.get(item.key) or {}
            jokbo_pdf = link.get("jokbo_pdf") if link.get("confident") else None
            jokbo_label = link.get("jokbo_label") if link.get("confident") else None

            if not links:
                notes.append("과목 족보가 아직 안 잘려 있다. 필기에 붙은 캡처본을 쓴다 "
                             f"(`studyez jokbo {subject}`로 원본을 쓸 수 있다)")
            elif jokbo_pdf and not Path(jokbo_pdf).exists():
                notes.append(f"족보 조각이 사라졌다: {jokbo_pdf}. 필기 캡처본으로 진행")
                jokbo_pdf = jokbo_label = None
            elif not jokbo_pdf:
                hint = link.get("jokbo_label")
                notes.append(
                    f"족보 연결이 확실하지 않다 ({link.get('score', 0)}, 후보 {hint or '없음'}). "
                    "필기에 붙은 캡처본을 쓴다")

            items.append(WorkItem(
                subject=subject, run_id=run_id, key=item.key, date=item.date,
                title=item.title, this_pdf=str(pdf), this_version=item.version,
                reason=reason, jokbo_pdf=jokbo_pdf, jokbo_label=jokbo_label,
                jokbo_score=link.get("score", 0.0), notes=notes,
            ))

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


def run_prep(pdf: str, run_id: str, runs_dir: Path, repo_root: Path,
             jokbo_pdf: str | None = None) -> tuple[bool, str]:
    """prep.py를 따로 띄운다. 한 편이 죽어도 나머지가 계속 가야 한다."""
    command = [
        sys.executable, str(repo_root / "quiz" / "prep.py"), pdf,
        "--out", str(runs_dir), "--run-id", run_id,
    ]
    if jokbo_pdf:
        command += ["--jokbo-pdf", jokbo_pdf]
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=1800, cwd=str(repo_root))
    except subprocess.TimeoutExpired:
        return False, "prep 30분 초과"
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()
        return False, (tail[-1] if tail else f"prep 실패 (코드 {done.returncode})")
    return True, ""


def prepare(queue: Queue, runs_dir: Path, repo_root: Path, workers: int = 0) -> Queue:
    """큐의 각 편에 prep을 돌린다. 강의끼리 완전히 독립이라 동시에 돌린다.

    prep은 40~60쪽을 세 배율로 렌더하느라 편당 1~2분이 걸리고 전부 CPU 작업이다.
    별도 프로세스로 띄우므로 GIL과 무관하게 코어를 쓴다.

    한 편이 죽어도 나머지는 계속 간다 - 하룻밤 분량이 한 편 때문에 통째로
    날아가면 안 된다.
    """
    if not queue.items:
        return queue

    workers = workers or min(len(queue.items), max(1, (os.cpu_count() or 4) - 1))
    survivors: list[WorkItem] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_prep, item.this_pdf, item.run_id, runs_dir, repo_root,
                        item.jokbo_pdf): item
            for item in queue.items
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                ok, error = future.result()
            except Exception as exc:                    # noqa: BLE001
                ok, error = False, f"{type(exc).__name__}: {exc}"
            if ok:
                survivors.append(item)
            else:
                queue.skipped.append(f"{item.subject}/{item.run_id} — prep 실패: {error}")

    survivors.sort(key=lambda w: (w.date, w.run_id))
    queue.items = survivors
    return queue


def stamp_sources(queue: Queue, runs_dir: Path) -> None:
    """빌드가 끝난 뒤 호출한다. 이 표시가 있어야 다음 스캔에서 빠진다."""
    for item in queue.items:
        pdf = Path(item.this_pdf)
        if not pdf.exists():
            continue
        parsed = filenames.parse(pdf)
        if parsed is None:
            continue
        (runs_dir / item.run_id / "source.json").write_text(
            json.dumps(_source_record(pdf, parsed), ensure_ascii=False, indent=2),
            encoding="utf-8")


def save(queue: Queue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at": queue.generated_at,
        "items": [asdict(i) for i in queue.items],
        "skipped": queue.skipped,
        "warnings": queue.warnings,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
