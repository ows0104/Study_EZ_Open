"""옛 문항의 표시만 제거하며 질문·cloze·강조는 보존한다."""
import pytest

from quizgen.textutil import strip_prequiz_label


@pytest.mark.parametrize("label", [
    "[선택 도전] ", "[선택도전]: ", "［선택 도전］： ",
    "**[선택 도전]** ", "선택 도전: ", "**선택 도전:** ",
])
def test_old_challenge_labels_are_removed(label):
    question = "조건이 바뀌면 **결과**가 어떻게 달라지는가?"
    assert strip_prequiz_label(label + question) == question


def test_label_removal_preserves_cloze_and_ordinary_brackets():
    question = "[조건 A]에서는 {{c1::감소}}한다."
    assert strip_prequiz_label("[선택 도전] " + question) == question
    assert strip_prequiz_label(question) == question


def test_bracket_label_is_removed_after_a_number():
    assert strip_prequiz_label("10. [선택 도전] 결과는?") == "10. 결과는?"
