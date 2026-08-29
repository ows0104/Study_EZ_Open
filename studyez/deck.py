"""pdf2anki를 부르고, 그 산출물을 서버가 아는 모양으로 옮긴다.

**로컬 러너와 파이프라인의 유일한 접점이다.** `studyez/`의 다른 모듈은 pdf2anki를
직접 부르지 않고 여기를 지난다. 계약이 바뀌면 `docs/artifact-contract.md`와 이
파일이 함께 움직인다.

## 왜 한 명령인가

예전 파이프라인은 가운데가 뚫려 있었다 — 코드가 prep까지 하고, `runs/queue.json`을
남기고, **사람이 연 Claude Code 세션**이 `/quiz`를 돌려 문항을 만들고, 다시 코드가
빌드했다. 그래서 편당 53~72분이 들었고 그 시간이 세션의 컨텍스트를 통째로 먹었다.

pdf2anki는 모델이 필요한 자리마다 `claude -p`로 **빈 세션을 스스로 띄운다**
(`pdf2anki/session.py`). 이력도 설정도 도구도 없는 세션이라 이 저장소의 CLAUDE.md도
메모리도 딸려가지 않는다. 그러니 이 자리에서 할 일은 하위 프로세스를 띄우는 것뿐이고,
**부르는 쪽의 컨텍스트는 한 글자도 쓰이지 않는다.**

## 작업 폴더와 덱 ID를 나눠 둔 이유

pdf2anki는 기본적으로 `out/<id>/`에서 일하고 `<id>`는 파일명 앞머리에서 딴
`p260820_03`이다. 서버 계약의 기본키는 `260820_03`(`run_id`)이라 둘이 다르다.

둘을 억지로 맞추지 않는다. **`<id>`는 guid의 씨앗이다** — 바꾸면 Anki가 이미 받아
간 카드를 전부 새 노트로 보고, 학생의 복습 이력이 통째로 끊긴다. 그래서 폴더만
`runs/<run_id>/`로 옮기고 ID는 pdf2anki가 쓰던 그대로 `p<run_id>`를 준다.

## 무엇을 만들어 두는가

pdf2anki가 남기는 것(`run.config.json`·`items.reproduced.json`·`suspects.json`·
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

from pdf2anki import build as pdf2anki_build

# 웹에서 풀 수 있는 카드. 그림 카드는 앞면이 이미지라 텍스트만으로는 물음이
# 성립하지 않는다("이 조직은 어느 장기이며…"). apkg에는 그대로 들어 있다.
WEB_FORMATS = ("basic", "cloze", "ox")

# `{{c1::답::힌트}}`. 웹은 Anki가 아니므로 빈칸으로 펴서 보여 준다.
RE_CLOZE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.+?))?\}\}", re.S)

# pdf2anki가 media/에 남기는 슬라이드 렌더. 앞머리는 파이프라인마다 달라서
# (복습은 강의 ID, 예습은 `lecture`) 번호만 본다.
RE_SLIDE_PNG = re.compile(r"slide(\d+)\.png$", re.IGNORECASE)

MAIN, PRE = "main", "pre"

# 한 편이 이만큼 안에 안 끝나면 버린다. 실측 상한이 편당 72분이었고 pdf2anki는
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

    예습·강의록·기출이 한 노드 아래 모이는 것은 그대로다. 예습 덱의 이름도 **올해
    강의**에서 나오기 때문이다(`calendar_name`). 실측으로 짝이 선 15쌍 중 올해
    필기가 이미 있는 12쌍이 전부 같은 노드에 섰다.
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


def apkg_name(run_id: str, title: str, kind: str,
              professors: tuple[str, ...] | list[str] = ()) -> str:
    """덱 파일 이름. **자료 파일명과 같은 꼴로 세운다.**

        [260820_03] 소아질환의 병태생리(2) 소아기 특이 질환 1(김은나).apkg
        [260825_01] 종양의 분자생물학(1)(전윤경) 예습.apkg

    받아 보는 사람이 그 자리에서 어느 강의인지 알아야 한다. `p260820_03.apkg`는
    파이프라인의 이름이지 사람의 이름이 아니다.

    **`deck_id`는 안 바꾼다.** 그쪽이 guid의 씨앗이라 바꾸면 Anki가 이미 받아 간
    카드를 전부 새 노트로 본다. 파일 이름은 guid에 안 들어간다.

    괄호 안 교수는 필기에서 온 제목이면 이미 들어 있다(`LectureFile.title`은 파일명에서
    뽑은 표시용 원문이다). **시간표에서 온 제목에는 없다** — 캘린더는 제목과 교수를 따로
    들고 있어서, 그때만 여기서 붙인다.

    덱 나무의 가운데 마디도 같은 이름을 쓴다(`deck_node`). Anki 안에서 보는 이름과
    받아 둔 파일 이름이 다르면 둘을 맞춰 보는 일이 사람 몫이 된다.
    """
    name = deck_node(run_id, title, professors)
    # 예습 덱은 파일에서만 꼬리를 단다. 덱 나무에서는 마지막 마디가 이미 `::예습`이다.
    return f"{name} 예습" if kind == PRE else name


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


def calendar_name(run_dir: Path, run_id: str, title: str, kind: str,
                  professors: tuple[str, ...] | list[str] = ()) -> str:
    """이 자리에서 나올 덱의 파일 이름."""
    rid, name, profs = calendar_of(run_dir, run_id, title, kind, professors)
    return apkg_name(rid, name, kind, profs)


def calendar_deck(run_dir: Path, run_id: str, title: str, kind: str, subject: str,
                  professors: tuple[str, ...] | list[str] = ()) -> str:
    """이 자리에서 나올 덱의 **전체 이름**. `<과목>::<가운데 마디>[::예습]`.

    마지막 마디(`::강의록`·`::기출`)는 복습 빌드가 카드의 기원을 보고 스스로 단다.
    예습은 덱이 하나뿐이라 여기서 붙인다.
    """
    rid, title, profs = calendar_of(run_dir, run_id, title, kind, professors)
    node = deck_node(rid, title, profs)
    name = f"{subject}::{node}" if subject else node
    return f"{name}::예습" if kind == PRE else name


def jokbo_dir(runs_dir: Path, subject: str) -> Path:
    """과목마다 따로 둔다. pdf2anki는 조각을 **강의 제목으로** 대조하는데, 제목만
    보면 과목이 다른 두 강의가 서로의 족보를 물어 갈 수 있다."""
    return runs_dir / "_jokbo" / subject


@dataclass
class Result:
    ok: bool
    run_dir: Path
    log: Path
    error: str = ""
    tail: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ 실행


def _spawn(argv: list[str], run_dir: Path, repo_root: Path, timeout: int,
           log_name: str) -> Result:
    """하위 프로세스로 띄우고 출력을 로그로 받는다.

    화면으로 흘리지 않는 이유는 한 편이 수십 분이고 밤에도 돌기 때문이다. 끝난
    뒤 꼬리만 사람에게 보여 주고, 전체는 로그에 남는다.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / log_name
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    with log.open("a", encoding="utf-8") as sink:
        sink.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} "
                   f"{' '.join(argv[1:])}\n")
        sink.flush()
        try:
            done = subprocess.run(argv, stdout=sink, stderr=subprocess.STDOUT,
                                  cwd=str(repo_root), env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return Result(False, run_dir, log, f"{timeout // 60}분 안에 끝나지 않았다")

    tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
    if done.returncode != 0:
        return Result(False, run_dir, log, f"pdf2anki가 {done.returncode}로 끝났다", tail)
    return Result(True, run_dir, log, tail=tail)


def run_main(*, pdf: str | Path, run_id: str, subject: str, lecture: str, title: str = "",
             runs_dir: Path, repo_root: Path, note: str = "", model: str = "",
             timeout: int = DEFAULT_TIMEOUT, extra: list[str] | None = None) -> Result:
    """복습 덱 한 편. `python -m pdf2anki.run`을 그대로 부른다.

    `--jokbo-dir`을 `runs/_jokbo`로 주면 `studyez jokbo`가 잘라 둔 조각을 스스로
    찾아 쓴다. 어느 조각을 물릴지는 pdf2anki가 목차 제목으로 대조한다 —
    로컬 러너가 따로 짝지어 줄 것이 없다.
    """
    run_dir = runs_dir / run_id
    argv = [sys.executable, "-m", "pdf2anki.run", str(pdf),
            "--out", str(run_dir), "--id", deck_id(run_id),
            "--subject", subject, "--lecture", lecture,
            "--jokbo-dir", str(jokbo_dir(runs_dir, subject)),
            "--check-dir", str(runs_dir / "_image_check"),
            "--apkg-name", apkg_name(run_id, title or lecture, MAIN)]
    if note:
        argv += ["--note", note]
    if model:
        argv += ["--model", model]
    argv += extra or []
    return _spawn(argv, run_dir, repo_root, timeout, "pipeline.log")


def run_pre(*, pdf: str | Path, run_id: str, subject: str, lecture: str, note: str,
            runs_dir: Path, repo_root: Path, hint: str = "", model: str = "",
            timeout: int = DEFAULT_TIMEOUT, extra: list[str] | None = None) -> Result:
    """예습 덱 한 편. **작년 필기로 만들므로 `run_id`도 작년 것이다.**

    `--lecture`를 올해 강의명으로 주는 것이 중요하다. 안 주면 덱의 가운데 마디가
    작년 파일제목이 되어 복습 덱과 다른 노드에 선다.
    """
    run_dir = runs_dir / run_id
    argv = [sys.executable, "-m", "pdf2anki.prequiz.run", str(pdf),
            "--out", str(run_dir), "--id", deck_id(run_id),
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
    return _spawn(argv, run_dir, repo_root, timeout, "prequiz.log")


def cut_jokbo(pdf: Path, out_dir: Path, repo_root: Path) -> int:
    """과목 족보 PDF를 강의별 조각으로 자른다. `pdf2anki.jokbo` 를 그대로 부른다.

    학기당 과목당 한 번이라 사람이 지켜보는 명령이다. 그래서 `_spawn` 과 달리
    출력을 로그로 삼키지 않고 화면으로 흘린다. 돌려주는 것은 종료 코드뿐이고,
    산출물이 제대로 나왔는지는 부르는 쪽이 본다.
    """
    argv = [sys.executable, "-m", "pdf2anki.jokbo", str(pdf), "-o", str(out_dir)]
    done = subprocess.run(argv, cwd=str(repo_root),
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return done.returncode


def rebuild(*, run_dir: Path, kind: str, deck_name: str, id: str, jokbo_dir: Path,
            apkg_name: str, repo_root: Path) -> tuple[bool, list[str]]:
    """이미 만든 카드로 덱만 다시 굽는다. **모델을 부르지 않는다.**

    `run_main`·`run_pre` 가 부르는 `pdf2anki.run` 은 prep부터 빌드까지 하는
    오케스트레이터다. 여기는 그 마지막 단계인 `pdf2anki.build` 만 직접 부른다 —
    **`build` 의 인자 모양을 아는 유일한 자리다.**

    편당 몇 초라 로그 파일을 열지 않고 받아서 실패했을 때만 꼬리를 돌려준다.
    """
    module = "pdf2anki.prequiz.build" if kind == PRE else "pdf2anki.build"
    argv = [sys.executable, "-m", module, str(run_dir),
            "--deck", deck_name, "--id", id,
            "--jokbo-dir", str(jokbo_dir), "--apkg-name", apkg_name]
    done = subprocess.run(argv, cwd=str(repo_root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()
        return False, tail or [str(done.returncode)]
    return True, []


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


def config_of(run_dir: Path, kind: str) -> dict | None:
    name = "prequiz.config.json" if kind == PRE else "run.config.json"
    got = _load(run_dir / name)
    return got if isinstance(got, dict) else None


def source_pdf(run_dir: Path) -> str:
    """이 자리를 무엇으로 만들었는가. 원본 PDF의 경로 또는 파일명.

    `run_id`는 날짜_교시라서 **과목을 포함하지 않는다**(계약 §run_id). 다른 과목이
    같은 교시에 돌면 `runs/260813_03`을 두 강의가 나눠 갖게 되므로, 산출물을 올리기
    전에 이걸로 주인을 확인한다. 이 확인이 없으면 남의 덱을 올릴 수 있다.

    `*.config.json`이 전체 경로를 들고 있고 `prep.json`은 파일명만 들고 있다.
    둘 다 파일명에서 강의를 읽어내는 데는 충분하지만, 경로가 있는 쪽을 먼저 본다.
    """
    for name in ("run.config.json", "prequiz.config.json"):
        cfg = _load(run_dir / name)
        if isinstance(cfg, dict) and (cfg.get("pdf") or cfg.get("pdf_name")):
            return str(cfg.get("pdf") or cfg.get("pdf_name"))
    prep = _load(run_dir / "prep.json")
    if isinstance(prep, dict):
        return str(prep.get("source") or prep.get("source_pdf") or "")
    return ""


def cards_of(run_dir: Path) -> list[dict]:
    got = _load(run_dir / "items.reproduced.json")
    cards = (got or {}).get("cards") if isinstance(got, dict) else None
    return cards if isinstance(cards, list) else []


def plain_stem(card: dict) -> str:
    """빈칸 카드의 앞면을 웹에서 읽히게 편다. 힌트가 있으면 힌트를 남긴다."""
    if card.get("card_format") != "cloze":
        return card.get("q") or ""
    return RE_CLOZE.sub(lambda m: f"[{m.group(3) or '____'}]", card.get("q") or "")


def _slides(run_dir: Path, run_id: str) -> int:
    """카드 뒷면 슬라이드를 서버가 찾을 수 있는 이름으로 옮긴다.

    서버는 파일명 끝의 `_s042.png`에서만 슬라이드 번호를 읽는다
    (`server/app/naming.py`). pdf2anki의 이름은 파이프라인마다 앞머리가 달라
    그 규칙에 안 맞으므로 여기서 한 번 맞춰 둔다. 그림 크롭은 옮기지 않는다 —
    웹이 읽는 것은 「이 카드의 근거가 몇 번 슬라이드인가」뿐이다.
    """
    out = run_dir / "slides"
    if out.exists():
        shutil.rmtree(out)
    media = run_dir / "media"
    if not media.is_dir():
        return 0

    out.mkdir(parents=True)
    moved = 0
    for png in sorted(media.glob("*.png")):
        match = RE_SLIDE_PNG.search(png.name)
        if not match:
            continue
        shutil.copy2(png, out / f"{run_id}_s{int(match.group(1)):03d}.png")
        moved += 1
    return moved


def _web_items(cards: list[dict]) -> list[dict]:
    """웹 예습 풀이가 읽는 모양. 자기채점 플래시카드라 선택지가 없다.

    그림 카드는 뺀다. 앞면이 이미지인데 웹에는 그 이미지가 없으므로, 실으면
    「이 조직은 어느 장기인가」가 그림 없이 뜬다. 그 카드들은 apkg에 그대로 있다.
    """
    items = []
    for card in cards:
        if card.get("card_format") not in WEB_FORMATS:
            continue
        items.append({
            "id": card.get("id") or "",
            "qtype": card.get("card_format"),
            "stem": plain_stem(card),
            "answer": card.get("a") or "",
            "explanation": card.get("explanation") or "",
            # 예습 카드는 전부 「꼭 반드시」다. 등급 대신 **왜 그런가**를 싣는다
            # (`reason`: spine·vocabulary·mechanism·clinical·repeated).
            "focus": card.get("reason") or card.get("importance") or "",
            "card_type": card.get("card_type") or "",
            "exam_hit": bool(card.get("exam_hit")),
            "slide_no": card.get("slide_no"),
            "source_type": card.get("source_type") or "lecture",
            "source_anchor": card.get("evidence_type") or "",
            "flags": list(card.get("review_flags") or []),
        })
    return items


def _reproduce_mix(cards: list[dict]) -> dict[str, int]:
    """재현 판정을 종류별로 센다.

    `different`나 `partial`이 있다고 나쁜 덱은 아니다. 눈가리개 세션이 그 지식을
    몰랐을 뿐일 수 있고, pdf2anki가 덱을 거부하는 것은 **문항 자체의 결함**으로
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
    """덱에 들어와서는 안 될 카드. 여기 뭔가 있으면 빌드가 자기 규칙을 어긴 것이다."""
    return [str(c.get("id") or "?") for c in cards
            if (c.get("reproduce") or {}).get("reason") in pdf2anki_build.DEFECT_REASONS]


def reflag(run_dir: Path) -> dict[str, int]:
    """이미 만들어 둔 카드에 **소프트 플래그만 다시 계산해 덧붙인다.**

    검사 규칙이 늘었을 때 쓰는 자리다. 카드를 다시 쓰지 않고 표시만 붙이므로 모델을
    부르지 않고, 그다음 `studyez rebuild` 가 그 표시를 카드 뒷면 경고 박스로 내보낸다.
    관리자가 계수기를 따로 안 보고 **카드 뒷면에서 걸러낸다**고 했기 때문에, 표시가
    가야 할 자리는 `suspects.json` 이 아니라 거기다(CLAUDE.md).

    **더하기만 한다.** 이미 붙어 있던 플래그는 지우지 않는다 — 옛 규칙으로 붙은 것을
    새 규칙이 조용히 떼어 가면, 사람이 이미 보고 넘긴 표시가 근거 없이 사라진다.
    hard 제거도 하지 않는다. 이 카드들은 이미 한 번 통과한 것이고, 여기서 떨어뜨리면
    재현 검사까지 지난 카드가 표시 하나 때문에 사라진다.
    """
    from pdf2anki import validate as pdf2anki_validate

    cards = cards_of(run_dir)
    prep = _load(run_dir / "prep.json")
    if not cards or not isinstance(prep, dict):
        return {}

    # **처음 검증할 때 쓴 설정을 그대로 다시 준다.** 안 주면 교수가 바뀌어 필기를
    # 근거로 인정한 편에서 `annotation_evidence_without_exam_hit` 이 무더기로 붙는다
    # (실측: 6편 90장). 근거 없는 표시는 진짜 표시를 묻어 버린다.
    cfg = config_of(run_dir, MAIN) or config_of(run_dir, PRE) or {}
    annotation_evidence = bool(cfg.get("annotation_evidence"))

    # 계약에 없는 키를 떼고 넘긴다. `CARD_SCHEMA` 는 `additionalProperties: False` 라서
    # 뒤 단계가 붙인 `reproduce`·`review_flags` 가 그대로 들어가면 **전 카드가 스키마
    # 위반으로 떨어지고**, 그러면 조용히 아무 표시도 안 붙는다.
    allowed = set(pdf2anki_validate.CARD_SCHEMA["properties"])
    clean = [{k: v for k, v in c.items() if k in allowed} for c in cards]

    fresh, _ = pdf2anki_validate.validate({"cards": clean}, prep, None,
                                          annotation_evidence)
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


def contract(run_dir: Path, run_id: str, title: str, kind: str) -> dict:
    """pdf2anki 산출물을 서버 계약으로 옮긴다. 만든 `run.meta`를 돌려준다.

    **여기서 아무것도 판정하지 않는다.** 세어서 적을 뿐이고, 올려도 되는지는
    `studyez.gate`가 이 파일을 읽고 정한다. 문서를 코드보다 세게 적지 않는다는
    것과 같은 이유로, 세는 자리와 막는 자리를 갈라 둔다.
    """
    prefix = "pre_" if kind == PRE else ""
    apkg = apkg_of(run_dir, kind)
    if apkg is None:
        raise FileNotFoundError(f"{run_dir.name}: {kind} 덱(.apkg)이 없다")

    cfg = config_of(run_dir, kind) or {}
    cards = cards_of(run_dir)
    suspects = _load(run_dir / "suspects.json") or {}
    prep = _load(run_dir / "prep.json") or {}

    got = pdf2anki_build.counts(apkg)
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
        "pipeline": "pdf2anki",
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
        "dropped": len(suspects.get("dropped") or []),
        "similar_pairs": len(suspects.get("similar_pairs") or []),
        "slides_total": total,
        "slides_used": used,
        # 자료의 생김새를 재는 값(표지·학습목표 슬라이드가 여기 들어온다).
        "slides_unused": [n for n in range(1, total + 1) if n not in set(used)],
        # 이쪽이 진짜 누락 신호다 — 건너뛰겠다고 선언한 것을 이미 뺀 값이다.
        "untouched_slides": coverage.get("untouched_undeclared") or [],
        "objectives_without_card": coverage.get("objectives_without_card") or [],
    }

    if kind == MAIN:
        meta["strategy"] = cfg.get("strategy") or ""
        meta["strategy_why"] = cfg.get("strategy_why") or ""
    else:
        items = _web_items(cards)
        meta["web_items"] = len(items)
        meta["web_excluded"] = len(cards) - len(items)
        meta["slides_exported"] = _slides(run_dir, run_id)
        (run_dir / "pre_items.final.json").write_text(json.dumps(
            {"lecture_id": run_id, "deck_id": meta["deck_id"],
             "generated_by": "pdf2anki.prequiz", "items": items},
            ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / f"{prefix}run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
