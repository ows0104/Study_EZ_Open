"""Read-only calendar/panel projection. Does not import or mutate legacy history."""
import os
from datetime import datetime
from sqlalchemy import select, tuple_
from app.models import QuizBank
from app.models.learning import LearningDay, LearningProfile
from app.study_engine import now_ms
from app.study_engine.planning import KOREA
from app.study_engine.learning import catalog_unit, progress, workload


def lecture_progress(db, user_id, keys):
    if not keys or os.getenv("STUDYEZ_LEARNING_ENABLED", "1") == "0": return {}
    profile = db.get(LearningProfile, user_id)
    if not profile or not profile.enabled: return {}
    now = now_ms()
    day = db.get(LearningDay, (user_id, datetime.fromtimestamp(now / 1000, KOREA).date().isoformat()))
    plan = day.plan if day else None
    rows = db.scalars(select(QuizBank).where(tuple_(QuizBank.subject, QuizBank.run_id).in_(keys), QuizBank.open_to_students.is_(True)))
    out = {}
    for row in rows:
        if not row.bank or not (row.validation or {}).get("pass"): continue
        units = catalog_unit(row.subject, row.run_id, "", row.bank, "")
        out[(row.subject, row.run_id)] = {**progress(units, profile.state),
            "workload": workload(units, profile.state, plan, now, profile.buffer_days)}
    return out
