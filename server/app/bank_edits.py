"""Admin decisions live in validation JSON and survive identical runner rebuilds.

The server imports only the dependency-free validator, never generation code.
"""
from __future__ import annotations

import copy

from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_dropping


def candidates(bank: dict, validation: dict) -> dict[str, dict]:
    out = {q["question_id"]: q for q in bank.get("questions", [])}
    for d in validation.get("dropped", []):
        out.setdefault(d["question_id"], d["question"])
    for qid, edit in validation.get("edits", {}).items():
        out.setdefault(qid, edit.get("question") or edit["original"])
    return copy.deepcopy(out)


def with_edits(bank: dict, validation: dict, edits: dict, source_ids: list[str]) -> tuple[dict, dict]:
    """Revalidate the whole bank, retaining unrelated quarantined cards."""
    all_questions = candidates(bank, validation)
    for qid, edit in edits.items():
        if edit["action"] == "delete":
            all_questions.pop(qid, None)
        else:
            all_questions[qid] = edit["question"]
    draft = without_retired({**bank, "questions": list(all_questions.values())})
    # Removing a question also removes edges pointing to it. Dependent integration
    # questions without a foundation are quarantined by the normal validator.
    deleted = {qid for qid, e in edits.items() if e["action"] == "delete"}
    for q in draft["questions"]:
        if isinstance(q.get("prerequisites"), list):
            q["prerequisites"] = [p for p in q["prerequisites"] if p not in deleted]
    clean, checked = validate_dropping(draft, source_ids)
    return clean, {**{k: v for k, v in validation.items() if k not in ("maintenance", "dropped")}, **checked, "edits": edits}


def reapply(bank: dict, validation: dict, previous: dict, source_ids: list[str]) -> tuple[dict, dict]:
    incoming = candidates(bank, validation)
    edits = {}
    for qid, edit in previous.get("edits", {}).items():
        question = incoming.get(qid)
        if question and without_retired({"questions": [question]})["questions"][0] in (
            edit["original"], edit.get("question")
        ):
            edits[qid] = edit
    if not edits:
        return bank, validation
    return with_edits(bank, validation, edits, source_ids)


def question_errors(bank: dict, validation: dict, edits: dict, qid: str, source_ids: list[str]) -> list[str]:
    """An edited card must pass even if validate_dropping would simply hide it."""
    draft, checked = with_edits(bank, validation, edits, source_ids)
    errors = list(checked["errors"])
    errors += [e for d in checked.get("dropped", []) if d["question_id"] == qid for e in d["errors"]]
    # Also validate schema errors before traversing the structured question.
    if not errors and not any(q["question_id"] == qid for q in draft["questions"]):
        errors.append(f"{qid}: 검증을 통과한 문항이 필요합니다.")
    return errors


def current_review(review: dict | None, validation: dict | None) -> dict:
    """Keep old verdicts in the admin record; expose only current ones to students."""
    changed = {qid for qid, e in (validation or {}).get("edits", {}).items()
               if e.get("question") != e.get("original")}
    return {**(review or {}), "reviews": [r for r in (review or {}).get("reviews", [])
                                         if r["question_id"] not in changed]}
