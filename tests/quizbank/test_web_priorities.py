import pytest

from quizbank import web_priorities
from quizbank.session import SessionError


def test_original_web_labels_are_read_from_three_historical_formats():
    raw = '''
| question_id | tier | importance | question |
| --- | --- | --- | --- |
| Q001 | Core | 5 | original table goal |

### Q002
- tier: Optional
- importance: 2
- question: original field goal

### Q003 | basic | Advanced | 3 | 2 | direct
문제: original compact goal
정답: ["A"]
'''
    rows = web_priorities.read(raw)
    assert [(r["question_id"], r["tier"], r["importance"], r["question"]) for r in rows] == [
        ("Q001", "Core", 5, "original table goal"),
        ("Q002", "Optional", 2, "original field goal"),
        ("Q003", "Advanced", 3, "original compact goal")]


def test_concept_and_detail_tables_do_not_replace_question_metadata():
    raw = '''
| concept_id | tier | importance | title |
| --- | --- | --- | --- |
| C01 | Core | 5 | concept |

| question_id | option_id | explanation |
| --- | --- | --- |
| Q001 | A | explanation |
'''
    assert web_priorities.read(raw) == []


@pytest.mark.parametrize("suffix", ["", "\n- importance: 9"])
def test_partial_or_invalid_metadata_is_not_silently_guessed(suffix):
    with pytest.raises(SessionError):
        web_priorities.read("### Q001\n- tier: Core" + suffix)


def test_repeated_identical_paste_is_deduplicated_but_conflicts_are_retained():
    raw = "### Q001\n- tier: Core\n- importance: 5\n- question: original\n"
    assert len(web_priorities.read(raw + raw)) == 1
    conflict = raw + raw.replace("importance: 5", "importance: 2")
    assert len(web_priorities.candidates(conflict)) == 2
    with pytest.raises(SessionError, match="중복"):
        web_priorities.read(conflict)


def test_saved_json_is_identified_as_an_export_not_as_web_markdown():
    rows = web_priorities.read('prefix\n{"questions":[{"question_id":"Q1","question":"goal","tier":"Core","importance":4}]}')
    assert rows[0]["origin"] == "saved_json"


def test_malformed_later_columns_never_shift_question_text_into_metadata():
    raw = '''
| question_id | concept_id | tier | importance | format | retrieval_direction | question |
| --- | --- | --- | --- | --- | --- | --- |
| X-Q1 | C1 | Core | 5 | direct | missing format |
'''
    row = web_priorities.read(raw)[0]
    assert row["tier"] == "Core" and row["importance"] == 5
    assert row["question"] == "" and row["origin"] == "web_table_metadata_only"


def test_unreadable_original_metadata_is_reported_without_blocking_source_audit():
    ref = web_priorities.reference("### Q001\n- tier: Core")
    assert ref["status"] == "unavailable" and ref["reason"] and not ref["candidates"]
    ref = web_priorities.reference("### Q001\n- tier: Core\n- importance: 4")
    assert ref["status"] == "available" and ref["candidates"][0]["importance"] == 4
