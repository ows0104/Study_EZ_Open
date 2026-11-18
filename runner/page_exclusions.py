"""관리자가 강의마다 적어 둔 「모델에 보내지 않을 쪽」 기록을 읽어 실행에 굳힌다 (docs/changes/2026-11-18-root-exclude-pages).

`runs/page-exclusions.json`:

    {"version": 1, "lectures": {"<과목>/<runId>": {
        "sources": [{"assetId": "…", "sha256": "<원본 SHA-256>", "pages": [36, "37-48"]}],   빼는 쪽(1부터, 원본 쪽 번호)
        "reason": "…", "approval": "사용자 발언 원문", "at": "ISO 시각"}}}

자료는 서버 자산 ID와 원본 지문 둘 다로 가리킨다. 그 강의의 Main-Quiz 요청을 받으면 내려받은 사본 옆에
`<사본>.withheld-pages.json`(quizbank.withheld_pages, page-withhold/1)으로 굳힌다. 그 뒤 앞 단계·생성기·근거 보강이
사본을 모델 입력으로 바꿀 때 그 쪽만 빈 안내 쪽으로 바뀐다. 쪽 수와 쪽 번호는 원본 그대로다.
원본 파일·서버 packet·사이트에 올라간 자료는 바뀌지 않는다.

- 기록이 없으면 None — 러너 동작은 지금과 같다.
- 한 번 굳힌 실행은 기록이 바뀌어도 처음 것을 쓴다(이어 하기가 다른 쪽으로 돌지 않게).
- 형식이 틀리거나, 기록이 가리킨 자료(자산 ID+지문)가 요청에 없거나, 이미 자료를 만든 실행에 처음 걸리면
  PageExclusionError로 그 일감을 보류한다. 조용히 원본 전체를 보내지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from quizbank import withheld_pages

FILENAME = "page-exclusions.json"
_RANGE = re.compile(r"(\d+)-(\d+)")


class PageExclusionError(ValueError):
    pass


def _pages(value, where: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise PageExclusionError(f"{FILENAME}: {where}의 pages가 비었거나 목록이 아니다")
    found: set[int] = set()
    for item in value:
        if isinstance(item, int) and not isinstance(item, bool) and item >= 1:
            found.add(item)
            continue
        match = _RANGE.fullmatch(str(item)) if isinstance(item, str) else None
        if not match or not 1 <= int(match[1]) <= int(match[2]):
            raise PageExclusionError(f"{FILENAME}: {where}의 쪽 {item!r}는 1 이상의 쪽 번호나 「36-48」 꼴이어야 한다")
        found.update(range(int(match[1]), int(match[2]) + 1))
    return sorted(found)


def load(runs_dir: Path) -> dict[str, dict]:
    """「과목/runId」 → 기록(pages는 펼친 정수 목록). 파일이 없으면 빈 dict."""
    target = Path(runs_dir) / FILENAME
    if not target.exists():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as cause:
        raise PageExclusionError(f"{FILENAME}을 읽지 못했다: {cause}") from cause
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("lectures"), dict):
        raise PageExclusionError(f'{FILENAME} 형식이 다르다: {{"version": 1, "lectures": {{…}}}}이어야 한다')
    rows = {}
    for key, row in value["lectures"].items():
        if not isinstance(row, dict) or not isinstance(row.get("sources"), list) or not row["sources"]:
            raise PageExclusionError(f"{FILENAME}: {key}에 sources(목록)가 없다")
        for name in ("reason", "approval", "at"):
            if not isinstance(row.get(name), str) or not row[name].strip():
                raise PageExclusionError(f"{FILENAME}: {key}에 {name}가 없다(이유·승인 발언·시각을 남긴다)")
        sources = []
        for i, source in enumerate(row["sources"]):
            where = f"{key} sources[{i}]"
            if not isinstance(source, dict) or not str(source.get("assetId") or "").strip() \
                    or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256") or "")):
                raise PageExclusionError(f"{FILENAME}: {where}에 assetId와 sha256(64자리 소문자 16진수)이 있어야 한다")
            sources.append({"assetId": str(source["assetId"]), "sha256": source["sha256"], "pages": _pages(source.get("pages"), where)})
        rows[key] = {**row, "sources": sources}
    return rows


def freeze(out: Path, packet: dict, runs_dir: Path) -> dict[str, list[int]]:
    """이 실행의 사본 옆에 제외 쪽을 굳힌다. 돌려주는 값: 출처 ID → 굳어 있는 제외 쪽(이번에 굳힌 것과 전에 굳힌 것)."""
    out = Path(out)
    local = [s for s in packet["sources"] if s.get("localPath")]
    frozen = {s["id"]: sorted(withheld_pages.pages(Path(s["localPath"]))) for s in local
              if withheld_pages.sidecar(Path(s["localPath"])).is_file()}
    row = load(runs_dir).get(f"{packet['subject']}/{packet['runId']}")
    if row is None:
        return frozen
    started = any(p.exists() for p in (out / "front" / "material-hashes.json", out / "front" / "material",
                                       out / "generation" / "material", out / "material"))
    for wanted in row["sources"]:
        source = next((s for s in local if str(s.get("assetId")) == wanted["assetId"] and s["sha256"] == wanted["sha256"]), None)
        if source is None:
            raise PageExclusionError(f"{FILENAME}: 기록이 가리킨 자료(asset {wanted['assetId']}, sha256 {wanted['sha256'][:12]}…)가 "
                                     "이 요청에 없다. 자료가 바뀌었으면 기록을 고치거나 지운 뒤 다시 요청한다")
        path = Path(source["localPath"])
        if source["id"] in frozen:
            if frozen[source["id"]] != wanted["pages"]:
                print(f"제외 쪽: {source['id']}는 처음 굳힌 {frozen[source['id']]}을 그대로 쓴다(기록은 {wanted['pages']})", flush=True)
            continue
        if started:
            raise PageExclusionError(f"{FILENAME}: 이미 자료를 만든 실행이라 제외 쪽을 새로 걸지 않는다. 새 요청(restart)으로 다시 돌린다")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != source["sha256"]:
            raise PageExclusionError(f"{source['id']}: 내려받은 사본의 지문이 packet과 다르다")
        import fitz
        with fitz.open(path) as pdf:
            count = pdf.page_count
        if wanted["pages"][-1] > count:
            raise PageExclusionError(f"{FILENAME}: {source['id']}는 {count}쪽인데 {wanted['pages'][-1]}쪽을 빼라고 적혀 있다")
        record = {"policy": withheld_pages.POLICY, "sourceId": source["id"], "assetId": wanted["assetId"],
                  "sourceSha256": source["sha256"], "pageCount": count, "pages": wanted["pages"],
                  "reason": row["reason"], "approval": row["approval"], "at": row["at"],
                  "record": f"runs/{FILENAME}", "frozenAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        withheld_pages.sidecar(path).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        frozen[source["id"]] = wanted["pages"]
        print(f"제외 쪽: {source['id']} {source['filename']} — {_phrase(wanted['pages'])}쪽을 모델 입력에서 뺀다({FILENAME})", flush=True)
    return frozen


def _phrase(pages: list[int]) -> str:
    runs, start = [], None
    for i, page in enumerate(pages):
        if start is None: start = page
        if i + 1 == len(pages) or pages[i + 1] != page + 1:
            runs.append(str(start) if start == page else f"{start}~{page}"); start = None
    return "·".join(runs)


def cited(value, withheld: dict[str, list[int]]) -> list[dict]:
    """결과 안에서 제외 쪽을 가리키는 인용·그림 쪽(경고용). {source_id, page(s)}를 가진 모든 곳을 본다."""
    found = []

    def walk(node, path):
        if isinstance(node, list):
            for i, x in enumerate(node): walk(x, f"{path}[{i}]")
        elif isinstance(node, dict):
            sid = node.get("source_id")
            if sid in withheld:
                pages = node.get("pages") if isinstance(node.get("pages"), list) else [node.get("page")]
                hit = sorted(p for p in pages if isinstance(p, int) and p in withheld[sid])
                if hit: found.append({"path": path, "source_id": sid, "pages": hit})
            for k, x in node.items(): walk(x, f"{path}.{k}")
    walk(value, "$")
    return found
