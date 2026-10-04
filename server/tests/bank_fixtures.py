"""Quiz Bank 검사용 문제은행 둘 — AdaptiveStudy3 의 tests/fixtures.mjs · simulator/fixtures.mjs 를 옮겼다.

의학 내용이 없다. 엔진 정책을 재는 것이지 문항을 재는 것이 아니다.
"""

from __future__ import annotations

_EMPTY = {"options": [], "correct_option_ids": [], "matching_left": [], "matching_right": [],
          "answer_pairs": [], "sequence_items": [], "correct_order": []}


def example_bank() -> dict:
    ref = [{"source_id": "S1", "locator": "1절"}]

    def question(qid: str, direction: str, **over) -> dict:
        return {"question_id": qid, "concept_id": "C1", "tier": "Core" if direction == "direct" else "Advanced",
                "importance": 5, "concept_difficulty": 2, "item_difficulty": 2, "format": "basic",
                "cognitive_type": direction, "retrieval_direction": direction,
                "question": f"{qid}: {direction} 예시 질문?", "answer": "예시 정답", "answer_units": ["예시 정답"],
                "prerequisites": [], "source_refs": ref, "source_strength": ["lecture_core"],
                "exam_rationale": "강의의 핵심", "conflict_id": "", **_EMPTY, **over}

    return {
        "build_meta": {"schema_version": "3.0", "lecture_title": "검증용 예시"},
        "source_summary": [{"source_id": "S1", "summary": "테스트용 자료"}], "source_conflicts": [],
        "concepts": [{"concept_id": "C1", "title": "예시 개념", "core_facts": ["기초 사실"], "source_refs": ref,
                      "importance": 5, "importance_rationale": "학습목표", "concept_difficulty": 2, "tier": "Core",
                      "exam_signal_strength": "high", "related_concepts": []}],
        "retrieval_plan": [{"concept_id": "C1", "directions": ["direct", "reverse", "integration"],
                            "rationale": "직접·역방향·통합 회상", "repetition_budget": 4, "target_mastery": 0.85}],
        "questions": [question("Q1", "direct"), question("Q2", "reverse"),
                      question("Q3", "integration", prerequisites=["Q1"])],
        "audit_summary": {"summary": "예시 문항 확인", "rejected_candidate_count": 0, "changes": []},
        "warnings": [],
    }


def simulation_bank() -> dict:
    directions = ["direct", "reverse", "discrimination", "mechanism", "integration", "sequence", "trap"]
    refs = [{"source_id": "SIM", "locator": "synthetic"}]
    concepts, questions, plan = [], [], []
    for i in range(1, 7):
        cid = f"C{i}"
        importance = 5 if i <= 3 else 4 if i <= 5 else 2
        concepts.append({"concept_id": cid, "title": f"합성 개념 {i}", "core_facts": ["합성 사실"], "source_refs": refs,
                         "importance": importance, "importance_rationale": "정책 실험", "concept_difficulty": 2,
                         "tier": "Optional" if importance == 2 else "Core", "exam_signal_strength": "high",
                         "related_concepts": []})
        supported = ["direct"] if importance == 2 else directions
        plan.append({"concept_id": cid, "directions": supported, "rationale": "회상 방향 비교", "repetition_budget": 8,
                     "target_mastery": 0.55 if importance == 2 else 0.85})
        for d in supported:
            advanced = d in ("mechanism", "integration", "sequence")
            questions.append({
                "question_id": f"{cid}-{d}", "concept_id": cid,
                "tier": "Optional" if importance == 2 else "Advanced" if advanced else "Core",
                "importance": importance, "concept_difficulty": 2, "item_difficulty": 3 if advanced else 2,
                "format": "basic", "cognitive_type": d, "retrieval_direction": d, "question": f"{cid} {d} 회상",
                "answer": "합성 정답", "answer_units": ["합성 정답"],
                "prerequisites": [f"{cid}-direct", f"{cid}-mechanism"] if d == "integration" else [f"{cid}-direct"] if advanced else [],
                "source_refs": refs, "source_strength": ["lecture_core"], "exam_rationale": "실험", "conflict_id": "", **_EMPTY})
    return {"build_meta": {"schema_version": "3.0", "lecture_title": "정책 실험용 합성 문제은행"},
            "source_summary": [{"source_id": "SIM", "summary": "의학 내용 없는 합성 자료"}], "source_conflicts": [],
            "concepts": concepts, "retrieval_plan": plan, "questions": questions,
            "audit_summary": {"summary": "정책 실험용", "rejected_candidate_count": 0, "changes": []}, "warnings": []}
