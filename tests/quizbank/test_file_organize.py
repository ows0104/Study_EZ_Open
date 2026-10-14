import copy
import json
from pathlib import Path

import pytest

from quizbank import file_organize, organize
from quizbank.schema import without_retired
from quizbank.validate import validate_dropping
from studyez_llm.codex import SessionError


@pytest.fixture
def bank():
    data = json.loads((Path(__file__).parent / "fixtures/bank_261002_02.json").read_text(encoding="utf-8"))
    return without_retired(validate_dropping(data, ["S1", "S2"])[0])


def raw_table(bank):
    return "| question_id | concept_id |\n| --- | --- |\n" + "\n".join(
        f"| {q['question_id']} | {q['concept_id']} |" for q in bank["questions"])


def provider(bank):
    def run(prompt, **kwargs):
        assert not kwargs["blind"] and kwargs["schema"] == file_organize.WRITTEN
        assert "response.md" in prompt and "bank.schema.json" in prompt
        assert "CHATGPT_RESPONSE_DATA\nresponse.md" in prompt
        (kwargs["cwd"] / "bank.json").write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
        return {"text": '{"written":true}', "duration_ms": 1000, "cost_usd": None,
                "usage": {"input_tokens": 2, "cache_read_input_tokens": 1, "output_tokens": 3},
                "models": {"gpt-test": 3}, "session_id": "test-session"}
    return run


def test_large_web_bank_is_read_from_a_validated_file_without_reprinting(bank, tmp_path, monkeypatch):
    monkeypatch.setattr(file_organize.codex, "run", provider(bank))
    raw = raw_table(bank)
    prompt = organize.organizer_prompt(raw, {"title": "강의", "sources": [], "prompt_version": "1.31"})
    converted, info = file_organize.convert(raw, prompt, tmp_path)
    assert converted == bank
    assert info["input_tokens"] == 3 and info["session_id"] == "test-session"
    assert (tmp_path / "response.md").read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("change", ["missing", "added", "duplicate"])
def test_converter_cannot_drop_add_or_duplicate_authored_questions(bank, tmp_path, monkeypatch, change):
    altered = copy.deepcopy(bank)
    if change == "missing":
        altered["questions"].pop()
    else:
        q = copy.deepcopy(altered["questions"][0])
        if change == "added": q["question_id"] = "Q_EXTRA"
        altered["questions"].append(q)
    monkeypatch.setattr(file_organize.codex, "run", provider(altered))
    raw = raw_table(bank)
    with pytest.raises(SessionError, match="문항 ID"):
        file_organize.convert(raw, "\nCHATGPT_RESPONSE_DATA\nunused", tmp_path)


def test_other_tables_are_not_new_questions():
    assert file_organize.question_ids("| question_id | concept_id |\n| --- | --- |\n| Q001 | C001 |\n"
        "| question_id | options |\n| --- | --- |\n| Q999 | A: detail |") == {"Q001"}


def test_blank_line_between_question_rows_keeps_the_question_header():
    raw = "| question_id | concept_id |\n| --- | --- |\n| Q001 | C001 |\n\n| Q002 | C002 |\n"
    assert file_organize.question_ids(raw) == {"Q001", "Q002"}


def test_blank_line_does_not_make_choice_details_authored_questions():
    raw = "| question_id | concept_id |\n| --- | --- |\n| Q001 | C001 |\n\n" \
        "| question_id | options |\n| --- | --- |\n| Q999 | A: detail |"
    assert file_organize.question_ids(raw) == {"Q001"}
