"""Inspect authored questions and the current point plan; CLI repair consumes the findings."""
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
from .generate import item_quality_guidance, lecture_scope
from . import priority, web_priorities
from .points import INT, STR, _array, _object
from .session import SessionError
from server.app.bank_validation import pool_checks

PROMPT = Path(__file__).parent / "prompts" / "web-review.md"

def enum(*values):
    return {"type": "string", "enum": list(values)}

REPORT = _object({
    "summary": STR,
    "pages": _array(_object({"page": INT, "status": enum("checked", "excluded", "unreadable"), "note": STR})),
    "checks": _array(_object({"point_id": STR, "status": enum("covered", "partial", "gap", "uncertain", "excluded"),
                              "question_ids": _array(STR), "note": STR})),
    "plan_issues": _array(_object({"kind": enum("missing_point", "out_of_scope", "uncertain"),
        "point_ids": _array(STR), "pages": _array(INT), "fact": STR, "reason": STR})),
    "question_issues": _array(_object({"question_id": STR, "severity": enum("error", "doubt", "suggestion"),
        "issue": STR, "reason": STR, "suggested_action": STR})),
    "duplicates": _array(_object({"question_ids": _array(STR), "reason": STR, "suggested_action": STR})),
    "classifications": _array(_object({"question_id": STR, "recommended_mode": enum("recall_first", "comparison"), "reason": STR})),
    "pool_checks": pool_checks.CHECK_SCHEMA,
    "tier_checks": priority.CHECK_SCHEMA,
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
        row = dict(zip(header, cells, strict=True))
        if not all(row.values()) or row["point_id"] in seen:
            raise SessionError("웹 출제 포인트의 ID·내용·근거가 없거나 ID가 중복됐습니다.")
        seen.add(row["point_id"])
        result.append(row)
    if not result:
        raise SessionError("Exam Point Plan이 없습니다. CLI에서 원본에 근거한 출제 포인트 보완이 필요합니다.")
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
    raw = copy.deepcopy(raw)
    # Historical reports remain readable; newly produced REPORTs require this
    # field through their schema. Global Tier decisions are never item-cached.
    tier_review = None
    if "tier_checks" in raw:
        tier_review, tier_issues = priority.assess(bank, raw["tier_checks"])
        for issue in tier_issues:
            if issue not in raw["question_issues"]:
                raw["question_issues"].append(issue)
    pool_coverage, valid_pool_checks = pool_checks.assess(bank, raw.get('pool_checks', []))
    for row in pool_checks.notes(valid_pool_checks):
        issue = {'question_id': row['question_id'],
            'severity': 'error' if row['verdict'] == 'wrong' else 'doubt',
            'issue': '보기 풀 후보 검수', 'reason': row['note'],
            'suggested_action': '해당 후보의 참·거짓·선택 기준과 근거를 확인한다.'}
        if issue not in raw['question_issues']:
            raw['question_issues'].append(issue)
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
        if check["status"] == "excluded" and not check["note"].strip():
            raise SessionError("원본 검수: 학습 목표 제외의 범위·출처 관리 근거가 필요합니다.")
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
    excluded = {pid for pid, check in checks.items() if check["status"] == "excluded"}
    active = point_ids - excluded
    for point in points:
        check = checks[point["point_id"]]
        if point["point_id"] in excluded:
            continue
        refs = authored_pages(point["source_refs"], pdf_source)
        refs = [p for p in refs if p in pages]
        for p in set(refs):
            pages[p]["points"].append({**check, "fact": point["point"],
                "status": check["status"] if check["status"] in ("covered", "uncertain") else "gap"})
    unresolved = sum(checks[pid]["status"] in ("partial", "gap") for pid in active)
    uncertain = sum(checks[pid]["status"] == "uncertain" for pid in active)
    unreadable = sum(row["status"] == "unreadable" for row in pages.values())
    wrong_modes = sum(row["recommended_mode"] != mcqs[qid].get("mcq_mode") for qid, row in modes.items())
    plan_issues = [issue for issue in raw["plan_issues"] if not (
        issue["kind"] in ("uncertain", "out_of_scope") and issue["point_ids"]
        and set(issue["point_ids"]).issubset(excluded))]
    issues = sum(issue["kind"] != "uncertain" for issue in plan_issues) + len(raw["duplicates"]) + wrong_modes + int(not active)
    issues += int(pool_coverage['status'] != 'verified')
    issues += sum(row["severity"] == "error" for row in raw["question_issues"])
    classification = {"status": "partial" if wrong_modes else "verified", "classifiedCount": len(mcqs),
        "recallFirstCount": sum(q.get("mcq_mode") == "recall_first" for q in mcqs.values()),
        "comparisonCount": sum(q.get("mcq_mode") == "comparison" for q in mcqs.values()), "classifications": raw["classifications"]}
    return {"status": "partial" if unresolved or unreadable or issues else "verified", "summary": raw["summary"],
        "pages": [pages[p] for p in range(1, count + 1)], "totalPages": count,
        "checkedPages": sum(row["status"] == "checked" for row in pages.values()),
        "excludedPages": sum(row["status"] == "excluded" for row in pages.values()),
        "unreadablePages": unreadable, "gapCount": unresolved, "pointCount": len(active),
        "coveredPointCount": len(active) - unresolved - uncertain, "uncertainPointCount": uncertain,
        "excludedPointCount": len(excluded),
        "excludedPoints": [{**p, "note": checks[p["point_id"]]["note"]} for p in points if p["point_id"] in excluded],
        "addedQuestions": 0, "addedMcq": 0,
        "checkedAt": datetime.now(UTC).isoformat(), "bankHash": bank_hash(bank),
        "classification": classification, "webAudit": raw, "poolCoverage": pool_coverage,
        "tierReview": tier_review,
        "requiresRevision": bool(unresolved or unreadable or issues)}

def inspect(bank: dict, raw: str, pdf: Path, title: str, sources: list[dict], out: Path,
            *, jokbo: Path | None = None, model: str | None = None,
            points: list[dict] | None = None, defer_structure: bool = False) -> tuple[dict, list[dict]]:
    points = parse_points(raw) if points is None else points
    work = out / "web-audit"
    work.mkdir(exist_ok=True)
    with fitz.open(pdf) as doc:
        count = len(doc)
        source_text = "\n\n".join(f"## PDF p.{i + 1}\n{page.get_text()}" for i, page in enumerate(doc))
    images = render(pdf, f"1-{count}", work / "source-pages")
    (work / "source-text.md").write_text(source_text, encoding="utf-8")
    for name, data in [("bank.json", bank), ("point-plan.json", points),
                       ("source-pages.json", [str(path.resolve()) for path in images]),
                       ("context.json", {"title": title, "sources": sources, "page_count": count,
                                         "lecture_scope": lecture_scope(title, sources)}),
                       ("pool-candidates.json", pool_checks.candidates(bank)),
                       ("web-priorities.json", web_priorities.reference(raw))]:
        (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (work / "web-response.md").write_text(raw, encoding="utf-8")
    if jokbo:
        (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
    prompt = PROMPT.read_text(encoding="utf-8")
    if defer_structure:
        prompt += "\n문항 우선 단계다. point-plan.json은 원본 독립 추출 결과다. concepts·retrieval_plan과 " \
            "concept_id·prerequisites는 내용 검수 뒤 연결하므로 현재 빈 값은 정상 계약이다. " \
            "integration을 포함한 선행 관계는 사후 연결 단계에서 검토한다."
    else:
        prompt += "\n과거 계획 선행 응답의 포인트·개념도·회상 계획·선행 관계는 정상 입력 계약이다. " \
            "새 웹 출력 형식을 이유로 기존 학습 구조를 삭제하거나 오류로 판정하지 않는다."
    prompt += "\n\n" + item_quality_guidance()
    raw_report, info = _call(prompt, REPORT, work, model, "원본·포인트·중복 검수")
    pdf_source = next((s["id"] for s in sources if s.get("filename") == pdf.name), "S1")
    report = shape_report(raw_report, bank, points, count, pdf_source=pdf_source)
    report.update(sourceFilename=pdf.name, sourceSha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
    (out / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "web-audit.json").write_text(json.dumps(report["webAudit"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "classification.json").write_text(json.dumps(report["classification"], ensure_ascii=False, indent=2), encoding="utf-8")
    return report, [{"step": "원본·포인트·중복 검수", **info}]
