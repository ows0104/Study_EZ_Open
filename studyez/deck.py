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


def lecture_name(title: str, professors: tuple[str, ...] | list[str] = ()) -> str:
    """덱 나무의 가운데 마디. 교수 괄호를 뗀 강의 제목이다.

    `LectureFile.title`은 파일명에서 뽑은 표시용 원문이라 `소아질환의 병태생리(2)
    소아기 특이 질환 1(김은나)`처럼 교수가 붙어 있다. 그대로 쓰면 **교수가 바뀌는
    해에 같은 강의가 두 노드로 갈린다.**

    순번 괄호는 남긴다. `조직 재생 및 수복(1)`과 `(2)`는 다른 강의이고, 같이
    떼면 한 노드로 뭉개진다.

    `::`는 Anki의 하위덱 구분자라 치환한다. pdf2anki의 `pack.lecture_of`가 같은
    자리에서 같은 일을 한다.
    """
    name = title
    for professor in professors:
        name = name.replace(f"({professor})", "")
    # `(김옥주, 이규원)`처럼 여럿이 한 괄호에 든 경우. 위에서 안 떨어진다.
    if professors:
        joined = ", ".join(professors)
        name = name.replace(f"({joined})", "").replace(f"({joined.replace(', ', ',')})", "")
    return " ".join(name.replace("::", "-").split()) or title


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


def run_main(*, pdf: str | Path, run_id: str, subject: str, lecture: str,
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
            "--check-dir", str(runs_dir / "_image_check")]
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
            "--check-dir", str(runs_dir / "_image_check")]
    if hint:
        argv += ["--hint", hint]
    if model:
        argv += ["--model", model]
    argv += extra or []
    return _spawn(argv, run_dir, repo_root, timeout, "prequiz.log")


# ------------------------------------------------------------------ 산출물 옮기기


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def apkg_of(run_dir: Path, kind: str) -> Path | None:
    """`<id>.apkg`가 복습, `<id>_pre.apkg`가 예습이다.

    한 디렉터리에 둘이 같이 있을 수 있다 — 올해 필기로 복습 덱을 만든 강의가
    내년에는 「작년 필기」가 되어 같은 자리에서 예습 덱을 낳는다.
    """
    decks = sorted(run_dir.glob("*.apkg"))
    pre = [p for p in decks if p.stem.endswith("_pre")]
    return (pre[0] if pre else None) if kind == PRE else next(
        (p for p in decks if not p.stem.endswith("_pre")), None)


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


def _reproduce_defects(cards: list[dict]) -> list[str]:
    """덱에 들어와서는 안 될 카드. 여기 뭔가 있으면 빌드가 자기 규칙을 어긴 것이다."""
    return [str(c.get("id") or "?") for c in cards
            if (c.get("reproduce") or {}).get("reason") in pdf2anki_build.DEFECT_REASONS]


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
        "review_flags": suspects.get("flag_counts") or {},
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
