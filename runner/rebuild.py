"""이미 만든 카드로 덱만 다시 굽는다. **모델을 부르지 않는다.**

`python -m runner rebuild` 의 몸통이다. 2026-09-23 에 여기로 뗐다 — 사이트에서 고친
카드를 덱에 얹는 쪽(`runner/site_edits.py`)도 같은 걸음으로 구워야 해서다. 두 곳에
적으면 덱 이름·옛 덱 지우기·계약 중 하나가 한쪽에만 붙는 날이 온다.

**guid는 안 바뀐다.** 씨앗이 `(강의 ID, 질문)`이고 둘 다 그대로이므로, 다시
임포트하면 Anki가 같은 노트의 갱신으로 받아 복습 이력이 살아 있다. 사이트에서 질문을
고친 카드도 원래 질문을 씨앗으로 쓴다(`quizgen/site_edits.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import deck, filenames

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Target:
    run_dir: Path
    kind: str
    cfg: dict
    work: Path


def target(run_dir: Path, kind: str) -> Target | None:
    """그 자리·갈래를 다시 구울 수 있으면 그 재료. 카드나 설정이 없으면 None."""
    cfg = deck.config_of(run_dir, kind)
    # **판 폴더를 거쳐 묻는다.** `run_dir / …` 로 바로 보면 접은 편이 전부
    # 「카드가 없다」로 읽혀 다시 굽는 길이 막힌다.
    cards = deck._attempt(run_dir, "items.reproduced.json", kind)
    if cfg and cfg.get("deck") and cards.is_file():
        return Target(run_dir, kind, cfg, cards.parent)
    return None


def targets(runs_dir: Path, run_id: str = "") -> list[Target]:
    found = []
    for entry in sorted(runs_dir.iterdir() if runs_dir.is_dir() else []):
        if not entry.is_dir() or (run_id and entry.name != run_id):
            continue
        for kind in (deck.MAIN, deck.PRE):
            got = target(entry, kind)
            if got:
                found.append(got)
    return found


def names(t: Target) -> tuple[str, str, str]:
    """(제목, 파일 이름, 덱 이름)."""
    subject = t.cfg["deck"].split("::")[0]
    parsed = filenames.parse(deck.source_pdf(t.run_dir))
    title = parsed.title if parsed else t.run_dir.name
    professors = parsed.professors if parsed else ()
    name = deck.calendar_name(t.run_dir, t.run_dir.name, title, t.kind, professors,
                              subject=subject)
    # **덱 이름도 다시 세운다.** `run.config.json`의 것을 그대로 쓰면 이름 규칙이
    # 바뀌어도 Anki 안에서 보이는 이름만 옛것으로 남는다 — 파일만 바뀌고 덱은
    # 그대로였던 것이 실제로 그 이유였다.
    deck_name = deck.calendar_deck(t.run_dir, t.run_dir.name, title, t.kind, subject, professors)
    return title, name, deck_name


def one(t: Target, runs_dir: Path) -> tuple[bool, dict | list[str]]:
    """굽고 계약까지 쓴다. 성공이면 `(True, run.meta)`, 실패면 `(False, 꼬리)`."""
    subject = t.cfg["deck"].split("::")[0]
    title, name, deck_name = names(t)
    ok, tail = deck.rebuild(
        run_dir=t.run_dir, kind=t.kind, deck_name=deck_name,
        id=t.cfg.get("id") or deck.deck_id(t.run_dir.name),
        jokbo_dir=deck.jokbo_dir(runs_dir, subject), apkg_name=name,
        repo_root=REPO_ROOT, work=t.work)
    if not ok:
        return False, tail
    # 이름 규칙이 바뀌면 옛 이름의 덱이 옆에 남는다. 같은 갈래의 낡은 것은
    # 지우고 간다 — 남겨 두면 어느 것이 참인지 파일만 봐서는 모른다.
    #
    # **굽기가 성공한 뒤에 지운다.** 먼저 지우던 때가 있었는데, 빌드가 결함을
    # 이유로 거부하면 그 편에 덱이 하나도 안 남았다. `runs/` 는 gitignore 라
    # 되돌릴 데가 없다 — 2026-08-23 에 `260821_05` 가 실제로 그렇게 날아갔다.
    for stale in t.run_dir.glob("*.apkg"):
        if deck.is_pre(stale) == (t.kind == deck.PRE) and stale.stem != name:
            stale.unlink()
    # 폴더가 기억하는 이름도 새것으로 바꾼다. 안 바꾸면 `--resume`이나 다음
    # rebuild가 옛 이름으로 되돌린다 — 그 자리가 정본이기 때문이다.
    if deck_name != t.cfg["deck"]:
        t.cfg["deck"] = deck_name
        (t.run_dir / ("prequiz.config.json" if t.kind == deck.PRE else "run.config.json")
         ).write_text(json.dumps(t.cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, deck.contract(t.run_dir, t.run_dir.name, title, t.kind)
