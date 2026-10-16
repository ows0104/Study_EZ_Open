"""Admin decisions live in validation JSON and survive identical runner rebuilds.

The server imports only the dependency-free validator, never generation code.
"""
from __future__ import annotations

import copy

from app.bank_validation.schema import without_retired
from app.bank_validation.choice_mode import choice_mode
from app.bank_validation.validate import validate_dropping
from app.bank_validation.validate import validate_bank
from app.bank_validation.publication import stamp as publication_stamp


def _content(question):
    if question is None:
        return None
    normalized = without_retired({"questions": [question]})["questions"][0]
    return {k: v for k, v in normalized.items() if k != "mcq_mode"}


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
    previous_children = {q['question_id'] for e in validation.get('edits', {}).values()
                         for q in e.get('children', [])}
    active_children = {q['question_id'] for e in edits.values() if e['action'] != 'delete'
                       for q in e.get('children', [])}
    removed_children = previous_children - active_children
    for qid in removed_children:
        all_questions.pop(qid, None)
    for edit in edits.values():
        if edit['action'] != 'delete':
            for child in edit.get('children', []):
                all_questions[child['question_id']] = child
    for qid, edit in edits.items():
        if qid in removed_children:
            continue
        if edit["action"] == "delete":
            all_questions.pop(qid, None)
        else:
            all_questions[qid] = edit["question"]
    # Keep split children next to their source card without moving unrelated cards.
    children = {qid: e.get('children', []) for qid, e in edits.items() if e['action'] != 'delete'}
    ordered = []
    for qid, question in all_questions.items():
        if qid in active_children:
            continue
        ordered.append(question)
        ordered.extend(all_questions[q['question_id']] for q in children.get(qid, [])
                       if q['question_id'] in all_questions)
    draft = without_retired({**bank, "questions": ordered})
    split_concepts = {e['question']['concept_id'] for e in edits.values()
                      if e['action'] != 'delete' and e.get('children')}
    for plan in draft.get('retrieval_plan', []):
        if plan['concept_id'] in split_concepts:
            plan['directions'] = list(dict.fromkeys(q['retrieval_direction'] for q in draft['questions']
                if q['concept_id'] == plan['concept_id']))
    # Removing a question also removes edges pointing to it. Dependent integration
    # questions without a foundation are quarantined by the normal validator.
    deleted = {qid for qid, e in edits.items() if e["action"] == "delete"}
    deleted.update(previous_children - active_children)
    for q in draft["questions"]:
        if isinstance(q.get("prerequisites"), list):
            q["prerequisites"] = [p for p in q["prerequisites"] if p not in deleted]
    permitted = bool((validation.get('publication') or {}).get('allowed'))
    clean, checked = (draft, validate_bank(draft, source_ids)) if permitted else validate_dropping(draft, source_ids)
    merged = {**{k: v for k, v in validation.items() if k not in ("maintenance", "dropped")}, **checked, "edits": edits}
    return clean, publication_stamp(clean, merged, source_ids, allow_unresolved=permitted)


def reapply(bank: dict, validation: dict, previous: dict, source_ids: list[str]) -> tuple[dict, dict]:
    incoming = candidates(bank, validation)
    edits = {}
    previous_edits = previous.get('edits', {})
    child_ids = {q['question_id'] for e in previous_edits.values() for q in e.get('children', [])}
    for qid, edit in sorted(previous_edits.items(), key=lambda pair: pair[0] in child_ids):
        question = incoming.get(qid)
        if (question is None and edit["action"] == "delete") or (question and _content(question) in (
            _content(edit["original"]), _content(edit.get("question"))
        )):
            carried = copy.deepcopy(edit)
            if question and carried.get("question"):
                carried["question"]["mcq_mode"] = choice_mode(question)
            edits[qid] = carried
            # Child decisions can be reapplied against their source split even
            # when an identical runner rebuild contains only the original card.
            for child in carried.get('children', []) if carried['action'] != 'delete' else []:
                incoming.setdefault(child['question_id'], child)
    if not edits:
        return bank, validation
    return with_edits(bank, validation, edits, source_ids)


def question_errors(bank: dict, validation: dict, edits: dict, qid: str, source_ids: list[str]) -> list[str]:
    """An edited card must pass even if validate_dropping would simply hide it."""
    draft, checked = with_edits(bank, validation, edits, source_ids)
    if (validation.get('publication') or {}).get('allowed'):
        structural = validate_bank(draft, source_ids, check_quality=False)
        errors = list(structural['errors']) + [e for e in checked['errors'] if e.startswith(qid + ': ') or e.startswith(qid + ' ')]
    else:
        errors = list(checked["errors"])
    errors += [e for d in checked.get("dropped", []) if d["question_id"] == qid for e in d["errors"]]
    # Also validate schema errors before traversing the structured question.
    if not errors and not any(q["question_id"] == qid for q in draft["questions"]):
        errors.append(f"{qid}: 검증을 통과한 문항이 필요합니다.")
    return errors


def current_review(review: dict | None, validation: dict | None) -> dict:
    """Keep old verdicts in the admin record; expose only current ones to students."""
    changed = {qid for qid, e in (validation or {}).get("edits", {}).items()
               if _content(e.get("question")) != _content(e.get("original"))}
    return {**(review or {}), "reviews": [r for r in (review or {}).get("reviews", [])
                                         if r["question_id"] not in changed]}
