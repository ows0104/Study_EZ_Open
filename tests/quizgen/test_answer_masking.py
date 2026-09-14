"""앞면 크롭에 인쇄된 정답을 가린다. 무엇을 가릴지는 **그 카드의 정답**이 정한다."""

from quizgen.textutil import answer_runs


def test_caption_matching_the_answer_is_a_run():
    assert answer_runs(["Plasma", "cell"], "형질세포(plasma cell)") == [(0, 2)]


def test_case_and_bracket_differences_do_not_matter():
    assert answer_runs(["KERATIN", "pearl"], "keratin-pearl") == [(0, 2)]


def test_the_word_may_be_wider_than_the_answer():
    """그림은 복수형으로 적는 일이 잦다. 한 방향만 보면 가림과 누출 판정이 어긋난다."""
    assert answer_runs(["Neurofibromas", "Lisch", "nodules"], "Neurofibroma") == [(0, 1)]
    assert answer_runs(["Lipoblasts"], "Lipoblast") == [(0, 1)]


def test_a_short_incidental_overlap_is_left_alone():
    """`cell` 은 정답의 일부이면서 그림 여기저기에 있다. 덜 가리는 쪽이 낫다."""
    assert answer_runs(["some", "cell", "here"], "Plasma cell") == []


def test_unrelated_words_are_never_masked():
    assert answer_runs(["Lisch", "nodule"], "Neurofibroma") == []
    assert answer_runs([], "Plasma cell") == []
    assert answer_runs(["Plasma"], "") == []


def test_runs_do_not_overlap():
    runs = answer_runs(["Keratin", "pearl", "Keratin", "pearl"], "Keratin pearl")
    assert runs == [(0, 2), (2, 4)]
