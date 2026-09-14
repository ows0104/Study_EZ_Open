"""답의 강조. **무엇을 강조할지는 모델이 정하고 코드는 보여 주기만 한다.**"""

from quizgen.build import render_answer


def test_unmarked_answer_is_untouched():
    """표시가 없으면 예전 모양 그대로다 — `.a` 가 통째로 한 색이다."""
    out = render_answer("10% buffered formalin에 24시간")
    assert out == "10% buffered formalin에 24시간"
    assert "body" not in out and "key" not in out


def test_marks_become_the_only_colored_part():
    out = render_answer("공격하는 쪽은 **graft의 T cell**, 받는 쪽은 host다")
    assert '<span class="body">' in out
    assert '<b class="key">graft의 T cell</b>' in out
    assert "**" not in out


def test_marks_work_inside_a_list_item():
    out = render_answer("- 세포: **smooth muscle cell**과 macrophage\n- 층: intimal layer")
    assert '<div class="body">' in out
    assert '<b class="key">smooth muscle cell</b>' in out


def test_lead_line_can_carry_marks():
    out = render_answer("**세 단계**로 나뉜다\n- 하나: a\n- 둘: b")
    assert '<div class="lead"><b class="key">세 단계</b>로 나뉜다</div>' in out


def test_code_never_picks_a_word_on_its_own():
    """`핵심어: 설명` 꼴이어도 코드는 아무것도 고르지 않는다.

    한동안 콜론 앞을 기계적으로 들었는데, 그 자리가 회수 대상이 아니라 질문의 축인
    항목이 있었다 — `세포:` 를 칠하면 정답이 검게 내려간다. 틀린 강조는 강조 없음보다
    나쁘므로 그 추측을 버렸다.
    """
    out = render_answer("- 세포: 평활근세포와 대식세포\n- 층: 대동맥의 내막")
    assert "key" not in out and "body" not in out
    assert out.startswith("<ul>")


def test_list_structure_survives_without_marks():
    out = render_answer("- 수세(washing)\n- 탈수(dehydration)\n- 투명(clearing)")
    assert out.startswith("<ul>") and out.count("<li>") == 3


def test_html_in_the_answer_is_still_escaped():
    out = render_answer("**a<b>** & <script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out and "a&lt;b&gt;" in out
