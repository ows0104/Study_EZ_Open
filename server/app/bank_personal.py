"""Private text overrides never modify a shared bank or learning policy."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import BankPersonalEdit, QuizBank
from app.bank_validation.priorities import priority_fields


def added_question(question_id: str, question: str, answer: str, tier: str, explanation: str, *, settings: dict | None = None) -> dict:
    """User-authored recall cards use the same serving and review contract."""
    from app.bank_validation.priorities import IMPORTANCE
    out = {"question_id": question_id, "concept_id": f"PC_{question_id}",
            "personalAdded": True, "tier": tier, "importance": IMPORTANCE[tier],
            "advanced": False, "item_difficulty": 1, "format": "basic",
            "retrieval_direction": "direct", "mcq_mode": "none", "question": question,
            "answer": answer, "explanation": explanation, "answer_units": [],
            "prerequisites": [], "source_refs": [], "exam_rationale": "사용자가 직접 추가한 문제",
            "conflict_id": "", "options": [], "correct_option_ids": [], "matching_left": [],
            "matching_right": [], "answer_pairs": [], "sequence_items": [], "correct_order": [],
            "option_explanations": [], "option_pools": []}
    if settings:
        out.update(settings)
        out["matching_left"] = [pair["left"] for pair in out["answer_pairs"]]
        out["matching_right"] = [pair["right"] for pair in out["answer_pairs"]]
        out["sequence_items"] = list(out["correct_order"])
    return out


def augment(db: Session, row: QuizBank, user_id: str, *, edits: list | None = None) -> dict:
    """Merge private additions into a copy, independent of shared bank rebuilds."""
    from app.study_engine.policy import DEFAULT
    from app.bank_excluded import augment as include_restored
    bank = include_restored(db, row, user_id, row.bank or {})
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
        plans.append({"concept_id": q["concept_id"], "directions": [q["retrieval_direction"]],
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
    return apply_edit(question, edit)


def apply_edit(question: dict, edit: BankPersonalEdit | None) -> dict:
    """Apply an already loaded edit; catalogs load private edits in one query."""
    if not edit or not same_source(edit.original, question):
        return question
    structure = getattr(edit, "structure", None)
    if structure:
        return with_structure(question, edit.question, edit.answer, structure)
    answer_changed = edit.answer != question["answer"]
    out = {**question, "question": edit.question, "answer": edit.answer,
           "personalEdited": edit.question != question["question"] or answer_changed,
           "personalAnswer": answer_changed or bool(question.get("personalAnswerOverride")) or (bool(question.get("personalAdded"))
                              and question["format"] not in {"mcq", "multi_select", "matching", "sequence"})}
    if answer_changed:
        # A prose correction replaces the old answer and its structured scoring data.
        out.update(answer_units=[], correct_option_ids=[], answer_pairs=[], correct_order=[], explanation="")
    return out


STRUCTURE_FIELDS = ("format", "mcq_mode", "answer_units", "options", "correct_option_ids", "explanation")


def with_structure(question: dict, text: str, answer: str, structure: dict) -> dict:
    """Main-Quiz 형식 바꾸기(2026-11-17): 사용자가 형식·구조·해설을 함께 정한 수정본은 판 문항처럼 보인다.
    그래서 personalAnswer(원래 해설이 고친 답과 안 맞는다)는 켜지 않는다. 덧붙인 선지는 원래 형식의 칸이라
    붙이지 않는다(personalFormat, root_learning.mcq)."""
    from studyez_contracts.bank.cloze import normalize_cloze
    out = {**question, "question": text, "answer": answer,
           **{k: structure[k] for k in STRUCTURE_FIELDS if k in structure},
           "answer_pairs": [], "correct_order": [], "matching_left": [], "matching_right": [], "sequence_items": [],
           "option_explanations": [], "option_pools": [],
           "personalEdited": True, "personalAnswer": False, "personalFormat": True}
    if out["format"] == "cloze":
        out["answer_units"] = normalize_cloze(out).get("answer_units", [])
    return out
