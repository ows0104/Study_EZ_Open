"""Optional learning contract shared by generation, validation and the study service.

Legacy banks have no coverage inventory. Never manufacture verified coverage from
their question count, or merge facts merely because their concept labels match.
"""

import hashlib
import json
import re
import unicodedata


def fingerprint(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def objective_identity(objective: dict) -> str:
    # Meaning changes require a new identity; IDs and page moves alone do not.
    return fingerprint([normalized(objective["title"]), normalized(objective["target"]), objective["kind"]])


def question_identity(q: dict) -> str:
    options = {o["id"]: normalized(o["text"]) for o in q["options"]}
    if q["format"] in ("mcq", "multi_select"):
        # Relabeling options or rewriting an explanation does not make a new
        # exam question. Track the stem, choices and correct choice meanings.
        return fingerprint([normalized(q["question"]), q["format"], sorted(options.values()),
                            sorted(options[i] for i in q["correct_option_ids"] if i in options)])
    return fingerprint([normalized(q["question"]), q["format"], sorted(options.values()),
                        sorted(options[i] for i in q["correct_option_ids"] if i in options),
                        normalized(q["answer"]), q["answer_units"], q["answer_pairs"], q["correct_order"]])


def learning_content(bank: dict) -> tuple[list[dict], list[dict]]:
    """Read adapter. Original bank and its question IDs are never rewritten."""
    if bank.get("learning_objectives"):
        return bank["learning_objectives"], bank["questions"]
    objectives, questions = [], []
    for q in bank.get("questions", []):
        oid = "legacy-" + question_identity(q)[:24]
        objective = {"objective_id": oid, "concept_id": q["concept_id"], "title": q["question"],
            "target": q["answer"], "kind": "fact", "importance": q["importance"],
            "rationale": q.get("exam_rationale", ""), "source_refs": q["source_refs"],
            "context": "", "explanation": "", "minimum": q["answer"], "prerequisites": [], "legacy": True}
        if not any(o["objective_id"] == oid for o in objectives): objectives.append(objective)
        questions.append({**q, "primary_objective_id": oid, "supporting_objective_ids": [],
                          "role": q.get("role", "learning"), "recall_prompt": q.get("recall_prompt", ""),
                          "option_explanations": q.get("option_explanations", [])})
    return objectives, questions


def scope_only(bank: dict) -> bool:
    """An explicitly excluded lecture still needs a validated source inventory."""
    inventory = bank.get("coverage_inventory", [])
    return (bank.get("build_meta", {}).get("schema_version") == "4.0"
            and not any(bank.get(k) for k in ("learning_objectives", "concepts", "questions"))
            and bool(inventory) and any(e["status"] == "excluded" for e in inventory)
            and all(e["status"] != "target" for e in inventory))


def learning_errors(bank: dict, source_ids: set[str]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    objectives = bank.get("learning_objectives", [])
    inventory = bank.get("coverage_inventory", [])
    if not objectives and not scope_only(bank):
        if bank.get("build_meta", {}).get("schema_version") == "4.0":
            errors.append("learning_objectives: 새 은행의 학습요점 필요")
        return errors, warnings
    if scope_only(bank):
        warnings.append("범위 검토 완료: 등록된 학습 대상 요점이 없습니다. 제외 근거를 확인하세요.")
    ids = {o["objective_id"] for o in objectives}
    concepts = {c["concept_id"] for c in bank["concepts"]}
    if len(ids) != len(objectives):
        errors.append("learning_objectives: ID 중복")
    if len({objective_identity(o) for o in objectives}) != len(objectives):
        errors.append("learning_objectives: 같은 목표 내용 중복")
    for o in objectives:
        label = "objective " + o["objective_id"]
        if not all(o[k].strip() for k in ("objective_id", "title", "target", "rationale", "minimum", "explanation")):
            errors.append(f"{label}: 목표·근거·최소 암기·설명 필요")
        if o["concept_id"] not in concepts or not 1 <= o["importance"] <= 5:
            errors.append(f"{label}: 개념 또는 중요도 오류")
        if not o["source_refs"] or any(r["source_id"] not in source_ids or not r["locator"].strip() for r in o["source_refs"]):
            errors.append(f"{label}: 출처 필요")
        if any(p not in ids or p == o["objective_id"] for p in o["prerequisites"]):
            errors.append(f"{label}: 선행 요점 오류")
    # Cycles must not leave first-pass content permanently unreachable.
    graph = {o["objective_id"]: o["prerequisites"] for o in objectives}
    remaining = {k: set(v) & ids for k, v in graph.items()}
    ready = [k for k, v in remaining.items() if not v]
    while ready:
        key = ready.pop(); remaining.pop(key, None)
        for other, dependencies in remaining.items():
            if key in dependencies:
                dependencies.remove(key)
                if not dependencies: ready.append(other)
    if remaining:
        errors.append("learning_objectives: 선행 요점 순환")
    covered = set()
    for entry in inventory:
        if not entry["source_refs"] or not entry["reason"].strip():
            errors.append("coverage_inventory: 원본 위치와 포함·제외 근거 필요")
        if any(r["source_id"] not in source_ids or not r["locator"].strip() for r in entry["source_refs"]):
            errors.append("coverage_inventory: 출처 오류")
        if any(oid not in ids for oid in entry["objective_ids"]):
            errors.append("coverage_inventory: 없는 학습요점")
        if entry["status"] == "target":
            if not entry["objective_ids"]: errors.append("coverage_inventory: 학습 대상의 요점 누락")
            covered.update(entry["objective_ids"])
    if covered != ids:
        errors.append("coverage_inventory: 모든 학습요점의 원본 범위 연결 필요")
    for q in bank["questions"]:
        label = q["question_id"]
        if q.get("primary_objective_id") not in ids:
            errors.append(f"{label}: primary_objective_id 오류")
        if any(oid not in ids for oid in q.get("supporting_objective_ids", [])):
            errors.append(f"{label}: supporting_objective_ids 오류")
        if q.get("role") == "exam" and q["format"] not in ("mcq", "multi_select"):
            errors.append(f"{label}: 시험용 문항은 객관식 필요")
        explanations = q.get("option_explanations", [])
        if q["format"] in ("mcq", "multi_select"):
            if {e["option_id"] for e in explanations} != {o["id"] for o in q["options"]} or len(explanations) != len(q["options"]):
                errors.append(f"{label}: 모든 선지의 구조화된 해설 필요")
            if any(not e["text"].strip() for e in explanations):
                errors.append(f"{label}: 빈 선지 해설")
    for oid in ids:
        if not any(q.get("primary_objective_id") == oid and q.get("role") != "exam" for q in bank["questions"]):
            # Keep the objective even when its question is dropped. Visible gap;
            # explanation-only first exposure is still possible.
            warnings.append(f"objective {oid}: 학습용 문항 미준비 — 설명 학습만 가능")
    return errors, warnings
