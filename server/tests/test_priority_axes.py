"""Priority/depth contract across validation, selection, targets and existing state."""
import copy
from types import SimpleNamespace

from app.bank_validation.schema import QUESTION, schema_errors, without_retired
from app.bank_validation.validate import validate_bank
from app.study_engine import empty_state, record_review
from app.study_engine.batch import select_batch_question
from app.study_engine.daily_queue import lecture_goal, select_daily_question
from app.study_engine.engine import rank_questions, select_question, target_for
from tests.bank_fixtures import example_bank

NOW = 1791824400000
EXAM = "2026-11-20"


def bank_with_questions():
    bank = without_retired(example_bank())
    template = bank["questions"][0]
    bank["questions"] = [
        {**copy.deepcopy(template), "question_id": qid, "tier": tier, "advanced": depth,
         "importance": {"Core": 5, "Important": 4, "Optional": 2}[tier],
         "source_refs": [{"source_id": "S1", "locator": f"p.{page}"}]}
        for qid, tier, depth, page in (
            ("optional-depth", "Optional", True, 1), ("important", "Important", False, 2),
            ("core-depth", "Core", True, 3), ("core", "Core", False, 4),
            ("optional", "Optional", False, 5), ("important-depth", "Important", True, 6))]
    bank["retrieval_plan"][0]["directions"] = ["direct"]
    return bank


def main():
    bank = bank_with_questions()
    assert validate_bank(bank, ["S1"], check_quality=False)["pass"]
    before = copy.deepcopy(bank)
    state = empty_state()
    order = []
    for i in range(6):
        chosen = select_daily_question(bank, state, EXAM, NOW + i)["question"]
        order.append(chosen["question_id"])
        state = record_review(bank, state, chosen["question_id"], "Again", NOW + i)
    assert order == ["core", "core-depth", "important", "important-depth", "optional", "optional-depth"], order
    assert bank == before and len(state["history"]) == 6
    assert select_daily_question(bank, state, EXAM, NOW + 10)["question"] is None
    assert lecture_goal(bank, state, "test", NOW + 10)["met"]
    assert select_question(bank, empty_state(), EXAM, NOW, prefer_unseen=True)["question"]["question_id"] == "core"
    # Shared concept plans cannot give Optional a Core target; depth never raises it.
    targets = {q["question_id"]: target_for(bank, q)["effective"] for q in bank["questions"]}
    assert targets == {"core": .85, "core-depth": .85, "important": .78, "important-depth": .78,
                       "optional": .55, "optional-depth": .55}
    bank["retrieval_plan"][0]["target_mastery"] = .4
    assert all(target_for(bank, q)["effective"] == .4 for q in bank["questions"])
    # The separate depth flag, rather than Important, controls adaptive depth gating.
    ranked = {r["question_id"]: r for r in rank_questions(bank, empty_state(), EXAM, NOW)}
    assert ranked["important"]["eligible"] and not ranked["core-depth"]["eligible"]
    # Prerequisites can cross priorities and must still be seen first.
    bank["questions"] = [q for q in bank["questions"] if q["question_id"] in ("core", "optional")]
    bank["questions"][0]["prerequisites"] = ["optional"]
    assert select_daily_question(bank, empty_state(), EXAM, NOW)["question"]["question_id"] == "optional"
    # Core in another lecture takes precedence over an earlier lecture's Important.
    a = bank_with_questions(); b = bank_with_questions()
    a["questions"] = [q for q in a["questions"] if q["question_id"] == "important"]
    b["questions"] = [q for q in b["questions"] if q["question_id"] == "core"]
    entries = [{"key": ("test", str(i)), "bank": bank, "state": empty_state(), "exam": EXAM,
                "row": SimpleNamespace(pages={}), "goal": lecture_goal(bank, empty_state(), "test", NOW)}
               for i, bank in enumerate((a, b))]
    entry, picked = select_batch_question(entries, NOW)
    assert entry is entries[1] and picked["question"]["question_id"] == "core"
    # Historical middle priorities remain readable, without guessing depth.
    legacy = example_bank(); original = copy.deepcopy(legacy)
    normalized = without_retired(legacy)
    assert legacy == original and normalized["questions"][1]["tier"] == "Important"
    assert normalized["questions"][1]["advanced"] is False
    normalized["build_meta"]["schema_version"] = "3.1"
    assert validate_bank(normalized, ["S1"], check_quality=False)["pass"]
    question = copy.deepcopy(normalized["questions"][0]); question.pop("advanced")
    assert any("advanced" in e for e in schema_errors(question, QUESTION))
    question["advanced"] = "true"
    assert any("boolean" in e for e in schema_errors(question, QUESTION))
    print("PASS: independent priority/depth, daily/batch/unseen order, prerequisites, per-question targets, adaptive gating, history and legacy compatibility")


if __name__ == "__main__":
    main()
