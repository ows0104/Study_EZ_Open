"""문제은행 JSON 의 모양. 정리 세션에 `--output-schema` 로 주고, 같은 것으로 다시 잰다.

AdaptiveStudy3/bank_builder/schema.mjs 를 옮겼다(2026-10-04). 서버도 같은 모양을 받으므로
필드를 바꿀 때는 server/app/routes/bank.py와 web/src/types/bank.ts를 같이 본다.
"""

from __future__ import annotations

FORMATS = ["basic", "cloze", "list", "ox", "mcq", "multi_select", "matching", "sequence"]
DIRECTIONS = ["direct", "reverse", "mechanism", "discrimination", "integration", "sequence", "trap"]
TIERS = ["Core", "Advanced", "Optional"]
SCHEMA_VERSION = "4.2"

_STR = {"type": "string"}
_NUM = {"type": "number"}
_INT = {"type": "integer"}
_STRS = {"type": "array", "items": _STR}


def _enum(values: list[str]) -> dict:
    return {"type": "string", "enum": values}


def _array(items: dict) -> dict:
    return {"type": "array", "items": items}


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


SOURCE_REF = _object({"source_id": _STR, "locator": _STR})

# Both forms are authored and medically reviewed. The service never invents a
# negation or infers truth from an existing distractor.
OPTION_POOL = _object({
    "pool_id": _STR, "select_count": _INT, "correct_when": _enum(["true", "false"]),
    "candidates": _array(_object({
        "candidate_id": _STR, "true_text": _STR, "false_text": _STR,
        "true_explanation": _STR, "false_explanation": _STR,
        "source_refs": _array(SOURCE_REF),
    })),
})

OBJECTIVE = _object({
    "objective_id": _STR, "concept_id": _STR, "title": _STR, "target": _STR,
    "kind": _enum(["fact", "mechanism", "discrimination", "sequence"]),
    "importance": _INT, "rationale": _STR, "source_refs": _array(SOURCE_REF),
    "context": _STR, "explanation": _STR, "minimum": _STR, "prerequisites": _STRS,
})

QUESTION = _object({
    "question_id": _STR, "concept_id": _STR, "tier": _enum(TIERS), "importance": _INT,
    "item_difficulty": _INT, "format": _enum(FORMATS), "retrieval_direction": _enum(DIRECTIONS),
    "question": _STR, "answer": _STR, "answer_units": _STRS, "prerequisites": _STRS,
    "source_refs": _array(SOURCE_REF), "exam_rationale": _STR,
    "conflict_id": _STR, "options": _array(_object({"id": _STR, "text": _STR})),
    "correct_option_ids": _STRS,
    # matching 은 왼쪽·오른쪽을 따로 보여 주고 짝은 답을 볼 때만 준다.
    "matching_left": _STRS, "matching_right": _STRS,
    "answer_pairs": _array(_object({"left": _STR, "right": _STR})),
    "sequence_items": _STRS, "correct_order": _STRS,
    "primary_objective_id": _STR, "supporting_objective_ids": _STRS,
    "role": _enum(["learning", "variant", "exam"]), "recall_prompt": _STR,
    "option_explanations": _array(_object({"option_id": _STR, "text": _STR})),
    "option_pools": _array(OPTION_POOL),
})

BANK = _object({
    "build_meta": _object({"schema_version": _STR, "lecture_title": _STR}),
    "source_summary": _array(_object({"source_id": _STR, "summary": _STR})),
    "source_conflicts": _array(_object({
        "conflict_id": _STR, "description": _STR, "source_refs": _array(SOURCE_REF),
        "unresolved": {"type": "boolean"}})),
    "concepts": _array(_object({
        "concept_id": _STR, "title": _STR, "graph_title": _STR, "core_facts": _STRS, "source_refs": _array(SOURCE_REF),
        "importance": _INT, "importance_rationale": _STR, "concept_difficulty": _INT,
        "tier": _enum(TIERS), "exam_signal_strength": _enum(["low", "medium", "high"]),
        "related_concepts": _STRS})),
    "retrieval_plan": _array(_object({
        "concept_id": _STR, "directions": _array(_enum(DIRECTIONS)),
        "repetition_budget": _INT, "target_mastery": _NUM})),
    "questions": _array(QUESTION),
    "learning_objectives": _array(OBJECTIVE),
    "coverage_inventory": _array(_object({
        "title": _STR, "source_refs": _array(SOURCE_REF),
        "status": _enum(["target", "explanation", "excluded", "uncertain"]),
        "reason": _STR, "objective_ids": _STRS,
    })),
    "exam_design": _array(_object({
        "question_id": _STR, "basis_refs": _array(SOURCE_REF),
        "changed_dimension": _enum(["condition", "direction", "contrast", "integration"]),
        "novelty": _STR,
    })),
    "audit_summary": _object({"summary": _STR, "rejected_candidate_count": _INT, "changes": _STRS}),
    "warnings": _STRS,
})

# 프롬프트 v1.6(2026-10-05, 관리자)에서 뺀 칸. 앱이 읽지 않았다. 옛 응답·옛 은행에는 남아 있으므로
# 형식을 잴 때와 정리할 때 걷어 낸다(`without_retired`) — 「모르는 칸」 오류로 옛 은행이 막히지 않게.
RETIRED_QUESTION = ("concept_difficulty", "cognitive_type", "source_strength")
RETIRED_PLAN = ("rationale",)


def without_retired(bank: dict) -> dict:
    """뺀 칸을 걷고 새 표시 필드의 기본값을 채운 사본. 받은 은행은 그대로 둔다."""
    if not isinstance(bank, dict):
        return bank
    out = dict(bank)
    out.setdefault("learning_objectives", [])
    out.setdefault("coverage_inventory", [])
    out.setdefault("exam_design", [])
    # 그래프용 요약이 없던 은행도 유효하다. 원래 제목은 바꾸지 않는다.
    if isinstance(bank.get("concepts"), list):
        out["concepts"] = [{"graph_title": "", **c} if isinstance(c, dict) else c for c in bank["concepts"]]
    if isinstance(bank.get("questions"), list):
        out["questions"] = [{"primary_objective_id": "", "supporting_objective_ids": [],
                             "role": "learning", "recall_prompt": "", "option_explanations": [], "option_pools": [],
                             **{k: v for k, v in q.items() if k not in RETIRED_QUESTION}} if isinstance(q, dict) else q
                            for q in bank["questions"]]
    if isinstance(bank.get("retrieval_plan"), list):
        out["retrieval_plan"] = [{k: v for k, v in p.items() if k not in RETIRED_PLAN} if isinstance(p, dict) else p
                                 for p in bank["retrieval_plan"]]
    return out


VERDICTS = ["ok", "doubt", "wrong"]

REVIEW = {
    "type": "object", "additionalProperties": False, "required": ["summary", "reviews"],
    "properties": {
        "summary": _STR,
        "reviews": _array({
            "type": "object", "additionalProperties": False,
            "required": ["question_id", "verdict", "note", "suggested_answer"],
            "properties": {"question_id": _STR, "verdict": _enum(VERDICTS),
                           "note": _STR, "suggested_answer": _STR}}),
    },
}

_TYPES = {"string": str, "boolean": bool, "object": dict, "array": list}


def _type_ok(value, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


def schema_errors(value, schema: dict = BANK, path: str = "$", errors: list[str] | None = None) -> list[str]:
    """`schema` 에 어긋난 자리를 사람이 읽을 말로 모은다. 첫 어긋남에서 멈추지 않는다."""
    errors = [] if errors is None else errors
    if not _type_ok(value, schema["type"]):
        errors.append(f"{path}: {schema['type']} 형식이 필요합니다.")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 허용 값 {', '.join(schema['enum'])}")
    if schema["type"] == "object":
        for key in schema["required"]:
            if key not in value:
                errors.append(f"{path}.{key}: 필수 필드 누락")
        for key, item in value.items():
            if key not in schema["properties"]:
                errors.append(f"{path}.{key}: 알 수 없는 필드")
            else:
                schema_errors(item, schema["properties"][key], f"{path}.{key}", errors)
    if schema["type"] == "array":
        for i, item in enumerate(value):
            schema_errors(item, schema["items"], f"{path}[{i}]", errors)
    return errors
