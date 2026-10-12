"""Quizgen의 선행 목표·회수 포인트 계획을 문제은행과 별도로 고정한다."""
from __future__ import annotations

import copy
from datetime import UTC, datetime

from studyez_llm.codex import SessionError


def _object(fields: dict) -> dict:
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def _array(item: dict) -> dict:
    return {"type": "array", "items": item}


STR = {"type": "string"}
INT = {"type": "integer"}
PLAN = _object({"summary": STR, "objectives": _array(_object({
    "objective_id": STR, "objective": STR, "slides": _array(INT),
    "retrieval_targets": _array(_object({"point_id": STR, "target": STR}))})),
    "rejected_candidates": _array(_object({"slides": _array(INT), "reason": STR})),
    "unreadable_pages": _array(INT)})
MATCH_REPORT = _object({"summary": STR, "checks": _array(_object({
    "point_id": STR, "status": {"type": "string", "enum": ["covered", "gap"]},
    "question_ids": _array(STR), "note": STR})),
    "mcq_opportunities": _array(_object({"point_id": STR, "reason": STR}))})


def shape_plan(raw: dict, count: int) -> dict:
    plan = copy.deepcopy(raw)
    objectives, points, pages = set(), set(), set(plan["unreadable_pages"])
    for objective in plan["objectives"]:
        oid = objective["objective_id"]
        if not oid.strip() or oid in objectives or not objective["objective"].strip():
            raise SessionError("출제 포인트 계획: 목표 ID 중복·누락")
        objectives.add(oid)
        if not objective["slides"] or not objective["retrieval_targets"]:
            raise SessionError(f"출제 포인트 계획: {oid} 근거 쪽과 회수 대상이 필요합니다.")
        pages.update(objective["slides"])
        for target in objective["retrieval_targets"]:
            pid = target["point_id"]
            if not pid.strip() or pid in points or not target["target"].strip():
                raise SessionError("출제 포인트 계획: 포인트 ID 중복·누락")
            points.add(pid)
    for rejected in plan["rejected_candidates"]:
        if not rejected["slides"] or not rejected["reason"].strip():
            raise SessionError("출제 포인트 계획: 의도적 제외의 쪽과 근거가 필요합니다.")
        pages.update(rejected["slides"])
    if any(page < 1 or page > count for page in pages):
        raise SessionError("출제 포인트 계획: PDF에 없는 근거 쪽")
    plan["unreadable_pages"] = sorted(set(plan["unreadable_pages"]) | (set(range(1, count + 1)) - pages))
    plan["extracted_at"] = datetime.now(UTC).isoformat()
    return plan


def match_report(raw: dict, bank: dict, plan: dict, count: int) -> dict:
    targets = {target["point_id"]: {**target, "slides": objective["slides"]}
               for objective in plan["objectives"] for target in objective["retrieval_targets"]}
    known = {q["question_id"] for q in bank["questions"]}
    checks = {}
    for check in raw["checks"]:
        pid = check["point_id"]
        if pid not in targets or pid in checks:
            raise SessionError("출제 포인트 대조: 미계획·중복 포인트 ID")
        qids = list(dict.fromkeys(qid for qid in check["question_ids"] if qid in known))
        checks[pid] = {**check, "question_ids": qids,
                       "status": "covered" if check["status"] == "covered" and qids else "gap"}
    for pid in targets:
        checks.setdefault(pid, {"point_id": pid, "status": "gap", "question_ids": [], "note": "이 포인트의 대조 결과가 없습니다."})
    pages = []
    for page in range(1, count + 1):
        points = [{**checks[pid], "fact": target["target"]} for pid, target in targets.items() if page in target["slides"]]
        rejected = [item["reason"] for item in plan["rejected_candidates"] if page in item["slides"]]
        status = "unreadable" if page in plan["unreadable_pages"] else "checked" if points else "excluded"
        pages.append({"page": page, "status": status, "note": " · ".join(rejected) if status != "unreadable"
                      else "출제 포인트 추출에서 이 쪽을 읽지 못했습니다.", "points": points})
    opportunities = []
    for opportunity in raw["mcq_opportunities"]:
        target = targets.get(opportunity["point_id"])
        if target is None:
            raise SessionError("객관식 보강: 계획에 없는 포인트 ID")
        opportunities.append({**opportunity, "page": target["slides"][0], "fact": target["target"]})
    return {"summary": raw["summary"], "pages": pages, "mcq_opportunities": opportunities,
            "pointCount": len(targets), "coveredPointCount": sum(check["status"] == "covered" for check in checks.values()),
            "gapCount": sum(check["status"] == "gap" for check in checks.values()), "extractedAt": plan["extracted_at"]}
