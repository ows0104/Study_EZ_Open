"""Pure page-reference parsing used by the runner and edited bank cards."""
import re

MAX_RANGE = 8
_PAGE_RE = re.compile(r"(?:\bp\.?\s*|\bslide\s*)(\d{1,4})(?:\s*[–\-~]\s*(?:p\.?\s*)?(\d{1,4}))?|(\d{1,4})\s*쪽", re.I)


def pages_of(locator: str) -> list[int]:
    pages = []
    for match in _PAGE_RE.finditer(locator):
        if match.group(3):
            pages.append(int(match.group(3)))
            continue
        a = int(match.group(1))
        b = int(match.group(2)) if match.group(2) else a
        lo, hi = min(a, b), max(a, b)
        pages.extend(range(lo, hi + 1) if hi - lo < MAX_RANGE else (lo, hi))
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


def primary_pages(question: dict, available: list[int]) -> set[int]:
    """직접 인용한 근거를 인용 순서대로 최대 두 장 보여 준다.

    별도의 핵심 근거 표시는 없으므로 보기 후보 전체의 출처는 우선하지 않는다.
    해당 이미지가 없거나 옛 문항에 쪽 정보가 없으면 제공 가능한 첫 장을 쓴다.
    """
    direct = dict.fromkeys(page for ref in question.get("source_refs", [])
                           if ref["source_id"] == "S1" for page in pages_of(ref["locator"])
                           if page in available)
    return set(list(direct)[:2] or available[:1])
