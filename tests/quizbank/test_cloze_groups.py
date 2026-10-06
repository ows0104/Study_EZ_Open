"""Repeated c1 blanks must survive validation as separate answer positions."""

import json
from pathlib import Path

import pytest

from quizbank.validate import validate_bank, validate_dropping


@pytest.mark.parametrize("markers", [("c1", "c1"), ("c1", "c2")])
def test_cloze_groups_preserve_each_answer_position(markers):
    bank = json.loads((Path(__file__).parent / "fixtures" / "bank_261002_02.json").read_text(encoding="utf-8"))
    q = next(q for q in bank["questions"] if q["format"] == "cloze")
    q["question"] = "Omeprazole은 {{" + markers[0] + "}}의 {{" + markers[1] + "}}를 비가역적으로 억제한다."
    q["answer_units"] = ["벽세포", "H+/K+-ATPase"]
    qid = q["question_id"]
    assert not any(e.startswith(qid + ":") for e in validate_bank(bank, ["S1", "S2"])["errors"])
    cleaned, _ = validate_dropping(bank, ["S1", "S2"])
    kept = next(item for item in cleaned["questions"] if item["question_id"] == qid)
    assert kept["question"] == q["question"]
    assert kept["answer_units"] == q["answer_units"]

    q["answer_units"] = ["벽세포"]
    assert any(e.startswith(qid + ": cloze는") for e in validate_bank(bank, ["S1", "S2"])["errors"])
