"""Review undo restores full learning state and never crosses session boundaries."""
import copy
from app import study_engine as engine
from app.study_engine.review_undo import remember_review, undo_review, undo_token
from tests.bank_fixtures import example_bank

bank = example_bank()
now = 1_791_320_000_000
initial = engine.start_session(bank, engine.empty_state(), 10, now)
initial["remediations"] = [{"parent_id": "Q3", "prerequisite_id": "Q1", "remaining": 2, "started_at": now}]

def review(state, question_id, rating, at, token):
    state = copy.deepcopy(state)
    state["served"] = {"question_id": question_id, "token": token, "revealed": True, "presented_at": at}
    got = engine.record_review(bank, state, question_id, rating, at)
    remember_review(state, got)
    return state, got

for rating in ("Again", "Hard", "Good", "Easy"):
    before, rated = review(initial, "Q1", rating, now, rating)
    assert undo_review(rated, rating) == before
    print(f"PASS: {rating} restores state including remediation and schedule")

before1, rated1 = review(initial, "Q1", "Good", now, "first")
before2, rated2 = review(rated1, "Q3", "Again", now + 1000, "second")
closed = engine.end_session(bank, rated2, "size_reached", now + 2000)
assert undo_review(closed, "second") == before2
assert undo_token(undo_review(closed, "second")) == "first"
assert undo_review(undo_review(closed, "second"), "first") == before1
assert undo_token(engine.start_session(bank, closed, 10, now + 3000)) is None
legacy = copy.deepcopy(closed)
legacy["history"][-1].pop("undo")
assert undo_token(legacy) is None
assert initial["history"] == []
print("PASS: completion reopen, repeated undo, new session boundary, legacy state and immutable inputs")
