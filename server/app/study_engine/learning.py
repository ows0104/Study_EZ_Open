"""Time-bounded, objective-based learning. Pure functions; no DB or wall clock.

Review intervals use FSRS defaults, not personalized or exam probabilities.
Coverage, delayed recall and unfamiliar-question performance remain separate.
"""

import copy
import math

from app.bank_validation.learning import fingerprint, learning_content, objective_identity, question_identity
from .memory import DAY_MS
from .learning_srs import delayed_recall, recall_rating, schedule_review

POLICY_VERSION = "learning-2-fsrs"
SHARES = {"new": .5, "review": .25, "drill": .125, "mixed": .125}


def catalog_unit(subject: str, run_id: str, title: str, bank: dict, version: str,
                 deadline: int | None = None) -> list[dict]:
    objectives, questions = learning_content(bank)
    keys = {o["objective_id"]: fingerprint([subject, run_id, objective_identity(o)]) for o in objectives}
    return [{"key": keys[o["objective_id"]], "subject": subject, "runId": run_id, "title": title,
             "objective": o, "version": version, "deadline": deadline,
             "prerequisites": [keys[p] for p in o.get("prerequisites", []) if p in keys],
             "questions": [{**q, "identity": fingerprint([subject, run_id, question_identity(q)]),
                            "supportingKeys": [keys[p] for p in q.get("supporting_objective_ids", []) if p in keys]}
                           for q in questions if q["primary_objective_id"] == o["objective_id"]]}
            for o in objectives]


def estimate(unit: dict, state: dict, lane: str) -> int:
    observed = state.get("objectives", {}).get(unit["key"], {}).get("seconds")
    default = 120 if lane == "new" else 35 if lane == "drill" else 75
    return round(max(20, min(240, observed or default)))


def choose_question(unit: dict, state: dict, *, exam: bool = False) -> dict | None:
    exposures = state.get("exposures", {})
    questions = [q for q in unit["questions"] if (q.get("role") == "exam") == exam]
    if exam:
        questions = [q for q in questions if q["identity"] not in exposures
                     and all(state.get("objectives", {}).get(k, {}).get("covered")
                             for k in q.get("supportingKeys", []))]
    questions.sort(key=lambda q: (q["identity"] in exposures,
                                  exposures.get(q["identity"], 0),
                                  q.get("role") != "learning", q["item_difficulty"], q["question_id"]))
    return questions[0] if questions else None


def build_plan(units: list[dict], state: dict, now: int, minutes: int, buffer_days: int = 3) -> dict:
    budget = minutes * 60
    states = state.get("objectives", {})
    unseen = [u for u in units if not states.get(u["key"], {}).get("covered")]
    known = [u for u in units if states.get(u["key"], {}).get("covered")]
    due = [u for u in known if states[u["key"]].get("dueAt", 0) <= now]
    # Breadth: fewer covered objectives in a lecture comes first. Deadline
    # urgency precedes fairness between exams; never require repeated mastery.
    lecture_progress = {}
    for u in known:
        k = (u["subject"], u["runId"])
        lecture_progress[k] = lecture_progress.get(k, 0) + 1
    unseen.sort(key=lambda u: (u["deadline"] or now + 365 * DAY_MS,
                              lecture_progress.get((u["subject"], u["runId"]), 0),
                              any(not states.get(p, {}).get("covered") for p in u["prerequisites"]),
                              -u["objective"]["importance"], u["key"]))
    # Round-robin within the ordered lecture groups, so a large question bank
    # cannot consume every new slot before another lecture is encountered.
    buckets = {}
    for u in unseen: buckets.setdefault((u["subject"], u["runId"]), []).append(u)
    unseen = []
    introduced = {u["key"] for u in known}
    while any(buckets.values()):
        for group in buckets.values():
            if not group: continue
            candidate = next((u for u in group if all(p in introduced for p in u["prerequisites"])), group[0])
            group.remove(candidate); unseen.append(candidate); introduced.add(candidate["key"])
    def priority(u):
        s = states[u["key"]]
        overdue = max(0, (now - s.get("dueAt", now)) / DAY_MS)
        urgency = 2 if u["deadline"] and u["deadline"] - now < 7 * DAY_MS else 1
        return (u["objective"]["importance"] * urgency + min(30, overdue)
                + (4 if s.get("lastCorrect") is False else 0)) / math.sqrt(estimate(u, state, "review"))
    due.sort(key=priority, reverse=True)
    pools = {"new": unseen,
             "review": [u for u in due if u["objective"]["kind"] != "fact"],
             "drill": [u for u in due if u["objective"]["kind"] == "fact"],
             "mixed": sorted([u for u in known if choose_question(u, state)], key=lambda u: states[u["key"]].get("lastAt", 0))}
    daily_need = sum(estimate(u, state, "new") / max(1, ((u["deadline"] or now + 14 * DAY_MS) - buffer_days * DAY_MS - now) / DAY_MS) for u in unseen)
    # Increase new share when needed, keeping a review opportunity; report any
    # remaining infeasibility rather than silently expanding the day.
    new_budget = min(budget * .8, max(budget * .5, daily_need)) if unseen else 0
    remaining = budget - new_budget
    limits = {"new": new_budget, "review": remaining * .5, "drill": remaining * .25, "mixed": remaining * .25}
    selected, picked = {lane: [] for lane in pools}, set()
    used = 0
    def add(lane, limit):
        nonlocal used
        spent = 0
        for u in pools[lane]:
            cost = estimate(u, state, lane)
            if u["key"] in picked or spent + cost > limit or used + cost > budget:
                continue
            if lane != "new" and not choose_question(u, state):
                continue
            picked.add(u["key"]); spent += cost; used += cost
            selected[lane].append({"key": u["key"], "lane": lane, "seconds": cost})
    for lane in pools:
        add(lane, limits[lane])
    # Unused allocation can be used elsewhere, but it never exceeds the total.
    for lane in pools:
        add(lane, budget - used)
    entries = []
    while any(selected.values()):
        for lane in ("new", "review", "new", "drill", "mixed"):
            if selected[lane]: entries.append(selected[lane].pop(0))
    return {"policy": POLICY_VERSION, "budgetSeconds": budget, "estimatedSeconds": used,
            "entries": entries, "createdAt": now, "newRequiredMinutes": math.ceil(daily_need / 60),
            "infeasible": daily_need > budget * .8, "bufferDays": buffer_days,
            "completed": [], "activeSeconds": 0, "revision": 1}


def grade(q: dict, answer: dict) -> bool | None:
    if q["format"] in ("mcq", "multi_select"):
        selected = answer.get("selected", [])
        ids = {o["id"] for o in q["options"]}
        if (not isinstance(selected, list) or not selected or any(not isinstance(x, str) for x in selected)
                or len(set(selected)) != len(selected) or any(x not in ids for x in selected)):
            raise ValueError("선택지를 확인하세요.")
        if q["format"] == "mcq" and len(selected) != 1: raise ValueError("하나의 답을 선택하세요.")
        return set(selected) == set(q["correct_option_ids"])
    if q["format"] == "ox":
        if answer.get("text") not in ("O", "X"): raise ValueError("O 또는 X를 선택하세요.")
        return answer["text"] == q["answer"].strip().upper()
    if q["format"] == "matching":
        pairs = answer.get("pairs", {})
        if not isinstance(pairs, dict) or set(pairs) != set(q["matching_left"]) or any(v not in q["matching_right"] for v in pairs.values()):
            raise ValueError("모든 항목의 짝을 선택하세요.")
        return pairs == {p["left"]: p["right"] for p in q["answer_pairs"]}
    if q["format"] == "sequence":
        order = answer.get("order", [])
        if (not isinstance(order, list) or any(not isinstance(x, str) for x in order)
                or sorted(order) != sorted(q["sequence_items"])): raise ValueError("순서 항목을 확인하세요.")
        return order == q["correct_order"]
    return None  # Human self-report is separately recorded after feedback.


def apply_attempt(previous: dict, attempt: dict) -> dict:
    state = copy.deepcopy(previous)
    objectives = state.setdefault("objectives", {})
    key, at = attempt["objectiveKey"], attempt["at"]
    old = objectives.get(key, {})
    correct = attempt.get("correct")
    if correct is None: correct = attempt.get("selfCorrect")
    rating = recall_rating(attempt)
    schedule = schedule_review(old, attempt, rating) if rating else {
        "dueAt": min(old.get("dueAt", at + DAY_MS), at + DAY_MS)}
    successes = old.get("delayedSuccesses", 0) + int(delayed_recall(old, attempt))
    if rating == "Again": successes = 0
    objectives[key] = {**old, "covered": True, "lastAt": at, "lastCorrect": correct,
                       "confidence": attempt.get("confidence"), **schedule, "delayedSuccesses": successes,
                       "assessments": old.get("assessments", 0) + int(correct is not None),
                       "seconds": round(.7 * old.get("seconds", attempt["seconds"]) + .3 * attempt["seconds"]),
                       "evidence": "self_report" if attempt.get("correct") is None else "graded"}
    return state


def progress(units: list[dict], state: dict) -> dict:
    states = state.get("objectives", {})
    return {"total": len(units), "covered": sum(bool(states.get(u["key"], {}).get("covered")) for u in units),
            "delayedRecall": sum(states.get(u["key"], {}).get("delayedSuccesses", 0) >= 2 for u in units),
            "questionGaps": sum(not choose_question(u, state) for u in units),
            "legacyObjectives": sum(bool(u["objective"].get("legacy")) for u in units)}


def workload(units: list[dict], state: dict, plan: dict | None, now: int, buffer_days: int) -> dict:
    """Count distinct objectives, scoped to one lecture or the whole dashboard.

    Today's count follows the fixed plan, not the number of variants/attempts.
    Time-budget closure defers unfinished entries; it never marks them studied.
    A missing plan is unknown in the read-only calendar projection.
    """
    unique = {u["key"]: u for u in units}
    states = state.get("objectives", {})
    unseen = sum(not states.get(key, {}).get("covered") for key in unique)
    review_dates = [states[key].get("dueAt", 0) for key, u in unique.items()
                    if states.get(key, {}).get("covered") and choose_question(u, state)]
    deadlines = [u["deadline"] for u in unique.values() if u.get("deadline")]
    exam = min(deadlines) if deadlines else None
    daily = None
    if plan is not None:
        entries = {e["key"]: e for e in plan["entries"] if e["key"] in unique}
        done = set(plan["completed"]) & entries.keys()
        pending = [e for key, e in entries.items() if key not in done]
        stopped = plan["activeSeconds"] >= plan["budgetSeconds"]
        remaining = [] if stopped else pending
        daily = {"total": len(entries), "completed": len(done), "remaining": len(remaining),
                 "new": sum(e["lane"] == "new" for e in remaining),
                 "review": sum(e["lane"] != "new" for e in remaining),
                 "deferred": len(pending) if stopped else 0}
    return {"unseen": unseen, "dueReviews": sum(at <= now for at in review_dates),
            "nextReviewAt": min((at for at in review_dates if at > now), default=None),
            "firstPassTargetAt": exam - buffer_days * DAY_MS if exam else None,
            "examAt": exam, "today": daily}
