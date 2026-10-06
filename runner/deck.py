"""quizgen를 부르고, 그 산출물을 서버가 아는 모양으로 옮긴다.

**로컬 러너와 파이프라인의 유일한 접점이다.** `runner/`의 다른 모듈은 quizgen를
직접 부르지 않고 여기를 지난다. 계약이 바뀌면 `docs/artifact-contract.md`와 이
파일이 함께 움직인다.

## 왜 한 명령인가

예전 파이프라인은 가운데가 뚫려 있었다 — 코드가 prep까지 하고, `runs/queue.json`을
남기고, **사람이 연 Claude Code 세션**이 `/quiz`를 돌려 문항을 만들고, 다시 코드가
빌드했다. 그래서 편당 53~72분이 들었고 그 시간이 세션의 컨텍스트를 통째로 먹었다.

quizgen는 모델이 필요한 자리마다 `codex exec`로 세션을 띄운다
(`quizgen/session.py`). 저작은 파일 도구를 사용하며, 재현 검사는 도구·이력·
사용자 설정을 끈 독립 세션으로 실행한다. 그러니 이 자리에서 할 일은 하위 프로세스를 띄우는 것뿐이고,
**부르는 쪽의 컨텍스트는 한 글자도 쓰이지 않는다.**

## 작업 폴더와 덱 ID를 나눠 둔 이유

quizgen는 기본적으로 `out/<id>/`에서 일하고 `<id>`는 파일명 앞머리에서 딴
`p260820_03`이다. 서버 계약의 기본키는 `260820_03`(`run_id`)이라 둘이 다르다.

둘을 억지로 맞추지 않는다. **`<id>`는 guid의 씨앗이다** — 바꾸면 Anki가 이미 받아
간 카드를 전부 새 노트로 보고, 학생의 복습 이력이 통째로 끊긴다. 그래서 폴더만
`runs/<run_id>/`로 옮기고 ID는 quizgen가 쓰던 그대로 `p<run_id>`를 준다.

## 무엇을 만들어 두는가

quizgen가 남기는 것(`run.config.json`·`items.reproduced.json`·`suspects.json`·
`.apkg`)은 파이프라인 안쪽이라 서버가 보지 않는다. `contract()`가 그것을 읽어
서버가 아는 셋으로 옮긴다.

    run.meta.json / pre_run.meta.json   덱 하나의 요약. 관리자 화면과 gate가 읽는다
    pre_items.final.json                웹에서 푸는 예습 카드
    slides/<run_id>_s042.png            카드 뒷면 근거 슬라이드

슬라이드는 **예습 쪽만** 만든다. 그 이미지를 읽는 곳이 서버에 한 군데뿐이고
(웹 예습 풀이의 근거 그림) 편당 12~27MB이기 때문이다. 복습 덱의 이미지는 apkg
안에 이미 들어 있다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from quizgen import build as quizgen_build

from . import runlayout

# 웹에서 풀 수 있는 카드. 그림 카드는 앞면이 이미지라 텍스트만으로는 물음이
# 성립하지 않는다("이 조직은 어느 장기이며…"). apkg에는 그대로 들어 있다.
WEB_FORMATS = ("basic", "cloze", "ox")

# `{{c1::답::힌트}}`. 웹은 Anki가 아니므로 빈칸으로 펴서 보여 준다.
# 빈칸 표기는 `quizgen.site_edits.RE_CLOZE` 하나다 — 사이트에서 고친 빈칸 카드를
# 덱으로 되돌리려면 펴는 규칙이 두 곳에 살면 안 된다.
RE_CLOZE = quizgen_build.site_edits.RE_CLOZE

# quizgen가 media/에 남기는 슬라이드 렌더. 앞머리는 파이프라인마다 달라서
# (복습은 강의 ID, 예습은 `lecture`) 번호만 본다.
RE_SLIDE_PNG = re.compile(r"slide(\d+)\.png$", re.IGNORECASE)

MAIN, PRE = "main", "pre"

# 한 편이 이만큼 안에 안 끝나면 버린다. 실측 상한이 편당 72분이었고 quizgen는
# 그보다 짧지만, 빈 세션 하나가 멈춰 서면 밤을 통째로 먹는다.
DEFAULT_TIMEOUT = 3 * 3600


def deck_id(run_id: str) -> str:
    """`260820_03` → `p260820_03`. guid의 씨앗이라 한 번 정하면 안 바꾼다."""
    return f"p{run_id}"


def deck_node(run_id: str, title: str,
              professors: tuple[str, ...] | list[str] = ()) -> str:
    """덱 나무의 가운데 마디. **파일 이름과 같은 꼴이다.**

        병리학::[260814_01] 급성 염증의 병태 생리(고재문)::강의록

    Anki 안에서 보는 이름과 받아 둔 파일 이름이 다르면, 둘을 맞춰 보는 일이 사람
    몫이 된다. 그래서 한 함수가 둘 다 짓는다(`apkg_name`이 여기에 꼬리만 단다).

    **한동안 교수를 일부러 뗐다.** 교수가 바뀌는 해에 노드가 갈린다는 이유였는데,
    `run_id`가 들어온 지금은 어차피 해마다 갈린다 — 그리고 갈리는 편이 맞다.
    번호가 없어 `260820_01`과 `260820_02`(같은 제목의 연강)가 한 노드로 뭉개지고
    있었다.

    예습·강의록·기출이 한 노드 아래 모이는 것은 **두 갈래가 같은 제목을 받을 때만**
    성립한다. 이 함수는 받은 제목을 다듬을 뿐이라 갈린 것을 붙여 주지 못한다 —
    한동안 그 자리가 뚫려 있었고 2026-09-03 실측에서 짝이 선 20쌍 중 5쌍이 어긋나
    있었다. 지금은 `pinned_node`가 못을 박는다.
    """
    clean = RE_FS_UNSAFE.sub("", unicodedata.normalize("NFC", title))
    clean = " ".join(clean.split()).rstrip(". ")
    here = [p for p in professors if p and p not in clean]
    if here:
        clean += f"({', '.join(here)})"
    return (f"[{run_id}] {clean}".strip() if clean else f"[{run_id}]")[:120]


# 예습 자리가 **어느 올해 강의를 위해** 도는지. `prequeue`가 적고 여기가 읽는다.
TARGET_NAME = "pre_target.json"

# Windows가 파일명에 못 쓰는 글자. 강의 제목에 들어온 적은 아직 없지만, 하나
# 들어오면 그 편만 조용히 빌드가 깨진다.
RE_FS_UNSAFE = re.compile(r'[\\/:*?"<>|]')


def apkg_name(node: str, kind: str) -> str:
    """덱 파일 이름. **덱 나무의 가운데 마디에 갈래 꼬리만 단다.**

        [260820_03] 소아질환의 병태생리(2) 소아기 특이 질환 1(김은나).apkg
        [260825_01] 종양의 분자생물학(1)(전윤경) 예습.apkg

    받아 보는 사람이 그 자리에서 어느 강의인지 알아야 한다. `p260820_03.apkg`는
    파이프라인의 이름이지 사람의 이름이 아니다.

    **`deck_id`는 안 바꾼다.** 그쪽이 guid의 씨앗이라 바꾸면 Anki가 이미 받아 간
    카드를 전부 새 노트로 본다. 파일 이름은 guid에 안 들어간다.

    괄호 안 교수를 붙이는 자리는 `deck_node`다. 필기에서 온 제목이면 이미 들어 있고
    (`LectureFile.title`은 파일명에서 뽑은 표시용 원문이다) 시간표에서 온 제목에는
    없어서, 거기서 한 번만 가른다.

    덱 나무의 가운데 마디와 **같은 글자를 쓴다**(`deck_node`). Anki 안에서 보는 이름과
    받아 둔 파일 이름이 다르면 둘을 맞춰 보는 일이 사람 몫이 된다. 그래서 마디를
    여기서 다시 짓지 않고 받아만 온다 — 한동안 이 함수가 따로 짓고 있었고, 그동안
    파일 이름만 옛 규칙으로 남는 자리가 생겼다(`calendar_name`).
    """
    # 예습 덱은 파일에서만 꼬리를 단다. 덱 나무에서는 마지막 마디가 이미 `::예습`이다.
    return f"{node} 예습" if kind == PRE else node


def pre_seat_of(runs_dir: Path, run_id: str, subject: str = "") -> Path | None:
    """올해 강의 `run_id`의 예습이 도는 **작년 자리**.

    예습 산출물은 작년 run 디렉터리에 있고 거기 적힌 `run_id`가 올해 것이다. 그래서
    올해 쪽에서 자기 짝을 찾으려면 `runs/`를 훑는 수밖에 없다
    (`agent.prev_run_of`가 같은 훑기를 단계 로그를 찾는 데 쓴다).

    **같은 교시를 두 과목이 나눠 쓸 수 있다.** 둘이 걸리면 아무것도 돌려주지 않는다 —
    남의 강의 이름이 붙는 것보다 갈려 있는 편이 낫다.
    """
    hits = []
    for target in sorted(runs_dir.glob(f"*/{TARGET_NAME}")):
        row = _load(target)
        if not isinstance(row, dict) or str(row.get("run_id") or "") != run_id:
            continue
        if subject and row.get("subject") and str(row["subject"]) != subject:
            continue
        hits.append(target.parent)
    return hits[0] if len(hits) == 1 else None


def node_of(deck_name: str) -> str:
    """덱 전체 이름에서 가운데 마디만. 마디에는 `::`가 못 들어간다(`RE_FS_UNSAFE`)."""
    parts = [p for p in str(deck_name or "").split("::") if p]
    if parts and parts[-1] == "예습":
        parts.pop()
    return parts[-1] if parts else ""


def pinned_node(runs_dir: Path, run_id: str, kind: str, subject: str = "") -> str:
    """**이미 나간 예습 덱이 쓰고 있는 마디.** 없으면 빈 문자열.

    ## 왜 못을 박는가

    두 갈래가 제목을 다른 데서 딴다 — 예습은 시간표 칸, 복습은 올해 필기의 파일명.
    사람이 손으로 적는 두 글이라 띄어쓰기 하나로 갈린다. 2026-09-03 실측에서 짝이
    선 20쌍 중 5쌍이 어긋나 있었다.

        예습  [260831_01] 기생충학 총론 (1)(최민호)      ← 시간표
        복습  [260831_01] 기생충학 총론1(최민호)         ← 파일명

        예습  [260831_05] 연충란(최민호, 신은희, 여선주)
        복습  [260831_05] 감염의 기초 실습 1 - 연충란

    갈리면 Anki에서 형제로 안 서고 각자 나무를 하나씩 만든다.

    **`pre_target.json`을 보고 맞추는 것으로는 안 된다.** 그 파일은 돌 때마다 다시
    쓰이는데, 올해 필기가 들어오는 순간 출처가 시간표에서 파일명으로 갈아탄다
    (`publish.plan_subject` — 필기가 없을 때만 `ahead`의 시간표 칸을 쓴다). 위 다섯
    편의 `pre_target.json`은 지금 전부 파일명 쪽을 들고 있고, 이미 나간 예습 덱만
    시간표 이름을 들고 있다.

    그래서 **이미 나간 덱의 이름에 못을 박는다.** 그 덱은 학생의 Anki에 이미 들어가
    있어서, 뒤늦게 이름을 바꾸면 카드가 옛 마디에 남고 새 마디가 옆에 하나 더 선다.

    이름을 정말 바꿔야 하면 그 자리의 `pre_run.meta.json`을 지우고 두 갈래를 다시
    구우면 된다 — 못은 그 파일 하나에 박혀 있다.

    **못이 이 강의의 것인지는 마디에 박힌 `run_id`로 본다.** 짝이 바뀌면 한 자리가
    지난번 강의의 덱을 그대로 안고 있다(`prequeue --force`) — 그때 못을 그냥 믿으면
    남의 강의 이름으로 굽고, `rebuild`가 옛 파일까지 지운다.
    """
    seat = runs_dir / run_id if kind == PRE else pre_seat_of(runs_dir, run_id, subject)
    if seat is None:
        return ""
    row = _load(seat / "pre_run.meta.json")
    node = node_of(row.get("deck_name", "")) if isinstance(row, dict) else ""
    if kind == PRE:
        # 예습의 `run_id`는 작년 것이고 마디에는 올해 것이 박힌다. 지금 겨냥한
        # 올해 강의가 무엇인지는 `pre_target.json`만 안다.
        target = _load(seat / TARGET_NAME)
        run_id = str((target or {}).get("run_id") or run_id) if isinstance(target, dict) else run_id
    return node if node.startswith(f"[{run_id}]") else ""


def calendar_of(run_dir: Path, run_id: str, title: str, kind: str,
                professors: tuple[str, ...] | list[str] = ()) -> tuple:
    """이 자리가 이름을 어디서 가져오는가. `(run_id, 제목, 교수)`.

    **예습은 작년 필기로 만들지만 이름은 올해 강의로 선다.** 학생은 캘린더를 보고
    예습하므로 작년 날짜와 작년 제목이 붙은 이름은 어느 강의의 것인지 안 보인다.
    그 올해 강의가 무엇인지는 `prequeue`가 `pre_target.json`에 적어 두었다.

    이 조회를 이름 짓는 함수마다 따로 두지 않는다 — 한동안 파일 이름만 올해로 서고
    **덱 이름은 작년으로 서 있었다.** 둘이 같은 자리에서 갈라져 나가야 안 어긋난다.
    """
    if kind == PRE:
        target = _load(run_dir / TARGET_NAME)
        if isinstance(target, dict):
            run_id = str(target.get("run_id") or run_id)
            title = str(target.get("title") or title)
            professors = target.get("professors") or professors
    return run_id, title, professors


def calendar_node(runs_dir: Path, run_id: str, title: str, kind: str,
                  professors: tuple[str, ...] | list[str] = (),
                  subject: str = "") -> str:
    """이 자리에서 나올 덱의 **가운데 마디**. 아직 자리가 없어도 부를 수 있다.

    `run_dir`가 아니라 `runs_dir`를 받는다 — 쓸기가 덱을 만들기 전에 이름을 세우고
    (`watch.build_queue`) 그때는 올해 자리가 아직 안 생겼기 때문이다.
    """
    pinned = pinned_node(runs_dir, run_id, kind, subject)
    if pinned:
        return pinned
    rid, name, profs = calendar_of(runs_dir / run_id, run_id, title, kind, professors)
    return deck_node(rid, name, profs)


def calendar_name(run_dir: Path, run_id: str, title: str, kind: str,
                  professors: tuple[str, ...] | list[str] = (),
                  subject: str = "") -> str:
    """이 자리에서 나올 덱의 파일 이름."""
    return apkg_name(calendar_node(run_dir.parent, run_id, title, kind,
                                   professors, subject), kind)


def calendar_deck(run_dir: Path, run_id: str, title: str, kind: str, subject: str,
                  professors: tuple[str, ...] | list[str] = ()) -> str:
    """이 자리에서 나올 덱의 **전체 이름**. `<과목>::<가운데 마디>[::예습]`.

    마지막 마디(`::강의록`·`::기출`)는 복습 빌드가 카드의 기원을 보고 스스로 단다.
    예습은 덱이 하나뿐이라 여기서 붙인다.
    """
    node = calendar_node(run_dir.parent, run_id, title, kind, professors, subject)
    name = f"{subject}::{node}" if subject else node
    return f"{name}::예습" if kind == PRE else name


MATERIALS = "_materials"      # 과목 공용 재료. 지금은 족보 컷뿐이다
LEGACY_MATERIALS = "_jokbo"   # 2026-09-15 개명 전 이름


def subject_dir(runs_dir: Path, subject: str) -> Path:
    """그 과목의 재료가 사는 폴더. **판 폴더들의 부모다.**

    과목마다 따로 두는 이유는 quizgen 가 조각을 **강의 제목으로** 대조하기 때문이다 —
    제목만 보면 과목이 다른 두 강의가 서로의 족보를 물어 갈 수 있다.

    **옛 이름(`_jokbo`)도 본다.** 개명 전에 자른 컷이 아직 거기 있을 수 있고, 편
    111개의 `run.config.json` 이 그 경로를 적고 있다(`--resume` 이 되살린다).
    """
    new = Path(runs_dir) / MATERIALS / subject
    if new.is_dir():
        return new
    old = Path(runs_dir) / LEGACY_MATERIALS / subject
    return old if old.is_dir() else new


def jokbo_dir(runs_dir: Path, subject: str) -> Path:
    """**지금 쓸 족보 컷의 폴더.** `--jokbo-dir` 로 넘어가는 값이다.

    새 모양에서는 `_materials/<과목>/<판>/` 이고 `current` 가 어느 판인지 말한다.
    옛 모양에서는 조각이 과목 폴더에 그대로 널려 있어 그 폴더 자신이다 —
    `cutmark.resolve` 가 둘을 가른다.

    **자르는 쪽은 이 함수를 쓰지 않는다.** 자를 때는 과목 폴더를 줘야 하고
    (`subject_dir`), 판 폴더는 `quizgen.jokbo` 가 그 아래에 만든다 — 과목 이름을
    폴더 이름에서 읽기 때문이다.
    """
    from quizgen import cutmark
    return cutmark.resolve(subject_dir(runs_dir, subject))


def cut_line(cut_dir: Path) -> str:
    """그 컷의 판을 사람이 읽는 한 줄. **`runner/` 에서 판을 묻는 자리는 여기다.**

    판을 적는 쪽은 `quizgen.cutmark` 이고, 이 파일이 quizgen 을 부르는 유일한
    자리라서 (`runner/CLAUDE.md`) 묻는 것도 여기를 지난다.
    """
    from quizgen import cutmark
    return cutmark.describe(cut_dir)


def cut_stale(cut_dir: Path) -> str | None:
    """원본 족보가 그 컷보다 새것이면 사람이 읽을 한 줄, 아니면 None.

    **막는 데 쓰지 마라.** 원본이 갈렸다고 지금 컷이 못 쓰는 것이 아니다 — 다시
    자르면 되는 일이고 그 판단은 사람이 한다(`quizgen/cutmark.stale_source`).
    """
    from quizgen import cutmark
    try:
        return cutmark.stale_source(cut_dir)
    except OSError:
        return None            # 원본이 네트워크 드라이브에 있다. 못 읽으면 말을 안 한다


@dataclass
class Result:
    ok: bool
    run_dir: Path            # 강의 폴더. 계약과 문지기가 보는 자리다
    log: Path
    error: str = ""
    tail: list[str] = field(default_factory=list)
    # 이번 실행이 실제로 쓴 자리. 옛 모양에서는 `run_dir` 과 같다.
    work: Path | None = None


# ------------------------------------------------------------------ 실행


def new_work_dir(run_dir: Path, kind: str = MAIN, resume: bool = False) -> Path:
    """이번 실행이 쓸 자리. 새 모양이면 판 폴더 하나, 옛 모양이면 강의 폴더.

    **`--resume` 은 새 판을 열지 않는다.** 이어 돌리는 것은 그 시도를 계속하는
    것이므로 같은 자리를 줘야 한다 — 새 판을 열면 앞 단계 산출물이 안 보여
    prep 부터 다시 돈다(30분·$12).

    옛 모양(`WRITES_ATTEMPT_DIRS` 가 거짓)에서는 강의 폴더를 그대로 준다. 그래서
    이 함수를 끼워 두어도 지금 동작이 한 글자도 안 바뀐다.
    """
    run_dir = Path(run_dir)
    layout_kind = runlayout.PREQUIZ if kind == PRE else runlayout.MAIN
    if not runlayout.WRITES_ATTEMPT_DIRS:
        return run_dir
    if resume:
        return runlayout.work_dir(run_dir, layout_kind)
    root = runlayout.attempt_root(run_dir, layout_kind)
    want = runlayout.new_version()
    taken = set(runlayout.versions(run_dir, layout_kind))
    base, n = want, 1
    while want in taken:
        n += 1
        want = f"{base}.{n}"
    return root / want


def version_of(work: Path | None) -> str | None:
    """이번 실행이 쓴 판의 이름. 옛 모양이면 `None`.

    **계약을 쓸 때 이것을 넘겨야 한다.** 안 넘기면 `contract` 가 `work_dir` 에게
    「어느 판이냐」를 되묻고, `work_dir` 은 `run.meta.json` 이 적어 둔 **이미 배포된
    판**을 먼저 고른다(`_published_version`). 그러면 **한 번 배포된 편은 다시 구워도
    옛 판이 계속 나간다** — 새 판은 폴더에만 남고 아무도 안 본다.

    2026-09-15 에 `260914_03` 이 그랬다. 두 번 다시 구웠는데 계약은 내내 첫 판
    (`260915-1303`)을 가리켰고, 그 판의 결함 카드(`c041`)로 문지기에 걸렸다.
    새 판에는 그 결함이 없었다.
    """
    if work is None:
        return None
    name = Path(work).name
    return name if runlayout.RE_VERSION.match(name) else None


def revise_from(run_dir: Path, work: Path, extra: list[str] | None) -> list[str]:
    """`--revise` 로 도는 실행에 **옛 판이 어디인지** 알려 준다.

    갈아 끼우기는 옛 판의 `prep.json` 과 카드를 읽어야 성립한다. 옛 모양에서는 그것이
    강의 폴더에 그대로 있어서 `--out` 만 주면 됐는데, **판 폴더로 가르고 나서는 이번
    판이 빈 폴더다.** 그러면 `revise.compare` 가 「옛 판의 산출물이 없다」로 읽고
    통째로 다시 만들기로 내려간다 — 2026-09-15 에 `260831_02` 가 그렇게 죽었다.

    통째로 다시 만들면 **질문 글자가 달라져 복습 이력이 죽는다**(`260903_05` 실측:
    53장 중 7장). `--revise` 가 있는 이유가 그것이므로 조용히 그리로 내려가면 안 된다.

    어느 판을 옛 판으로 삼는가는 `runlayout.work_dir` 이 답한다 — **지금 나가는 덱을
    만든 시도**다. 이력이 이어져야 할 카드가 그 판의 것이다.
    """
    if not any("--revise" in a for a in (extra or ())):
        return []
    work = Path(work).resolve()
    picked = runlayout.work_dir(run_dir, runlayout.MAIN)
    if picked.resolve() == work:
        return []                      # 옛 모양이거나 `--resume` — 이미 그 자리다
    if _has_cards(picked):
        return ["--revise-from", str(picked)]
    # **고른 판에 카드가 없을 수 있다.** `work_dir` 의 ③(제일 새 판)은 `run.config.json`
    # 만 보는데, 전략 판정까지 갔다 죽은 실행이 그 파일을 이미 써 놓는다. 2026-09-15 에
    # 바로 그런 폴더가 생겼다 — 카드 없이 `prep.json` 과 설정만 있는 판이다.
    # 그것을 옛 판으로 주면 들여올 것이 없어 갈아 끼우기가 헛돈다.
    for version in reversed(runlayout.versions(run_dir, runlayout.MAIN)):
        cand = runlayout.attempt_root(run_dir, runlayout.MAIN) / version
        if cand.resolve() != work and _has_cards(cand):
            return ["--revise-from", str(cand)]
    return []                          # 카드를 가진 판이 없다 — 통째로 만드는 것이 맞다


def _has_cards(work: Path) -> bool:
    """갈아 끼울 카드가 실제로 있는 판인가. `revise.source_cards` 와 같은 자리를 본다."""
    return any((work / name).exists() for name in
               ("items.reproduced.json", "items.checked.json", "items.raw.json"))


def _spawn(argv: list[str], run_dir: Path, repo_root: Path, timeout: int,
           log_name: str, work: Path | None = None) -> Result:
    """하위 프로세스로 띄우고 출력을 로그로 받는다.

    화면으로 흘리지 않는 이유는 한 편이 수십 분이고 밤에도 돌기 때문이다. 끝난
    뒤 꼬리만 사람에게 보여 주고, 전체는 로그에 남는다.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    # **로그는 강의 폴더에 둔다.** 판마다 갈라 놓으면 한 편이 왜 죽었는지 찾으려고
    # 판을 뒤져야 한다. 사람이 보는 것은 「이 편이 어떻게 됐나」다.
    log = run_dir / log_name
    if work is not None:
        work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    with log.open("a", encoding="utf-8") as sink:
        sink.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} "
                   f"{' '.join(argv[1:])}\n")
        sink.flush()
        try:
            done = subprocess.run(argv, stdout=sink, stderr=subprocess.STDOUT,
                                  cwd=str(repo_root), env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return Result(False, run_dir, log, f"{timeout // 60}분 안에 끝나지 않았다",
                          work=work or run_dir)

    tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
    if done.returncode != 0:
        return Result(False, run_dir, log, f"quizgen가 {done.returncode}로 끝났다", tail,
                      work=work or run_dir)
    return Result(True, run_dir, log, tail=tail, work=work or run_dir)


def run_main(*, pdf: str | Path, run_id: str, subject: str, lecture: str, title: str = "",
             runs_dir: Path, repo_root: Path, note: str = "", model: str = "",
             timeout: int = DEFAULT_TIMEOUT, extra: list[str] | None = None) -> Result:
    """기존 호출자에게 전환을 알리고 새 quizgen 생성을 막는다."""
    run_dir = runs_dir / run_id
    return Result(False, run_dir, run_dir / "pipeline.log",
                  "Main Quiz는 Quizbank로 전환되었습니다. 웹에서 ChatGPT 답을 저장하세요.")


def run_pre(*, pdf: str | Path, run_id: str, subject: str, lecture: str, note: str,
            runs_dir: Path, repo_root: Path, hint: str = "", model: str = "",
            timeout: int = DEFAULT_TIMEOUT, extra: list[str] | None = None) -> Result:
    """예습 덱 한 편. **작년 필기로 만들므로 `run_id`도 작년 것이다.**

    `--lecture`를 올해 강의명으로 주는 것이 중요하다. 안 주면 덱의 가운데 마디가
    작년 파일제목이 되어 복습 덱과 다른 노드에 선다.
    """
    run_dir = runs_dir / run_id
    work = new_work_dir(run_dir, PRE, resume=any("--resume" in a for a in (extra or [])))
    argv = [sys.executable, "-m", "quizgen.prequiz.run", str(pdf),
            "--out", str(work), "--id", deck_id(run_id),
            "--subject", subject, "--lecture", lecture, "--note", note,
            "--jokbo-dir", str(jokbo_dir(runs_dir, subject)),
            "--schema-dir", str(runs_dir / "_prequiz_schema"),
            "--check-dir", str(runs_dir / "_image_check"),
            # 이름은 **올해 강의**로 선다. 그게 무엇인지는 `pre_target.json`이 안다.
            "--apkg-name", calendar_name(run_dir, run_id, lecture, PRE)]
    if hint:
        argv += ["--hint", hint]
    if model:
        argv += ["--model", model]
    argv += extra or []
    return _spawn(argv, run_dir, repo_root, timeout, "prequiz.log", work=work)


def cut_jokbo(pdf: Path, out_dir: Path, repo_root: Path,
              practical: list[Path] | None = None,
              older: list[Path] | None = None) -> int:
    """과목 족보 PDF를 강의별 조각으로 자른다. `quizgen.jokbo` 를 그대로 부른다.

    학기당 과목당 한 번이라 사람이 지켜보는 명령이다. 그래서 `_spawn` 과 달리
    출력을 로그로 삼키지 않고 화면으로 흘린다. 돌려주는 것은 종료 코드뿐이고,
    산출물이 제대로 나왔는지는 부르는 쪽이 본다.
    """
    argv = [sys.executable, "-m", "quizgen.jokbo", str(pdf), "-o", str(out_dir)]
    if practical:
        argv += ["--practical", *[str(p) for p in practical]]
    if older:
        argv += ["--older", *[str(p) for p in older]]
    done = subprocess.run(argv, cwd=str(repo_root),
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return done.returncode


def rebuild(*, run_dir: Path, kind: str, deck_name: str, id: str, jokbo_dir: Path,
            apkg_name: str, repo_root: Path,
            work: Path | None = None) -> tuple[bool, list[str]]:
    """이미 만든 카드로 덱만 다시 굽는다. **모델을 부르지 않는다.**

    `run_main`·`run_pre` 가 부르는 `quizgen.run` 은 prep부터 빌드까지 하는
    오케스트레이터다. 여기는 그 마지막 단계인 `quizgen.build` 만 직접 부른다 —
    **`build` 의 인자 모양을 아는 유일한 자리다.**

    편당 몇 초라 로그 파일을 열지 않고 받아서 실패했을 때만 꼬리를 돌려준다.

    **분량 계약은 여기서 안 건다**(`--allow-size`). 그것은 모델이 무엇을 낼지를 죄는
    값인데 이 자리는 모델을 안 부른다 — 이미 있는 카드를 다시 쌀 뿐이다. 걸어 두면
    상한을 내리는 날 **이미 나간 덱이 전부 다시 못 구워진다.** 2026-09-03 에 상한을
    30 에서 20 으로 내리면서 그렇게 됐고, 하필 그날 같이 고친 것이 뒷면 CSS 라
    「고쳤는데 아무 덱에도 안 붙는」 자리가 될 뻔했다. 장수는 빌드가 화면에 찍는다.
    """
    module = "quizgen.prequiz.build" if kind == PRE else "quizgen.build"
    edits = site_edits_path(run_dir, kind)
    # **카드가 있는 자리를 넘긴다.** 새 모양에서는 `main/<판>/` 안이라 강의 폴더를
    # 그대로 주면 `build` 가 `items.reproduced.json` 을 못 찾는다. 옛 모양이면 둘이 같다.
    argv = [sys.executable, "-m", module, str(work or run_dir),
            "--deck", deck_name, "--id", id,
            "--jokbo-dir", str(jokbo_dir), "--apkg-name", apkg_name]
    if kind == PRE:
        argv.append("--allow-size")
    else:
        # **결함 카드가 있어도 굽는다**(2026-09-23). 문지기가 더는 그것으로 막지 않고
        # 사이트의 「카드 검토」로 보낸다 — 여기서 거부하면 바로 그 편들, 사람이 사이트에서
        # 고친 편들이 다시 구워지지 않는다. `quizgen.run` 은 이미 같은 것을 붙인다.
        argv.append("--allow-defects")
    if edits.is_file():
        argv += ["--site-edits", str(edits)]
    done = subprocess.run(argv, cwd=str(repo_root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()
        return False, tail or [str(done.returncode)]
    built = apkg_of(Path(work or run_dir), kind)
    mark = site_edits_mark(run_dir, kind)
    if edits.is_file() and built is not None:
        mark.write_text(json.dumps({"sha256": _sha(edits), "apkg": built.name,
                                    "mtime_ns": built.stat().st_mtime_ns}), encoding="utf-8")
    elif mark.is_file():
        mark.unlink()
    return True, []


def site_edits_stale(run_dir: Path, kind: str) -> str:
    """사이트 판정과 지금 덱이 어긋났으면 그 까닭, 아니면 빈 문자열.

    어긋나는 길은 셋이다 — 판정이 바뀌었다, 판정이 다 거둬졌는데 덱은 그것으로
    구운 것이다, 파이프라인이 덱을 새로 구웠다(표시가 가리키는 덱과 지금 덱이 다르다).
    """
    edits, mark = site_edits_path(run_dir, kind), site_edits_mark(run_dir, kind)
    got = _load(mark) if mark.is_file() else None
    if not edits.is_file():
        return "판정이 다 거둬졌다" if got else ""
    if not isinstance(got, dict):
        return "판정으로 구운 덱이 없다"
    if got.get("sha256") != _sha(edits):
        return "판정이 바뀌었다"
    now = apkg_of(Path(run_dir), kind)
    if now is None or now.name != got.get("apkg") or now.stat().st_mtime_ns != got.get("mtime_ns"):
        return "덱이 판정 없이 새로 구워졌다"
    return ""


# ------------------------------------------------------------------ 산출물 옮기기


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# 예습 덱임을 알리는 꼬리. ` 예습`이 지금 쓰는 것이고 나머지는 옛 이름이다 —
# 이미 만들어 둔 덱이 섞여 있는 자리에서 갈래를 잘못 읽으면 남의 덱을 올린다.
PRE_SUFFIXES = (" 예습", "_pre", "_예습")


def is_pre(apkg: Path) -> bool:
    return any(apkg.stem.endswith(s) for s in PRE_SUFFIXES)


def apkg_of(run_dir: Path, kind: str) -> Path | None:
    """그 자리의 덱 하나. 꼬리가 두 갈래를 가른다.

    한 디렉터리에 둘이 같이 있을 수 있다 — 올해 필기로 복습 덱을 만든 강의가
    내년에는 「작년 필기」가 되어 같은 자리에서 예습 덱을 낳는다.

    **가장 새 것을 고른다.** 이름 규칙이 바뀌면 옛 이름의 덱이 옆에 남는데,
    이름순으로 집으면 낡은 쪽을 올릴 수 있다.
    """
    decks = [p for p in run_dir.glob("*.apkg") if is_pre(p) == (kind == PRE)]
    return max(decks, key=lambda p: p.stat().st_mtime) if decks else None


def _attempt(run_dir: Path, name: str, kind: str = MAIN,
             version: str | None = None) -> Path:
    """시도 것 하나의 자리. **새 모양이면 `main/<판>/` 안이고 옛 모양이면 여기다.**

    `runlayout` 이 그 둘을 가른다(`docs/runs-layout.md` 5단계). 이 함수를 지나지
    않고 `run_dir / name` 을 쓰면 옮긴 편에서만 조용히 빈 값을 읽는다 — 그러면
    계약이 `item_count 0` 으로 나가고 문지기가 그것을 막는다(막는 것이 맞지만
    원인이 엉뚱하게 보인다).
    """
    layout_kind = runlayout.PREQUIZ if kind == PRE else runlayout.MAIN
    if version:
        # 판을 지목했으면 그 판만 본다. 없으면 없는 것이다 — 다른 판으로 내려가면
        # 계약이 한 판의 카드와 다른 판의 통계를 섞어 쓴다.
        return runlayout.attempt_root(run_dir, layout_kind) / version / name
    return runlayout.find(run_dir, name, layout_kind) or run_dir / name


def config_of(run_dir: Path, kind: str) -> dict | None:
    name = "prequiz.config.json" if kind == PRE else "run.config.json"
    got = _load(_attempt(run_dir, name, kind))
    return got if isinstance(got, dict) else None


def source_pdf(run_dir: Path) -> str:
    """이 자리를 무엇으로 만들었는가. 원본 PDF의 경로 또는 파일명.

    `run_id`는 날짜_교시라서 **과목을 포함하지 않는다**(계약 §run_id). 다른 과목이
    같은 교시에 돌면 `runs/260813_03`을 두 강의가 나눠 갖게 되므로, 산출물을 올리기
    전에 이걸로 주인을 확인한다. 이 확인이 없으면 남의 덱을 올릴 수 있다.

    `*.config.json`이 전체 경로를 들고 있고 `prep.json`은 파일명만 들고 있다.
    둘 다 파일명에서 강의를 읽어내는 데는 충분하지만, 경로가 있는 쪽을 먼저 본다.
    """
    for name, kind in (("run.config.json", MAIN), ("prequiz.config.json", PRE)):
        cfg = _load(_attempt(run_dir, name, kind))
        if isinstance(cfg, dict) and (cfg.get("pdf") or cfg.get("pdf_name")):
            return str(cfg.get("pdf") or cfg.get("pdf_name"))
    prep = _load(_attempt(run_dir, "prep.json"))
    if isinstance(prep, dict):
        return str(prep.get("source") or prep.get("source_pdf") or "")
    return ""


def cards_of(run_dir: Path, kind: str = MAIN, version: str | None = None) -> list[dict]:
    got = _load(_attempt(run_dir, "items.reproduced.json", kind, version))
    cards = (got or {}).get("cards") if isinstance(got, dict) else None
    return cards if isinstance(cards, list) else []


def plain_stem(card: dict) -> str:
    """빈칸 카드의 앞면을 웹에서 읽히게 편다. 힌트가 있으면 힌트를 남긴다."""
    return quizgen_build.site_edits.web_stem(card)


# ------------------------------------------------------------------ 사이트 판정
#
# 관리자가 「카드 검토」에서 고치거나 뺀 카드(2026-09-23). 러너가 서버에서 당겨
# 여기 적고(`runner/site_edits.py`), 덱을 구울 때와 계약을 쓸 때 **둘 다** 얹는다 —
# 한쪽만 얹으면 apkg 노트 수와 `item_count` 가 갈라져 문지기가 막는다.


def site_edits_path(run_dir: Path, kind: str) -> Path:
    return Path(run_dir) / f"site_edits.{kind}.json"


def site_edits_mark(run_dir: Path, kind: str) -> Path:
    """그 판정으로 **어느 덱을** 구웠나. 파이프라인이 새로 구우면 덱이 바뀌어 어긋난다."""
    return Path(run_dir) / f"site_edits.{kind}.built.json"


def site_edits_of(run_dir: Path, kind: str) -> list[dict]:
    path = site_edits_path(run_dir, kind)
    return quizgen_build.site_edits.load(path) if path.is_file() else []


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _slides(run_dir: Path, run_id: str, kind: str = MAIN) -> int:
    """카드 뒷면 슬라이드를 서버가 찾을 수 있는 이름으로 옮긴다.

    서버는 파일명 끝의 `_s042.png`에서만 슬라이드 번호를 읽는다
    (`server/app/naming.py`). quizgen의 이름은 파이프라인마다 앞머리가 달라
    그 규칙에 안 맞으므로 여기서 한 번 맞춰 둔다. 그림 크롭은 옮기지 않는다 —
    웹이 읽는 것은 「이 카드의 근거가 몇 번 슬라이드인가」뿐이다.

    **`kind` 를 받는 이유는 판 폴더다.** 옛 모양에서는 `media` 가 갈래와 상관없이
    강의 폴더 하나였고, 그래서 5단계(`862edb4`)가 여기에 `PRE` 를 못 박아도 값이
    같았다. 판을 가르고 나서는 그것이 **복습 덱을 구우면서 예습 판의 `media` 를
    찾는 것**이 되고, 없으면 아래에서 `slides/` 를 지운다 — 서버가 읽는 강의 것이
    복습 빌드마다 날아간다. 2026-09-15 `260831_02` 에서 실제로 날아갔다.
    """
    out = run_dir / "slides"                      # 강의 것 — 서버가 읽는 자리
    media = _attempt(run_dir, "media", kind)      # 시도 것 — quizgen 이 낸 렌더
    if not media.is_dir():
        if out.exists():
            shutil.rmtree(out)
        return 0

    # **다 채운 뒤에 바꿔치기한다.** 예전에는 `out`을 먼저 통째로 지우고 채웠는데,
    # 그 사이 폴더가 반쯤 빈다. 빌드와 업로드가 겹쳐 돌기 시작한 뒤(2026-09-01
    # 일꾼 둘) 그 창이 실제로 열렸다 — 2026-09-02 `260902_01`이 103장을 만들어
    # 놓고 올리다 죽었다. `slides/`의 앞 9장이 이름 순서대로 사라진 뒤였다.
    staging = run_dir / "slides.tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    moved = 0
    for png in sorted(media.glob("*.png")):
        match = RE_SLIDE_PNG.search(png.name)
        if not match:
            continue
        shutil.copy2(png, staging / f"{run_id}_s{int(match.group(1)):03d}.png")
        moved += 1

    old = run_dir / "slides.old"
    if old.exists():
        shutil.rmtree(old)
    if out.exists():
        out.rename(old)
    staging.rename(out)
    shutil.rmtree(old, ignore_errors=True)
    return moved


def _web_items(cards: list[dict]) -> list[dict]:
    """웹 풀이가 읽는 모양. 자기채점 플래시카드라 선택지가 없다.

    그림 카드는 뺀다. 앞면이 이미지인데 웹에는 그 이미지가 없으므로, 실으면
    「이 조직은 어느 장기인가」가 그림 없이 뜬다. 그 카드들은 apkg에 그대로 있다.

    **두 갈래가 같은 모양을 쓴다.** `focus` 자리만 갈리는데, 예습 카드는 전부
    「꼭 반드시」라 등급 대신 **왜 그런가**(`reason`)가 들어가고 복습 카드는
    등급(`importance`)이 들어간다. 아래 `or`가 그 갈림이다.
    """
    items = []
    for card in cards:
        if card.get("card_format") not in WEB_FORMATS:
            continue
        items.append({
            "id": card.get("id") or "",
            "qtype": card.get("card_format"),
            "stem": plain_stem(card),
            # 빈칸 카드의 원문. 사이트가 이것을 고쳐야 덱으로 되돌릴 수 있다 —
            # 답이 질문 안(`{{c1::…}}`)에 있어서다(`quizgen/site_edits.py`).
            "source_stem": (card.get("q") or "") if card.get("card_format") == "cloze" else "",
            "answer": card.get("a") or "",
            "explanation": card.get("explanation") or "",
            # 예습은 `reason`(spine·vocabulary·mechanism·clinical·repeated),
            # 복습은 `importance`. 위 설명을 보라.
            "focus": card.get("reason") or card.get("importance") or "",
            "card_type": card.get("card_type") or "",
            "exam_hit": bool(card.get("exam_hit")),
            "slide_no": card.get("slide_no"),
            "source_type": card.get("source_type") or "lecture",
            "source_anchor": card.get("evidence_type") or "",
            "flags": list(card.get("review_flags") or []),
            # 예습만 쓴다(2026-10-04). 왜 이 문제를 냈나 · 도전 문제인가 — 앞면에 뜬다.
            # 복습 카드와 그 전에 만든 예습 카드에는 없으므로 빈 값이 간다.
            "why_asked": card.get("why_asked") or "",
            "why_tags": list(card.get("why_tags") or []),
            "challenge": bool(card.get("challenge")),
        })
    return items


def _reproduce_mix(cards: list[dict]) -> dict[str, int]:
    """재현 판정을 종류별로 센다.

    `different`나 `partial`이 있다고 나쁜 덱은 아니다. 눈가리개 세션이 그 지식을
    몰랐을 뿐일 수 있고, quizgen가 덱을 거부하는 것은 **문항 자체의 결함**으로
    갈린 것(`DEFECT_REASONS`)뿐이다. 그래서 판정과 결함을 따로 센다.

    그림 카드는 판정이 `없음`이다 — 앞면이 이미지라 텍스트만으로 풀 수 없다.
    """
    mix: dict[str, int] = {}
    for card in cards:
        verdict = str((card.get("reproduce") or {}).get("verdict") or "없음")
        mix[verdict] = mix.get(verdict, 0) + 1
    return mix


def _flag_counts(cards: list[dict]) -> dict[str, int]:
    """검토 표시를 종류별로. 사람을 부르는 신호는 개수가 아니라 종류에 있다."""
    counted: dict[str, int] = {}
    for card in cards:
        for flag in card.get("review_flags") or []:
            counted[str(flag)] = counted.get(str(flag), 0) + 1
    return dict(sorted(counted.items()))


def _reproduce_defects(cards: list[dict]) -> list[str]:
    """재현 검사가 문항 결함으로 가른 카드. 막지는 않고 올린다(`gate.py` 머리)."""
    return [str(c.get("id") or "?") for c in cards
            if (c.get("reproduce") or {}).get("reason") in quizgen_build.DEFECT_REASONS]


def _reproduce_defect_notes(cards: list[dict]) -> dict[str, dict[str, str]]:
    """결함 카드마다 **왜** 갈렸는가. 사이트의 「카드 검토」가 그대로 보여 준다.

    2026-09-23 에 붙었다 — 문지기가 결함 카드를 막는 대신 올리게 되면서, 고치는
    사람이 서버에서 사유를 읽어야 했다. 그 전의 run.meta 에는 id 만 있다.
    """
    out: dict[str, dict[str, str]] = {}
    for c in cards:
        r = c.get("reproduce") or {}
        if r.get("reason") in quizgen_build.DEFECT_REASONS:
            out[str(c.get("id") or "?")] = {
                "reason": str(r.get("reason") or ""),
                "note": str(r.get("note") or ""),
                "reproduced": str(r.get("reproduced_answer") or ""),
            }
    return out


def _axis_unresolved(cards: list[dict]) -> list[str]:
    """축 검사가 「무엇을 묻는지 모르겠다」고 한 채로 덱에 남은 빈칸 카드.

    `_reproduce_defects`와 갈라 둔다. 저쪽은 문지기가 배포를 미루던 값이고(2026-09-23
    부터는 둘 다 안 미룬다) 이쪽은 처음부터 아니었다 — 축 검사는 2026-09-06에 붙었고 한 편에서만 재 봤다(`build.AXIS_REASON`
    주석). 세어서 적기만 하고, 사람이 보는 자리는 카드 뒷면이다(`build.warning_of`).
    """
    return [str(c.get("id") or "?") for c in cards
            if (c.get("reproduce") or {}).get("reason") == quizgen_build.AXIS_REASON]


JOKBO_REF_FLAGS = ("jokbo_ref_outside_slice", "jokbo_ref_not_found")


def _reflag_jokbo(prep: dict, cfg: dict) -> dict | None:
    """이 편이 물었던 족보 조각. 못 찾으면 None.

    **못 찾은 것과 안 물린 것은 다르다.** 둘을 같은 None으로 넘기므로, 부르는 쪽은
    None일 때 기출 ref 표시를 떼지 않는다(`reflag`).
    """
    from quizgen.assemble import slice_for

    jokbo_dir = cfg.get("jokbo_dir")
    if not jokbo_dir or not Path(jokbo_dir).is_dir():
        return None
    path, _, _ = slice_for(prep, Path(jokbo_dir), cfg.get("jokbo") or None)
    if not path or not path.is_file():
        return None
    got = _load(path)
    return got if isinstance(got, dict) else None


def reflag(run_dir: Path) -> dict[str, int]:
    """이미 만들어 둔 카드에 **소프트 플래그만 다시 계산해 덧붙인다.**

    검사 규칙이 늘었을 때 쓰는 자리다. 카드를 다시 쓰지 않고 표시만 붙이므로 모델을
    부르지 않고, 그다음 `runner rebuild` 가 그 표시를 카드 뒷면 경고 박스로 내보낸다.
    관리자가 계수기를 따로 안 보고 **카드 뒷면에서 걸러낸다**고 했기 때문에, 표시가
    가야 할 자리는 `suspects.json` 이 아니라 거기다(CLAUDE.md).

    **표시를 지금 규칙으로 다시 계산한다** — 늘어난 것은 붙이고 철회된 것은 뗀다.
    돌려주는 표에서 뗀 것은 `-` 를 달고 온다(`-missing_explanation 15장`).

    한동안 이 자리가 "더하기만 한다"고 적혀 있었는데 **본문은 그렇지 않다.** 더하기만
    하면 잘못 붙인 표시가 영영 안 지워지고(설정을 안 넘겨 90장이 붙은 적이 있다),
    「해설 없음」처럼 철회한 규칙의 표시가 카드 뒷면에 계속 남는다. 사람이 보고 넘긴
    표시가 근거 없이 사라질 걱정은 없다 — 규칙이 그대로면 같은 표시가 다시 계산된다.

    **hard 제거는 하지 않는다.** 이 카드들은 이미 한 번 통과한 것이고, 여기서
    떨어뜨리면 재현 검사까지 지난 카드가 표시 하나 때문에 사라진다.
    """
    from quizgen import validate as quizgen_validate

    cards = cards_of(run_dir)
    prep = _load(run_dir / "prep.json")
    if not cards or not isinstance(prep, dict):
        return {}

    # **처음 검증할 때 쓴 설정을 그대로 다시 준다.** 안 주면 교수가 바뀌어 필기를
    # 근거로 인정한 편에서 `annotation_evidence_without_exam_hit` 이 무더기로 붙는다
    # (실측: 6편 90장). 근거 없는 표시는 진짜 표시를 묻어 버린다.
    cfg = config_of(run_dir, MAIN) or config_of(run_dir, PRE) or {}
    annotation_evidence = bool(cfg.get("annotation_evidence"))

    # **족보 조각과 전략도 같이 준다.** 안 주면 조각을 못 본 채로 판정하게 되는데,
    # 그러면 기출 ref 표시(`jokbo_ref_outside_slice`·`jokbo_ref_not_found`)가 전부
    # 「맞는 것」으로 나와 **근거 없이 지워진다.** 전략도 마찬가지다 — 기본값
    # `base` 로 재면 사진 중심 편의 표시가 다른 규칙으로 계산된다.
    jokbo = _reflag_jokbo(prep, cfg)
    strategy = cfg.get("strategy") or "base"

    # 계약에 없는 키를 떼고 넘긴다. `CARD_SCHEMA` 는 `additionalProperties: False` 라서
    # 뒤 단계가 붙인 `reproduce`·`review_flags` 가 그대로 들어가면 **전 카드가 스키마
    # 위반으로 떨어지고**, 그러면 조용히 아무 표시도 안 붙는다.
    allowed = set(quizgen_validate.CARD_SCHEMA["properties"])
    clean = [{k: v for k, v in c.items() if k in allowed} for c in cards]

    fresh, _ = quizgen_validate.validate({"cards": clean}, prep, jokbo,
                                          annotation_evidence, strategy)
    by_id = {c.get("id"): set(c.get("review_flags") or []) for c in fresh if c.get("id")}

    added: dict[str, int] = {}
    for card in cards:
        was = set(card.get("review_flags") or [])
        now = by_id.get(card.get("id"))
        if now is None:
            continue
        # 규칙이 **철회**된 것은 뗀다. 이 자리가 한 번 잘못 붙인 적이 있는데
        # (설정을 안 넘겨 90장), 더하기만 하면 그런 실수가 영영 안 지워진다.
        # 사람이 보고 넘긴 표시가 근거 없이 사라지는 일은 없다 — 규칙이 그대로면
        # 같은 표시가 다시 계산되기 때문이다.
        if jokbo is None:
            # 조각을 못 봤으면 기출 ref 는 판정할 수 없다. 그 표시는 손대지 않는다 —
            # 안 그러면 「조각이 없다」가 「표시가 철회됐다」로 둔갑한다.
            now = now | {f for f in was if f in JOKBO_REF_FLAGS}
        if was == now:
            continue
        card["review_flags"] = sorted(now)
        for flag in now - was:
            added[flag] = added.get(flag, 0) + 1
        for flag in was - now:
            added["-" + flag] = added.get("-" + flag, 0) + 1

    if added:
        (run_dir / "items.reproduced.json").write_text(
            json.dumps({"cards": cards}, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def _attempt_mark(run_dir: Path, kind: str, version: str | None = None) -> dict | None:
    """이 계약을 만든 시도. 옛 모양이면 None — 판이라는 것이 없다.

    **`version` 은 올린 쪽이 준 그 값이어야 한다.** 여기서 `work_dir` 에게 다시
    물으면 「고른 판」이 나오는데, 사람이 다른 판을 지목해 올렸으면 그것과 다르다 —
    그러면 계약이 **올라가지 않은 판**을 가리키고, `chosen.verdict` 가 고른 것과
    맞대 보며 늘 같다고 한다. 검사가 꺼진 것과 같다. 2026-09-15 에 그렇게 한 번 꺼졌다.
    """
    layout_kind = runlayout.PREQUIZ if kind == PRE else runlayout.MAIN
    work = runlayout.work_dir(run_dir, layout_kind, version)
    if work == Path(run_dir):
        return None
    return {"kind": layout_kind, "version": work.name,
            "cards_sha256": _cards_sha256(work)}


def _cards_sha256(work: Path) -> str:
    """그 시도의 신원. `attempts.cards_sha256` 과 같은 값을 낸다."""
    import hashlib
    p = Path(work) / "items.raw.json"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def promote(run_dir: Path, kind: str = MAIN, version: str | None = None) -> Path | None:
    """그 시도의 덱을 강의 폴더로 **올린다.** 올라간 덱의 자리를 돌려준다.

    `docs/runs-layout.md` 5단계의 마지막 조각이다. 강의 폴더의 루트는 「지금 나가는
    것」만 들고, 시도는 `main/<판>/` 에 산다 — 그 둘을 잇는 걸음이 이것이다.

    **4단계가 「안 만들었다」고 적어 둔 명령과 같은 것이다.** 고른 시도를 그 자리로
    올리는 일과 새로 구운 시도를 그 자리로 올리는 일이 같은 걸음이었다. 그래서 하나다.

    올리는 것은 덱 하나뿐이다. 나머지 계약(`run.meta.json`·`*_items.final.json`·
    `slides/`)은 `contract` 가 **읽어서 다시 쓴다** — 그것이 원래 하던 일이라 옮길
    것이 없다.

    **옛 모양에서는 아무것도 안 한다.** 시도가 이미 강의 폴더에 있으면 덱도 거기 있다.
    """
    run_dir = Path(run_dir)
    layout_kind = runlayout.PREQUIZ if kind == PRE else runlayout.MAIN
    work = runlayout.work_dir(run_dir, layout_kind, version)
    if work == run_dir:
        return apkg_of(run_dir, kind)

    src = apkg_of(work, kind)
    if src is None:
        # **접은 편의 「배포 중인 판」이 이 자리에 온다.** 그 판의 덱은 접을 때
        # 강의 폴더에 남았으므로(`migrate_attempts` 가 강의 폴더의 `.apkg` 를 지금
        # 나가는 것으로 보고 안 옮긴다) 판 폴더에는 덱이 없다. **이미 올라가 있는
        # 것이고 올릴 것이 없는 것이 맞다.**
        already = apkg_of(run_dir, kind)
        if already is not None:
            return already
        raise FileNotFoundError(f"{work.name}: {kind} 덱(.apkg)이 없다 — 올릴 것이 없다")
    dest = run_dir / src.name
    # **같은 내용이면 건드리지 않는다.** `publish` 가 (크기, mtime)으로 다시 밀 것을
    # 고르므로(`runs/published.json`), 내용이 같은데 mtime 만 새로 찍으면 수백 MB 가
    # 다시 올라간다.
    #
    # **크기만으로는 갈리지 않는다.** `copy2` 가 mtime 을 그대로 옮기므로 안 건드린
    # 덱은 src 와 dest 의 mtime 이 같다 — 판 폴더 쪽이 **더 새것이면 다시 구운
    # 것이다.** 2026-09-18 에 예습 덱 둘을 카드 하나씩 고쳐 다시 구웠는데 둘 다
    # 바이트 수가 09-16 것과 같았고, 크기만 보던 이 자리가 새 덱을 안 올려서
    # **옛 덱이 그대로 나갔다.** 계약은 카드 파일을 읽으므로 깨끗했다 —
    # 화면 어디에도 어긋남이 안 떴다.
    if (dest.is_file() and dest.stat().st_size == src.stat().st_size
            and src.stat().st_mtime_ns <= dest.stat().st_mtime_ns):
        return dest
    shutil.copy2(src, dest)
    return dest


def contract(run_dir: Path, run_id: str, title: str, kind: str,
             version: str | None = None) -> dict:
    """quizgen 산출물을 서버 계약으로 옮긴다. 만든 `run.meta`를 돌려준다.

    **여기서 아무것도 판정하지 않는다.** 세어서 적을 뿐이고, 올려도 되는지는
    `runner.gate`가 이 파일을 읽고 정한다. 문서를 코드보다 세게 적지 않는다는
    것과 같은 이유로, 세는 자리와 막는 자리를 갈라 둔다.
    """
    prefix = "pre_" if kind == PRE else ""
    # **덱을 먼저 올린다.** 새 모양에서는 덱이 판 폴더 안에 있고, 아래 `apkg_of` 는
    # 강의 폴더를 훑으므로 올리지 않으면 「덱이 없다」가 된다(`promote`).
    apkg = promote(run_dir, kind, version)
    if apkg is None:
        raise FileNotFoundError(f"{run_dir.name}: {kind} 덱(.apkg)이 없다")

    cfg = config_of(run_dir, kind) or {}
    cards = cards_of(run_dir, kind, version)
    # 사이트 판정을 덱과 **같이** 얹는다. 덱은 `rebuild` 가 `--site-edits` 로 얹었다.
    cards, site_applied = quizgen_build.site_edits.apply(cards, site_edits_of(run_dir, kind))
    suspects = _load(_attempt(run_dir, "suspects.json", kind, version)) or {}
    prep = _load(_attempt(run_dir, "prep.json", kind, version)) or {}

    got = quizgen_build.counts(apkg)
    used = sorted({c["slide_no"] for c in cards if isinstance(c.get("slide_no"), int)})
    total = int(prep.get("slides") or 0)
    coverage = suspects.get("coverage") or {}

    meta = {
        "lecture_id": run_id,
        "lecture_title": title,
        "deck_id": cfg.get("id") or deck_id(run_id),
        "deck_name": cfg.get("deck") or "",
        "deck_file": apkg.name,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                  time.localtime(apkg.stat().st_mtime)),
        # **옛 덱은 여기에 `pdf2anki` 라고 적혀 있다.** 2026-09-14 개명 전에 구운
        # 72편이 그렇다. 읽는 쪽이 아무 데도 없어서 고치지 않았다 — 맞추겠다고
        # 옛 산출물을 일괄로 손대면, 그 편들이 「그때 무엇으로 구웠는지」를 잃는다.
        "pipeline": "quizgen",
        # **어느 시도로 만들었나.** 새 모양에서만 붙는다(`runs/<편>/main/<판>/`).
        # 이것이 없으면 「사람이 고른 판」과 「실제로 올라간 판」을 맞대 볼 수 없다 —
        # `chosen.verdict` 가 이 값을 본다. 2026-09-15.
        "attempt": _attempt_mark(run_dir, kind, version),
        "source_pdf": cfg.get("pdf") or "",
        # 덱을 다시 열어 센 값이다. `item_count`와 어긋나면 덱이 내용과 다른 것을
        # 담고 있다는 뜻이고, 그건 gate가 막는 몇 안 되는 것 중 하나다.
        "verified": {"notes": got.get("n_notes"), "cards": got.get("n_cards"),
                     "media": got.get("n_media"), "decks": got.get("n_decks"),
                     "missing_media": got.get("missing_media") or []},
        "item_count": len(cards),
        "format": suspects.get("format_mix") or {},
        "sources": suspects.get("source_mix") or {},
        "importance": suspects.get("importance_mix") or {},
        "exam_hit": suspects.get("exam_hit") or 0,
        "review_flagged": sum(1 for c in cards if c.get("review_flags")),
        # 장수와 종류를 **같은 곳에서** 센다. 종류를 `suspects.json` 에서 읽던 때가
        # 있었는데, 그건 검증 단계가 쓰고 그대로 굳는 파일이라 `reflag` 로 표시가
        # 늘거나 줄면 둘이 어긋났다. 어긋난 채로도 아무 데서도 안 터진다.
        "review_flags": _flag_counts(cards),
        "reproduce": _reproduce_mix(cards),
        "reproduce_defects": _reproduce_defects(cards),
        "reproduce_defect_notes": _reproduce_defect_notes(cards),
        "dropped": len(suspects.get("dropped") or []),
        "similar_pairs": len(suspects.get("similar_pairs") or []),
        "slides_total": total,
        "slides_used": used,
        # 자료의 생김새를 재는 값(표지·학습목표 슬라이드가 여기 들어온다).
        "slides_unused": [n for n in range(1, total + 1) if n not in set(used)],
        # 이쪽이 진짜 누락 신호다 — 건너뛰겠다고 선언한 것을 이미 뺀 값이다.
        # **예습 덱에서는 늘 빈다.** 예습은 슬라이드를 다 훑는 덱이 아니라 중요한 것만
        # 가져가는 덱이라 `prequiz/validate.py` 가 이 값을 아예 안 잰다 — 여기가 비어
        # 있는 것은 「빠진 슬라이드가 없다」가 아니라 「그것을 재지 않는다」는 뜻이다.
        "untouched_slides": coverage.get("untouched_undeclared") or [],
        "objectives_without_card": coverage.get("objectives_without_card") or [],
        # **기출 목표는 따로 센다 — 슬라이드로는 못 맞추기 때문이다**(`validate.py`가
        # 인용 문항이 겹치는지로 본다). 값은 예전부터 `suspects.json` 에 있었는데 이
        # 자리로 안 넘어와서 문지기도 publish 보고도 못 봤고, 2026-09-03 `260901_01`
        # 이 기출 목표 11개를 세워 놓고 ②단계에서 카드를 한 장도 안 쓴 채 나갈 뻔했다.
        # 그때 옆칸의 `objectives_without_card` 는 `[]` 였다.
        "jokbo_objectives_without_card": coverage.get("jokbo_objectives_without_card") or [],
        # 축 검사가 잡았는데 수선 고리(`--repair-rounds`)를 다 쓰고도 남은 빈칸 카드.
        # 배포는 안 막는다 — 다만 남은 것이 어디에도 안 적히면 세어 볼 자리가 없다.
        "axis_unresolved": _axis_unresolved(cards),
        # 사이트 「카드 검토」에서 고치거나 뺀 것 중 이 덱에 얹힌 것(2026-09-23).
        "site_edits": {k: v for k, v in site_applied.items() if v},
    }

    if kind == MAIN:
        meta["strategy"] = cfg.get("strategy") or ""
        meta["strategy_why"] = cfg.get("strategy_why") or ""

    # 웹에서 푸는 문항과 그 근거 슬라이드. **복습도 낸다(2026-08-31 관리자 지시).**
    #
    # 복습 카드의 90%가 이 잣대를 지난다 — 39편 3,762장 중 3,384장이고 편별
    # 중앙값이 94장이다(예습은 28장). 빠지는 것은 전부 그림 카드이고, 비율이
    # 낮은 편 넷은 모두 실습이다.
    #
    # **아직 이것을 읽는 화면이 없다.** 서버에 복습 문항을 받는 자리가 없어서
    # `publish`도 안 올린다. 여기서 먼저 내는 이유는 재료가 쌓이는 데 시간이
    # 걸려서다 — 이 줄이 붙기 전에 구운 39편에는 이 파일도 `slides/`도 없다.
    items = _web_items(cards)
    meta["web_items"] = len(items)
    meta["web_excluded"] = len(cards) - len(items)
    # 웹 풀이는 틀렸을 때 해설을 보여 준다. **복습은 그 자리가 절반이 빈다**
    # (실측 54%) — Anki는 앞뒤만 보므로 지금까지 아쉬울 일이 없었다. 세어만 둔다.
    meta["web_without_explanation"] = sum(
        1 for item in items if not str(item.get("explanation") or "").strip())
    meta["slides_exported"] = _slides(run_dir, run_id, kind)
    # 이름은 갈래마다 못 박는다. `prefix`로 만들면 복습이 `items.final.json`이
    # 되는데, 복습 폴더에는 이미 `items.raw/checked/reproduced.json`이 있고 그것들은
    # **모양이 다른 것**(카드 그대로)이라 한 가족처럼 읽히면 안 된다.
    name = "pre_items.final.json" if kind == PRE else "main_items.final.json"
    (run_dir / name).write_text(json.dumps(
        {"lecture_id": run_id, "deck_id": meta["deck_id"],
         "generated_by": "quizgen.prequiz" if kind == PRE else "quizgen.main",
         "items": items},
        ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / f"{prefix}run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
