"""관리자가 저장한 예습 링크를 받아 Pre-Quiz를 만들 자리까지 세운다.

    python -m studyez prequeue              서버의 예습 링크를 훑어 준비한다
    python -m studyez prequeue --dry-run    무엇이 준비될지만 본다

## 여기만 방향이 반대다

다른 모든 것은 로컬이 만들어 서버로 민다. 예습 링크만 **서버에서 로컬로** 온다 —
예습을 하는 것은 사람이고, 사람은 `/admin` 화면에서 링크를 저장한다.

    관리자가 /admin에 예습 링크 저장
      → GET /api/admin/previews          여기
      → 작년 짝을 찾아 prep + preview.md
      → runs/prequeue.json
      → 세션이 편마다 /prequiz
      → python -m studyez done <작년 run_id>   덱·문항·링크가 함께 올라간다

이 명령이 **문항을 만들지는 않는다.** 만드는 것은 `/prequiz`이고 그건 모델이
하는 일이다. 여기서 하는 것은 그 앞의 결정적인 부분 — 어느 작년 run에서 만들
것인지 고르고, `prep.py`를 돌리고, 공유 대화를 `preview.md`로 앉히는 것이다.

## 링크는 올해 강의에 붙고 퀴즈는 작년 run에서 만든다

관리자가 링크를 저장하는 자리는 **올해 강의**다 — `lecture` 표의 키가 그것이다.
그런데 Pre-Quiz는 **작년 필기**로 만든다(족보가 정리돼 붙은 쪽이 작년이다).
그래서 여기서 한 번 갈아탄다.

짝은 `publish.plan_subject`가 이미 계산하고 있으므로 그것을 그대로 부른다.
같은 눈으로 골라야 여기서 만든 편이 나중에 그대로 올라간다 — 다른 규칙으로
고르면 만들어 놓고 못 올리는 편이 생긴다. **확정이 아닌 짝은 세우지 않는다.**
어긋난 짝을 세우면 남의 강의 예습 문항이 만들어진다.

## 예습이 필요한 강의에는 올해 필기가 없다

예습은 **안 지나간 강의**에 하는 것이라 올해 필기가 아직 없다. 그런 자리는
`studyez.ahead`가 시간표에서 세우므로 여기서도 시간표를 넘긴다. 안 넘기면
정작 필요한 편이 통째로 안 잡힌다.

## 이미 만든 편을 다시 만들지 않는다

`preview.md`의 머리글에 어느 대화에서 왔는지 적혀 있다(`preview.read_url`).
그것이 서버의 링크와 같고 `pre_items.final.json`이 있으면 끝난 편이다.

같은데 문항이 없으면 아직 안 만든 편이고, **다르면 관리자가 링크를 바꾼
것이다.** 바꿨는데 덱이 이미 있으면 그 덱은 다른 대화로 만든 것이므로
`stale`로 적어 다시 만들게 한다 — 조용히 두면 학생이 읽고 온 대화와 문항이
어긋난다.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import filenames, publish, watch
from . import preview as preview_mod

QUEUE_NAME = "prequeue.json"

# 한 편이 어디까지 왔는가.
READY = "ready"        # prep·preview.md까지 섰다. 이제 /prequiz
DONE = "done"          # 이 대화로 만든 문항이 이미 있다
STALE = "stale"        # 덱은 있는데 다른 대화로 만든 것이다. 다시 만든다
BLOCKED = "blocked"    # 세우지 못했다. 사람이 봐야 한다


@dataclass(frozen=True)
class Link:
    """서버에 저장된 예습 링크 한 줄. `run_id`는 **올해** 강의의 것이다."""

    subject: str
    run_id: str
    date: str
    title: str
    share_url: str
    updated_at: str = ""
    pre_item_count: int = 0


@dataclass
class Target:
    """한 링크가 가리키는 작업 하나. `prev_run_id`가 퀴즈를 만들 자리다."""

    link: Link
    prev_run_id: str = ""
    prev_pdf: str = ""
    state: str = READY
    reason: str = ""                                   # BLOCKED일 때 왜인지
    turns: int = 0                                     # 받아 온 대화의 크기
    chars: int = 0
    notes: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        row = asdict(self)
        row["link"] = asdict(self.link)
        return row


# ------------------------------------------------------------------ 서버에서 읽기


def fetch_links(client: publish.Client) -> list[Link]:
    """저장된 예습 링크 전부. 날짜 순으로."""
    answer = client.call("GET", "/api/admin/previews") or {}
    rows = answer.get("previews", []) if isinstance(answer, dict) else answer
    links: list[Link] = []
    for row in rows or []:
        url = str(row.get("shareUrl", "")).strip()
        if not url:
            continue
        links.append(Link(
            # Synology 폴더명과 맞춰야 하므로 여기서 NFC로 세운다. 서버에는
            # NFC로 들어가 있지만 오는 길에 무엇이 끼든 폴더를 못 찾으면
            # "로컬에서 이 강의를 못 찾았다"로만 보여 원인이 안 보인다.
            subject=unicodedata.normalize("NFC", str(row.get("subject", ""))),
            run_id=str(row.get("runId", "")),
            date=str(row.get("date", "")),
            title=unicodedata.normalize("NFC", str(row.get("title", ""))),
            share_url=url,
            updated_at=str(row.get("updatedAt", "")),
            pre_item_count=int(row.get("preItemCount") or 0),
        ))
    return sorted(links, key=lambda link: (link.date, link.run_id))


# ------------------------------------------------------------------ 자리 찾기


def resolve(
    links: list[Link],
    root: Path,
    this_year: str,
    prev_year: str,
    runs_dir: Path,
    timetable: Path | None = None,
) -> tuple[list[Target], list[str]]:
    """링크마다 만들 자리를 찾는다. (할 일, 사람이 볼 말)

    `publish`와 같은 계획을 쓴다. 과목마다 한 번만 계획을 세우고 그 안에서
    링크를 찾는다 — 계획 한 번이 폴더 두 개를 통째로 훑는 일이라 링크마다
    부르면 같은 과목을 몇 번씩 다시 읽는다.
    """
    targets: list[Target] = []
    warnings: list[str] = []

    by_subject: dict[str, list[Link]] = {}
    for link in links:
        if filenames.is_excluded(link.subject):
            # 학생마다 듣는 것이 다른 과목. 링크가 저장돼 있어도 만들지 않는다.
            warnings.append(f"{link.subject}: 파이프라인에서 뺀 과목이다 — "
                            f"{link.run_id}의 예습 링크를 쓰지 않는다")
            continue
        by_subject.setdefault(link.subject, []).append(link)

    for subject, subject_links in sorted(by_subject.items()):
        plans, subject_warnings = publish.plan_subject(
            root, subject, this_year, prev_year, runs_dir,
            # 검문은 **올릴 때** 하는 것이다. 여기서 걸면 아직 만들지도 않은
            # 편이 "덱이 없다"는 이유로 빠진다.
            gated=False,
            timetable=timetable)
        warnings += subject_warnings
        by_run = {plan.run_id: plan for plan in plans}

        for link in subject_links:
            plan = by_run.get(link.run_id)
            if plan is None:
                targets.append(Target(link=link, state=BLOCKED, reason=(
                    "로컬에서 이 강의를 못 찾았다 — 올해 필기도 시간표 칸도 없다. "
                    "시간표를 먼저 넣어야 할 수 있다")))
                continue

            pdf = next((u.path for u in plan.uploads if u.kind == "notes_prev"), None)
            if not plan.prev_run_id or pdf is None:
                # 왜 짝이 없는지는 계획이 이미 적어 두었다. 그대로 옮긴다 —
                # 여기서 다시 판정하면 `publish`와 말이 갈린다.
                why = next((note for note in plan.notes if "작년 짝" in note),
                           "작년 짝이 없어 Pre-Quiz를 만들 자리가 없다")
                targets.append(Target(link=link, state=BLOCKED, reason=why))
                continue

            targets.append(Target(link=link, prev_run_id=plan.prev_run_id, prev_pdf=str(pdf)))

    targets.sort(key=lambda target: (target.link.date, target.link.run_id))
    return targets, warnings


# ------------------------------------------------------------------ 자리 세우기


def _prep_source(run_dir: Path) -> str:
    prep = run_dir / "prep.json"
    if not prep.is_file():
        return ""
    try:
        return str(json.loads(prep.read_text(encoding="utf-8")).get("source_pdf", ""))
    except (OSError, ValueError):
        return ""


def needs_prep(run_dir: Path, pdf: str) -> bool:
    """이 자리에 prep을 (다시) 돌려야 하는가.

    `run_id`는 날짜_교시라서 과목을 포함하지 않는다. 다른 과목이 같은 교시에
    돌면 한 디렉터리를 두 강의가 나눠 갖게 되므로, 있는 것으로 넘기기 전에
    **정말 이 강의의 것인지** 확인한다. 판이 다르면 다시 돌린다.
    """
    source = _prep_source(run_dir)
    if not source:
        return True
    made, wanted = filenames.parse(source), filenames.parse(pdf)
    if made is None or wanted is None:
        return True
    return made.uid != wanted.uid or made.version != wanted.version


def prepare(
    targets: list[Target],
    runs_dir: Path,
    repo_root: Path,
    workers: int = 0,
) -> list[Target]:
    """prep을 돌리고 예습 대화를 앉힌다. 각 편의 `state`가 여기서 정해진다.

    prep은 40~60쪽을 세 배율로 렌더하느라 편당 1~2분이고 전부 CPU 작업이라
    따로 띄워 동시에 돌린다. 대화 내려받기는 그다음에 하나씩 한다 — 남의
    서비스를 두들기는 일이라 서두를 이유가 없다.

    한 편이 죽어도 나머지는 계속 간다.
    """
    live = [target for target in targets if target.state != BLOCKED]

    todo = [t for t in live if needs_prep(runs_dir / t.prev_run_id, t.prev_pdf)]
    if todo:
        workers = workers or min(len(todo), max(1, (os.cpu_count() or 4) - 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(watch.run_prep, t.prev_pdf, t.prev_run_id, runs_dir, repo_root): t
                for t in todo
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    ok, error = future.result()
                except Exception as exc:                        # noqa: BLE001
                    ok, error = False, f"{type(exc).__name__}: {exc}"
                if ok:
                    target.notes.append("prep 새로 돌림")
                else:
                    target.state, target.reason = BLOCKED, f"prep 실패: {error}"

    for target in [t for t in live if t.state != BLOCKED]:
        run_dir = runs_dir / target.prev_run_id
        # 지금 앉아 있는 대화가 어느 것인지. 받아 오기 **전에** 읽어야 한다 —
        # 덮어쓰고 나면 링크가 바뀌었다는 사실이 사라진다.
        standing = preview_mod.read_url(run_dir / "preview.md")
        built = (run_dir / "pre_items.final.json").is_file()

        if standing == target.link.share_url:
            target.notes.append("preview.md 그대로 — 같은 대화다")
        else:
            try:
                fetched = preview_mod.fetch(target.link.share_url)
            except (SystemExit, ValueError, OSError) as cause:
                # `preview.fetch`는 못 읽으면 SystemExit으로 멈춘다. 한 편 때문에
                # 나머지가 통째로 죽지 않게 여기서 받는다.
                first = str(cause).strip().splitlines()
                target.state = BLOCKED
                target.reason = f"예습 대화를 못 읽었다: {first[0] if first else cause}"
                if built and standing:
                    # 덱은 이미 있는데 링크가 바뀌었고 새 대화를 못 읽었다.
                    # 서버에는 **새 링크가 이미 올라가 있으므로** 학생이 읽고 올
                    # 대화와 문항이 지금 어긋나 있다. 조용히 넘기면 안 된다.
                    target.reason += (
                        f" — 덱은 이미 있고 링크만 바뀌었다. 학생이 읽을 대화와 문항이 "
                        f"어긋난 상태다. 링크를 확인하거나 {run_dir.name}을 다시 만들어야 한다")
                continue
            preview_mod.save(fetched, run_dir)
            target.turns, target.chars = len(fetched.turns), fetched.chars
            target.notes.append("preview.md 새로 받음"
                                + (" — 링크가 바뀌었다" if standing else ""))

        if built:
            target.state = DONE if standing == target.link.share_url else STALE
        else:
            target.state = READY

    return targets


# ------------------------------------------------------------------ 큐


def save(targets: list[Target], path: Path) -> None:
    """`/prequiz`가 무엇을 돌릴지 여기서 읽는다.

    `queue.json`처럼 통째로 다시 쓴다. 편이 끝났다는 표시는 이 파일이 아니라
    `pre_items.final.json`이 들고 있으므로, 다시 써도 진행이 지워지지 않는다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "items": [target.as_row() for target in targets],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
