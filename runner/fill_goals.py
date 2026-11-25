"""관리자가 강의마다 적어 둔 「채우기」 기록을 읽는다 (docs/changes/2026-11-17-fill-recovery).

`runs/fill-goals.json`:

    {"version": 1, "lectures": {"<과목>/<runId>": {
        "previousRevision": "auto-…",            이 기록이 겨냥한 공개판
        "goals": ["T009-D", …],                  문항을 써 넣을 목표(direction ID)
        "rewrite": [{"question_id": "Q124", "note": "…", "fix": "…"}],   지적과 함께 다시 쓸 공개 문항(없으면 빈 목록)
        "reason": "…", "approval": "사용자 발언 원문", "at": "ISO 시각"}}}

같은 강의에 `runs/marked-pages.json` 기록(교수가 짚은 쪽)이 있으면 굳힐 때 `markedPages`로 함께 넣는다
(runner.marked_pages). 생성기가 공개판 프로필에 더해, 짚은 쪽이 답인 문항을 Core 이상으로 다시 계산한다.

보강(presuppose-only/1) 요청을 돌릴 때 그 강의의 기록이 있으면 실행 폴더에 `fill.json`으로 굳혀 생성기에 넘긴다.
한 번 굳힌 실행은 파일이 바뀌어도 처음 것을 쓴다(이어 하기가 다른 목록으로 돌지 않게). 기록이 없으면 None —
러너 명령은 지금과 같다. 형식이 틀리면 FillError로 그 일감을 보류한다. 내용 검사(판·목표·문항이 맞는가)는
생성기가 공개판을 읽고 한다(quizbank.connection_presuppose.check_fill).
"""
from __future__ import annotations

import json
from pathlib import Path

FILENAME = "fill-goals.json"
FROZEN = "fill.json"


class FillError(ValueError):
    pass


def load(runs_dir: Path) -> dict[str, dict]:
    """「과목/runId」 → 기록. 파일이 없으면 빈 dict."""
    target = Path(runs_dir) / FILENAME
    if not target.exists():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as cause:
        raise FillError(f"{FILENAME}을 읽지 못했다: {cause}") from cause
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("lectures"), dict):
        raise FillError(f'{FILENAME} 형식이 다르다: {{"version": 1, "lectures": {{…}}}}이어야 한다')
    for key, row in value["lectures"].items():
        if not isinstance(row, dict) or not isinstance(row.get("goals"), list) or not isinstance(row.get("rewrite", []), list):
            raise FillError(f"{FILENAME}: {key}에 goals(목록)가 없거나 rewrite가 목록이 아니다")
        for name in ("previousRevision", "reason", "approval", "at"):
            if not isinstance(row.get(name), str) or not row[name].strip():
                raise FillError(f"{FILENAME}: {key}에 {name}가 없다(겨냥한 판·이유·승인 발언·시각을 남긴다)")
    return value["lectures"]


def frozen(out: Path, subject: str, run_id: str) -> Path | None:
    """이 실행의 채우기 기록 파일. 처음이면 `runs/fill-goals.json`에서 굳힌다. 기록이 없으면 None."""
    out = Path(out)
    target = out / FROZEN
    if target.exists():
        return target
    runs = out.parent.parent
    row = load(runs).get(f"{subject}/{run_id}")
    if row is None:
        return None
    # The administrator's marked pages of this lecture go with it (docs/changes/2026-11-25-professor-marked-pages).
    from . import marked_pages
    marked = marked_pages.load(runs).get(f"{subject}/{run_id}")
    if marked is not None:
        row = {**row, "markedPages": marked}
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
