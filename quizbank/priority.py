"""Validate source-grounded priority decisions; never infer tiers from keywords."""
from __future__ import annotations

from .points import STR, _array, _object
from .session import SessionError

BASIS = ("emphasis", "objective", "past_exam", "essential_dependency", "extension", "detail")
CORE_BASES = set(BASIS[:4])
ISSUE = "Tier 근거 불일치"
CHECK_SCHEMA = _array(_object({
    "question_id": STR,
    "recommended_tier": {"type": "string", "enum": ["Core", "Advanced", "Optional"]},
    "tested_target": STR,
    "basis": {"type": "string", "enum": list(BASIS)},
    "source_refs": _array(STR),
    "evidence": STR,
    "essential_target": STR,
    "reason": STR,
}))


def assess(bank: dict, rows: list[dict]) -> tuple[dict, list[dict]]:
    """Require one decision per question and concrete support for a Core claim.

    The CLI decides educational priority. This checks coverage and provenance,
    and forwards disagreements to repair without silently relabeling questions.
    """
    questions = {q["question_id"]: q for q in bank["questions"]}
    seen, issues = set(), []
    for row in rows:
        qid = row["question_id"]
        if qid not in questions or qid in seen:
            raise SessionError("Tier 검수: 문항 ID가 없거나 중복됐습니다.")
        seen.add(qid)
        if (not all(row[key].strip() for key in ("tested_target", "evidence", "reason"))
                or not row["source_refs"] or not all(ref.strip() for ref in row["source_refs"])):
            raise SessionError("Tier 검수: 실제 인출 목표와 원본 근거가 필요합니다.")
        tier, basis = row["recommended_tier"], row["basis"]
        if tier not in ("Core", "Advanced", "Optional") or basis not in BASIS:
            raise SessionError("Tier 검수: 등급·근거 유형이 맞지 않습니다.")
        if tier == "Core" and (basis not in CORE_BASES
                or (basis == "essential_dependency" and not row["essential_target"].strip())):
            raise SessionError("Tier 검수: Core의 직접 근거 또는 구체적 필수 의존 목표가 필요합니다.")
        if tier != questions[qid]["tier"]:
            issues.append({"question_id": qid, "severity": "error", "issue": ISSUE,
                "reason": f"{questions[qid]['tier']} → {tier}: {row['reason']} 근거: {row['evidence']}",
                "suggested_action": f"원본 근거를 대조해 {tier}로 교정한다. 기존 오류·누락 판정은 보존한다."})
    if seen != set(questions):
        raise SessionError("Tier 검수: 일부 문항의 우선순위 검토가 빠졌습니다.")
    return {"status": "partial" if issues else "verified", "checkedCount": len(seen),
            "mismatchCount": len(issues), "checks": rows}, issues
