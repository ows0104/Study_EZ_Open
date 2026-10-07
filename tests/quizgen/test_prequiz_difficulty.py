"""새 난도는 생성·검증·웹 전달·Anki에서 유지하고, 기존 문항은 미분류로 둔다."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from quizgen.prequiz.build import tags_of, why_of
from quizgen.prequiz.schema import CARD_SCHEMA, GENERATE_SCHEMA
from quizgen.prequiz.validate import validate
from runner.deck import _web_items


def cards():
    return [{"q": f"개념 {i}의 역할은?", "a": f"역할{i}", "card_format": "basic",
             "card_type": "term", "reason": "vocabulary", "source_type": "note",
             "evidence_type": "preview_note", "explanation": "수업의 기전을 이해한다",
             "why_asked": "기전을 설명할 때 쓰는 용어다", "why_tags": ["basis"],
             "challenge": i >= 8, "learning_support": {
                 "difficulty": "basic" if i < 5 else "advanced" if i < 8 else "challenge",
                 "hint": "역할의 방향을 생각해 보자", "scope": "개념의 역할 하나",
                 "lecture_focus": "기전에서 맡는 역할", "preview_excerpt": ""}}
            for i in range(10)]


def check(rows):
    return validate({"cards": deepcopy(rows)}, {"slides": 1, "pages": []}, None)


def test_three_levels_and_non_fixed_ratio():
    rows = cards()
    assert check(rows)[1]["difficulty_mix"] == {"basic": 5, "advanced": 3, "challenge": 2}
    rows[4]["learning_support"]["difficulty"] = "advanced"
    kept, report = check(rows)
    assert not report["contract_violations"]
    assert report["difficulty_mix"] == {"basic": 4, "advanced": 4, "challenge": 2}
    assert not any("difficulty_challenge_mismatch" in c["review_flags"] for c in kept)


def test_new_generation_requires_difficulty_but_old_validation_remains_compatible():
    rows = cards()
    assert not list(Draft202012Validator(GENERATE_SCHEMA).iter_errors({"cards": rows}))
    for row in rows:
        del row["learning_support"]["difficulty"]
    assert list(Draft202012Validator(GENERATE_SCHEMA).iter_errors({"cards": rows}))
    assert not list(Draft202012Validator(CARD_SCHEMA).iter_errors(rows[0]))
    kept, report = check(rows)
    assert not report["contract_violations"]
    assert all("missing_difficulty" not in row["review_flags"] for row in kept)


def test_missing_level_or_inconsistent_challenge_requires_repair():
    rows = cards()
    rows[0]["challenge"] = True
    rows[9]["challenge"] = False
    del rows[1]["learning_support"]["difficulty"]
    kept, _ = check(rows)
    assert "difficulty_challenge_mismatch" in kept[0]["review_flags"]
    assert "difficulty_challenge_mismatch" in kept[9]["review_flags"]
    assert "missing_difficulty" in kept[1]["review_flags"]
    rows = cards()
    for row in rows[5:8]:
        row["learning_support"]["difficulty"] = "basic"
    assert any("심화" in issue for issue in check(rows)[1]["contract_violations"])


@pytest.mark.parametrize("level,label", [("basic", "기본"), ("advanced", "심화"), ("challenge", "도전")])
def test_difficulty_reaches_web_and_anki(level, label):
    row = cards()[0]
    row["learning_support"]["difficulty"] = level
    row["challenge"] = level == "challenge"
    assert _web_items([row])[0]["learning_support"]["difficulty"] == level
    assert f'<span class="tag {level}">{label}</span>' in why_of(row)
    assert "도전 문제" not in why_of(row)
    assert f"난도::{label}" in tags_of(row, "preview")
