"""Bank checkpoint identity, repair budget, and artifact diagnostics. No HTTP or processes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _resume(runs_dir: Path, run_id: str, got: dict, pdf: Path) -> dict | None:
    record = _read(runs_dir / run_id / "bank" / "resume.json")
    if not record or got.get("existingBank") is None:
        return None
    expected = hashlib.sha256(json.dumps(got["existingBank"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if (record.get("expectedBankHash") != expected or record.get("baseBuildId") != got.get("baseBuildId")
            or record.get("sourceSha256") != hashlib.sha256(pdf.read_bytes()).hexdigest()):
        return None
    if not all(Path(record.get(key, "")).is_file() for key in ("bankPath", "pointPlanPath")):
        return None
    return record


def _response_identity(got: dict, pdf: Path, jokbo: Path | None = None) -> dict:
    return {"responseHash": hashlib.sha256(got.get("raw", "").encode("utf-8")).hexdigest(),
            "respondedAt": got["respondedAt"], "promptVersion": got.get("promptVersion", ""),
            "title": got["title"], "sources": got.get("sources", []),
            "sourceSha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "jokboSha256": hashlib.sha256(jokbo.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if jokbo is not None and jokbo.is_file() else None}


def _response_resume(runs_dir: Path, run_id: str, got: dict, pdf: Path,
                     jokbo: Path | None = None) -> dict | None:
    """Continue CLI edits only when the response and every source identity still match."""
    root = (runs_dir / run_id / "bank").resolve()
    try:
        record = _read(root / "response-resume.json")
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("identity") != _response_identity(got, pdf, jokbo):
        return None
    remaining = record.get("remainingRepairRounds", 2)  # Legacy records retain the old allowance.
    if type(remaining) is not int or not 0 <= remaining <= 3:
        return None
    for key in ("bankPath", "pointPlanPath"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        path = Path(value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
    return record


def _record_response_resume(runs_dir: Path, run_id: str, got: dict, pdf: Path, out: Path,
                            jokbo: Path | None = None, *, identity: dict | None = None,
                            remaining_repair_rounds: int | None = None) -> None:
    point_path = next((path for path in (out / "authored-points.json", out / "web-audit/point-plan.json")
                       if path.is_file()), None)
    if not (out / "bank.json").is_file() or point_path is None:
        return
    try:
        if not isinstance(_read(out / "bank.json"), dict) or not isinstance(_read(point_path), list):
            return
    except (OSError, ValueError):
        return  # Interrupted writes are never a resumable candidate.
    current_identity = _response_identity(got, pdf, jokbo)
    if identity is not None and identity != current_identity:
        return
    record = {"identity": current_identity, "bankPath": str((out / "bank.json").resolve()),
              "pointPlanPath": str(point_path.resolve())}
    if remaining_repair_rounds is not None:
        if type(remaining_repair_rounds) is not int or not 0 <= remaining_repair_rounds <= 3:
            raise ValueError("CLI 수정 상한은 0~3회여야 합니다.")
        record["remainingRepairRounds"] = remaining_repair_rounds
    path = runs_dir / run_id / "bank/response-resume.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_additions(out: Path, original: dict) -> None:
    validation = _read(out / "validation.json")
    if not isinstance((validation or {}).get("coverage"), dict):
        return
    current = _read(out / "bank.json")
    def mcqs(bank):
        return sum(q.get("format") in ("mcq", "multi_select") for q in bank["questions"])
    counts = {"addedQuestions": len(current["questions"]) - len(original["questions"]), "addedMcq": mcqs(current) - mcqs(original)}
    validation["coverage"].update(counts)
    (out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    if (out / "coverage.json").is_file():
        (out / "coverage.json").write_text(json.dumps(validation["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")
    result = _read(out / "result.json")
    if result and result.get("coverage"):
        result["coverage"].update(counts)
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _revision_summary(out: Path, result: dict) -> str:
    """Summarize blocking CLI findings without counting nonblocking doubts."""
    audit = _read(out / "web-audit.json") or {}
    review = _read(out / "review.json") or {}
    explanations = _read(out / "explanations.json") or {}
    wrong = {row["question_id"] for row in audit.get("question_issues", []) if row.get("severity") == "error"}
    wrong.update(row["question_id"] for row in review.get("reviews", []) if row.get("verdict") == "wrong")
    wrong.update(row["question_id"] for row in explanations.get("annotations", []) if row.get("verdict") == "wrong")
    parts = []
    if wrong:
        parts.append(f"문항 오류 {len(wrong)}건({', '.join(sorted(wrong)[:5])})")
    for label, count in (("구조·의미 검증 오류", result.get("errors", 0)),
                         ("미충족 포인트", (result.get("coverage") or {}).get("gapCount", 0)),
                         ("누락된 출제 목표", sum(row.get("kind") == "missing_point" for row in audit.get("plan_issues", []))),
                         ("중복 묶음", len(audit.get("duplicates", []))),
                         ("정답 검토 누락", len(review.get("missing", []))),
                         ("읽지 못한 원본 쪽", (result.get("coverage") or {}).get("unreadablePages", 0))):
        if count:
            parts.append(f"{label} {count}건")
    return " · ".join(parts)
