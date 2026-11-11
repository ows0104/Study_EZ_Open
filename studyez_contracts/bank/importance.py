"""Importance from source evidence: one judgment (the basis), everything else is computed.

Decided with the administrator on 2026-11-08 (docs/changes/2026-11-08-importance-basis). A point
carries its `importance_basis` (what the original shows); this module turns it into a score, a
tier and the bank importance, and projects the three review axes of a learning target. Notebook
legends, colours and stamps differ by writer, so they are cues for the extractor, never weights here.
"""
from __future__ import annotations

import json

POLICY = "importance-basis/1"
BANK_IMPORTANCE = {"Essential": 5, "Core": 4, "Important": 3, "Optional": 2}  # bank 3.3
LABEL = {"Essential": "Must-Know", "Core": "Core", "Important": "Important", "Optional": "Optional"}
WEIGHTS = {
    "current_exam": 2.0,         # this year's professor, per distinct exam year
    "learning_objective": 1.5,   # objectives, Summary, Take-home
    "slide_emphasis": 1.0,       # bold / colour / underline / box on the original slide (not titles)
    "professor_remark": 1.0,     # the professor's words written down in the notes
    "clinical": 1.0,
    "structural": 1.0,
    "writer_stamp": 0.5,
    "writer_remark": 0.5,        # a note whose author cannot be told from its wording
    "other_exam": 0.5,           # another professor's exam on the same topic
    "last_year_emphasis": 0.5,
}
OVERRIDES = ("exam_forecast", "exam_exclusion")
FLOOR = "writer_mark"            # parts the professor read out: at least Important
KINDS = (*OVERRIDES, FLOOR, *WEIGHTS)
STYLES = ("slide", "verbal")     # verbal: the professor emphasises by speech, so writer marks count +1
MUST_KNOW_SCORE, CORE_SCORE, IMPORTANT_SCORE = 4.0, 1.5, 1.0
# 2026-11-08 live Quiz Bank, 35 lectures: per-lecture Must-Know share median 9%, p90 34%, max 63%.
MUST_KNOW_SHARE_WARN = 0.34
AXES = {"exam": ("exam_forecast", "current_exam", "other_exam", "learning_objective", "slide_emphasis",
                 "professor_remark", "writer_mark", "writer_stamp", "writer_remark", "last_year_emphasis"),
        "clinical": ("clinical",), "structural": ("structural",)}
REVIEW_KIND = {"exam_forecast": "exam_forecast", "current_exam": "observed_exam", "other_exam": "observed_exam",
               "clinical": "clinical_rationale", "structural": "structural_rationale"}


class ImportanceError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise ImportanceError(message)


def validate_basis(basis):
    """Shape of one point's basis. `current_exam` rows name their exam year (`year`)."""
    _require(type(basis) is list, "importance_basis: list required")
    for row in basis:
        _require(type(row) is dict and row.get("kind") in KINDS, f"importance_basis: unknown kind {row!r:.80}")
        _require(type(row.get("reason")) is str and row["reason"].strip(), "importance_basis: reason required")
        _require(type(row.get("quote")) is str, "importance_basis: quote must be a string")
        refs = row.get("refs")
        _require(type(refs) is list and refs and all(type(r) is dict and type(r.get("source_id")) is str
                 and type(r.get("pages")) is list and all(type(p) is int and p >= 1 for p in r["pages"]) for r in refs),
                 "importance_basis: refs need source_id and physical pages")
        if row["kind"] == "current_exam":
            _require(type(row.get("year")) is int, "importance_basis: current_exam needs its exam year")
        if row["kind"] in OVERRIDES:
            _require(row["quote"].strip(), f"importance_basis: {row['kind']} needs the original wording")


def score(basis, style="slide"):
    """`{tier, importance, score, rule}` for one point. Same kinds count once; exam years each."""
    validate_basis(basis)
    _require(style in STYLES, "emphasis_style must be slide or verbal")
    kinds = {r["kind"] for r in basis}
    if "exam_exclusion" in kinds:
        return {"tier": "Optional", "importance": BANK_IMPORTANCE["Optional"], "score": 0.0, "rule": "exclusion"}
    if "exam_forecast" in kinds:
        return {"tier": "Essential", "importance": BANK_IMPORTANCE["Essential"], "score": None, "rule": "forecast"}
    total = sum(WEIGHTS[k] for k in kinds if k in WEIGHTS and k != "current_exam")
    total += WEIGHTS["current_exam"] * len({r["year"] for r in basis if r["kind"] == "current_exam"})
    if FLOOR in kinds and style == "verbal":
        total += 1.0
    tier = ("Essential" if total >= MUST_KNOW_SCORE else "Core" if total >= CORE_SCORE
            else "Important" if total >= IMPORTANT_SCORE else "Optional")
    rule = "sum"
    if FLOOR in kinds and tier == "Optional":
        tier, rule = "Important", "floor"
    return {"tier": tier, "importance": BANK_IMPORTANCE[tier], "score": total, "rule": rule}


ORDER = {"Optional": 0, "Important": 1, "Core": 2, "Essential": 3}


def point_table(points, profile):
    """Per point: its basis and computed decision. `points` is exam-point-extract/3."""
    _require(type(profile) is dict and profile.get("emphasis_style") in STYLES, "notebook_profile.emphasis_style required")
    table = {}
    for p in points:
        _require(p["point_id"] not in table, "duplicate point_id")
        table[p["point_id"]] = {"basis": p["importance_basis"], **score(p["importance_basis"], profile["emphasis_style"])}
    return {"policy": POLICY, "emphasis_style": profile["emphasis_style"], "points": table}


def question_table(basis_by_question, profile):
    """Per question (root-generation/4): the question's own basis and computed decision.

    From 2026-11-10 the authoring stages write the basis per question and the exam points carry none
    (docs/changes/2026-11-10-importance-at-authoring R2). Kinds, weights and lines are the point table's."""
    _require(type(profile) is dict and profile.get("emphasis_style") in STYLES, "notebook_profile.emphasis_style required")
    _require(type(basis_by_question) is dict, "question basis must map question_id to a basis")
    rows = {qid: {"basis": basis, **score(basis, profile["emphasis_style"])} for qid, basis in basis_by_question.items()}
    return {"policy": POLICY, "source": "question", "emphasis_style": profile["emphasis_style"], "questions": rows}


def _rows(table):
    return table["questions"] if table.get("source") == "question" else table["points"]


def question_decision(table, point_ids):
    """The highest decision among the points a question implements (bases are not pooled)."""
    _require(type(point_ids) is list and point_ids and all(p in table["points"] for p in point_ids),
             "question point_ids must name extracted points")
    best = max((table["points"][p] for p in point_ids), key=lambda d: ORDER[d["tier"]])
    return {"tier": best["tier"], "importance": best["importance"]}


def _ref(r, quote, page_counts):
    """A review REF. Pages stay only when the source declares a page count that covers them."""
    count = (page_counts or {}).get(r["source_id"])
    pages = list(r["pages"]) if count and max(r["pages"]) <= count else []
    where = "physical PDF page " + ", ".join(map(str, r["pages"]))
    return {"source_id": r["source_id"], "pages": pages, "locator": (quote.strip() + " — " + where) if quote.strip() else where}


def _unique(refs):
    """Each reference once, in first-seen order. An authoring basis can name the same page twice (2026-11-11 아데노·
    폭스: {S1, [15]} twice), and the review document rejects repeated entries."""
    seen, out = set(), []
    for r in refs:
        key = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def target_axes(table, point_ids, page_counts=None):
    """The three review axes of a learning target from its points' bases (no `unreviewed`).

    With a question table (`question_table`) the ids are the target's question ids."""
    axes = {}
    rows = _rows(table)
    source = "문항" if table.get("source") == "question" else "포인트"
    for axis, kinds in AXES.items():
        evidence = []
        for pid in point_ids:
            for row in rows[pid]["basis"]:
                if row["kind"] in kinds:
                    evidence.append({"kind": REVIEW_KIND.get(row["kind"], "teaching_emphasis"),
                                     "reason": f"{pid} {row['kind']}: {row['reason']}",
                                     "refs": _unique([_ref(r, row["quote"], page_counts) for r in row["refs"]])})
        excluded = [pid for pid in point_ids if rows[pid]["rule"] == "exclusion"]
        # Points: one excluded point marks the target. Questions: only when every question is excluded, since
        # several questions of one target can ask different parts of it.
        marks = len(excluded) == len(point_ids) if table.get("source") == "question" else bool(excluded)
        if axis == "exam" and excluded and marks:
            axes[axis] = {"status": "insufficient", "reason": "출제 제외: " + ", ".join(excluded), "evidence": []}
        else:
            axes[axis] = ({"status": "supported", "reason": f"{POLICY} {source} 근거에서 계산", "evidence": evidence} if evidence
                          else {"status": "insufficient", "reason": f"{POLICY}: 이 축의 근거 없음", "evidence": []})
    return axes


def must_know_share(decisions):
    """Share of Must-Know questions and the warning when it passes the live p90 line."""
    n = len(decisions)
    share = sum(1 for d in decisions if d["tier"] == "Essential") / n if n else 0.0
    warn = [f"Must-Know {share:.0%}(운영 Quiz Bank 편별 p90 {MUST_KNOW_SHARE_WARN:.0%}) — 예고 원문이 회상 단위마다 맞는지 확인"] \
        if share > MUST_KNOW_SHARE_WARN else []
    return share, warn


def forecast_spread(points):
    """How many points share one forecast quote (reported; the warning line comes from the first runs)."""
    spread = {}
    for p in points:
        for r in p["importance_basis"]:
            if r["kind"] == "exam_forecast":
                spread.setdefault(r["quote"].strip(), []).append(p["point_id"])
    return spread
