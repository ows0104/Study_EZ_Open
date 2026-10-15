"""내용 대조로 선택한 근거만 사용한다. 인용 순서로 핵심을 추측하지 않는다."""
import hashlib
import json
import re

FIELDS = ("question_id", "question", "answer", "answer_units", "explanation", "format", "source_refs",
          "options", "correct_option_ids", "matching_left", "matching_right", "answer_pairs",
          "sequence_items", "correct_order", "option_pools", "option_explanations", "conflict_id")


def question_hash(question: dict) -> str:
    arrays = {"answer_units", "source_refs", "options", "correct_option_ids", "matching_left", "matching_right",
              "answer_pairs", "sequence_items", "correct_order", "option_pools", "option_explanations"}
    body = {key: question.get(key, [] if key in arrays else "") for key in FIELDS}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def authored_hash(question: dict) -> str:
    """해설·학습 구조만 덧붙인 경우 출제 때 선택한 근거를 다시 고르지 않는다."""
    keys = ("question_id", "question", "answer", "format", "source_refs", "options", "correct_option_ids",
            "matching_left", "matching_right", "answer_pairs", "sequence_items", "correct_order", "conflict_id")
    return question_hash({key: question[key] for key in keys if key in question})


def source_id(slide: dict) -> str:
    return slide.get("source_id") or "self"


def external_filename(run_id: str, source: str, digest: str, page: int) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid evidence source identity")
    return f"{run_id}_xref_{source}_{digest[:16]}_p{page:04d}.png"


def selected_references(report: dict | None, original: dict, available: set[tuple[str, int]],
                        presented: dict | None = None) -> set[tuple[str, int]]:
    if not isinstance(report, dict) or report.get("version") not in (2, 3):
        return set()
    record = report.get("questions", {}).get(original.get("question_id")) or {}
    if record.get("questionHash") != question_hash(original):
        return set()
    if presented and presented.get("personalEdited") and question_hash(presented) != question_hash(original):
        return set()
    variant = (presented or {}).get("choice_variant") or {}
    selections = [record.get("base")]
    if variant.get("poolId"):
        pool = next((p for p in original.get("option_pools", []) if p["pool_id"] == variant["poolId"]), None)
        if pool is None:
            return set()
        correct = "true" if pool["correct_when"] == "true" else "false"
        keys = [f"{pool['pool_id']}/{cid}" for cid, form in variant.get("forms", {}).items() if form == correct]
        selections = [record.get("candidates", {}).get(key) for key in keys]
    if not selections:
        return set()
    pages = set()
    for selection in selections:
        if not isinstance(selection, dict) or selection.get("mode") not in ("single", "linked"):
            return set()
        evidence = selection.get("slides", [])
        if not evidence or selection["mode"] == "single" and len(evidence) != 1 \
                or selection["mode"] == "linked" and len(evidence) < 2:
            return set()
        for slide in evidence:
            page = slide.get("page")
            source = source_id(slide)
            if source != "self":
                meta = report.get("sources", {}).get(source) or {}
                if report.get("version") != 3 or type(meta.get("pageCount")) is not int \
                        or type(page) is not int or not 1 <= page <= meta["pageCount"]:
                    return set()
            if type(page) is not int or (source, page) not in available or not slide.get("evidence", "").strip():
                return set()  # 일부 연결 근거가 없으면 충분한 근거인 것처럼 표시하지 않는다.
            pages.add((source, page))
    return pages


def selected_pages(report: dict | None, original: dict, available: list[int], presented: dict | None = None) -> set[int]:
    return {page for _, page in selected_references(report, original, {("self", p) for p in available}, presented)}


def all_selected_references(report: dict, question_id: str) -> list[dict]:
    record = report.get("questions", {}).get(question_id) or {}
    selections = [record.get("base", {})] + list(record.get("candidates", {}).values())
    unique = {}
    for selection in selections:
        for slide in selection.get("slides", []):
            unique[(source_id(slide), slide["page"])] = slide
    return list(unique.values())


def all_selected_pages(report: dict, question_id: str) -> set[int]:
    return {s["page"] for s in all_selected_references(report, question_id) if source_id(s) == "self"}
