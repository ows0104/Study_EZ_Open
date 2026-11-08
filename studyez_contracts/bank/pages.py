"""Pure page-reference parsing used by the runner and edited bank cards."""
import re

MAX_RANGE = 8
_PAGE_RE = re.compile(r"(?:\bp\.?\s*|\bslide\s*)(\d{1,4})(?:\s*[–\-~]\s*(?:p\.?\s*)?(\d{1,4}))?|(\d{1,4})\s*쪽", re.I)
# Map 판(importance.py)은 "physical PDF page 7, 9, 11"처럼 page 뒤에 쉼표 목록을 쓴다.
_SPAN = r"\d{1,4}(?:\s*[–\-~]\s*\d{1,4})?"
_PAGE_LIST_RE = re.compile(rf"\bpages?\s*({_SPAN}(?:\s*,\s*{_SPAN})*)", re.I)
_SPAN_RE = re.compile(r"(\d{1,4})(?:\s*[–\-~]\s*(\d{1,4}))?")


def _span(pages: list[int], a: int, b: int) -> None:
    lo, hi = min(a, b), max(a, b)
    pages.extend(range(lo, hi + 1) if hi - lo < MAX_RANGE else (lo, hi))


def pages_of(locator: str) -> list[int]:
    pages = []
    for match in _PAGE_RE.finditer(locator):
        if match.group(3):
            pages.append(int(match.group(3)))
            continue
        a = int(match.group(1))
        _span(pages, a, int(match.group(2)) if match.group(2) else a)
    for match in _PAGE_LIST_RE.finditer(locator):
        for span in _SPAN_RE.finditer(match.group(1)):
            a = int(span.group(1))
            _span(pages, a, int(span.group(2)) if span.group(2) else a)
    return sorted(set(pages))


def cited_pages(bank: dict, pdf_source: str) -> dict[str, list[int]]:
    out = {}
    for q in bank["questions"]:
        refs = q["source_refs"] + [ref for pool in q.get("option_pools", [])
                                   for candidate in pool["candidates"] for ref in candidate["source_refs"]]
        pages = {p for ref in refs if ref["source_id"] == pdf_source for p in pages_of(ref["locator"])}
        if pages:
            out[q["question_id"]] = sorted(pages)
    return out
