"""Private text overrides never modify a shared bank or learning policy."""
import hashlib
import json

from sqlalchemy.orm import Session
from app.models import BankPersonalEdit, QuizBank


def revision(question: dict) -> str:
    content = {k: v for k, v in question.items() if k != "mcq_mode"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def same_source(first: dict, second: dict) -> bool:
    return {k: v for k, v in first.items() if k != "mcq_mode"} == {k: v for k, v in second.items() if k != "mcq_mode"}


def apply(db: Session, row: QuizBank, user_id: str, question: dict) -> dict:
    edit = db.get(BankPersonalEdit, (user_id, row.subject, row.run_id, question["question_id"]))
    if not edit or not same_source(edit.original, question):
        return question
    answer_changed = edit.answer != question["answer"]
    out = {**question, "question": edit.question, "answer": edit.answer,
           "personalEdited": edit.question != question["question"] or answer_changed,
           "personalAnswer": answer_changed}
    if answer_changed:
        # A prose correction replaces the old answer and its structured scoring data.
        out.update(answer_units=[], correct_option_ids=[], answer_pairs=[], correct_order=[])
    return out
