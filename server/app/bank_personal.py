"""Private text overrides never modify a shared bank or learning policy."""
import hashlib
import json

from sqlalchemy.orm import Session
from app.models import BankPersonalEdit, QuizBank


def revision(question: dict) -> str:
    return hashlib.sha256(json.dumps(question, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply(db: Session, row: QuizBank, user_id: str, question: dict) -> dict:
    edit = db.get(BankPersonalEdit, (user_id, row.subject, row.run_id, question["question_id"]))
    if not edit or edit.original != question:
        return question
    answer_changed = edit.answer != question["answer"]
    out = {**question, "question": edit.question, "answer": edit.answer,
           "personalEdited": edit.question != question["question"] or answer_changed,
           "personalAnswer": answer_changed}
    if answer_changed:
        # A prose correction replaces the old answer and its structured scoring data.
        out.update(answer_units=[], correct_option_ids=[], answer_pairs=[], correct_order=[])
    return out
