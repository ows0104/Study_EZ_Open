"""생성기 의존성 없이 원본 대조 보고서의 현재성만 확인한다."""
import hashlib
import json


def bank_hash(bank: dict) -> str:
    return hashlib.sha256(json.dumps(bank, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def coverage_summary(bank: dict, validation: dict) -> dict | None:
    report = validation.get("coverage")
    if not isinstance(report, dict):
        return None
    current = report.get("bankHash") == bank_hash(bank)
    keys = ("status", "totalPages", "checkedPages", "excludedPages", "unreadablePages", "gapCount",
            "addedQuestions", "addedMcq", "checkedAt", "sourceFilename")
    issues = [{"page": row["page"], "note": row["note"],
               "facts": [point["fact"] for point in row.get("points", []) if point.get("status") == "gap"]}
              for row in report.get("pages", []) if row.get("status") == "unreadable"
              or any(point.get("status") == "gap" for point in row.get("points", []))]
    return {**{key: report.get(key) for key in keys}, "issues": issues,
            "status": report.get("status") if current else "stale"}
