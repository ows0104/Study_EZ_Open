"""Objective-based study sessions. All mutations lock one user's profile.

Answers live on the server until submission; a snapshot pins grading even if a
bank is regenerated. Authorization is rechecked against the current lecture.
"""
import copy
import os
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import BankState, Lecture, QuizBank, TimetableEvent
from app.models.learning import LearningAttempt, LearningBankVersion, LearningDay, LearningLegacyState, LearningProfile, LearningSession
from app.bank_validation.learning import fingerprint, learning_content, question_identity, scope_only
from app.learning_versions import snapshot
from app.learning_media import references
from app.naming import normalize_stem
from app.study_engine import now_ms
from app.study_engine.learning import POLICY_VERSION, apply_attempt, build_plan, catalog_unit, choose_question, grade, progress, workload
from app.study_engine.learning_srs import RATINGS, delayed_recall, recall_rating, schedule_review
from app.study_engine.choices import realize_choices
from app.study_engine.planning import KOREA
from app.study_engine.memory import DAY_MS
from .study_plan import exam_time

router = APIRouter(prefix="/learning")


def enabled():
    return os.getenv("STUDYEZ_LEARNING_ENABLED", "1") != "0"


@router.get("/availability")
def availability(user: CurrentUser = Depends(require_approved_user)):
    return {"enabled": enabled()}


def profile(db: Session, user: CurrentUser) -> LearningProfile:
    if not enabled(): raise HTTPException(404, "새 학습 기능이 꺼져 있습니다.")
    # The profile exists before sessions can be created. Concurrent first reads
    # use the dialect's conflict-safe insert, then acquire the row lock.
    if db.get(LearningProfile, user.id) is None:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(LearningProfile).values(user_id=user.id, minutes=60, buffer_days=3, enabled=True, state={})
                   .on_conflict_do_nothing(index_elements=["user_id"]))
    return db.scalars(select(LearningProfile).where(LearningProfile.user_id == user.id)
                      .with_for_update().execution_options(populate_existing=True)).one()


def today(now):
    return datetime.fromtimestamp(now / 1000, KOREA).date().isoformat()


def catalog(db: Session, user: CurrentUser, now: int, scope_only_lectures: list | None = None):
    rows = db.scalars(select(QuizBank).where(QuizBank.open_to_students.is_(True))).all()
    lectures = {(l.subject, l.run_id): l for l in db.scalars(select(Lecture))}
    events = list(db.scalars(select(TimetableEvent).order_by(TimetableEvent.date, TimetableEvent.start_time)))
    exams = [e for e in events if e.category == "exam" and "실습" not in e.title]
    event_by_id = {e.id: e for e in events}
    units, missing, uncertain = [], [], 0
    available_events = set()
    for row in rows:
        if not row.bank or not (row.validation or {}).get("pass"): continue
        lecture = lectures.get((row.subject, row.run_id))
        if not lecture: continue
        ev = event_by_id.get(lecture.timetable_event_id)
        course = normalize_stem(ev.course if ev else row.subject)
        exam = next((e for e in exams if course and normalize_stem(e.title).startswith(course)
                     and e.date >= lecture.date), None)
        deadline = exam_time(exam) if exam else None
        if scope_only_lectures is not None and scope_only(row.bank):
            scope_only_lectures.append({"subject": row.subject, "runId": row.run_id, "title": lecture.title,
                "examId": exam.id if exam else None, "current": deadline is None or deadline > now,
                "ranges": row.bank["coverage_inventory"]})
        version = snapshot(db, row, now)
        new_units = catalog_unit(row.subject, row.run_id, lecture.title, row.bank, version, deadline)
        from app.bank_edits import current_review
        reviews = current_review(row.review, row.validation)["reviews"]
        for unit in new_units:
            unit["examId"] = exam.id if exam else None
            unit["current"] = deadline is None or deadline > now
            for q in unit["questions"]:
                q["medicalReview"] = next((r for r in reviews if r["question_id"] == q["question_id"]), None)
                q["sourceConflict"] = next((c["description"] for c in row.bank.get("source_conflicts", []) if c["conflict_id"] == q.get("conflict_id")), "")
        units.extend(new_units)
        uncertain += sum(e["status"] == "uncertain" for e in row.bank.get("coverage_inventory", []))
        available_events.add(lecture.timetable_event_id)
    for ev in events:
        if ev.category != "lecture" or ev.id in available_events: continue
        course = normalize_stem(ev.course)
        exam = next((e for e in exams if course and normalize_stem(e.title).startswith(course)
                     and exam_time(e) >= exam_time(ev)), None)
        if exam and exam_time(exam) > now:
            missing.append({"title": ev.title, "date": ev.date.isoformat(), "examId": exam.id})
    return units, missing, uncertain


def migrate_legacy(db, user, person, units):
    state = copy.deepcopy(person.state)
    imported = set(state.get("legacyImports", []))
    sources = [(s.subject, s.run_id, s.build_id, s.state, None) for s in db.scalars(select(BankState).where(BankState.user_id == user.id))]
    for archive in db.scalars(select(LearningLegacyState).where(LearningLegacyState.user_id == user.id)):
        version = db.get(LearningBankVersion, archive.version_id)
        if version: sources.append((version.subject, version.run_id, version.build_id, archive.data["state"], version.id))
    for subject, run_id, build_id, old, vid in sources:
        version = db.get(LearningBankVersion, vid) if vid else db.scalars(select(LearningBankVersion).where(
            LearningBankVersion.subject == subject, LearningBankVersion.run_id == run_id,
            LearningBankVersion.build_id == build_id).order_by(LearningBankVersion.created_at.desc())).first()
        if not version: continue
        # A changing legacy history gets a fresh import key; never overwrite
        # stronger evidence collected by the new learner.
        marker = fingerprint([version.id, old])
        if marker in imported: continue
        old_units = catalog_unit(subject, run_id, "", version.bank, version.id)
        history_ids = {h["question_id"] for h in old.get("history", [])}
        viewed = history_ids | set(old.get("seen_question_ids", [])) | {
            k for k, v in old.get("items", {}).items() if v.get("reviews", 0)}
        if old.get("served"): viewed.add(old["served"]["question_id"])
        for unit in old_units:
            for q in unit["questions"]:
                if q["question_id"] in viewed:
                    state.setdefault("exposures", {}).setdefault(q["identity"], 1)
                if q["question_id"] in history_ids or old.get("items", {}).get(q["question_id"], {}).get("reviews"):
                    state.setdefault("objectives", {}).setdefault(unit["key"], {
                        "covered": True, "dueAt": 0, "evidence": "legacy_self_report", "delayedSuccesses": 0})
        imported.add(marker)
    state["legacyImports"] = sorted(imported)
    person.state = state


def day_plan(db, user, person, units, now):
    day = db.get(LearningDay, (user.id, today(now)))
    if day is None:
        day = LearningDay(user_id=user.id, day=today(now), plan=build_plan(
            [u for u in units if u["current"]], person.state, now, person.minutes, person.buffer_days))
        db.add(day); db.flush()
    return day


def scope_units(units, subject=None, run_id=None, exam_id=None):
    return [u for u in units if (not subject or u["subject"] == subject)
            and (not run_id or u["runId"] == run_id) and (not exam_id or u.get("examId") == exam_id)]


@router.get("/dashboard")
def dashboard(subject: str | None = None, runId: str | None = None, examId: str | None = None,
              user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user)
    scope_only_lectures = []
    units, missing, uncertain = catalog(db, user, now, scope_only_lectures)
    migrate_legacy(db, user, person, units)
    day = day_plan(db, user, person, units, now)
    scoped = scope_units(units, subject, runId, examId)
    if not subject and not examId: scoped = [u for u in scoped if u["current"]]
    keys = {u["key"] for u in scoped}; plan = day.plan
    active = db.scalars(select(LearningSession).where(LearningSession.user_id == user.id,
        LearningSession.status == "active").order_by(LearningSession.created_at.desc())).first()
    active_unit = None
    if active:
        active_entries = active.data.get("entries", [])
        active_index = active.data.get("index", 0)
        if 0 <= active_index < len(active_entries):
            active_unit = active.data.get("units", {}).get(active_entries[active_index]["key"])
    lessons = {}
    for unit in scoped:
        key = (unit["subject"], unit["runId"])
        lessons.setdefault(key, []).append(unit)
    out = {"enabled": person.enabled, "minutes": person.minutes, "bufferDays": person.buffer_days,
           "scopeOnlyLectures": [l for l in scope_units(scope_only_lectures, subject, runId, examId)
                                 if subject or examId or l["current"]],
           "progress": progress(scoped, person.state), "workload": workload(scoped, person.state, plan, now, person.buffer_days),
           "missingLectures": missing, "uncertainRanges": uncertain,
           "plan": {**plan, "remaining": sum(e["key"] in keys and e["key"] not in plan["completed"] for e in plan["entries"]),
                    "complete": len(plan["completed"]) >= len(plan["entries"]) or plan["activeSeconds"] >= plan["budgetSeconds"]},
           "activeSession": active.id if active else None,
           "activeSessionInfo": {"lecture": active_unit["title"], "subject": active_unit["subject"],
                                 "runId": active_unit["runId"]} if active_unit else None,
           "examQuestions": sum(choose_question(u, person.state, exam=True) is not None for u in scoped
                                if person.state.get("objectives", {}).get(u["key"], {}).get("covered")),
           "lectures": [{"subject": k[0], "runId": k[1], "title": us[0]["title"], **progress(us, person.state),
                         "workload": workload(us, person.state, plan, now, person.buffer_days)} for k, us in lessons.items()],
           "objectives": [{"key": u["key"], "subject": u["subject"], "runId": u["runId"],
                "lecture": u["title"], "title": u["objective"]["title"], "kind": u["objective"]["kind"],
                "sourceRefs": u["objective"]["source_refs"], "covered": bool(person.state.get("objectives", {}).get(u["key"], {}).get("covered")),
                "related": u["prerequisites"]} for u in scoped]}
    db.commit(); return out


class SettingsIn(BaseModel):
    minutes: int = Field(60, ge=5, le=480)
    bufferDays: int = Field(3, ge=0, le=14)
    enabled: bool = True
    replan: bool = False


@router.put("/settings")
def settings(payload: SettingsIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user)
    person.minutes, person.buffer_days, person.enabled = payload.minutes, payload.bufferDays, payload.enabled
    if payload.replan:
        if db.scalars(select(LearningSession).where(LearningSession.user_id == user.id, LearningSession.status == "active")).first():
            raise HTTPException(409, "진행 중 학습을 마친 뒤 오늘 계획을 조정하세요.")
        units, _, _ = catalog(db, user, now); day = day_plan(db, user, person, units, now)
        previous = day.plan
        remaining_minutes = max(0, payload.minutes - math_ceil(previous["activeSeconds"] / 60))
        new = build_plan([u for u in units if u["current"] and u["key"] not in previous["completed"]],
                         person.state, now, remaining_minutes, payload.bufferDays)
        done_entries = [e for e in previous["entries"] if e["key"] in previous["completed"]]
        new.update(entries=done_entries + new["entries"], completed=previous["completed"],
                   activeSeconds=previous["activeSeconds"], budgetSeconds=payload.minutes * 60,
                   revision=previous["revision"] + 1)
        day.plan = new
    db.commit(); return {"ok": True}


def math_ceil(value):
    import math
    return math.ceil(value)


class StartIn(BaseModel):
    mode: Literal["daily", "extra", "exam"] = "daily"
    subject: str | None = None
    runId: str | None = None
    examId: str | None = None
    count: int = Field(20, ge=1, le=100)


@router.post("/sessions")
def start(payload: StartIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user)
    if not person.enabled: raise HTTPException(409, "학습 설정에서 새 학습을 켜주세요.")
    active = db.scalars(select(LearningSession).where(LearningSession.user_id == user.id, LearningSession.status == "active")).first()
    if active: return {"sessionId": active.id}
    units, _, _ = catalog(db, user, now); migrate_legacy(db, user, person, units)
    day = day_plan(db, user, person, units, now)
    scoped = scope_units(units, payload.subject, payload.runId, payload.examId)
    if not payload.subject and not payload.examId: scoped = [u for u in scoped if u["current"]]
    by_key = {u["key"]: u for u in scoped}
    entries = []
    if payload.mode == "daily":
        if day.plan["activeSeconds"] < day.plan["budgetSeconds"]:
            entries = [e for e in day.plan["entries"] if e["key"] in by_key and e["key"] not in day.plan["completed"]]
    elif payload.mode == "extra":
        ordered = sorted(scoped, key=lambda u: (bool(person.state.get("objectives", {}).get(u["key"], {}).get("covered")),
            person.state.get("objectives", {}).get(u["key"], {}).get("lastAt", 0)))
        entries = [{"key": u["key"], "lane": "extra", "seconds": 90} for u in ordered[:payload.count]]
    else:
        entries = [{"key": u["key"], "lane": "exam", "seconds": 90} for u in scoped
                   if person.state.get("objectives", {}).get(u["key"], {}).get("covered")
                   and choose_question(u, person.state, exam=True)][:payload.count]
    if not entries:
        raise HTTPException(409, "이 범위의 오늘 분량을 마쳤거나 사용할 문항이 없습니다. 전체 계획 또는 추가 학습을 선택하세요.")
    session = LearningSession(id=uuid.uuid4().hex, user_id=user.id, mode=payload.mode, status="active", created_at=now,
        data={"entries": entries, "units": {e["key"]: by_key[e["key"]] for e in entries}, "index": 0,
              "day": day.day, "served": None, "policy": POLICY_VERSION, "seconds": 0})
    db.add(session); db.commit(); return {"sessionId": session.id}


def session_for(db, user, session_id):
    session = db.get(LearningSession, session_id)
    if not session or session.user_id != user.id: raise HTTPException(404, "학습 회차를 찾을 수 없습니다.")
    return session


def authorized_unit(db, unit):
    row = db.get(QuizBank, (unit["subject"], unit["runId"]))
    if not row or not row.open_to_students: raise HTTPException(404, "현재 공개되지 않은 강의입니다.")
    return row


def public_question(q):
    fields = ("question_id", "concept_id", "format", "question", "options", "matching_left", "matching_right", "sequence_items", "source_refs")
    return {k: q[k] for k in fields}


def feedback(db, unit, served, attempt):
    q = served["question"]
    media = references(db, unit, q)
    if q is None: return {"explanation": unit["objective"]["explanation"], "minimum": unit["objective"]["minimum"],
                          "sourceRefs": unit["objective"]["source_refs"], **media}
    return {"answer": q["answer"], "answerUnits": q["answer_units"], "correctOptionIds": q["correct_option_ids"],
            "answerPairs": q["answer_pairs"], "correctOrder": q["correct_order"],
            "optionExplanations": q.get("option_explanations", []), "sourceRefs": q["source_refs"],
            "medicalReview": q.get("medicalReview"), "sourceConflict": q.get("sourceConflict"),
            "correct": attempt.get("correct"), "confidence": attempt.get("confidence"),
            "explanation": unit["objective"]["explanation"], "minimum": unit["objective"]["minimum"], **media}


def serve(db, person, session, now):
    data = copy.deepcopy(session.data)
    if session.status != "active" or data["index"] >= len(data["entries"]):
        return None
    if data.get("served"):
        # Existing sessions retain their frozen choices/answer mapping, while
        # the retired pre-choice hiding step is removed immediately.
        frozen = data["served"]
        if frozen.get("question") and frozen["question"]["format"] in ("mcq", "multi_select") and not frozen["optionsShown"]:
            frozen["optionsShown"] = True
            session.data = data
        return frozen
    entry = data["entries"][data["index"]]; unit = data["units"][entry["key"]]
    authorized_unit(db, unit)
    q = choose_question(unit, person.state, exam=session.mode == "exam")
    if session.mode == "exam" and not q: raise HTTPException(409, "아직 보지 않은 시험 문항이 없습니다.")
    # Freeze personal wording/answer for practice. Exam uses vetted source only.
    if q and session.mode != "exam":
        from app import bank_personal
        row = db.get(QuizBank, (unit["subject"], unit["runId"]))
        version = db.get(LearningBankVersion, unit["version"])
        if row.build_id == version.build_id:
            original = next(x for x in version.bank["questions"] if x["question_id"] == q["question_id"])
            edited = bank_personal.apply(db, row, person.user_id, original)
            if edited.get("personalEdited"):
                q = {**q, **edited, "identity": fingerprint([unit["subject"], unit["runId"], question_identity(edited)])}
    base_identity = q["identity"] if q else None
    if q:
        q = realize_choices(q, uuid.uuid4().hex, person.state.get("choiceHistory", {}).get(base_identity),
                            use_pools=session.mode != "exam")
        q["identity"] = fingerprint([unit["subject"], unit["runId"], question_identity(q)])
    fresh = bool(q) and q["identity"] not in person.state.get("exposures", {})
    served = {"token": uuid.uuid4().hex, "question": q, "at": now, "assisted": q is None,
              "optionsShown": True,
              "fresh": fresh, "submitted": False}
    if q:
        state = copy.deepcopy(person.state); state.setdefault("exposures", {})[q["identity"]] = now
        state["exposures"][base_identity] = now
        if q.get("choice_variant"):
            state.setdefault("choiceHistory", {})[base_identity] = q["choice_variant"]
        person.state = state
    data["served"] = served; session.data = data
    return served


def session_view(db, person, session, now):
    data = session.data
    attempts = [a for a in db.scalars(select(LearningAttempt).where(LearningAttempt.session_id == session.id,
        LearningAttempt.undone.is_(False)).order_by(LearningAttempt.created_at)) if a.data.get("acknowledged")]
    out = {"sessionId": session.id, "mode": session.mode, "status": session.status,
           "index": data["index"], "total": len(data["entries"]), "seconds": data["seconds"],
           "canUndo": bool(data.get("lastAttempt")) and session.mode != "exam"}
    if session.status != "active":
        graded = [a for a in attempts if a.data.get("correct") is not None]
        fresh = [a for a in graded if a.data.get("fresh") and not a.data.get("assisted")]
        out["summary"] = {"completed": len(attempts), "graded": len(graded),
            "correct": sum(a.data["correct"] for a in graded), "freshGraded": len(fresh),
            "freshCorrect": sum(a.data["correct"] for a in fresh),
            "newObjectives": sum(a.data.get("wasNew", False) for a in attempts),
            "delayedRecall": sum(a.data.get("delayed", False) for a in attempts),
            "burden": data.get("burden")}
        out["results"] = []
        if session.mode == "exam":
            for a in attempts:
                unit = data["units"][a.objective_key]; authorized_unit(db, unit)
                out["results"].append({"title": unit["title"], "question": public_question(a.data["served"]["question"]),
                    "submittedAnswer": a.data["answer"], **feedback(db, unit, a.data["served"], a.data)})
        return out
    served = serve(db, person, session, now); data = session.data
    if served is None: return out
    entry = data["entries"][data["index"]]; unit = data["units"][entry["key"]]
    authorized_unit(db, unit)
    q = served["question"]
    out.update(token=served["token"], lane=entry["lane"], lecture=unit["title"], subject=unit["subject"],
               runId=unit["runId"], optionsShown=served["optionsShown"], assisted=served["assisted"],
               submitted=served["submitted"], question=public_question(q) if q else None,
               recallPrompt=q.get("recall_prompt", "") if q else "",
               objective=unit["objective"]["title"] if session.mode != "exam" else "",
               help=None, feedback=None, submittedAnswer=None)
    if q and not served["optionsShown"]: out["question"]["options"] = []
    if served["assisted"]:
        out["help"] = {k: unit["objective"][k] for k in ("context", "explanation", "minimum", "rationale", "source_refs")}
    if served["submitted"]:
        attempt = db.get(LearningAttempt, served["token"])
        out["submittedAnswer"] = attempt.data["answer"]
        out["activeSeconds"] = attempt.data["seconds"]
        if session.mode != "exam":
            out["feedback"] = feedback(db, unit, served, attempt.data)
            if q:
                old = person.state.get("objectives", {}).get(unit["key"], {})
                out["reviewChoices"] = []
                for rating in RATINGS:
                    candidate = {**attempt.data, "selfCorrect": rating != "Again", "reviewRating": rating}
                    if recall_rating(candidate) == rating:
                        scheduled = schedule_review(old, candidate, rating)
                        out["reviewChoices"].append({"rating": rating, "dueAt": scheduled["dueAt"],
                            "intervalDays": scheduled["intervalDays"]})
    return out


@router.get("/sessions/{session_id}")
def read_session(session_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    person = profile(db, user); session = session_for(db, user, session_id)
    out = session_view(db, person, session, now_ms()); db.commit(); return out


class ActionIn(BaseModel):
    token: str
    action: Literal["options", "help"]


@router.post("/sessions/{session_id}/action")
def action(session_id: str, payload: ActionIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    person = profile(db, user); session = session_for(db, user, session_id)
    data = copy.deepcopy(session.data); served = data.get("served") or {}
    if session.status != "active" or served.get("token") != payload.token or served.get("submitted"):
        raise HTTPException(409, "현재 답변 전 문항이 아닙니다.")
    authorized_unit(db, data["units"][data["entries"][data["index"]]["key"]])
    if payload.action == "help":
        if session.mode == "exam": raise HTTPException(409, "시험 중에는 도움을 제공하지 않습니다.")
        served["assisted"] = True
    else: served["optionsShown"] = True
    session.data = data; out = session_view(db, person, session, now_ms()); db.commit(); return out


class SubmitIn(BaseModel):
    token: str
    confidence: Literal["sure", "unsure", "guess"] | None = None
    answer: dict = Field(default_factory=dict)
    activeSeconds: int = Field(0, ge=0, le=3600)


@router.post("/sessions/{session_id}/submit")
def submit(session_id: str, payload: SubmitIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user); session = session_for(db, user, session_id)
    existing = db.get(LearningAttempt, payload.token)
    if existing and existing.user_id == user.id and existing.session_id == session.id:
        if existing.undone: raise HTTPException(409, "되돌린 답변입니다.")
        out = session_view(db, person, session, now); db.commit(); return out
    data = copy.deepcopy(session.data); served = data.get("served") or {}
    if session.status != "active" or served.get("token") != payload.token:
        raise HTTPException(409, "현재 문항이 아닙니다.")
    unit = data["units"][data["entries"][data["index"]]["key"]]; authorized_unit(db, unit)
    q = served["question"]
    if q and q["options"] and not served["optionsShown"]: raise HTTPException(409, "보기를 확인하고 답을 선택하세요.")
    try: correct = grade(q, payload.answer) if q else None
    except ValueError as e: raise HTTPException(422, str(e)) from e
    if q and q.get("personalAnswer"): correct = None
    seconds = min(payload.activeSeconds, max(0, (now - served["at"]) // 1000), 900)
    attempt = {"objectiveKey": unit["key"], "at": now, "answer": payload.answer,
        "correct": correct, "confidence": payload.confidence, "seconds": seconds,
        "assisted": served["assisted"], "fresh": served["fresh"], "optionsShown": served["optionsShown"],
        "kind": "question" if q else "explanation", "version": unit["version"], "mode": session.mode,
        "policy": POLICY_VERSION, "served": copy.deepcopy(served), "acknowledged": False}
    db.add(LearningAttempt(id=payload.token, user_id=user.id, session_id=session.id,
        objective_key=unit["key"], created_at=now, data=attempt))
    served["submitted"] = True; session.data = data; db.flush()
    out = session_view(db, person, session, now); db.commit(); return out


class AcknowledgeIn(BaseModel):
    token: str
    selfCorrect: bool | None = None
    reviewRating: Literal["Again", "Hard", "Good", "Easy"] | None = None
    activeSeconds: int = Field(0, ge=0, le=3600)


def complete_attempt(db, person, session, attempt, self_correct, seconds, now, review_rating=None):
    data = copy.deepcopy(session.data); event = copy.deepcopy(attempt.data)
    unit = data["units"][attempt.objective_key]
    old = person.state.get("objectives", {}).get(unit["key"])
    event.update(selfCorrect=self_correct, reviewRating=review_rating, acknowledged=True,
        seconds=min(900, max(event["seconds"], seconds)), wasNew=not old or not old.get("covered"),
        before=copy.deepcopy(old))
    event["reviewRating"] = recall_rating(event)
    event["delayed"] = delayed_recall(old or {}, event)
    if event["reviewRating"]:
        event["fsrsReview"] = schedule_review(old or {}, event, event["reviewRating"])["fsrsReview"]
    if session.mode != "exam": person.state = apply_attempt(person.state, event)
    day = db.get(LearningDay, (person.user_id, data["day"]))
    event["dayBefore"] = copy.deepcopy(day.plan) if day and session.mode == "daily" else None
    if day and session.mode == "daily":
        plan = copy.deepcopy(day.plan)
        if unit["key"] not in plan["completed"]: plan["completed"].append(unit["key"])
        plan["activeSeconds"] += event["seconds"]; day.plan = plan
    # Assign after loading the day: that query can autoflush JSON, so the
    # undo snapshot must already be included in the newly assigned value.
    attempt.data = event
    data["index"] += 1; data["seconds"] += event["seconds"]
    data["lastAttempt"] = attempt.id; data["served"] = None
    if data["index"] >= len(data["entries"]) or (day and session.mode == "daily" and day.plan["activeSeconds"] >= day.plan["budgetSeconds"]):
        session.status = "complete"
    session.data = data


def release_exam(db, person, session):
    if session.mode != "exam" or session.status == "active" or session.data.get("released"): return
    state = person.state
    for attempt in db.scalars(select(LearningAttempt).where(LearningAttempt.session_id == session.id,
            LearningAttempt.undone.is_(False)).order_by(LearningAttempt.created_at)):
        if attempt.data.get("acknowledged"): state = apply_attempt(state, attempt.data)
    person.state = state; session.data = {**session.data, "released": True}


@router.post("/sessions/{session_id}/acknowledge")
def acknowledge(session_id: str, payload: AcknowledgeIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user); session = session_for(db, user, session_id)
    attempt = db.get(LearningAttempt, payload.token)
    if not attempt or attempt.user_id != user.id or attempt.session_id != session.id or attempt.undone:
        raise HTTPException(409, "제출한 답을 찾을 수 없습니다.")
    if not attempt.data.get("acknowledged"):
        if (session.data.get("served") or {}).get("token") != payload.token or session.status != "active":
            raise HTTPException(409, "현재 문항이 아닙니다.")
        authorized_unit(db, session.data["units"][attempt.objective_key])
        self_correct = payload.selfCorrect
        if attempt.data["correct"] is None and payload.reviewRating and self_correct is None:
            self_correct = payload.reviewRating != "Again"
        if attempt.data["correct"] is None and attempt.data["kind"] != "explanation" and self_correct is None:
            raise HTTPException(422, "정답과 비교한 자기평가가 필요합니다.")
        if payload.reviewRating and payload.reviewRating != "Again" and recall_rating({
                **attempt.data, "selfCorrect": self_correct, "reviewRating": payload.reviewRating}) == "Again":
            raise HTTPException(422, "오답·찍음·도움을 받은 답은 ‘다시’로 평가하세요.")
        seconds = min(payload.activeSeconds, max(0, (now - attempt.data["served"]["at"]) // 1000))
        complete_attempt(db, person, session, attempt, self_correct, seconds, now, payload.reviewRating)
        db.flush(); release_exam(db, person, session)
    out = session_view(db, person, session, now); db.commit(); return out


@router.post("/sessions/{session_id}/undo")
def undo(session_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    person = profile(db, user); session = session_for(db, user, session_id)
    if session.mode == "exam": raise HTTPException(409, "시험 답변은 되돌릴 수 없습니다.")
    other = db.scalars(select(LearningSession).where(LearningSession.user_id == user.id,
        LearningSession.created_at > session.created_at)).first()
    if other: raise HTTPException(409, "더 최근 학습 회차가 있습니다.")
    data = copy.deepcopy(session.data); attempt = db.get(LearningAttempt, data.get("lastAttempt", ""))
    if not attempt or attempt.undone or (data.get("served") or {}).get("submitted"):
        raise HTTPException(409, "마지막 완료 답변만 되돌릴 수 있습니다.")
    authorized_unit(db, data["units"][attempt.objective_key])
    state = copy.deepcopy(person.state); before = attempt.data.get("before")
    if before is None: state.setdefault("objectives", {}).pop(attempt.objective_key, None)
    else: state.setdefault("objectives", {})[attempt.objective_key] = before
    person.state = state; attempt.undone = True
    if attempt.data.get("dayBefore"):
        day = db.get(LearningDay, (user.id, data["day"]))
        if day and day.plan["revision"] != attempt.data["dayBefore"]["revision"]:
            raise HTTPException(409, "계획이 조정된 뒤에는 이전 계획의 평가를 되돌릴 수 없습니다.")
        if day: day.plan = attempt.data["dayBefore"]
    data["index"] -= 1; data["seconds"] = max(0, data["seconds"] - attempt.data["seconds"])
    restored = copy.deepcopy(attempt.data["served"])
    restored.update(token=uuid.uuid4().hex, at=now_ms(), submitted=False, fresh=False, assisted=True, optionsShown=True)
    data["served"] = restored; data["lastAttempt"] = None
    session.data = data; session.status = "active"
    out = session_view(db, person, session, now_ms()); db.commit(); return out


class EndIn(BaseModel):
    burden: Literal["light", "okay", "heavy"] | None = None
    token: str | None = None
    activeSeconds: int = Field(0, ge=0, le=3600)


@router.post("/sessions/{session_id}/end")
def end(session_id: str, payload: EndIn, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    now = now_ms(); person = profile(db, user); session = session_for(db, user, session_id)
    served = session.data.get("served") or {}
    seconds = min(payload.activeSeconds, max(0, (now - served.get("at", now)) // 1000), 900)
    if session.status == "active" and payload.token and payload.token != served.get("token"):
        raise HTTPException(409, "현재 문항이 아닙니다.")
    if session.status == "active" and session.mode == "exam" and served.get("submitted"):
        attempt = db.get(LearningAttempt, served["token"])
        if attempt and not attempt.data.get("acknowledged"):
            authorized_unit(db, session.data["units"][attempt.objective_key])
            complete_attempt(db, person, session, attempt, None, seconds, now)
    elif session.status == "active" and served:
        # Stopping counts spent time but never marks unread feedback as covered.
        attempt = db.get(LearningAttempt, served["token"])
        seconds = max(seconds, attempt.data["seconds"] if attempt else 0)
        session.data = {**session.data, "seconds": session.data["seconds"] + seconds}
        day = db.get(LearningDay, (user.id, session.data["day"]))
        if day and session.mode == "daily":
            day.plan = {**day.plan, "activeSeconds": day.plan["activeSeconds"] + seconds}
        # An earlier undo would incorrectly erase the later unfinished work.
        session.data = {**session.data, "lastAttempt": None}
    session.status = "complete"; session.data = {**session.data, "burden": payload.burden or session.data.get("burden")}
    db.flush(); release_exam(db, person, session)
    out = session_view(db, person, session, now_ms()); db.commit(); return out
