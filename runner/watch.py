"""매일 21:30, 새로 올라온 올해 필기를 찾아 덱을 만든다.

## 가운데가 더 이상 뚫려 있지 않다

한동안 워처는 prep까지만 하고 `runs/queue.json`을 남겼다. 문항을 만드는 것은
사람이 연 Claude Code 세션의 `/quiz`였고, 그 한 편이 53~72분 동안 세션의 컨텍스트를
통째로 먹었다.

지금은 `quizgen`가 모델이 필요한 자리마다 **빈 세션을 스스로 띄운다**
(`quizgen/session.py`). 그래서 워처가 한 편을 끝까지 만든다.

    스캔 · 최신 판 고르기 · 큐 쓰기        watch
    prep → ①② → 검증 → 재현 → 빌드        quizgen.run (하위 프로세스)
    계약 모양으로 옮기기                    runner.deck.contract

큐는 없어지지 않았다. `--build` 없이 부르면 **무엇을 만들지 보여 주기만** 한다 —
한 편이 수십 분이라 밤에 무엇이 돌지 먼저 보는 자리가 있어야 한다.

## 한 번에 한 편씩 만든다

quizgen 한 편이 이미 `--jobs 4`로 빈 세션 넷을 동시에 띄운다. 편을 겹쳐 돌리면
그 배수가 되어 노트북이 먼저 무릎을 꿇는다. prep만 돌리던 시절에는 편끼리 겹쳐
돌렸는데, 그때는 CPU 렌더가 전부였기 때문이다.

## 업로드는 여기서 하지 않는다

`publish`가 따로 한다. 두 자리에서 걸린다 — 편이 끝날 때 `runner done`이 그
편을, 하루 한 번 `scripts/nightly-publish.ps1`이 `publish --all`로 놓친 것을.
무엇이 나갈지는 `runner.gate`가 편마다 본다 — 막힌 편은 강의록만 나가고 덱은
미뤄진다. 무엇을 막고 무엇을 적기만 하는지는 그쪽 첫머리에 있다.

## 이미 만든 것을 다시 만들지 않는 방법

`runs/<run_id>/source.json`에 어느 파일의 몇 판으로 만들었는지 적어 둔다.
`runs/index.json`은 `lecture_id`로만 관리해서 v1으로 만든 뒤 v3이 올라온 경우를
구분하지 못한다 - 실제로 `260812_02`가 v1과 v3으로 두 번 올라왔다.

**그 표시를 찍는 길이 큐 밖에도 있어야 한다.** 예전에는 편이 끝날 무렵 `queue.json`이
이미 다시 쓰여 그 항목이 사라져 있는 일이 잦았고, 만든 13편 중 표시가 남은 것이 한
편뿐이었다. 지금은 `build_one()`이 끝나는 자리에서 바로 찍지만, `runner done`이
부르는 길도 남겨 둔다 — 손으로 만든 편과 옆 저장소에서 옮겨 온 편이 그리로 온다.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import deck, filenames, fingerprint
from .filenames import LectureFile

DEFAULT_ROOT = Path.home() / "SynologyDrive"

# 동기화가 끝나기 전 파일을 잡으면 잘린 PDF로 덱을 만든다. 마지막 수정이 이만큼
# 지난 것만 건드린다. 21:30 기준으로 그날 올라온 필기는 대부분 이미 안정돼 있다.
MIN_AGE_SECONDS = 10 * 60

# 하루 처리 상한. 병리학은 하루 3~5편이 올라온다.
# 넘치는 분량은 다음 날 자동으로 다시 잡힌다 - source.json 기준이기 때문이다.
#
# 2026-08-19에 관리자가 토큰이 모자라 2로 내렸다(6 → 3 → 2, 같은 날). 그날 큐는
# 6편을 잡고 7편을 상한으로 밀어냈는데, 그 6편을 다 돌릴 토큰이 없었다.
#
# **2026-09-15에 관리자가 4로 올렸다.** 그날 미생물학이 세 편 올라왔는데 둘만 잡히고
# `260915_02`·`_03`이 「내일 다시 잡힌다」로 밀렸다. 예습은 강의 전날 밤에 나가야
# 하므로 하루 밀리면 그 편은 예습 없이 강의를 듣게 된다.
#
# **이번에는 재고 올렸다.** 위 주석이 「편당 비용이 `run.report.json`에 남으므로 몇
# 편이 쌓이면 거기서 읽어 정하라」고 남겨 둔 것을 그대로 했다 — 그날 복습 10판이다.
#
#     편당 비용   중앙 $7.96 · 최대 $17.75
#     편당 시간   중앙 24분 · 최대 47분
#     4편이면     약 $32 · 94분
#
# 최대값이 중앙값의 두 배가 넘는다(`260914_03`이 $17.75). 넷이 다 그쪽이면 $70이므로
# **4는 안전한 값이 아니라 관리자가 고른 값이다.** 다시 모자라면 내리는 것이 맞다.
DEFAULT_MAX_ITEMS = 4

# 지문이 말한 상태 → 큐가 쓰는 사유. 사유가 「갱신」인 편에는 아래 `build_extra` 가
# `--revise` 를 실어 보낸다. **이 끈이 없어서 2026-09-03 에 세 편이 갇혔다** —
# 화면에는 「v2 갱신」이라고 찍고는 아무것도 안 만들었다.
REASON_OF = {
    fingerprint.ABSENT: "new",
    fingerprint.NEWER_VERSION: "newer_version",
    fingerprint.CONTENT_CHANGED: "content_changed",
}
UPDATED = ("newer_version", "content_changed")


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
    reason: str                      # 'new' | 'newer_version' | 'content_changed'
    # 파일명 괄호에서 뽑은 담당 교수. `PROFESSOR_STRATEGY`가 이걸 본다.
    professors: tuple[str, ...] = ()
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
    # 하루 상한에 밀린 것. **`skipped` 에 한 줄씩 이미 적히는데 따로 드는 이유**는
    # 그 줄이 다른 사유(동기화 대기·블럭 밖·빌드 실패)와 섞여 있어서 세어지지
    # 않기 때문이다. 큐가 줄고 있는지는 이 수가 날마다 어떻게 변하는지로만 안다.
    backlog: list[WorkItem] = field(default_factory=list)


# 족보 자리의 상태. **「없다」가 두 가지라 셋으로 가른다.**
#
# 2026-09-11 에 블럭이 미생물학으로 넘어갔는데 `runner jokbo 미생물학` 을 아무도
# 안 쳤다. 재료(`족보/2026/*.pdf`)는 있었다. 그동안 편마다 경고가 떴고 아무도
# 안 봤고, 세 편이 기출 0 으로 나갔고, `260911_03` 은 22.9분·$8.53 을 쓴 뒤
# **마지막 줄**에서 죽었다(`build.py` 가 기출 카드를 만들어 놓고 조각을 못 찾았다).
#
# 그때 화면에 뜬 것은 「족보가 없다」 한 가지였다. **한 줄이면 풀리는 것과 사람이
# 어찌할 수 없는 것이 같은 말로 나왔다는 것이 이 함정의 전부다.**
JOKBO_READY = "ready"      # 조각이 서 있다
JOKBO_UNCUT = "uncut"      # 원본은 있는데 안 잘랐다 — 명령 한 줄이면 풀린다
JOKBO_ABSENT = "absent"    # 원본이 없다 — 이 과목은 기출 없이 만든다


def jokbo_source_dir(root: Path, subject: str, year: str) -> Path:
    """과목 족보 원본이 사는 자리.

    **자르는 쪽과 세는 쪽이 같은 곳을 봐야 한다.** 이 경로가 `runner jokbo` 안에
    글자로 박혀 있었는데, 「잘렸는가」를 묻는 자리가 늘면서 둘이 갈릴 자리가 됐다.
    """
    return Path(root) / subject / "족보" / year


def jokbo_state(runs_dir: Path, subject: str,
                root: Path | None = None, year: str = "") -> str:
    """과목 족보가 어느 상태인가. `JOKBO_*` 중 하나.

    어느 조각을 어느 강의에 물릴지는 **여기서 정하지 않는다.** quizgen가 목차
    제목으로 대조한다 — 카드를 만들 때 본 조각과 뒷면에 붙이는 조각이 갈리면 안
    되므로 그 판단은 한 곳에만 있어야 한다. 여기서는 자리가 섰는지만 본다.

    `root` 를 안 주면 `UNCUT` 을 못 가른다 — 원본이 어디 있는지 모르기 때문이다.
    그때는 `ABSENT` 로 돌려준다. **덜 아는 쪽이 덜 막는다.**
    """
    if (deck.jokbo_dir(runs_dir, subject) / "index.json").is_file():
        return JOKBO_READY
    if root is not None and year:
        folder = jokbo_source_dir(root, subject, year)
        if folder.is_dir() and any(folder.glob("*.pdf")):
            return JOKBO_UNCUT
    return JOKBO_ABSENT


def jokbo_note(state: str, subject: str, runs_dir: Path | None = None) -> str:
    """그 상태를 사람에게 적어 주는 한 줄. 없으면 빈 문자열.

    **`READY` 에도 할 말이 있을 수 있다** — 컷은 서 있는데 원본이 그 뒤에 갈린 경우다.
    그때는 알리기만 한다. `jokbo_state` 가 넷째 상태를 만들지 않는 이유는 그것이
    **막을 일이 아니기** 때문이다. 갈린 원본으로 다시 자를지는 사람이 정한다.
    """
    if state == JOKBO_UNCUT:
        return ("과목 족보 원본은 있는데 아직 안 잘렸다 — "
                f"`python -m runner jokbo {subject}` 먼저")
    if state == JOKBO_ABSENT:
        return "이 과목은 족보 원본이 없다 — 기출 카드 없이 만들어진다"
    if (state == JOKBO_READY and runs_dir is not None
            and (stale := deck.cut_stale(deck.jokbo_dir(runs_dir, subject)))):
        return (f"족보 컷이 낡았다 — {stale}. 지금 컷으로도 만들어진다. "
                f"다시 자르려면 `python -m runner jokbo {subject}`")
    return ""


def _already_built(runs_dir: Path, run_id: str, item: LectureFile) -> str | None:
    """이미 만들었으면 None이 아닌 사유를 돌려준다.

    **판 번호만 보지 않는다.** `fingerprint` 가 내용 해시까지 본다 — 2026-09-04 에
    `260903_03` 의 v1 파일이 이름 그대로 내용만 갈렸고, 그 사이에 만든 덱이 아무
    검사도 안 걸렸다. 문지기(`publish._owns`)도 같은 값을 본다.
    """
    verdict = fingerprint.compare(runs_dir / run_id, item.path, item.version)
    if verdict.state == fingerprint.ABSENT or verdict.stale:
        return None
    where = (verdict.recorded or {}).get("where", "")
    return f"이미 만듦 ({where}{' · 내용 해시까지 같다' if verdict.by_hash else ''})"


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
    only_run_id: str = "",
) -> Queue:
    """`since`~`until`은 이번 블럭의 구간이다(`runner.blocks`).

    이게 없으면 `필기/<올해>` 폴더가 있는 과목을 전부 훑고 날짜 오름차순으로
    자르기 때문에, 학기가 바뀌어도 지난 학기 필기가 먼저 걸린다.

    `only_run_id`는 **사람이 그 편을 지목한 것이다**(캘린더의 「Main-Quiz 덱
    만들기」). 그래서 쓸기의 체 셋을 지난다 — 블럭 창, 하루 상한, 그리고 이미
    만들었다는 표시(`source.json`). 마지막 것을 지나는 이유는 **표시는 있는데
    덱이 없는 자리가 실제로 있기 때문이다**(빌드가 중간에 죽은 편). 사람이 다시
    누르는 편이 바로 그 편이다. 덱이 이미 있는지는 부르는 쪽이 본다
    (`runner.__main__.run_watch_one`).

    동기화 대기(`min_age_seconds`)는 지나지 않는다. 반쯤 올라온 PDF로 만든 덱은
    지목해서 만들었든 쓸어서 만들었든 똑같이 잘려 있다.
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
        jokbo = jokbo_state(runs_dir, subject, root, this_year)
        # **과목마다 한 번만 묻는다.** `READY` 일 때 원본 해시를 다시 뜨므로
        # 강의마다 물으면 한 과목 30편이면 30번 뜬다.
        jokbo_msg = jokbo_note(jokbo, subject, runs_dir)

        for item in this_files:
            run_id = run_ids[item.uid]
            pdf = item.path

            if only_run_id:
                if run_id != only_run_id:
                    continue
            else:
                # 블럭 밖은 세기만 한다. 한 줄씩 적으면 지난 학기 수십 편이 보고를 덮는다.
                if (since and item.date < since) or (until and item.date > until):
                    outside[subject] = outside.get(subject, 0) + 1
                    continue

                if _already_built(runs_dir, run_id, item):
                    continue

            age = now - pdf.stat().st_mtime
            if age < min_age_seconds:
                skipped.append(
                    f"{subject}/{run_id} {item.title[:26]} — 올라온 지 "
                    f"{int(age / 60)}분. 동기화 중일 수 있어 다음 차례로")
                continue

            verdict = fingerprint.compare(runs_dir / run_id, pdf, item.version)
            reason = REASON_OF.get(verdict.state, "new")
            notes: list[str] = []
            if verdict.note:
                notes.append(verdict.note)
            if jokbo_msg:
                notes.append(jokbo_msg)

            items.append(WorkItem(
                subject=subject, run_id=run_id, key=item.key, date=item.date,
                title=item.title, this_pdf=str(pdf), this_version=item.version,
                reason=reason, professors=tuple(item.professors),
                # 예습 짝이 이미 세워 둔 이름이 있으면 그것을 따른다. 파일명과
                # 시간표가 띄어쓰기 하나로 갈리면 두 덱이 형제로 안 선다.
                lecture=deck.calendar_node(runs_dir, run_id, item.title, deck.MAIN,
                                           item.professors, subject=subject),
                notes=notes,
            ))

    for subject, count in sorted(outside.items()):
        skipped.append(f"{subject} {count}편 — 이번 블럭({since}~{until}) 밖")

    items.sort(key=lambda w: (w.date, w.run_id))
    backlog: list[WorkItem] = []
    if not only_run_id and len(items) > max_items:
        backlog = items[max_items:]
        for extra in backlog:
            skipped.append(
                f"{extra.subject}/{extra.run_id} {extra.title[:26]} — "
                f"하루 상한 {max_items}편 초과. 내일 다시 잡힌다")
        items = items[:max_items]

    return Queue(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        items=items, skipped=skipped, warnings=warnings, backlog=backlog,
    )


PROFESSOR_STRATEGY = {
    # 최민호 — 강의록에 없는 것을 강의 중 설명해 낸다는 이야기가 있어 필기를 무겁게 본다.
    "최민호": "필기",
}


def strategy_for(professors) -> str | None:
    """이 편의 담당 교수에게 걸린 전략. 없으면 None.

    **이 표는 실측이 아니라 관리자의 판단이다.** 2026-09-07에 그 이야기를 2025 기출로
    재 봤고 **지지되지 않았다** — 최민호의 강의 7편 20문항에서 「강의록에 없다」가 0개였고,
    지면을 눈으로 본 판정에서도 0.83으로 대조군(송현범 0.80 · 홍성태 0.67)보다 높았다.
    이 연구에서 나온 유일한 `off_slide`는 다른 교수의 문항이었다.

    그런데도 이쪽으로 가는 것은 **안전 쪽으로 기운 선택**이다. 나중에 이 표를 보고
    「실측으로 정해졌다」고 읽지 마라. 되돌리는 것도 관리자만 한다.

    사람이 `--strategy`로 지정했으면 그쪽이 이긴다(`build_extra`).
    """
    for name in professors or ():
        if name in PROFESSOR_STRATEGY:
            return PROFESSOR_STRATEGY[name]
    return None


def build_extra(item: WorkItem, extra: list[str] | None = None) -> list[str]:
    """이 편에만 붙는 깃발. **판이 갈린 편에는 `--revise` 가 실린다.**

    안 실으면 `quizgen.run` 이 산출물이 있는 단계를 전부 건너뛰어(`runbase.step`)
    **아무것도 안 만들고 `source.json` 에만 새 판이 찍힌다.** 2026-09-03 에 세 편이
    그 상태였고, 그러면 쓸기는 「이미 만듦」·문지기는 「옛 판이라 못 내보낸다」가 되어
    그 편이 갇힌다.

    `--force`(통째로 다시)가 아니라 `--revise`(갈린 자리만)인 이유는 복습 이력이다 —
    통째로 다시 만들면 질문 글자가 달라져 그 편 카드의 이력이 거의 다 죽는다
    (`260903_05` 실측: 53장 중 7장만 살아남았다).
    """
    flags = list(extra or [])
    if item.reason in UPDATED and "--force" not in flags and "--revise" not in flags:
        flags.append("--revise")
    # 교수별 전략. **사람이 지정한 것을 덮지 않는다** — `--strategy`가 이미 있으면
    # 그건 그 편을 지목한 사람의 판단이고, 이 표보다 뒤에 온 것이다.
    if "--strategy" not in flags and (picked := strategy_for(item.professors)):
        flags += ["--strategy", picked]
    return flags


def build_one(item: WorkItem, runs_dir: Path, repo_root: Path, *,
              model: str = "", timeout: int = deck.DEFAULT_TIMEOUT,
              extra: list[str] | None = None) -> tuple[bool, str]:
    """한 편을 끝까지 만든다. (됐나, 사람이 볼 말)

    족보 조각을 손으로 물려 주지 않는다. `runner jokbo <과목>`이 잘라 둔
    `runs/_jokbo/`를 quizgen가 목차 제목으로 스스로 대조한다 — 카드를 만들 때 본
    조각과 뒷면에 붙이는 조각이 갈리면 안 되기 때문에 그 판단이 한 곳에 있어야 한다.

    한 편이 죽어도 나머지는 계속 간다. 하룻밤 분량이 한 편 때문에 통째로
    날아가면 안 된다.
    """
    result = deck.run_main(
        pdf=item.this_pdf, run_id=item.run_id, subject=item.subject,
        lecture=item.lecture or item.title, title=item.title,
        runs_dir=runs_dir, repo_root=repo_root,
        model=model, timeout=timeout, extra=build_extra(item, extra))
    if not result.ok:
        return False, f"{result.error} (로그: {result.log})"

    try:
        meta = deck.contract(result.run_dir, item.run_id, item.title, deck.MAIN,
                             deck.version_of(result.work))
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

    quizgen 한 편이 이미 빈 세션 넷을 동시에 띄우므로, 편을 겹치면 그 배수가 된다.
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
    빌드가 끝난 뒤 사람이 확인하고 부르는 `runner done`이 전부 여기로 온다.
    """
    if not pdf.exists():
        return False
    parsed = filenames.parse(pdf)
    if parsed is None:
        return False
    (runs_dir / run_id).mkdir(parents=True, exist_ok=True)
    (runs_dir / run_id / "source.json").write_text(
        json.dumps(fingerprint.record(pdf, parsed.version), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return True


def save(queue: Queue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at": queue.generated_at,
        "items": [asdict(i) for i in queue.items],
        "skipped": queue.skipped,
        "warnings": queue.warnings,
        "backlog": [asdict(i) for i in queue.backlog],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
