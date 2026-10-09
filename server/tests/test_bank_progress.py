"""Distinct viewed-question progress, including legacy state compatibility."""
from app.study_engine.progress import mark_seen, panel_progress

bank = {"questions": [{"question_id": f"Q{i}", "tier": "Core" if i < 30 else "Advanced"}
                       for i in range(58)] + [{"question_id": "optional", "tier": "Optional"}]}
state = {"items": {f"Q{i}": {"reviews": 4} for i in range(24)},
         "history": [{"question_id": "Q0"}] * 8 + [{"question_id": "retired"}],
         "served": {"question_id": "optional"}}
assert panel_progress(bank, state) == {"studyQuestionCount": 58, "seenQuestionCount": 24}
mark_seen(state, "Q24")
mark_seen(state, "Q24")
assert panel_progress(bank, state)["seenQuestionCount"] == 25
state["served"] = None
state["history"] = []
assert panel_progress(bank, state)["seenQuestionCount"] == 25  # ending or undoing a review cannot unsee it
assert panel_progress(bank, {}) == {"studyQuestionCount": 58, "seenQuestionCount": 0}
assert panel_progress({"questions": [{"question_id": "optional", "tier": "Optional"}]}, state) == {
    "studyQuestionCount": 0, "seenQuestionCount": 0}
print("PASS: 24/58, Optional excluded, repeated views, retained views, empty/replaced bank")
