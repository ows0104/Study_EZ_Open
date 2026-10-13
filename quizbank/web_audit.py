"""Verify a web-authored bank against its point plan without generating or editing questions."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import fitz

from studyez_llm.pdf import render
from .coverage import _call, bank_hash
from .generate import item_quality_guidance
from .points import _array, _object, STR, INT
from .session import SessionError

PROMPT = Path(__file__).parent / "prompts" / "web-review.md"

def enum(*values):
    return {"type": "string", "enum": list(values)}

REPORT = _object({
    "summary": STR,
    "pages": _array(_object({"page": INT, "status": enum("checked", "excluded", "unreadable"), "note": STR})),
    "checks": _array(_object({"point_id": STR, "status": enum("covered", "partial", "gap", "uncertain"),
                              "question_ids": _array(STR), "note": STR})),
    "plan_issues": _array(_object({"kind": enum("missing_point", "out_of_scope", "uncertain"),
        "point_ids": _array(STR), "pages": _array(INT), "fact": STR, "reason": STR})),
    "question_issues": _array(_object({"question_id": STR, "severity": enum("error", "doubt", "suggestion"),
        "issue": STR, "reason": STR, "suggested_action": STR})),
    "duplicates": _array(_object({"question_ids": _array(STR), "reason": STR, "suggested_action": STR})),
    "classifications": _array(_object({"question_id": STR, "recommended_mode": enum("recall_first", "comparison"), "reason": STR})),
})

def enabled(version: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.\d+)?", version)
    return bool(match and int(match[1]) == 1 and int(match[2]) >= 29)

def parse_points(raw: str) -> list[dict]:
    """Read the authored table deterministically; a missing plan is never silently rebuilt."""
    result, header, seen = [], None, set()
    for line in raw.splitlines():
        if "|" not in line:
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        normalized = [re.sub(r"[`*]", "", cell).strip().lower() for cell in cells]
        if set(normalized) == {"point_id", "point", "source_refs"} and len(cells) == 3:
            header = normalized
            continue
        if header is None or all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
            continue
        if len(cells) != len(header):
            raise SessionError("웹 출제 포인트 표의 열 수가 맞지 않습니다.")
        row = dict(zip(header, cells))
        if not all(row.values()) or row["point_id"] in seen:
            raise SessionError("웹 출제 포인트의 ID·내용·근거가 없거나 ID가 중복됐습니다.")
        seen.add(row["point_id"])
        result.append(row)
    if not result:
        raise SessionError("Exam Point Plan이 없습니다. 웹에서 출제 포인트 표를 포함해 다시 출력하세요.")
    return result

def authored_pages(refs: str, pdf_source: str = "S1") -> list[int]:
    """Read PDF ranges and comma lists without treating jokbo pages as PDF pages."""
    pages = set()
    for section in re.split(r";|<br\s*/?>", refs, flags=re.I):
        source = re.match(r"\s*([A-Za-z]+\d*|EXT)\b", section)
        if not source or source[1] != pdf_source:
            continue
        for match in re.finditer(r"\b(?:pp?\.?|slides?)\s*(\d+(?:\s*(?:[–—~\-]\s*\d+|,\s*\d+))*)", section, re.I):
            for span in match[1].split(","):
                bounds = re.split(r"[–—~\-]", span)
                first, last = int(bounds[0]), int(bounds[-1])
                if abs(last - first) > 1000:
                    raise SessionError("웹 출제 포인트의 근거 쪽 범위가 너무 큽니다.")
                pages.update(range(min(first, last), max(first, last) + 1))
    return sorted(pages)


def shape_report(raw: dict, bank: dict, points: list[dict], count: int, *, pdf_source: str = "S1") -> dict:
    known = {q["question_id"] for q in bank["questions"]}
    point_ids = {p["point_id"] for p in points}
    mcqs = {q["question_id"]: q for q in bank["questions"] if q["format"] in ("mcq", "multi_select")}
    pages, checks, modes = {}, {}, {}
    for row in raw["pages"]:
        if row["page"] in pages or not 1 <= row["page"] <= count:
            raise SessionError("웹 검수: 중복되거나 원본에 없는 쪽")
        pages[row["page"]] = copy.deepcopy(row)
    if set(pages) != set(range(1, count + 1)):
        raise SessionError("웹 검수: 일부 원본 쪽의 검토 결과가 없습니다.")
    for check in raw["checks"]:
        pid = check["point_id"]
        if pid not in point_ids or pid in checks or not set(check["question_ids"]).issubset(known):
            raise SessionError("웹 검수: 포인트·문항 ID가 없거나 중복됐습니다.")
        if check["status"] == "covered" and not check["question_ids"]:
            raise SessionError("웹 검수: 충족 판정에 실제 문항이 필요합니다.")
        checks[pid] = check
    if set(checks) != point_ids:
        raise SessionError("웹 검수: 일부 출제 포인트를 대조하지 않았습니다.")
    for issue in raw["question_issues"]:
        if issue["question_id"] not in known:
            raise SessionError("웹 검수: 존재하지 않는 문제의 지적")
    for issue in raw["plan_issues"]:
        if not set(issue["point_ids"]).issubset(point_ids) or any(not 1 <= p <= count for p in issue["pages"]):
            raise SessionError("웹 검수: 계획 지적의 ID·근거 쪽이 맞지 않습니다.")
    for group in raw["duplicates"]:
        if len(set(group["question_ids"])) < 2 or not set(group["question_ids"]).issubset(known):
            raise SessionError("웹 검수: 중복 묶음의 문항 ID가 맞지 않습니다.")
    for row in raw["classifications"]:
        qid = row["question_id"]
        if qid not in mcqs or qid in modes or not row["reason"].strip():
            raise SessionError("웹 검수: 객관식 분류의 문항·근거가 맞지 않습니다.")
        modes[qid] = row
    if set(modes) != set(mcqs):
        raise SessionError("웹 검수: 일부 객관식 유형을 검토하지 않았습니다.")
    for row in pages.values():
        row["points"] = []
    for point in points:
        check = checks[point["point_id"]]
        refs = authored_pages(point["source_refs"], pdf_source)
        refs = [p for p in refs if p in pages]
        for p in set(refs):
            pages[p]["points"].append({**check, "fact": point["point"],
                "status": "covered" if check["status"] == "covered" else "gap"})
    unresolved = sum(check["status"] != "covered" for check in checks.values())
    unreadable = sum(row["status"] == "unreadable" for row in pages.values())
    wrong_modes = sum(row["recommended_mode"] != mcqs[qid].get("mcq_mode") for qid, row in modes.items())
    issues = len(raw["plan_issues"]) + len(raw["duplicates"]) + wrong_modes
    issues += sum(row["severity"] != "suggestion" for row in raw["question_issues"])
    classification = {"status": "partial" if wrong_modes else "verified", "classifiedCount": len(mcqs),
        "recallFirstCount": sum(q.get("mcq_mode") == "recall_first" for q in mcqs.values()),
        "comparisonCount": sum(q.get("mcq_mode") == "comparison" for q in mcqs.values()), "classifications": raw["classifications"]}
    return {"status": "partial" if unresolved or unreadable or issues else "verified", "summary": raw["summary"],
        "pages": [pages[p] for p in range(1, count + 1)], "totalPages": count,
        "checkedPages": sum(row["status"] == "checked" for row in pages.values()),
        "excludedPages": sum(row["status"] == "excluded" for row in pages.values()),
        "unreadablePages": unreadable, "gapCount": unresolved, "pointCount": len(points),
        "coveredPointCount": len(points) - unresolved, "addedQuestions": 0, "addedMcq": 0,
        "checkedAt": datetime.now(UTC).isoformat(), "bankHash": bank_hash(bank),
        "classification": classification, "webAudit": raw, "requiresRevision": bool(unresolved or unreadable or issues)}

def inspect(bank: dict, raw: str, pdf: Path, title: str, sources: list[dict], out: Path,
            *, jokbo: Path | None = None, model: str | None = None) -> tuple[dict, list[dict]]:
    points = parse_points(raw)
    work = out / "web-audit"
    work.mkdir(exist_ok=True)
    with fitz.open(pdf) as doc:
        count = len(doc)
        source_text = "\n\n".join(f"## PDF p.{i + 1}\n{page.get_text()}" for i, page in enumerate(doc))
    images = render(pdf, f"1-{count}", work / "source-pages")
    (work / "source-text.md").write_text(source_text, encoding="utf-8")
    for name, data in [("bank.json", bank), ("point-plan.json", points),
                       ("source-pages.json", [str(path.resolve()) for path in images]),
                       ("context.json", {"title": title, "sources": sources, "page_count": count})]:
        (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (work / "web-response.md").write_text(raw, encoding="utf-8")
    if jokbo:
        (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
    prompt = item_quality_guidance() + "\n\n" + PROMPT.read_text(encoding="utf-8") + "\n\n작업 파일: context.json, source-text.md, source-pages.json, " \
        "point-plan.json, web-response.md, bank.json, 있으면 jokbo.md. 원본 이미지도 view_image로 확인한다. " \
        "파일을 변경하지 말고 지정 JSON 스키마로 최종 검수 결과를 반환한다. pages는 PDF의 모든 물리 쪽, " \
        "checks는 모든 point_id, classifications는 모든 mcq·multi_select question_id를 정확히 한 번 포함한다. " \
        "읽지 못한 쪽은 unreadable로 기록한다. note·reason은 간결하게 쓴다."
    raw_report, info = _call(prompt, REPORT, work, model, "웹 출제 원본·포인트·중복 검수")
    pdf_source = next((s["id"] for s in sources if s.get("filename") == pdf.name), "S1")
    report = shape_report(raw_report, bank, points, count, pdf_source=pdf_source)
    report.update(sourceFilename=pdf.name, sourceSha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
    (out / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "web-audit.json").write_text(json.dumps(raw_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "classification.json").write_text(json.dumps(report["classification"], ensure_ascii=False, indent=2), encoding="utf-8")
    return report, [{"step": "웹 출제 원본·포인트·중복 검수", **info}]
