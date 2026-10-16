"""Private text overrides never modify a shared bank or learning policy."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import BankPersonalEdit, QuizBank
from app.bank_validation.priorities import priority_fields


def added_question(question_id: str, question: str, answer: str, tier: str, explanation: str) -> dict:
    """User-authored recall cards use the same serving and review contract."""
    from app.bank_validation.priorities import IMPORTANCE
    return {"question_id": question_id, "concept_id": f"PC_{question_id}",
            "personalAdded": True, "tier": tier, "importance": IMPORTANCE[tier],
            "advanced": False, "item_difficulty": 1, "format": "basic",
            "retrieval_direction": "direct", "mcq_mode": "none", "question": question,
            "answer": answer, "explanation": explanation, "answer_units": [],
            "prerequisites": [], "source_refs": [], "exam_rationale": "사용자가 직접 추가한 문제",
            "conflict_id": "", "options": [], "correct_option_ids": [], "matching_left": [],
            "matching_right": [], "answer_pairs": [], "sequence_items": [], "correct_order": [],
            "option_explanations": [], "option_pools": []}


def augment(db: Session, row: QuizBank, user_id: str, *, edits: list | None = None) -> dict:
    """Merge private additions into a copy, independent of shared bank rebuilds."""
    from app.study_engine.policy import DEFAULT
    bank = row.bank or {}
    if edits is None:
        edits = list(db.scalars(select(BankPersonalEdit).where(
            BankPersonalEdit.user_id == user_id, BankPersonalEdit.subject == row.subject,
            BankPersonalEdit.run_id == row.run_id).order_by(BankPersonalEdit.question_id)))
    added = [edit for edit in edits if edit.original.get("personalAdded")]
    if not added:
        return bank
    questions, concepts, plans = [], [], []
    for edit in added:
        q = edit.original
        questions.append(q)
        concepts.append({"concept_id": q["concept_id"], "title": edit.question[:80],
            "graph_title": edit.question[:24], "core_facts": [], "source_refs": [],
            "tier": q["tier"], "importance": q["importance"], "importance_rationale": "내가 추가한 문제",
            "concept_difficulty": 1, "exam_signal_strength": "low", "related_concepts": []})
        plans.append({"concept_id": q["concept_id"], "directions": ["direct"],
                      "repetition_budget": 3, "target_mastery": DEFAULT["mastery"]["tierTargets"][q["tier"]]})
    return {**bank, "questions": [*bank.get("questions", []), *questions],
            "concepts": [*bank.get("concepts", []), *concepts],
            "retrieval_plan": [*bank.get("retrieval_plan", []), *plans]}


def revision(question: dict) -> str:
    content = {k: v for k, v in priority_fields(question, question=True).items() if k != "mcq_mode"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def same_source(first: dict, second: dict) -> bool:
    return revision(first) == revision(second)


def apply(db: Session, row: QuizBank, user_id: str, question: dict) -> dict:
    edit = db.get(BankPersonalEdit, (user_id, row.subject, row.run_id, question["question_id"]))
    if not edit or not same_source(edit.original, question):
        return question
    answer_changed = edit.answer != question["answer"]
    out = {**question, "question": edit.question, "answer": edit.answer,
           "personalEdited": edit.question != question["question"] or answer_changed,
           "personalAnswer": answer_changed or bool(question.get("personalAdded"))}
    if answer_changed:
        # A prose correction replaces the old answer and its structured scoring data.
        out.update(answer_units=[], correct_option_ids=[], answer_pairs=[], correct_order=[], explanation="")
    return out
