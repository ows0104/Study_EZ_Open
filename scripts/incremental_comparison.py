"""Read-only incremental review metrics, available in every Git checkout.

Preserved from the 2026-10-15 local observation helper. No model calls or writes.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from server.app.bank_validation import pool_checks
from server.app.bank_validation.publication import usable


def read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # A currently appended final line is not a completed record.
    return rows


def metrics(folder):
    usage = jsonl(folder / "usage.jsonl")
    by_stage = defaultdict(list)
    for row in usage:
        if isinstance(row.get("seconds"), (int, float)):
            by_stage[row["step"]].append(row["seconds"])
    result = read(folder / "result.json", {})
    return {"path": str(folder), "runId": folder.parents[1].name,
            "questions": result.get("questions"), "repairAttempts": result.get("repairs", {}).get("attempts"),
            "cliSeconds": round(sum(sum(v) for v in by_stage.values()), 1),
            "stageSeconds": {k: round(sum(v), 1) for k, v in by_stage.items()},
            "stageCalls": {k: len([x for x in v if x > 0]) for k, v in by_stage.items()},
            "stageDurations": dict(by_stage),
            "publicationAllowed": result.get("publication", {}).get("allowed"),
            "models": sorted({m for r in usage for m in r.get("models", [])})}


def quality_checks(folder, events):
    checks = {"scopeIdsDisjointAndComplete": True, "firstPassReviewsAllItems": True,
              "independentAnswerReuseMatchesPriorHashAndTime": True}
    checked_before, counts = {}, Counter()
    for event in events:
        stage = event["stage"]
        fresh, reused = event["checkedQuestionIds"], event["reusedQuestionIds"]
        known = set(event["keys"])
        checks["scopeIdsDisjointAndComplete"] &= (not set(fresh).intersection(reused)
            and set(fresh) | set(reused) == known and len(fresh) + len(reused) == len(known))
        if not counts[stage]:
            checks["firstPassReviewsAllItems"] &= not reused and set(fresh) == known
        if stage == "answer":
            for qid in reused:
                checks["independentAnswerReuseMatchesPriorHashAndTime"] &= checked_before.get(qid) == (
                    event["keys"][qid], event["priorJudgments"][qid])
            for qid in fresh:
                checked_before[qid] = (event["keys"][qid], event["checkedAt"])
        counts[stage] += 1
    source_events = [e for e in events if e["stage"] == "source"]
    checks["globalSourceCheckEveryRound"] = (bool(source_events)
        and len(source_events) == counts["answer"] and all(e.get("globalSourceCheck") for e in source_events))
    bank, review = read(folder / "bank.json"), read(folder / "review.json")
    validation, coverage = read(folder / "validation.json"), read(folder / "coverage.json")
    points = read(folder / "authored-points.json", [])
    explanations = read(folder / "explanations.json", {})
    if not all(isinstance(v, dict) for v in (bank, review, validation, coverage)):
        checks["finalRecordsAvailable"] = False
        return checks
    checks["finalRecordsAvailable"] = True
    ids = {q["question_id"] for q in bank["questions"]}
    reviewed = [r["question_id"] for r in review.get("reviews", [])]
    checks["finalAnswerReviewComplete"] = set(reviewed) == ids and len(reviewed) == len(ids) and not review.get("missing")
    expected_explanations = {q["question_id"] for q in bank["questions"] if q["format"] in ("mcq", "multi_select", "ox")}
    actual_explanations = [r["question_id"] for r in explanations.get("annotations", [])]
    checks["finalExplanationReviewComplete"] = set(actual_explanations) == expected_explanations and len(actual_explanations) == len(expected_explanations)
    answer_pools, _ = pool_checks.assess(bank, review.get("pool_checks", []))
    source_pools, _ = pool_checks.assess(bank, coverage.get("webAudit", {}).get("pool_checks", []))
    checks["poolChecksCurrentAndComplete"] = answer_pools["status"] == source_pools["status"] == "verified"
    raw = coverage.get("webAudit", {})
    checks["finalFullSourceAndPointCoverageRecorded"] = (
        {p["page"] for p in raw.get("pages", [])} == set(range(1, coverage.get("totalPages", 0) + 1))
        and len(raw.get("pages", [])) == coverage.get("totalPages", 0)
        and {p["point_id"] for p in raw.get("checks", [])} == {p["point_id"] for p in points}
        and len(raw.get("checks", [])) == len(points))
    result = read(folder / "result.json", {})
    checks["repairLimitRespected"] = result.get("repairs", {}).get("attempts", 4) <= 3
    checks["finalStructurePublishable"] = usable(bank, validation)
    # Compare aggregate judgments before and after repairs without generating a
    # new medical opinion. Source-derived doubt annotations may legitimately
    # change after a new global audit; an unchanged wrong answer must stay wrong.
    snapshots = []
    for path in sorted((folder / "repair").glob("[1-3]/findings.json")):
        findings = read(path, {})
        if findings.get("review"):
            snapshots.append(findings["review"])
    snapshots.append(review)
    answer_events = [e for e in events if e["stage"] == "answer"]
    checks["unchangedWrongVerdictsPreserved"] = True
    for i in range(1, min(len(snapshots), len(answer_events))):
        before = {r["question_id"]: r for r in snapshots[i - 1].get("reviews", [])}
        after = {r["question_id"]: r for r in snapshots[i].get("reviews", [])}
        for qid in answer_events[i]["reusedQuestionIds"]:
            if before.get(qid, {}).get("verdict") == "wrong":
                checks["unchangedWrongVerdictsPreserved"] &= after.get(qid, {}).get("verdict") == "wrong"
    return checks

