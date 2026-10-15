"""현재 문항이 실제로 인용한 족보 지면만 돌려준다."""
from .slide_focus import question_hash


def references(report: dict | None, original: dict, presented: dict | None = None) -> list[dict]:
    if not isinstance(report, dict) or report.get("version") != 1:
        return []
    record = report.get("questions", {}).get(original.get("question_id")) or {}
    if record.get("questionHash") != question_hash(original):
        return []
    locators = {ref["locator"] for ref in (presented or original).get("source_refs", []) if ref["source_id"] == "S2"}
    return [ref for locator, refs in record.get("locators", {}).items() if locator in locators for ref in refs]
