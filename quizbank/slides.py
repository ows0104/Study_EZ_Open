"""문항이 인용한 필기 PDF 쪽을 PNG 로 렌더한다 — 답을 볼 때 그 아래 붙는다.

한 문항이 여러 쪽을 인용할 수 있다(2026-10-03 관리자: 「참고슬라이드가 여러개일 수도 있어」).
쪽 번호는 프롬프트 §5 가 「PDF 파일의 실제 쪽 번호」로 적게 한다. 261002_02 에서 ChatGPT 가 적은
쪽 번호가 quizgen 의 slide_no 와 정확히 같았다(4·7·9·11·13–18·20–22).

파일 이름 `<run_id>_sNNN.png` 은 서버가 쪽 번호를 읽는 꼴이다(server/app/naming.py `_s(\\d{1,4})\\.png$`).
"""

from __future__ import annotations

import re
from pathlib import Path

ZOOM = 1.6          # quizgen/build.py SLIDE_ZOOM 과 같다 — 같은 화면에 같은 크기로 뜬다
MAX_RANGE = 8       # `p3–40` 같은 넓은 범위는 문항 근거가 아니라 개념 범위다. 그만큼은 안 그린다

# p13 · p 13 · p13–14 · p13-p14 · 13쪽 · slide 13. `S1` 의 1 을 쪽으로 읽지 않도록 접두가 꼭 있어야 한다.
_PAGE_RE = re.compile(r"(?:\bp\.?\s*|\bslide\s*)(\d{1,4})(?:\s*[–\-~]\s*(?:p\.?\s*)?(\d{1,4}))?|(\d{1,4})\s*쪽", re.I)


def pages_of(locator: str) -> list[int]:
    """locator 한 줄에서 쪽 번호들. 범위는 펼치되 MAX_RANGE 를 넘으면 양 끝만."""
    pages: list[int] = []
    for m in _PAGE_RE.finditer(locator):
        if m.group(3):
            pages.append(int(m.group(3)))
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        lo, hi = min(a, b), max(a, b)
        pages.extend(range(lo, hi + 1) if hi - lo < MAX_RANGE else (lo, hi))
    return sorted(set(pages))


def cited_pages(bank: dict, pdf_source: str) -> dict[str, list[int]]:
    """문항 ID → 그 문항이 `pdf_source`(필기 PDF 의 source_id)에서 인용한 쪽들."""
    out: dict[str, list[int]] = {}
    for q in bank["questions"]:
        pages: set[int] = set()
        for ref in q["source_refs"]:
            if ref["source_id"] == pdf_source:
                pages.update(pages_of(ref["locator"]))
        if pages:
            out[q["question_id"]] = sorted(pages)
    return out


def render(pdf: Path, pages: set[int] | list[int], out_dir: Path, run_id: str) -> tuple[list[Path], list[int]]:
    """`(그린 파일들, PDF 에 없는 쪽들)`."""
    import fitz  # PyMuPDF — 렌더할 때만 쓴다

    out_dir.mkdir(parents=True, exist_ok=True)
    made, missing = [], []
    with fitz.open(pdf) as doc:
        for no in sorted(set(pages)):
            if not 1 <= no <= doc.page_count:
                missing.append(no)
                continue
            path = out_dir / f"{run_id}_s{no:03d}.png"
            if not path.exists():
                doc[no - 1].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False).save(path)
            made.append(path)
    return made, missing
