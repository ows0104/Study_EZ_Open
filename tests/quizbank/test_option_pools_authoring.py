import copy
import json
from pathlib import Path

import pytest

from quizbank import option_pools
from quizbank.schema import without_retired
from quizbank.session import SessionError
from quizbank.validate import validate_dropping


@pytest.fixture
def bank():
    raw = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    return without_retired(validate_dropping(raw, ["S1", "S2"])[0])


def pool_for(q):
    return {"pool_id": "P1", "select_count": len(q["options"]), "correct_when": "true",
            "candidates": [{"candidate_id": f"C{i}", "true_text": f"Test true {i}", "false_text": f"Test false {i}",
                "true_explanation": "Test evidence", "false_explanation": "Test correction",
                "source_refs": [{"source_id": "S1", "locator": "p.1"}]} for i in range(len(q["options"]) + 1)]}


def proposal(bank):
    q = next(q for q in bank["questions"] if q["format"] == "mcq")
    return {"summary": "Additional judgment variations", "proposals": [{"question_id": q["question_id"],
        "option_pools": [pool_for(q)], "reason": "Different misconceptions under one criterion"}]}


def test_authoring_only_adds_pools_preserving_all_web_content(bank):
    before = copy.deepcopy(bank)
    output = proposal(bank)
    augmented = option_pools.apply(bank, output)
    for old, new in zip(bank["questions"], augmented["questions"]):
        assert {k: v for k, v in old.items() if k != "option_pools"} == {k: v for k, v in new.items() if k != "option_pools"}
    assert augmented["concepts"] == bank["concepts"] and bank == before
    assert augmented["questions"] != bank["questions"]
    assert option_pools.apply(bank, {"summary": "No additional learning value", "proposals": []}) == bank


@pytest.mark.parametrize("problem", ["unknown_id", "duplicate", "non_choice", "overwrite", "change_count", "rewrite_answer"])
def test_pool_authoring_rejects_unrelated_or_destructive_changes(bank, problem):
    output = proposal(bank)
    row = output["proposals"][0]
    if problem == "unknown_id":
        row["question_id"] = "UNKNOWN"
    elif problem == "duplicate":
        output["proposals"].append(copy.deepcopy(row))
    elif problem == "non_choice":
        row["question_id"] = next(q["question_id"] for q in bank["questions"] if q["format"] not in ("mcq", "multi_select"))
    elif problem == "overwrite":
        next(q for q in bank["questions"] if q["question_id"] == row["question_id"])["option_pools"] = row["option_pools"]
    elif problem == "change_count":
        row["option_pools"][0]["select_count"] += 1
    else:
        row["answer"] = "Changed answer"
    with pytest.raises(SessionError):
        option_pools.apply(bank, output)


def test_no_eligible_question_skips_the_cli_call(bank, tmp_path, monkeypatch):
    bank["questions"] = [q for q in bank["questions"] if q["format"] not in ("mcq", "multi_select")]
    result, report, info = option_pools.write(bank, [], tmp_path / "missing.pdf", "lecture", [], tmp_path)
    assert result is bank and report["status"] == "skipped" and info is None
    assert option_pools.enabled("1.43") and not option_pools.enabled("1.42")
