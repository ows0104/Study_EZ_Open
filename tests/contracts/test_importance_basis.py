"""Importance from point evidence. Each case is an administrator judgment from 2026-11-08."""
import pytest
from studyez_contracts.bank import importance as imp

TIER = {"Must-Know": "Essential", "Core": "Core", "Important": "Important", "Optional": "Optional"}


def row(kind, year=None, quote=""):
    value = {"kind": kind, "reason": "synthetic", "quote": quote or ("교수: 시험에 낸다" if kind in imp.OVERRIDES else ""),
             "refs": [{"source_id": "S1", "pages": [4]}]}
    if year is not None:
        value["year"] = year
    return value


def tier(*rows, style="slide"):
    return imp.score(list(rows), style)["tier"]


@pytest.mark.parametrize("rows, expected", [
    ([row("slide_emphasis")], "Important"),
    ([row("clinical")], "Important"),
    ([row("structural")], "Important"),
    ([row("other_exam")], "Optional"),
    ([row("slide_emphasis"), row("clinical")], "Core"),
    ([row("slide_emphasis"), row("other_exam")], "Core"),
    ([row("learning_objective")], "Core"),
    ([row("current_exam", 2023)], "Core"),
    ([row("current_exam", 2021), row("current_exam", 2024)], "Must-Know"),
    ([row("learning_objective"), row("current_exam", 2023), row("slide_emphasis")], "Must-Know"),
    ([row("learning_objective"), row("slide_emphasis")], "Core"),
    ([row("learning_objective"), row("current_exam", 2023)], "Core"),
    ([row("current_exam", 2023), row("clinical"), row("structural")], "Must-Know"),
    ([row("writer_mark")], "Important"),
    ([row("slide_emphasis"), row("writer_mark")], "Important"),
    ([row("writer_mark"), row("writer_stamp")], "Important"),
    ([row("writer_mark"), row("clinical")], "Important"),
    ([row("slide_emphasis"), row("professor_remark")], "Core"),
    ([row("writer_stamp")], "Optional"),
    ([], "Optional"),
])
def test_administrator_judgments(rows, expected):
    assert tier(*rows) == TIER[expected]


def test_verbal_professor_counts_writer_marks_like_slide_emphasis():
    assert tier(row("writer_mark"), row("clinical"), style="verbal") == "Core"


def test_forecast_is_must_know_and_exclusion_overrides_everything():
    assert tier(row("exam_forecast")) == "Essential"
    assert tier(row("exam_forecast"), row("exam_exclusion"), row("current_exam", 2023)) == "Optional"
    with pytest.raises(imp.ImportanceError):
        imp.score([{**row("exam_forecast"), "quote": " "}])


def test_same_kind_counts_once_but_exam_years_each():
    assert imp.score([row("clinical"), row("clinical")])["score"] == 1.0
    assert imp.score([row("current_exam", 2023), row("current_exam", 2023)])["score"] == 2.0


def test_bank_importance_follows_the_new_scale():
    assert imp.BANK_IMPORTANCE == {"Essential": 5, "Core": 4, "Important": 3, "Optional": 2}


def table():
    points = [{"point_id": "P001", "importance_basis": [row("slide_emphasis")]},
              {"point_id": "P002", "importance_basis": [row("exam_forecast", quote="이건 시험에 내기 좋겠죠?")]},
              {"point_id": "P003", "importance_basis": [row("exam_exclusion", quote="이거는 시험에 안 나온다")]}]
    return points, imp.point_table(points, {"emphasis_style": "slide"})


def test_question_takes_its_highest_point_and_targets_get_all_three_axes():
    points, t = table()
    assert imp.question_decision(t, ["P001", "P002"]) == {"tier": "Essential", "importance": 5}
    with pytest.raises(imp.ImportanceError):
        imp.question_decision(t, ["P999"])
    axes = imp.target_axes(t, ["P001", "P002"])
    assert axes["exam"]["status"] == "supported" and {e["kind"] for e in axes["exam"]["evidence"]} == {"teaching_emphasis", "exam_forecast"}
    assert axes["clinical"]["status"] == axes["structural"]["status"] == "insufficient"
    assert imp.target_axes(t, ["P003"])["exam"]["status"] == "insufficient"
    assert all(a["status"] != "unreviewed" for a in axes.values())


def test_must_know_share_warns_above_the_live_p90_and_spread_is_reported():
    share, warn = imp.must_know_share([{"tier": "Essential"}] * 4 + [{"tier": "Core"}] * 6)
    assert share == 0.4 and warn
    assert imp.must_know_share([{"tier": "Essential"}] + [{"tier": "Core"}] * 9)[1] == []
    points, _t = table()
    assert imp.forecast_spread(points) == {"이건 시험에 내기 좋겠죠?": ["P002"]}
