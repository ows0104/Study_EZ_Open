"""정리된 문제은행의 구조를 기계로 잰다. 의미가 맞는지는 재지 않는다 — 그건 review.py 다.

AdaptiveStudy3/bank_builder/validate.mjs 를 그대로 옮겼다(2026-10-04). 전체 검증 errors와
게시 가능한 구조는 publication.py에서 구분한다(2026-10-14 사용자 지시). 단 문항 하나의 탓인 오류는 그 문항만
빼고 다시 잰다(`validate_dropping`, 2026-10-05).

경고로 내린 셋 (2026-10-04 관리자 지시): 계획↔문항 대응 두 방향과 「한 자료 안의 충돌」.
261002_02 실측에서 오류 16건 중 13건이 이것이었고, 프롬프트가 요구하지 않는 것이며,
같은 족보 안·같은 필기 안의 충돌도 실제로 있었다.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from .schema import SCHEMA_VERSION, schema_errors, without_retired
from .choices import option_pool_errors
from .quality import quality_errors
from .priorities import IMPORTANCE


# 외부 의학지식으로 쓴 자리(프롬프트 v1.2, 2026-10-05). 첨부 자료가 아니라서 출처 요약에는 안 서지만
# 문항·개념·충돌의 근거로는 적을 수 있다.
EXTERNAL = "EXT"


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).lower()).strip()


def _in_range(value, lo: float, hi: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi


def validate_bank(bank: dict, source_ids: list[str], *, learning_structure: bool = True,
                  check_quality: bool = True) -> dict:
    """`{pass, errors, warnings, checked_at}`. `source_ids` 는 첨부한 자료의 ID(S1, S2…)."""
    bank = without_retired(bank)   # v1.6 에서 뺀 칸은 옛 은행에 있어도 형식 오류가 아니다
    errors = schema_errors(bank)
    warnings: list[str] = []

    def result() -> dict:
        return {"pass": not errors, "errors": errors, "warnings": warnings,
                "checked_at": datetime.now(UTC).isoformat()}

    if errors:
        return result()
    if any(q.get('stimuli')for q in bank['questions']):
        from ..roots.media import validate_images
        try:
            validate_images(bank)
            if any(s['source_id']not in source_ids for q in bank['questions']for s in q.get('stimuli',[])):
                errors.append('stimuli: 유효한 원본 source_id 필요')
        except (ValueError,KeyError,TypeError)as error:errors.append(str(error))
        if errors:return result()

    def fail(ok: bool, text: str) -> None:
        if not ok:
            errors.append(text)

    def warn(ok: bool, text: str) -> None:
        if not ok:
            warnings.append(text)

    def unique(items: list, label: str) -> None:
        fail(len(set(items)) == len(items), f"{label}: ID/값 중복")

    ids = set(source_ids) | {EXTERNAL}
    concepts = {c["concept_id"]: c for c in bank["concepts"]}
    questions = {q["question_id"]: q for q in bank["questions"]}
    conflicts = {c["conflict_id"]: c for c in bank["source_conflicts"]}

    def refs(items: list[dict], label: str) -> None:
        fail(len(items) > 0, f"{label}: 출처 필요")
        for ref in items:
            fail(ref["source_id"] in ids and (ref["source_id"] == EXTERNAL or _nonempty(ref["locator"])),
                 f"{label}: 유효한 source_id 및 page/slide/section 필요")

    fail(bank["build_meta"]["schema_version"] in ("3.0", "3.1", SCHEMA_VERSION), f"지원 schema_version: 3.0, 3.1, {SCHEMA_VERSION}")
    fail(_nonempty(bank["build_meta"]["lecture_title"]), "강의 제목 누락")
    fail(bool(bank["questions"]) and (bool(bank["concepts"]) if learning_structure else True), "개념과 문항이 비어 있습니다.")
    if not learning_structure:
        fail(not bank["concepts"] and not bank["retrieval_plan"], "문항 검수 단계에서는 학습 구조를 비워야 합니다.")
    fail(len(bank["questions"]) <= 5000 and len(bank["concepts"]) <= 2000, "단일 문제은행의 지원 크기를 초과했습니다.")
    if errors:
        return result()

    if bank["build_meta"]["schema_version"] == "3.2":
        for item in [*bank["questions"], *bank["concepts"]]:
            ident = item.get("question_id", item.get("concept_id"))
            fail(item["importance"] == IMPORTANCE[item["tier"]],
                 f"{ident}: 중요도 수치는 Essential=5, Core=5, Important=4, Optional=2여야 합니다.")

    if check_quality:
        quality_invalid, quality_warnings = quality_errors(bank)
        errors.extend(quality_invalid)
        warnings.extend(quality_warnings)

    unique([c["concept_id"] for c in bank["concepts"]], "concepts")
    unique([q["question_id"] for q in bank["questions"]], "questions")
    unique([c["conflict_id"] for c in bank["source_conflicts"]], "conflicts")
    unique([s["source_id"] for s in bank["source_summary"]], "source_summary")
    for s in bank["source_summary"]:
        fail(s["source_id"] in ids and _nonempty(s["summary"]), "source_summary: 잘못된 출처/빈 요약")
    # 자료마다 요약이 있어야 한다는 검사는 걷었다 — 프롬프트 v1.5(2026-10-05) 부터 자료 요약을 안 받는다.
    # 앱이 읽지 않는 출력이었다. 옛 응답에 있으면 위에서 형식만 본다.

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
        fail(cid in concepts and bool(p["directions"]), f"{cid}: 회상 계획 오류")
        unique(p["directions"], f"{cid} directions")
        fail(_in_range(p["target_mastery"], 0.1, 1) and _in_range(p["repetition_budget"], 1, 100),
             f"{cid}: 학습 예산/목표 범위 오류")
        for d in p["directions"]:
            warn(any(q["concept_id"] == cid and q["retrieval_direction"] == d for q in bank["questions"]),
                 f"{cid}/{d}: 계획에 대응하는 문항 누락")
    for c in bank["concepts"]:
        fail(any(p["concept_id"] == c["concept_id"] for p in bank["retrieval_plan"]), f"{c['concept_id']}: 회상 계획 누락")

    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for q in bank["questions"]:
        label = q["question_id"]
        fail(q["mcq_mode"] in ("recall_first", "comparison") if q["format"] in ("mcq", "multi_select")
             else q["mcq_mode"] == "none", f"{label}: 객관식 학습 유형이 문항 형식과 맞지 않습니다.")
        errors.extend(option_pool_errors(q, ids))
        explanations = q["option_explanations"]
        if explanations:
            fail(q["format"] in ("mcq", "multi_select"), f"{label}: 선지 해설은 객관식에만 허용")
            unique([e["option_id"] for e in explanations], f"{label} option_explanations")
            fail({e["option_id"] for e in explanations} == {o["id"] for o in q["options"]}
                 and all(_nonempty(e["text"]) for e in explanations), f"{label}: 모든 선지의 해설 필요")
        fail(_nonempty(label) and _nonempty(q["question"]) and _nonempty(q["answer"]), f"{label}: 발문/정답/ID 누락")
        fail(q["concept_id"] in concepts if learning_structure else not q["concept_id"],
             f"{label}: 존재하지 않는 concept_id" if learning_structure else f"{label}: 사후 연결 전 concept_id는 비워야 합니다.")
        fail(all(_in_range(n, 1, 5) for n in (q["importance"], q["item_difficulty"])),
             f"{label}: 중요도/난이도는 1–5")
        fail(bool(q["answer_units"]) and all(_nonempty(u) for u in q["answer_units"]), f"{label}: 채점 단위 필요")
        refs(q["source_refs"], label)
        unique(q["prerequisites"], f"{label} prerequisites")
        if "learning_page" in q:
            fail(_in_range(q["learning_page"], 1, float("inf")) and isinstance(q["learning_page"], int),
                 f"{label}: learning_page는 1 이상의 정수여야 합니다.")
        for pid in q["prerequisites"]:
            fail(pid in questions and pid != label, f"{label}: 잘못된 prerequisite {pid}")
            parent = questions.get(pid, {})
            if "learning_page" in q and "learning_page" in parent:
                fail(q["learning_page"] >= parent["learning_page"],
                     f"{label}: 학습 위치가 선행 문항 {pid}보다 앞섭니다.")
        if not learning_structure:
            fail(not q["prerequisites"], f"{label}: 사후 연결 전 prerequisites는 비워야 합니다.")
        if check_quality and learning_structure and q["retrieval_direction"] == "integration" and not q["prerequisites"]:
            errors.append(f"{label}: integration의 기초 문항 필요")
        # 객관식은 같은 발문에도 다른 오개념을 시험하는 보기 변형이 있다.
        # 보기 문자·순서나 정답표만 바뀐 것은 같은 문항으로 본다.
        option_content = tuple(sorted(_normalized(o["text"]) for o in q["options"])) \
            if q["format"] in ("mcq", "multi_select") else ()
        key = (_normalized(q["question"]), q["conflict_id"], option_content)
        if check_quality:
            fail(key not in seen, f"{label}: 중복 발문")
        seen.add(key)

        if q["conflict_id"]:
            # 충돌은 v1.2 부터 한 문항으로 합치고 외부 의학지식으로 답을 정한다(관리자 지시, 2026-10-05).
            # 그래서 「[출처 기준] 머리말」과 「출처 하나로 분리」를 걷었다 — 갈라 낸 옛 판 문항도 그대로 통과한다.
            fail(q["conflict_id"] in conflicts, f"{label}: Conflict ID 없음")
            if check_quality and q["conflict_id"] in conflicts:
                # 충돌 기록은 서로 다른 주장을 가진 자료만 담는다. 문항에는 같은 목표의
                # 족보 등 추가 근거가 있을 수 있으므로 전체 출처의 부분집합을 요구하지 않는다.
                conflict_sources = {r["source_id"] for r in conflicts[q["conflict_id"]]["source_refs"]}
                fail(bool(conflict_sources & {r["source_id"] for r in q["source_refs"]}),
                     f"{label}: 충돌 기록과 출처 불일치")

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
            fail(bool(blanks) and len(blanks) == len(q["answer_units"]),
                 f"{label}: cloze는 {{{{c1}}}} 형식의 빈칸 1개 이상과 등장 순서에 대응하는 answer_units 필요")
            fail("{{" not in re.sub(r"\{\{c\d+\}\}", "", q["question"]), f"{label}: 잘못된 cloze 표기")
        if q["format"] == "list":
            fail(len(q["answer_units"]) >= 2, f"{label}: list는 개별 채점 단위 2개 이상 필요")
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
        if learning_structure:
            warn(plan is not None and q["retrieval_direction"] in plan["directions"], f"{label}: 회상 계획에 없는 방향")

    for conflict in bank["source_conflicts"]:
        cid = conflict["conflict_id"]
        fail(_nonempty(cid) and _nonempty(conflict["description"]), "충돌 기록 필수 필드 누락")
        refs(conflict["source_refs"], cid)
        warn(len({r["source_id"] for r in conflict["source_refs"]}) >= 2, f"{cid}: 한 자료 안의 충돌")
        linked_questions = [q for q in bank["questions"] if q["conflict_id"] == cid]
        if not linked_questions:
            warnings.append(f"{cid}: 연결된 문항이 없는 출처 충돌 기록")
            continue  # 삭제·통합한 문항의 이력은 보존할 수 있다. 끊어진 문항 참조와 다르다.
        if check_quality and not conflict["unresolved"]:
            for ref in conflict["source_refs"]:
                fail(any(any(r["source_id"] == ref["source_id"] for r in q["source_refs"])
                         for q in linked_questions), f"{cid}: {ref['source_id']} 기준 문항 누락")
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
    # 점검 보고(audit_summary)도 v1.5 부터 안 받는다 — 비어 있어도 된다. 개수가 음수면 정리가 망가진 것이다.
    fail(bank["audit_summary"]["rejected_candidate_count"] >= 0, "audit_summary 범위 오류")
    warnings.extend(bank["warnings"])
    return result()


# 문항 하나의 탓인 오류는 그 문항 ID 로 시작한다 — `Q046: matching 참조 오류`,
# `Q046 pairs: ID/값 중복`. 개념(`C03: …`)·충돌(`IFN_…: …`)·전체 구조 오류는 여기 안 걸린다.
_LEAD = re.compile(r"^(\S+?)(?: [a-z]+)?: ")


def _question_of(error: str, qids: set[str]) -> str | None:
    match = _LEAD.match(error)
    return match.group(1) if match and match.group(1) in qids else None


def _without(bank: dict, drop: set[str]) -> dict:
    """그 문항들을 뺀 은행. 남은 문항이 선행으로 들던 것도 지운다."""
    kept = []
    for q in bank["questions"]:
        if q["question_id"] in drop:
            continue
        kept.append({**q, "prerequisites": [p for p in q["prerequisites"] if p not in drop]})
    return {**bank, "questions": kept}


def validate_dropping(bank: dict, source_ids: list[str], max_rounds: int = 5) -> tuple[dict, dict]:
    """검증에 걸린 **문항만 빼고** 다시 잰다. `(은행, 검증)` — 검증에 `dropped` 가 붙는다.

    2026-10-05 관리자 지시 — 「걸린 문항만 빼고 연다」. 261002_03 이 56문항 중 2문항(짝짓기 정답 쌍이
    보기 글과 다름 · 충돌 표시가 엉뚱한 문항에 붙음) 때문에 통째로 막혔다.

    **문항 하나의 탓이 아닌 오류가 하나라도 있으면 지금처럼 통째로 막는다.** 그때는 원래 은행과
    첫 검증을 그대로 돌려준다 — 관리자가 전체 그림을 봐야 한다. 빼서 생긴 오류(통합 문항이 기초를
    잃음 등)는 다음 회차에서 그 문항도 빼고 같이 적는다.
    """
    first = validate_bank(bank, source_ids)
    current, validation, dropped = bank, first, []
    for _ in range(max_rounds):
        if validation["pass"]:
            break
        qids = {q["question_id"] for q in current["questions"]}
        by_question: dict[str, list[str]] = {}
        for error in validation["errors"]:
            qid = _question_of(error, qids)
            if qid is None:
                return bank, {**first, "dropped": []}
            by_question.setdefault(qid, []).append(error)
        originals = {q["question_id"]: q for q in current["questions"]}
        dropped += [{"question_id": qid, "errors": errors, "question": originals[qid]}
                    for qid, errors in by_question.items()]
        current = _without(current, set(by_question))
        validation = validate_bank(current, source_ids)
    if not validation["pass"]:
        return bank, {**first, "dropped": []}
    if dropped:
        validation["warnings"].insert(0, f"검증에 걸려 뺀 문항 {len(dropped)}개: "
                                         + ", ".join(d["question_id"] for d in dropped))
    return current, {**validation, "dropped": dropped}
