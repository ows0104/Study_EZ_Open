"""족보 PDF에서 문항·보기를 코드로 읽는다(2026-11-14, docs/changes/2026-11-14-choices-merge).

강의 족보는 공통 PDF 형식(docs/policies/jokbo-attachments.md)이라 쪽마다 글이 있다:
머리 「2022 | 김동현 | 45번」, 「정답 2」, 발문, 보기 ①~⑤. 모델을 부르지 않는다.
글이 없거나 머리를 못 찾은 쪽은 건너뛰고 수만 센다. 결과는 PDF sha256으로 캐시한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "jokbo-items/1"
_HEAD = re.compile(r"^\s*(\d{4})\s*\|\s*([^|\n]+?)\s*\|\s*(\d+)\s*번", re.M)
_ANSWER = re.compile(r"정답\s*([①-⑳]|\d{1,2})")
_MARK = re.compile(r"([①-⑳])")
_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.)]\s*")
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_SPACE = re.compile(r"\s+")


def _flat(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def page_item(text: str) -> dict | None:
    """쪽 글 하나에서 족보 문항 하나. 머리가 없으면 None."""
    head = _HEAD.search(text)
    if not head:
        return None
    body = text[head.end():]
    answer = _ANSWER.search(body)
    if answer:
        body = body[answer.end():]
    start = re.search(rf"(?<!\d){head.group(3)}\s*[.)]\s", body)   # 발문은 「45. …」에서 시작한다
    if start:
        body = body[start.start():]
    parts = _MARK.split(body)
    stem = _NUMBER.sub("", _flat(parts[0]))
    stem = re.sub(r"^\d{1,3}\s+", "", stem)
    options = [{"mark": parts[i], "text": _flat(parts[i + 1])} for i in range(1, len(parts) - 1, 2) if _flat(parts[i + 1])]
    mark = answer.group(1) if answer else ""
    if mark.isdigit() and 1 <= int(mark) <= len(_CIRCLED):
        mark = _CIRCLED[int(mark) - 1]
    return {"year": head.group(1), "professor": head.group(2).strip(), "number": head.group(3),
            "answer": mark, "stem": stem[:400], "options": options}


def read_items(pdf: Path) -> dict:
    import fitz  # PyMuPDF — 생성기 PC(러너)에 있다
    items, skipped = [], 0
    with fitz.open(pdf) as doc:
        for number, page in enumerate(doc, 1):
            item = page_item(page.get_text())
            if item and item["options"]:
                items.append({**item, "page": number})
            else:
                skipped += 1
    return {"schema": SCHEMA, "items": items, "pagesSkipped": skipped}


def cached_items(pdf: Path, sha256: str, cache: Path) -> dict:
    """PDF sha로 캐시한 족보 문항. 못 읽으면 빈 목록."""
    path = cache / f"{sha256[:16]}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") == SCHEMA:
            return data
    except (OSError, ValueError):
        pass
    try:
        data = read_items(pdf)
    except Exception as error:  # noqa: BLE001 — 족보를 못 읽어도 다른 출처로 선지를 만든다
        return {"schema": SCHEMA, "items": [], "pagesSkipped": 0, "error": str(error)}
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def subject_items(sources: list[dict], cache: Path) -> list[dict]:
    """`jokbo-sources/1`의 강의마다 족보 문항. 강의 run_id·제목을 붙인다. 같은 PDF는 한 번만 읽는다."""
    lectures = []
    for lecture in sources:
        items = []
        for pdf in lecture.get("pdfs", []):
            path = Path(pdf.get("path") or "")
            if not path.is_file() or not pdf.get("sha256"):
                continue
            items += cached_items(path, pdf["sha256"], cache)["items"]
        lectures.append({"run_id": lecture.get("run_id", ""), "title": lecture.get("title", ""), "items": items})
    return lectures


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}|[가-힣]{2,}")


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "")}


def related(items: list[dict], text: str, limit: int = 6) -> list[dict]:
    """다른 강의 족보 중 이 문항과 낱말 두 개 이상이 겹치는 것(입력 크기 제한)."""
    mine = words(text)
    scored = []
    for item in items:
        overlap = len(mine & words(item["stem"] + " " + " ".join(o["text"] for o in item["options"])))
        if overlap >= 2:
            scored.append((overlap, item))
    scored.sort(key=lambda row: -row[0])
    return [item for _, item in scored[:limit]]
