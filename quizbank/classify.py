"""문항별 목표에 따른 객관식 공개 방식. 질문 내용과 ID는 보존한다."""
from __future__ import annotations

import copy
from datetime import UTC, datetime

from .points import _object, _array, STR
from .schema import without_retired
from studyez_llm.codex import SessionError

CLASSIFICATION = _object({"classifications": _array(_object({
    "question_id": STR, "mcq_mode": {"type": "string", "enum": ["recall_first", "comparison"]}, "reason": STR}))})


def apply_classifications(bank: dict, raw: dict) -> tuple[dict, dict]:
    updated = copy.deepcopy(without_retired(bank))
    questions = {q["question_id"]: q for q in updated["questions"] if q["format"] in ("mcq", "multi_select")}
    seen, changed = set(), 0
    for item in raw["classifications"]:
        qid = item["question_id"]
        if qid not in questions or qid in seen:
            raise SessionError("객관식 분류: 알 수 없거나 중복된 문항 ID")
        if item["mcq_mode"] not in ("recall_first", "comparison") or not item["reason"].strip():
            raise SessionError("객관식 분류: 유효한 유형과 분류 근거가 필요합니다.")
        seen.add(qid)
        changed += questions[qid]["mcq_mode"] != item["mcq_mode"]
        questions[qid]["mcq_mode"] = item["mcq_mode"]
    if seen != set(questions):
        raise SessionError("객관식 분류: 일부 문항의 분류가 빠졌습니다.")
    return updated, {"status": "verified", "classifiedCount": len(seen), "changedCount": changed,
                     "recallFirstCount": sum(q["mcq_mode"] == "recall_first" for q in questions.values()),
                     "comparisonCount": sum(q["mcq_mode"] == "comparison" for q in questions.values()),
                     "checkedAt": datetime.now(UTC).isoformat(), "classifications": raw["classifications"]}
