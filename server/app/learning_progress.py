"""Read-only calendar/panel projection. Does not import or mutate legacy history."""
import os
from sqlalchemy import select, tuple_
from app.models import QuizBank
from app.models.learning import LearningProfile
from app.study_engine.learning import catalog_unit, progress


def lecture_progress(db, user_id, keys):
    if not keys or os.getenv("STUDYEZ_LEARNING_ENABLED", "1") == "0": return {}
    profile = db.get(LearningProfile, user_id)
    if not profile or not profile.enabled: return {}
    rows = db.scalars(select(QuizBank).where(tuple_(QuizBank.subject, QuizBank.run_id).in_(keys), QuizBank.open_to_students.is_(True)))
    return {(r.subject, r.run_id): progress(catalog_unit(r.subject, r.run_id, "", r.bank, ""), profile.state)
            for r in rows if r.bank and (r.validation or {}).get("pass")}
