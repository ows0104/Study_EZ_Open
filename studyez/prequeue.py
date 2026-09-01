"""관리자가 저장한 예습 링크를 받아 Pre-Quiz를 만들 자리까지 세운다.

    python -m studyez prequeue              서버의 예습 링크를 훑어 준비한다
    python -m studyez prequeue --dry-run    무엇이 준비될지만 본다

## 여기만 방향이 반대다

다른 모든 것은 로컬이 만들어 서버로 민다. 예습 링크만 **서버에서 로컬로** 온다 —
예습을 하는 것은 사람이고, 사람은 `/admin` 화면에서 링크를 저장한다.

    관리자가 /admin에 예습 링크 저장
      → GET /api/admin/previews          여기
      → 작년 짝을 찾아 prep + preview.md + pre_target.json
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

갈아탄 자리를 `runs/<작년 run_id>/pre_target.json`에 적어 둔다. 덱 이름은
**올해 강의**로 서야 하는데(학생은 올해 시간표를 보고 예습을 한다) 작년 자리에서
빌드하는 `prequiz/build.py`가 볼 수 있는 것은 작년 PDF의 파일명뿐이라, 여기서
적어 주지 않으면 작년 제목이 붙는다.

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
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import deck, filenames, publish
from . import preview as preview_mod

QUEUE_NAME = "prequeue.json"

# 편 하나의 판정을 그 편의 자리에 적어 두는 파일. 큐 파일과 값은 같지만 **덮어쓰는
# 것이 자기 자신뿐**이다(`save_state`).
STATE_NAME = "pre_queue_state.json"

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
    # 덱 이름에 쓸 **올해** 강의 제목. `link.title`이 아니라 계획이 든 것을 쓴다 —
    # 서버에 올라간 제목은 계획이 밀어 넣은 것이라 여기서 다시 읽으면 한 번 더
    # 왕복할 뿐이고, 그 사이에 필기가 올라와 제목이 바뀌었으면 오히려 낡았다.
    this_title: str = ""
    # 덱 나무의 가운데 마디. 교수 괄호를 뗀 것이라 `this_title`과 다르다.
    this_lecture: str = ""
    professors: tuple[str, ...] = ()
    state: str = READY
    # 사람이 「다시 만들기」를 눌렀는가. 이어 돌리지 않고 통째로 다시 만든다.
    force: bool = False
    occupancy: str = ""                                # 이 자리를 무엇이 쓰고 있나
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

            targets.append(Target(
                link=link, prev_run_id=plan.prev_run_id, prev_pdf=str(pdf),
                this_title=plan.item.title, professors=tuple(plan.item.professors),
                this_lecture=deck.deck_node(link.run_id, plan.item.title,
                                           plan.item.professors)))

    targets.sort(key=lambda target: (target.link.date, target.link.run_id))
    return targets, warnings


# ------------------------------------------------------------------ 자리 세우기


TARGET_NAME = deck.TARGET_NAME   # 읽는 쪽(`deck.calendar_name`)이 이름을 갖는다


def write_target(run_dir: Path, target: Target) -> None:
    """이 작년 자리가 **어느 올해 강의를 위해** 도는지 적는다.

    `prequiz/build.py`가 덱 이름을 여기서 읽는다. 안 적어 두면 build가 볼 것은
    작년 PDF의 파일명뿐이라 덱이 작년 제목으로 선다 — 학생은 올해 시간표를 보고
    예습을 하므로 그 이름으로는 어느 강의의 것인지 안 보인다.

    돌 때마다 다시 쓴다. 짝이 바뀌면 이 파일도 따라 바뀌어야 하고, 낡은 짝이
    남아 있으면 남의 강의 제목이 덱에 붙는다.
    """
    (run_dir / TARGET_NAME).write_text(json.dumps({
        "subject": target.link.subject,
        "run_id": target.link.run_id,
        "date": target.link.date,
        "title": target.this_title or target.link.title,
        # 시간표에서 세운 자리는 제목에 교수가 없다. 덱 파일 이름이 그걸 붙이려면
        # 여기 적어 두는 수밖에 없다 — 나중에 그 칸을 다시 찾을 길이 없다.
        "professors": list(target.professors),
        # build가 "이 자리가 정말 이 짝의 것인가"를 보는 값. 같은 교시에 다른
        # 과목이 돌면 한 디렉터리를 나눠 쓴다.
        "prev_run_id": target.prev_run_id,
        "prev_pdf": target.prev_pdf,
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


# 이 자리가 누구 것인가. `occupancy()`가 돌려주는 셋.
EMPTY = "empty"        # 아직 아무것도 없다
SAME = "same"          # 같은 강의, 같은 판. 이어서 돌리면 된다
NEWER = "newer"        # 같은 강의인데 필기 판이 올라갔다. 통째로 다시 만든다
FOREIGN = "foreign"    # 남의 강의가 쓰고 있다. 사람이 봐야 한다


def occupancy(run_dir: Path, pdf: str) -> str:
    """이 디렉터리를 무엇이 쓰고 있는가.

    `run_id`는 날짜_교시라서 과목을 포함하지 않는다. 다른 과목이 같은 교시에
    돌면 한 디렉터리를 두 강의가 나눠 갖게 되므로, 돌리기 전에 **정말 이 강의의
    것인지** 확인한다. 확인 없이 돌리면 pdf2anki가 남의 prep을 그대로 이어받는다.

    남의 것이면 **지우지 않고 멈춘다.** 산출물 디렉터리를 코드가 조용히 비우면
    무엇이 사라졌는지 아무도 모른다.
    """
    source = deck.source_pdf(run_dir)
    if not source:
        return EMPTY
    made, wanted = filenames.parse(source), filenames.parse(pdf)
    if made is None or wanted is None:
        return FOREIGN
    if made.uid != wanted.uid:
        return FOREIGN
    return SAME if made.version == wanted.version else NEWER


def prepare(targets: list[Target], runs_dir: Path, *, force: bool = False) -> list[Target]:
    """예습 대화를 앉히고 각 편의 `state`를 정한다. **덱은 여기서 안 만든다.**

    `force`는 사람이 「다시 만들기」를 누른 것이다. 이미 만든 편도 `STALE`로 세워
    다시 만든다 — 안 그러면 `DONE`으로 건너뛰고, 누른 사람은 아무 일도 안 일어난
    것을 본다. 한 편에 빈 세션 넷이라 **부르는 쪽이 한 편으로 좁혀** 준다
    (`__main__`이 `--run-id` 없는 `--force`를 막는다).

    한동안 이 자리가 prep도 돌렸다. 지금은 pdf2anki가 prep부터 빌드까지 한 명령으로
    하므로, 남는 것은 그 앞의 결정적인 부분 둘뿐이다 — 자리를 확인하고, 남의
    서비스에 있는 예습 대화를 `preview.md`로 받아 오는 것.

    대화 내려받기는 하나씩 한다. 남의 서비스를 두들기는 일이라 서두를 이유가 없다.
    """
    for target in [t for t in targets if t.state != BLOCKED]:
        run_dir = runs_dir / target.prev_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        target.occupancy = occupancy(run_dir, target.prev_pdf)
        if target.occupancy == FOREIGN:
            target.state = BLOCKED
            target.reason = (
                f"{run_dir.name}을 다른 강의가 쓰고 있다 ({Path(deck.source_pdf(run_dir)).name[:44]}) "
                "— 그 자리를 사람이 정리해야 한다")
            continue

        write_target(run_dir, target)
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

        if force:
            # 사람이 눌렀다. 이미 있는 것을 버리고 처음부터 만든다 — 중간 산출물을
            # 이어받으면 「다시 만들었는데 그대로다」가 된다.
            target.force = True
            target.state = STALE if built else READY
            target.notes.append("다시 만들라고 눌렀다 — 중간 산출물을 버리고 처음부터 만든다"
                                if built else "다시 만들라고 눌렀다 — 아직 만든 것은 없다")
        elif built and target.occupancy == NEWER:
            target.state = STALE
            target.notes.append("작년 필기가 새 판으로 갈렸다 — 다시 만든다")
        elif built:
            target.state = DONE if standing == target.link.share_url else STALE
        else:
            target.state = READY

    return targets


def refresh(
    client: publish.Client,
    root: Path,
    this_year: str,
    prev_year: str,
    runs_dir: Path,
    *,
    subjects: tuple[str, ...] = (),
    timetable: Path | None = None,
) -> tuple[list[Target], list[str]]:
    """서버의 예습 링크를 다시 훑어 `preview.md`를 서버와 맞춘다. **덱은 안 만든다.**

    `publish`가 올리기 전에 부른다. 방향이 여기만 반대라(서버 → 로컬) 당겨 오지
    않으면, `publish`는 `preview.md`에 적힌 **옛 주소**를 서버에 덮어쓴다 —
    관리자가 방금 저장한 링크가 조용히 되돌아간다.

    큐 파일은 여기서 안 쓴다. `subjects`로 좁혀 부를 수 있어서, 그대로 쓰면
    `prequeue`가 과목 전체를 보고 적어 둔 표가 한 과목짜리로 잘린다.
    """
    links = fetch_links(client)
    if subjects:
        wanted = set(subjects)
        links = [link for link in links if link.subject in wanted]
    targets, warnings = resolve(links, root, this_year, prev_year, runs_dir,
                                timetable=timetable)
    return prepare(targets, runs_dir), warnings


def build_one(target: Target, runs_dir: Path, repo_root: Path, *, model: str = "",
              timeout: int = deck.DEFAULT_TIMEOUT,
              extra: list[str] | None = None) -> tuple[bool, str]:
    """한 편의 예습 덱을 끝까지 만든다. (됐나, 사람이 볼 말)

    `--lecture`에 **올해** 강의 제목을 준다. 안 주면 덱의 가운데 마디가 작년
    파일제목이 되어 복습 덱과 다른 노드에 서고, 학생은 올해 시간표를 보고 예습을
    하므로 그 이름으로는 어느 강의의 것인지 안 보인다.

    새 판으로 갈린 자리와 **사람이 다시 만들라고 누른 자리**는 `--force`로 통째로
    다시 만든다. 이어 돌리면 pdf2anki가 이미 만든 단계를 건너뛴다.
    """
    run_dir = runs_dir / target.prev_run_id
    note = run_dir / preview_mod.PREVIEW_NAME
    if not note.is_file():
        return False, "preview.md가 없다 — 예습 대화를 먼저 받아야 한다"

    result = deck.run_pre(
        pdf=target.prev_pdf, run_id=target.prev_run_id, subject=target.link.subject,
        lecture=target.this_lecture or target.this_title or target.link.title, note=str(note),
        runs_dir=runs_dir, repo_root=repo_root, model=model, timeout=timeout,
        extra=(extra or []) + (["--force"] if target.occupancy == NEWER or target.force else []))
    if not result.ok:
        return False, f"{result.error} (로그: {result.log})"

    try:
        meta = deck.contract(result.run_dir, target.prev_run_id,
                             target.this_title or target.link.title, deck.PRE)
    except (FileNotFoundError, OSError, ValueError) as cause:
        return False, f"산출물을 계약 모양으로 옮기지 못했다: {cause}"
    return True, f"{meta['item_count']}장 (웹 풀이 {meta['web_items']}장)"


def build(targets: list[Target], runs_dir: Path, repo_root: Path, *, model: str = "",
          timeout: int = deck.DEFAULT_TIMEOUT, extra: list[str] | None = None,
          limit: int = 0, until: str = "", announce=print) -> list[Target]:
    """`READY`·`STALE`인 편을 한 편씩 만든다. 급한 것(강의 날짜가 이른 것)부터.

    겹쳐 돌리지 않는 이유는 `studyez.watch.build`와 같다 — 한 편이 이미 빈 세션
    넷을 띄운다.

    **미룬 편은 이름을 적어 알린다.** `limit`으로 자르든 `until`(이 날짜까지만)로
    거르든 마찬가지다 — 조용히 자르면 다 만든 줄로 읽힌다.
    """
    todo = [t for t in targets if t.state in (READY, STALE)]
    if until:
        far = [t for t in todo if t.link.date > until]
        for target in far:
            announce(f"  {until} 밖이라 미룬다 — {target.link.run_id} "
                     f"{target.link.title[:30]} ({target.link.date})")
        todo = [t for t in todo if t.link.date <= until]
    if limit and len(todo) > limit:
        for extra_target in todo[limit:]:
            announce(f"  상한 {limit}편을 넘겨 미룬다 — "
                     f"{extra_target.link.subject}/{extra_target.link.run_id} "
                     f"{extra_target.link.title[:30]}")
        todo = todo[:limit]

    for index, target in enumerate(todo, 1):
        announce(f"[{index}/{len(todo)}] {target.link.subject}/{target.link.run_id} "
                 f"{(target.this_title or target.link.title)[:34]} — 만드는 중")
        try:
            ok, note = build_one(target, runs_dir, repo_root,
                                 model=model, timeout=timeout, extra=extra)
        except Exception as exc:                        # noqa: BLE001
            ok, note = False, f"{type(exc).__name__}: {exc}"
        if ok:
            target.state = DONE
            target.notes.append(f"덱을 만들었다 — {note}")
            announce(f"    끝났다 — {note}")
        else:
            target.state, target.reason = BLOCKED, f"빌드 실패: {note}"
            announce(f"    실패 — {note}")
    return targets


# ------------------------------------------------------------------ 큐


def save(targets: list[Target], path: Path) -> None:
    """이번 실행이 무엇을 봤는지. **사람이 읽는 자리다.**

    통째로 다시 쓴다. 그래서 **이 파일은 마지막 실행이 본 것만 든다** — 러너가
    `--run-id`로 한 편씩 부르므로 대개 한 줄뿐이다. 판정을 여기서 되읽지 마라;
    그 답은 편마다 자기 자리에 있다(`save_state`).

    한동안 `/prequiz` 스킬이 이걸 읽었는데 그 스킬은 2026-08-23에 지워졌다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "items": [target.as_row() for target in targets],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def save_state(target: Target, runs_dir: Path) -> Path | None:
    """이 편의 판정을 **그 편의 자리에** 적는다. 적었으면 그 경로.

    큐 파일(`save`)과 같은 값을 적지만 자리가 다르다. 큐는 한 파일이라 **나중에
    끝난 실행이 앞의 것을 지운다** — 일꾼이 둘이 된 뒤로는 두 편이 같은 초에
    덮어쓰고, 그 전에도 러너가 한 편씩 부르는 동안 늘 마지막 한 편만 남아 있었다
    (2026-08-31의 `runs/prequeue.json`에 한 줄뿐이었다).

    그 파일을 읽는 곳이 하나 있었다 — 러너의 `already_made`. 판정이 지워져 있으면
    **덱은 멀쩡한데 화면에 「덱을 못 만들었다」가 뜬다.**

    자리가 없는 편(`BLOCKED`)은 적을 곳이 없다. 그 편은 애초에 만들 자리를 못
    세운 것이라 판정할 산출물도 없다.
    """
    if not target.prev_run_id:
        return None
    run_dir = runs_dir / target.prev_run_id
    path = run_dir / STATE_NAME
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "subject": target.link.subject,
            "run_id": target.link.run_id,
            "prev_run_id": target.prev_run_id,
            "state": target.state,
            # **그때 본 링크다.** 이 값이 서버의 것과 다르면 판정도 낡은 것이다.
            "source": target.link.share_url,
            "reason": target.reason,
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return None
    return path


def state_of(runs_dir: Path, prev_run_id: str, subject: str, run_id: str) -> str:
    """그 편의 자리에 적힌 판정. 없거나 남의 것이면 빈 문자열.

    **자리를 나눠 쓰는 일이 있다**(`pre_target.json`의 `occupancy`와 같은 사정) —
    같은 교시에 다른 과목이 돌면 한 디렉터리를 두 강의가 쓴다. 그래서 적힌
    편이 묻는 편과 같은지 보고 답한다.
    """
    try:
        row = json.loads((runs_dir / prev_run_id / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(row, dict):
        return ""
    if row.get("run_id") != run_id or row.get("subject") != subject:
        return ""
    return str(row.get("state") or "")
