"""Validate source-grounded priority decisions; never infer tiers from keywords."""
from __future__ import annotations

from .points import STR, _array, _object
from .session import SessionError

BASIS = ("objective", "past_exam", "emphasis", "clinical", "detail")
CORE_BASES = {"objective", "past_exam"}
IMPORTANCE = {"Core": 5, "Important": 4, "Optional": 2}
ISSUE = "Tier 근거 불일치"
CHECK_SCHEMA = _array(_object({
    "question_id": STR,
    "recommended_tier": {"type": "string", "enum": list(IMPORTANCE)},
    "recommended_importance": {"type": "integer", "minimum": 1, "maximum": 5},
    "recommended_advanced": {"type": "boolean"},
    "advanced_reason": STR,
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
        if tier not in IMPORTANCE or basis not in BASIS:
            raise SessionError("Tier 검수: 등급·근거 유형이 맞지 않습니다.")
        if tier == "Core" and basis not in CORE_BASES:
            raise SessionError("Tier 검수: Core는 실제 학습목표 또는 해당 교수 기출의 직접 근거가 필요합니다.")
        if tier == "Important" and basis not in {"emphasis", "clinical"}:
            raise SessionError("Tier 검수: Important의 실제 강조 또는 구체적인 임상 중요성 근거가 필요합니다.")
        if tier == "Optional" and basis != "detail":
            raise SessionError("Tier 검수: Optional은 목표·기출·강조·임상 중요성에 해당하지 않는 세부사항이어야 합니다.")
        importance = row.get("recommended_importance", questions[qid]["importance"])
        if type(importance) is not int or not 1 <= importance <= 5:
            raise SessionError("Tier 검수: 중요도는 1–5 정수여야 합니다.")
        if importance != IMPORTANCE[tier]:
            raise SessionError("Tier 검수: Core=5, Important=4, Optional=2와 중요도가 다릅니다.")
        advanced = row.get("recommended_advanced")
        if type(advanced) is not bool or (advanced and not row.get("advanced_reason", "").strip()):
            raise SessionError("Tier 검수: 독립 심화 여부와 심화인 경우의 판단 이유가 필요합니다.")
        if (tier != questions[qid]["tier"] or importance != questions[qid]["importance"]
                or advanced != questions[qid].get("advanced", False)):
            issues.append({"question_id": qid, "severity": "error", "issue": ISSUE,
                "reason": f"{questions[qid]['tier']}/{questions[qid]['importance']} → {tier}/{importance}: {row['reason']} 근거: {row['evidence']}",
                "suggested_action": f"원본 근거를 대조해 Tier={tier}, importance={importance}, advanced={advanced}로 교정한다. 심화 근거: {row['advanced_reason']} 기존 오류·누락 판정은 보존한다."})
    if seen != set(questions):
        raise SessionError("Tier 검수: 일부 문항의 우선순위 검토가 빠졌습니다.")
    return {"status": "partial" if issues else "verified", "checkedCount": len(seen),
            "mismatchCount": len(issues), "checks": rows}, issues
