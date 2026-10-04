"""정리된 문제은행의 구조를 기계로 잰다. 의미가 맞는지는 재지 않는다 — 그건 review.py 다.

AdaptiveStudy3/bank_builder/validate.mjs 를 그대로 옮겼다(2026-10-04). **errors 가 하나라도
있으면 학생에게 열지 않는다.** warnings 는 보여 주기만 한다.

경고로 내린 셋 (2026-10-04 관리자 지시): 계획↔문항 대응 두 방향과 「한 자료 안의 충돌」.
261002_02 실측에서 오류 16건 중 13건이 이것이었고, 프롬프트가 요구하지 않는 것이며,
같은 족보 안·같은 필기 안의 충돌도 실제로 있었다.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from .schema import SCHEMA_VERSION, schema_errors


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).lower()).strip()


def _in_range(value, lo: float, hi: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi


def validate_bank(bank: dict, source_ids: list[str]) -> dict:
    """`{pass, errors, warnings, checked_at}`. `source_ids` 는 첨부한 자료의 ID(S1, S2…)."""
    errors = schema_errors(bank)
    warnings: list[str] = []

    def result() -> dict:
        return {"pass": not errors, "errors": errors, "warnings": warnings,
                "checked_at": datetime.now(UTC).isoformat()}

    if errors:
        return result()

    def fail(ok: bool, text: str) -> None:
        if not ok:
            errors.append(text)

    def warn(ok: bool, text: str) -> None:
        if not ok:
            warnings.append(text)

    def unique(items: list, label: str) -> None:
        fail(len(set(items)) == len(items), f"{label}: ID/값 중복")

    ids = set(source_ids)
    concepts = {c["concept_id"]: c for c in bank["concepts"]}
    questions = {q["question_id"]: q for q in bank["questions"]}
    conflicts = {c["conflict_id"]: c for c in bank["source_conflicts"]}

    def refs(items: list[dict], label: str) -> None:
        fail(len(items) > 0, f"{label}: 출처 필요")
        for ref in items:
            fail(ref["source_id"] in ids and _nonempty(ref["locator"]),
                 f"{label}: 유효한 source_id 및 page/slide/section 필요")

    fail(bank["build_meta"]["schema_version"] == SCHEMA_VERSION, f"schema_version은 {SCHEMA_VERSION}이어야 합니다.")
    fail(_nonempty(bank["build_meta"]["lecture_title"]), "강의 제목 누락")
    fail(bool(bank["concepts"]) and bool(bank["questions"]), "개념과 문항이 비어 있습니다.")
    fail(len(bank["questions"]) <= 5000 and len(bank["concepts"]) <= 2000, "단일 문제은행의 지원 크기를 초과했습니다.")
    if errors:
        return result()

    unique([c["concept_id"] for c in bank["concepts"]], "concepts")
    unique([q["question_id"] for q in bank["questions"]], "questions")
    unique([c["conflict_id"] for c in bank["source_conflicts"]], "conflicts")
    unique([s["source_id"] for s in bank["source_summary"]], "source_summary")
    for s in bank["source_summary"]:
        fail(s["source_id"] in ids and _nonempty(s["summary"]), "source_summary: 잘못된 출처/빈 요약")
    for source_id in source_ids:
        fail(any(s["source_id"] == source_id for s in bank["source_summary"]), f"{source_id}: 출처 요약 누락")

    for c in bank["concepts"]:
        cid = c["concept_id"]
        fail(_nonempty(cid) and _nonempty(c["title"]) and _nonempty(c["importance_rationale"]), f"{cid}: 개념 필드 누락")
        fail(bool(c["core_facts"]) and all(_nonempty(x) for x in c["core_facts"]), f"{cid}: core_facts 누락")
        fail(_in_range(c["importance"], 1, 5) and _in_range(c["concept_difficulty"], 1, 5), f"{cid}: 중요도/난이도는 1–5")
        refs(c["source_refs"], cid)
        for rid in c["related_concepts"]:
            fail(rid in concepts and rid != cid, f"{cid}: related_concepts 오류")

    unique([p["concept_id"] for p in bank["retrieval_plan"]], "retrieval_plan")
    for p in bank["retrieval_plan"]:
        cid = p["concept_id"]
        fail(cid in concepts and bool(p["directions"]) and _nonempty(p["rationale"]), f"{cid}: 회상 계획 오류")
        unique(p["directions"], f"{cid} directions")
        fail(_in_range(p["target_mastery"], 0.1, 1) and _in_range(p["repetition_budget"], 1, 100),
             f"{cid}: 학습 예산/목표 범위 오류")
        for d in p["directions"]:
            warn(any(q["concept_id"] == cid and q["retrieval_direction"] == d for q in bank["questions"]),
                 f"{cid}/{d}: 계획에 대응하는 문항 누락")
    for c in bank["concepts"]:
        fail(any(p["concept_id"] == c["concept_id"] for p in bank["retrieval_plan"]), f"{c['concept_id']}: 회상 계획 누락")

    seen: set[str] = set()
    for q in bank["questions"]:
        label = q["question_id"]
        fail(_nonempty(label) and _nonempty(q["question"]) and _nonempty(q["answer"]), f"{label}: 발문/정답/ID 누락")
        fail(q["concept_id"] in concepts, f"{label}: 존재하지 않는 concept_id")
        fail(all(_in_range(n, 1, 5) for n in (q["importance"], q["concept_difficulty"], q["item_difficulty"])),
             f"{label}: 중요도/난이도는 1–5")
        fail(bool(q["answer_units"]) and all(_nonempty(u) for u in q["answer_units"]), f"{label}: 채점 단위 필요")
        refs(q["source_refs"], label)
        fail(bool(q["source_strength"]) and all(_nonempty(s) for s in q["source_strength"]), f"{label}: 출처 강도 필요")
        unique(q["prerequisites"], f"{label} prerequisites")
        for pid in q["prerequisites"]:
            fail(pid in questions and pid != label, f"{label}: 잘못된 prerequisite {pid}")
        if q["retrieval_direction"] == "integration" and not q["prerequisites"]:
            errors.append(f"{label}: integration의 기초 문항 필요")
        key = _normalized(q["question"]) + "|" + q["conflict_id"]
        fail(key not in seen, f"{label}: 중복 발문")
        seen.add(key)

        if q["conflict_id"]:
            fail(q["conflict_id"] in conflicts, f"{label}: Conflict ID 없음")
            fail(bool(re.search(r"\[[^\]]+\]", q["question"])), f"{label}: 충돌 문항에 [출처 기준] 표시 필요")
            fail(len({r["source_id"] for r in q["source_refs"]}) == 1, f"{label}: 충돌 문항은 하나의 출처 기준으로 분리해야 합니다.")
            if q["conflict_id"] in conflicts:
                allowed = {r["source_id"] for r in conflicts[q["conflict_id"]]["source_refs"]}
                fail(all(r["source_id"] in allowed for r in q["source_refs"]), f"{label}: 충돌 기록과 출처 불일치")

        option_ids = [o["id"] for o in q["options"]]
        unique(option_ids, f"{label} options")
        unique(q["correct_option_ids"], f"{label} answers")
        fail(all(_nonempty(o["id"]) and _nonempty(o["text"]) for o in q["options"]), f"{label}: 빈 선택지")
        if q["format"] in ("mcq", "multi_select"):
            fail(_in_range(len(q["options"]), 2, 8), f"{label}: 선택지 2–8개 필요")
            fail(all(i in option_ids for i in q["correct_option_ids"]), f"{label}: 정답 선택지 ID 오류")
            n = len(q["correct_option_ids"])
            fail(n == 1 if q["format"] == "mcq" else 1 <= n < len(q["options"]), f"{label}: 정답 선택지 개수 오류")
        else:
            fail(not q["options"] and not q["correct_option_ids"], f"{label}: 선택형이 아닌 문항의 options는 비워야 합니다.")
        if q["format"] == "ox":
            fail(bool(re.fullmatch(r"[OX]", q["answer"].strip(), re.I)), f"{label}: OX 정답은 O 또는 X")
        if q["format"] == "cloze":
            blanks = re.findall(r"\{\{c\d+\}\}", q["question"])
            fail(_in_range(len(blanks), 1, 3) and len(set(blanks)) == len(blanks) and len(blanks) == len(q["answer_units"]),
                 f"{label}: cloze는 {{{{c1}}}} 형식의 고유 빈칸 1–3개와 대응 answer_units 필요")
            fail("{{" not in re.sub(r"\{\{c\d+\}\}", "", q["question"]), f"{label}: 잘못된 cloze 표기")
        if q["format"] == "list":
            fail(_in_range(len(q["answer_units"]), 2, 5), f"{label}: list는 채점 단위 2–5개")
        if q["format"] == "matching":
            unique(q["matching_left"], f"{label} left")
            unique(q["matching_right"], f"{label} right")
            fail(len(q["matching_left"]) >= 2 and len(q["matching_right"]) >= 2
                 and len(q["answer_pairs"]) == len(q["matching_left"]), f"{label}: matching 항목/정답 쌍 누락")
            unique([p["left"] for p in q["answer_pairs"]], f"{label} pairs")
            fail(all(p["left"] in q["matching_left"] and p["right"] in q["matching_right"] for p in q["answer_pairs"]),
                 f"{label}: matching 참조 오류")
        else:
            fail(not q["matching_left"] and not q["matching_right"] and not q["answer_pairs"],
                 f"{label}: matching 필드는 비워야 합니다.")
        if q["format"] == "sequence":
            unique(q["sequence_items"], f"{label} sequence")
            fail(len(q["sequence_items"]) >= 2 and sorted(q["sequence_items"]) == sorted(q["correct_order"]),
                 f"{label}: sequence 정답은 항목의 순열이어야 합니다.")
        else:
            fail(not q["sequence_items"] and not q["correct_order"], f"{label}: sequence 필드는 비워야 합니다.")
        plan = next((p for p in bank["retrieval_plan"] if p["concept_id"] == q["concept_id"]), None)
        warn(plan is not None and q["retrieval_direction"] in plan["directions"], f"{label}: 회상 계획에 없는 방향")

    for conflict in bank["source_conflicts"]:
        cid = conflict["conflict_id"]
        fail(_nonempty(cid) and _nonempty(conflict["description"]), "충돌 기록 필수 필드 누락")
        refs(conflict["source_refs"], cid)
        warn(len({r["source_id"] for r in conflict["source_refs"]}) >= 2, f"{cid}: 한 자료 안의 충돌")
        if not conflict["unresolved"]:
            for ref in conflict["source_refs"]:
                fail(any(q["conflict_id"] == cid and any(r["source_id"] == ref["source_id"] for r in q["source_refs"])
                         for q in bank["questions"]), f"{cid}: {ref['source_id']} 기준 문항 누락")
        else:
            warnings.append(f"{cid}: 미해결 출처 충돌 — {conflict['description']}")

    # 선행 문항 순환 — 위상 정렬이 끝까지 가는지 본다.
    indegree = {qid: sum(1 for p in q["prerequisites"] if p in questions) for qid, q in questions.items()}
    dependents: dict[str, list[str]] = {qid: [] for qid in questions}
    for q in questions.values():
        for p in q["prerequisites"]:
            if p in dependents:
                dependents[p].append(q["question_id"])
    queue = [qid for qid, n in indegree.items() if n == 0]
    for qid in queue:
        for nxt in dependents[qid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    fail(len(queue) == len(questions), "prerequisite 순환 참조가 있습니다.")
    fail(bank["audit_summary"]["rejected_candidate_count"] >= 0 and _nonempty(bank["audit_summary"]["summary"]),
         "audit_summary 누락/범위 오류")
    warnings.extend(bank["warnings"])
    return result()
