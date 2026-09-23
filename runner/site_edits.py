"""사이트 「카드 검토」의 판정을 당겨 와 덱에 얹는다.

2026-09-23 관리자 지시 — 「사이트에서 고친 카드가 apkg에도 반영되게 해줘.」

    서버 card_edit  →  runs/<편>/site_edits.<main|pre>.json  →  다시 굽기  →  publish

`publish` 가 계획을 세우기 **전에** 부른다(`cycle.report_publish`). 순서가 반대면
이번 실행은 판정 전의 덱을 밀고, 다음 실행에야 새 덱이 나간다. 예습 링크를 먼저
당기는 것(`sync_previews`)과 같은 까닭이다 — 사람이 사이트에 적는 것은 서버가 원본이다.

**다시 굽는 것은 어긋난 편뿐이다**(`deck.site_edits_stale`). 판정이 바뀌었거나, 다
거둬졌거나, 파이프라인이 그 사이 덱을 새로 구웠을 때다. 굽기는 모델을 안 부르고
편당 몇 초다(`runner.rebuild`).

**판정을 얹는 규칙은 `quizgen/site_edits.py` 에 있다** — 원본이 같을 때만 얹는다,
질문을 고쳐도 guid 는 원래 질문으로, 빈칸 카드는 원문을 고친다.

실패해도 올리기는 계속 간다. 판정 하나 때문에 강의록·다른 편이 밀리면 안 된다 —
그 편은 옛 덱으로 나가고, 웹 풀이는 서버가 이미 고쳐 두었다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import deck, rebuild

ROUTE = "/api/admin/card-edits"


def _entry(row: dict[str, Any]) -> dict[str, Any]:
    """서버 한 줄 → 파일 한 줄. **시각·사람은 안 싣는다** — 실으면 내용이 같아도
    파일이 바뀌어 덱을 괜히 다시 굽는다."""
    return {
        "item_id": row["itemId"],
        "action": row["action"],
        "stem": row.get("stem"),
        "source_stem": row.get("sourceStem"),
        "answer": row.get("answer"),
        "explanation": row.get("explanation"),
        "original": {k: (row.get("original") or {}).get(k) or ""
                     for k in ("stem", "answer", "explanation")},
    }


def seat(runs_dir: Path, subject: str, run_id: str, kind: str) -> Path | None:
    """서버의 (과목, 강의, 갈래)가 구워지는 자리. 복습은 올해 편, 예습은 작년 짝이다."""
    if kind == deck.PRE:
        return deck.pre_seat_of(runs_dir, run_id, subject)
    run_dir = runs_dir / run_id
    cfg = deck.config_of(run_dir, deck.MAIN) or {}
    # **같은 교시를 두 과목이 나눠 쓸 수 있다**(`run_id` 에 과목이 없다). 남의 덱에
    # 판정을 얹지 않으려고 덱 이름의 과목을 맞대 본다.
    if str(cfg.get("deck") or "").split("::")[0] != subject:
        return None
    return run_dir


def desired(rows: list[dict[str, Any]], runs_dir: Path,
            warn: list[str]) -> dict[tuple[Path, str], list[dict[str, Any]]]:
    out: dict[tuple[Path, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("action") not in ("edit", "delete"):
            continue
        where = seat(runs_dir, row["subject"], row["runId"], row["kind"])
        if where is None:
            warn.append(f"{row['subject']}/{row['runId']} {row['kind']} {row['itemId']} — "
                        "구울 자리를 못 찾았다. 웹 풀이만 고쳐져 있다")
            continue
        out.setdefault((where, row["kind"]), []).append(_entry(row))
    return out


def write(run_dir: Path, kind: str, edits: list[dict[str, Any]]) -> bool:
    """판정 파일을 맞춘다. 바뀌었으면 True. 빈 목록이면 파일을 지운다."""
    path = deck.site_edits_path(run_dir, kind)
    if not edits:
        if path.is_file():
            path.unlink()
            return True
        return False
    body = json.dumps({"edits": sorted(edits, key=lambda e: e["item_id"])},
                      ensure_ascii=False, indent=1)
    if path.is_file() and path.read_text(encoding="utf-8") == body:
        return False
    path.write_text(body, encoding="utf-8")
    return True


def sync(client, runs_dir: Path, subjects: tuple[str, ...] = (),
         dry_run: bool = False) -> list[str]:
    """당겨 와 적고 어긋난 편을 다시 굽는다. 화면에 찍을 줄을 돌려준다.

    `subjects` 가 있으면 그 과목의 편만 손댄다 — 한 과목을 올리는 실행이 남의
    과목 덱을 다시 굽지 않게.
    """
    lines: list[str] = []
    got = client.call("GET", ROUTE) or {}
    rows = [r for r in got.get("edits") or []
            if not subjects or r.get("subject") in subjects]
    want = desired(rows, runs_dir, lines)

    # 서버에서 거둔 판정의 파일도 지워야 한다 — 안 지우면 덱이 옛 판정을 계속 얹는다.
    present = {(p.parent, p.name.split(".")[1]) for p in runs_dir.glob("*/site_edits.*.json")
               if not p.name.endswith(".built.json")}
    seats = set(want) | present
    if subjects:
        seats = {s for s in seats if s in want or _subject_of(*s) in subjects}

    for run_dir, kind in sorted(seats):
        if dry_run:
            continue
        write(run_dir, kind, want.get((run_dir, kind), []))

    baked = 0
    for run_dir, kind in sorted(seats | _marked(runs_dir, subjects)):
        why = deck.site_edits_stale(run_dir, kind)
        if not why:
            continue
        label = f"{run_dir.name} {kind}"
        if dry_run:
            lines.append(f"{label} — {why}. 다시 구울 것이다 (--dry-run 이라 안 굽는다)")
            continue
        t = rebuild.target(run_dir, kind)
        if t is None:
            lines.append(f"{label} — {why}인데 다시 구울 카드가 없다. 웹 풀이만 고쳐져 있다")
            continue
        ok, result = rebuild.one(t, runs_dir)
        if not ok:
            lines.append(f"{label} — {why}. 다시 굽기 실패: {result[-1] if result else '?'}")
            continue
        baked += 1
        applied = result.get("site_edits") or {}
        lines.append(f"{label} — {why}. 다시 구웠다 · "
                     + (" · ".join(f"{_WORD[k]} {len(v)}장" for k, v in applied.items())
                        or "판정 없음(원래대로)"))
        if applied.get("stale"):
            lines.append(f"  ⚠ {label} 원본이 달라져 못 얹은 카드: {', '.join(applied['stale'])} — "
                         "파이프라인이 그 카드를 새로 만들었다")
    lines.insert(0, f"사이트 판정 {len(rows)}건 · 다시 구운 덱 {baked}편")
    return lines


_WORD = {"edited": "고침", "deleted": "뺌", "stale": "못 얹음"}


def _subject_of(run_dir: Path, kind: str) -> str:
    cfg = deck.config_of(run_dir, kind) or {}
    return str(cfg.get("deck") or "").split("::")[0]


def _marked(runs_dir: Path, subjects: tuple[str, ...]) -> set[tuple[Path, str]]:
    """판정으로 구운 표시가 남은 자리. 판정이 다 거둬졌으면 되돌려 구워야 한다."""
    found = {(p.parent, p.name.split(".")[1]) for p in runs_dir.glob("*/site_edits.*.built.json")}
    return {s for s in found if not subjects or _subject_of(*s) in subjects}
