"""출제 순서의 실제 흐름: 슬라이드·선행관계·방향 간격·가중 복습·강의 간 간격."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

from app.study_engine import empty_state, record_review
from app.study_engine.batch import select_batch_question
from app.study_engine.daily_queue import daily_candidates, lecture_goal, select_daily_question
from app.study_engine.memory import DAY_MS
from app.study_engine.ordering import review_weight
from app.study_engine.policy import DEFAULT, validate_policy
from app.study_engine.planning import day_start
from tests.bank_fixtures import example_bank

NOW = 1791824400000
EXAM = "2026-11-20"


def make_bank(specs):
    bank = example_bank()
    template = bank["questions"][0]
    bank["questions"] = []
    for qid, concept, direction, page, prerequisites in specs:
        bank["questions"].append({**copy.deepcopy(template), "question_id": qid, "concept_id": concept,
                                  "retrieval_direction": direction, "prerequisites": prerequisites,
                                  "source_refs": [{"source_id": "S1", "locator": f"p.{page}"}]})
    bank["concepts"] = [{**copy.deepcopy(bank["concepts"][0]), "concept_id": cid}
                        for cid in dict.fromkeys(q["concept_id"] for q in bank["questions"])]
    bank["retrieval_plan"] = [{**copy.deepcopy(bank["retrieval_plan"][0]), "concept_id": c["concept_id"]}
                              for c in bank["concepts"]]
    return bank


def solve(bank, state=None, **kwargs):
    state = state if state is not None else empty_state()
    sequence = []
    for tick in range(len(bank["questions"])):
        now = NOW + tick
        before = copy.deepcopy(state)
        q = select_daily_question(bank, state, EXAM, now, **kwargs)["question"]
        assert state == before
        if q is None:
            break
        sequence.append(q["question_id"])
        state = record_review(bank, state, q["question_id"], "Again", now)
    return sequence, state


def main():
    # Numeric slide order overrides tiers, IDs and input ordering, including legacy shuffle=True.
    bank = make_bank([("early-id", "C3", "direct", 10, []),
                      ("late-id", "C1", "direct", 2, []), ("middle", "C2", "direct", 3, [])])
    bank["questions"][1]["tier"] = "Optional"
    bank["questions"][0]["source_refs"].append({"source_id": "S2", "locator": "p.1"})
    with patch("app.study_engine.ordering.random.choices", side_effect=AssertionError("new must follow slides")):
        assert solve(bank)[0] == ["late-id", "middle", "early-id"]
        assert solve(bank, shuffle=True)[0] == ["late-id", "middle", "early-id"]
        assert solve(bank, pages={"early-id": [1]})[0] == ["early-id", "late-id", "middle"]
    unknown = copy.deepcopy(bank)
    for q in unknown["questions"]:
        q["source_refs"] = [{"source_id": "S2", "locator": "p.1"}]
    assert solve(unknown)[0] == [q["question_id"] for q in unknown["questions"]]
    # A future-slide prerequisite chain unlocks after feedback even on Again.
    prereq = make_bank([("child", "C1", "integration", 1, ["parent"]),
                        ("parent", "C2", "mechanism", 20, ["root"]),
                        ("root", "C3", "direct", 30, [])])
    assert solve(prereq)[0] == ["root", "parent", "child"]
    suspended = empty_state()
    suspended["suspended_question_ids"] = ["parent", "root"]
    assert solve(prereq, suspended)[0] == ["child"]
    # Same-slide directions are separated by four other questions when available.
    spaced = make_bank([("A", "CA", "direct", 1, []), ("A-reverse", "CA", "reverse", 1, ["A"])] +
                       [(f"B{i}", f"CB{i}", "direct", i + 2, []) for i in range(7)])
    sequence, state = solve(spaced)
    assert sequence.index("A-reverse") - sequence.index("A") - 1 == 4, sequence
    # Only three fillers: use three; no fillers: finish without a waiting/deadlock state.
    short = copy.deepcopy(spaced)
    short["questions"] = short["questions"][:5]
    assert solve(short)[0] == ["A", "B0", "B1", "B2", "A-reverse"]
    short["questions"] = short["questions"][:2]
    assert solve(short)[0] == ["A", "A-reverse"]
    assert lecture_goal(spaced, state, "test", NOW + 20)["met"]
    # Direction intervals restart at the Korean day boundary, including removed IDs as fillers.
    prior = record_review(spaced, empty_state(), "A", "Again", day_start(NOW) - 1)
    prior["suspended_question_ids"] = ["A"]
    assert select_daily_question(spaced, prior, EXAM, NOW)["question"]["question_id"] == "A-reverse"
    # Preserve original due dates even when all today's reviews are immediately available.
    review = make_bank([(f"R{i}", f"CR{i}", "direct", i + 1, []) for i in range(4)])
    state = empty_state()
    for qid in ("R0", "R1", "R2", "R3"):
        state = record_review(review, state, qid, "Good", NOW - DAY_MS)
    for qid, due in (("R0", NOW - 4 * DAY_MS), ("R1", NOW - 1000),
                     ("R2", day_start(NOW) + DAY_MS - 1), ("R3", day_start(NOW) + DAY_MS)):
        state["items"][qid]["due_at"] = due
        next(h for h in state["history"] if h["question_id"] == qid)["next_due_at"] = due
    # _due respects earliest next-day availability; use an older history for the overdue item.
    state["history"][0]["timestamp"] = NOW - 5 * DAY_MS
    state["dimensions"]["CR2:direct"]["mastery"] = 0.8
    state["dimensions"]["CR1:direct"]["mastery"] = 0.05
    pool, _ = daily_candidates(review, state, EXAM, NOW)
    by_id = {c["question"]["question_id"]: c for c in pool}
    assert set(by_id) == {"R0", "R1", "R2"}
    assert by_id["R0"]["unit"]["scheduled_due"] == NOW - 4 * DAY_MS
    assert by_id["R2"]["unit"]["due"] <= NOW < by_id["R2"]["unit"]["scheduled_due"]
    assert review_weight(by_id["R0"], NOW) > review_weight(by_id["R1"], NOW) > review_weight(by_id["R2"], NOW)
    for shuffle in (False, True):
        with patch("app.study_engine.ordering.random.choices", side_effect=lambda population, **kw: [population[-1]]) as draw:
            got = select_daily_question(review, state, EXAM, NOW, shuffle=shuffle)
            assert got["question"]["question_id"] == "R2"
            assert draw.call_count == 1 and len(set(draw.call_args.kwargs["weights"])) > 1
    # A known review does not demand its (already evaluated) prerequisite again.
    review["questions"][1]["prerequisites"] = ["R3"]
    assert "R1" in {c["question"]["question_id"] for c in daily_candidates(review, state, EXAM, NOW)[0]}
    # Batch uses the SAME ordering; other lectures' answers count as intervening questions.
    a = copy.deepcopy(short)
    b = make_bank([(f"B{i}", "CA", "direct", i + 1, []) for i in range(4)])
    entries = [{"key": ("subject", name), "bank": bank, "state": empty_state(), "exam": EXAM,
                "row": SimpleNamespace(pages={}), "goal": lecture_goal(bank, empty_state(), name, NOW)}
               for name, bank in (("A", a), ("B", b))]
    picked = []
    for tick in range(6):
        chosen, result = select_batch_question(entries, NOW + tick)
        qid = result["question"]["question_id"]
        picked.append((chosen["key"][1], qid))
        chosen["state"] = record_review(chosen["bank"], chosen["state"], qid, "Again", NOW + tick)
        chosen["goal"] = lecture_goal(chosen["bank"], chosen["state"], "test", NOW + tick)
    assert picked == [("A", "A"), ("B", "B0"), ("B", "B1"), ("B", "B2"), ("B", "B3"), ("A", "A-reverse")], picked
    assert select_batch_question(entries, NOW + 7) == (None, None)
    # On review, weights compete across lectures instead of random lecture selection first.
    for entry in entries:
        entry["goal"] = lecture_goal(entry["bank"], entry["state"], "test", NOW + DAY_MS)
    with patch("app.study_engine.ordering.random.choices", side_effect=lambda population, **kw: [population[-1]]) as draw:
        chosen, _ = select_batch_question(entries, NOW + DAY_MS)
        assert chosen["key"][1] == "B" and len(draw.call_args.args[0]) == 6
    invalid = copy.deepcopy(DEFAULT)
    invalid["ordering"]["minIntervening"] = 6
    try:
        validate_policy(invalid)
        raise AssertionError("invalid spacing accepted")
    except ValueError:
        pass
    print("PASS: slides, prerequisites, four/three/zero fillers, KST, suspensions, original due dates, weakness weights, shared batch history and namespaced concepts")


if __name__ == "__main__":
    main()
