"""Structural checks for source-grounded, explicitly authored truth pairs.

Medical truth and the stem's selection criterion are checked by review.py.
An invalid pool rejects its owning question, never the lecture's objectives.
"""
from .learning import fingerprint, normalized


def pool_review_identity(q: dict) -> str:
    """Bind the review to its stem, selection rule, count and every truth pair."""
    return fingerprint([q["question"], q["format"], len(q["correct_option_ids"]), q.get("option_pools", [])])


def option_pool_errors(q: dict, source_ids: set[str]) -> list[str]:
    pools = q.get("option_pools", [])
    label = q["question_id"]
    errors = []
    if not pools:
        return errors
    if q["format"] not in ("mcq", "multi_select"):
        return [f"{label}: 선지 풀은 객관식에만 허용"]
    if len(pools) > 8:
        errors.append(f"{label}: 선지 풀은 최대 8개")
    if len({p["pool_id"] for p in pools}) != len(pools) or any(not p["pool_id"].strip() for p in pools):
        errors.append(f"{label}: 선지 풀 ID 누락·중복")
    if len({p["correct_when"] for p in pools}) != 1:
        errors.append(f"{label}: 같은 발문의 참·거짓 선택 기준 불일치")
    for pool in pools:
        count = pool["select_count"]
        candidates = pool["candidates"]
        if not 2 <= count <= 8 or not count < len(candidates) <= 16:
            errors.append(f"{label}: 선지 풀은 2–8개 선택 및 선택 수보다 많은 후보(최대 16개) 필요")
        if not 0 < len(q["correct_option_ids"]) < count:
            errors.append(f"{label}: 선지 풀의 정답 수·선택 수 불일치")
        if len({c["candidate_id"] for c in candidates}) != len(candidates):
            errors.append(f"{label}: 선지 후보 ID 중복")
        texts = []
        for c in candidates:
            if not all(c[k].strip() for k in ("candidate_id", "true_text", "false_text", "true_explanation", "false_explanation")):
                errors.append(f"{label}: 선지 후보의 참·거짓 문장과 각각의 해설 필요")
            texts.extend([normalized(c["true_text"]).casefold(), normalized(c["false_text"]).casefold()])
            if not c["source_refs"] or any(r["source_id"] not in source_ids or not r["locator"].strip() for r in c["source_refs"]):
                errors.append(f"{label}: 선지 후보의 유효한 출처 필요")
        if len(set(texts)) != len(texts):
            errors.append(f"{label}: 선지 풀의 참·거짓 문장 중복")
    return errors
