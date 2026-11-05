import copy
import json

import pytest

from scripts import incremental_comparison as comparison


def test_usage_metrics_count_zero_time_cache_hits_without_counting_model_calls(tmp_path):
    folder = tmp_path / "runs/L1/bank/build"
    folder.mkdir(parents=True)
    rows = [{"step": "外部", "seconds": 12, "models": ["gpt-6.1-sol"]},
            {"step": "外部", "seconds": 0, "reused_questions": 30},
            {"step": "原本", "seconds": 20, "models": ["gpt-6.1-sol"]}]
    (folder / "usage.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    data = comparison.metrics(folder)
    assert data["cliSeconds"] == 32
    assert data["stageCalls"]["外部"] == 1 and data["stageDurations"]["外部"] == [12, 0]
    assert data["runId"] == "L1"


@pytest.mark.parametrize("broken", [None, "hash", "timestamp", "scope"])
def test_answer_reuse_audit_detects_broken_provenance(tmp_path, broken):
    first = {"stage": "answer", "checkedAt": "T0", "keys": {"Q1": "H1", "Q2": "H2"},
             "checkedQuestionIds": ["Q1", "Q2"], "reusedQuestionIds": [], "priorJudgments": {}}
    second = {"stage": "answer", "checkedAt": "T1", "keys": {"Q1": "H1", "Q2": "H2"},
              "checkedQuestionIds": [], "reusedQuestionIds": ["Q1", "Q2"],
              "priorJudgments": {"Q1": "T0", "Q2": "T0"}}
    if broken == "hash":
        second["keys"]["Q2"] = "Changed"
    elif broken == "timestamp":
        second["priorJudgments"]["Q2"] = "Unattested"
    elif broken == "scope":
        second["checkedQuestionIds"] = ["Q2"]
    result = comparison.quality_checks(tmp_path, [first, second])
    assert result["independentAnswerReuseMatchesPriorHashAndTime"] == (broken not in ("hash", "timestamp"))
    assert result["scopeIdsDisjointAndComplete"] == (broken != "scope")


def test_global_checks_must_be_present_for_every_answer_round(tmp_path):
    source = {"stage": "source", "checkedAt": "T0", "keys": {}, "checkedQuestionIds": [],
              "reusedQuestionIds": [], "priorJudgments": {}, "globalSourceCheck": True}
    answer = {**copy.deepcopy(source), "stage": "answer"}
    data = comparison.quality_checks(tmp_path, [source, answer, answer])
    assert not data["globalSourceCheckEveryRound"]
