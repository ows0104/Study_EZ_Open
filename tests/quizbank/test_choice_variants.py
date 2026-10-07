"""Choice variants survive the shared validator; reordered copies still drop."""

import copy
import json
from pathlib import Path

import pytest

from quizbank.validate import validate_dropping


def choice_bank(format="mcq"):
    path = Path(__file__).parent / "fixtures" / "bank_261002_02.json"
    bank = json.loads(path.read_text(encoding="utf-8"))
    bank, validation = validate_dropping(bank, ["S1", "S2"])
    assert validation["pass"]
    original = next(q for q in bank["questions"] if q["format"] == "mcq")
    original["format"] = format
    variant = copy.deepcopy(original)
    variant["question_id"] = "CHOICE-VARIANT"
    bank["questions"].append(variant)
    return bank, original, variant


@pytest.mark.parametrize("format", ["mcq", "multi_select"])
def test_different_misconception_choices_survive_same_stem(format):
    bank, original, variant = choice_bank(format)
    # A new comparison comes from another real question's answer.
    comparison = next(q["answer"] for q in bank["questions"]
                      if q["format"] == "basic" and q["answer"] not in
                      {o["text"] for o in original["options"]})
    distractor = next(o for o in variant["options"] if o["id"] not in variant["correct_option_ids"])
    distractor["text"] = comparison
    kept, validation = validate_dropping(bank, ["S1", "S2"])
    assert validation["pass"] and validation["dropped"] == []
    assert {original["question_id"], variant["question_id"]} <= {q["question_id"] for q in kept["questions"]}


@pytest.mark.parametrize("change", ["reorder", "relabel", "answer_only"])
def test_cosmetic_choice_copies_and_conflicting_answer_keys_still_drop(change):
    bank, original, variant = choice_bank()
    if change == "reorder":
        variant["options"].reverse()
    elif change == "relabel":
        labels = {o["id"]: f"V{i}" for i, o in enumerate(variant["options"])}
        for o in variant["options"]:
            o["id"] = labels[o["id"]]
        variant["correct_option_ids"] = [labels[i] for i in variant["correct_option_ids"]]
    else:
        variant["correct_option_ids"] = [next(o["id"] for o in variant["options"]
                                               if o["id"] not in original["correct_option_ids"])]
    kept, validation = validate_dropping(bank, ["S1", "S2"])
    assert validation["pass"]
    assert validation["dropped"][0]["errors"] == ["CHOICE-VARIANT: 중복 발문"]
    assert variant["question_id"] not in {q["question_id"] for q in kept["questions"]}


def test_basic_duplicate_rule_remains_unchanged():
    bank, _, variant = choice_bank()
    bank["questions"].remove(variant)
    original = next(q for q in bank["questions"] if q["format"] == "basic")
    variant = {**original, "question_id": "BASIC-COPY"}
    bank["questions"].append(variant)
    _, validation = validate_dropping(bank, ["S1", "S2"])
    assert validation["pass"]
    assert validation["dropped"][0]["errors"] == ["BASIC-COPY: 중복 발문"]
