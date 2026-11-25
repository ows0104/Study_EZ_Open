"""관리자가 강의마다 적어 둔 「교수가 짚은 쪽」 기록을 읽는다 (docs/changes/2026-11-25-professor-marked-pages).

`runs/marked-pages.json`:

    {"version": 1, "lectures": {"<과목>/<runId>": {
        "quote": "교수 말 원문(필기·공지에 적힌 그대로)",
        "year": 2026,                                   그 말을 한 해
        "marker": "슬라이드 오른쪽 위 해 그림",            쪽을 알아보는 표시(없으면 빈 문자열)
        "pages": [{"source_id": "S1", "pages": [10, 16]}],   그 강의 원본의 물리 쪽
        "approval": "사용자 발언 원문", "at": "ISO 시각"}}}

- 새 출제: 앞 단계 prepare가 실행 폴더 `front/marked-pages.json`으로 굳힌다. 포인트 추출 입력(input.json)에
  `marked_pages`로 넣고, 추출 결과의 `notebook_profile.marked_pages`는 이 값으로 덮는다(source: admin).
- 보강(채우기): 채우기 기록을 굳힐 때(`runner.fill_goals.frozen`) 같은 강의의 이 기록을 `markedPages`로 함께 굳힌다.
  생성기가 공개판 프로필에 더한다(`quizbank.connection_presuppose`).

한 번 굳힌 실행은 파일이 바뀌어도 처음 것을 쓴다. 기록이 없으면 None — 지금과 같다. 형식이 틀리면 MarkedError로
그 일감을 보류한다. 필기 말씀이 작년 것뿐인 강의는 모델 추출만으로는 등급에 쓰이지 않는다(결정 3). 관리자가 여기 적으면 쓰인다.
"""
from __future__ import annotations

import json
from pathlib import Path

FILENAME = "marked-pages.json"
FROZEN = "marked-pages.json"


class MarkedError(ValueError):
    pass


def entry(key: str, row: dict) -> dict:
    """One record → `notebook_profile.marked_pages` (source admin), checked by the contract."""
    from studyez_contracts.roots import generation_v4 as v4
    if not isinstance(row, dict):
        raise MarkedError(f"{FILENAME}: {key} 기록이 객체가 아니다")
    for name in ("quote", "approval", "at"):
        if not isinstance(row.get(name), str) or not row[name].strip():
            raise MarkedError(f"{FILENAME}: {key}에 {name}가 없다(교수 말 원문·승인 발언·시각을 남긴다)")
    value = {"instruction": {"quote": row["quote"], "refs": [], "year": row.get("year"), "source": "admin"},
             "marker": row.get("marker", ""), "pages": row.get("pages")}
    try:
        return v4.check_marked_pages(value)
    except ValueError as cause:
        raise MarkedError(f"{FILENAME}: {key}: {cause}") from cause


def load(runs_dir: Path) -> dict[str, dict]:
    """「과목/runId」 → `marked_pages` 값. 파일이 없으면 빈 dict."""
    target = Path(runs_dir) / FILENAME
    if not target.exists():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as cause:
        raise MarkedError(f"{FILENAME}을 읽지 못했다: {cause}") from cause
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("lectures"), dict):
        raise MarkedError(f'{FILENAME} 형식이 다르다: {{"version": 1, "lectures": {{…}}}}이어야 한다')
    return {key: entry(key, row) for key, row in value["lectures"].items()}


def frozen(out: Path, runs_dir: Path, subject: str, run_id: str) -> dict | None:
    """이 실행의 짚은 쪽 기록. 처음이면 `runs/marked-pages.json`에서 `out/marked-pages.json`으로 굳힌다."""
    target = Path(out) / FROZEN
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    value = load(runs_dir).get(f"{subject}/{run_id}")
    if value is None:
        return None
    Path(out).mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value
