"""질문이 「지금 눈앞에 있는 것」을 가리키는데 그것이 카드에 없는 자리.

이 카드는 **아예 못 푼다.** 그런데 재현 검사가 이것을 못 막는다 — 그림이 필요한
카드는 검사를 건너뛰는데(`reproduce.status = skipped`), 이 카드들은 이미지 형식이
아니라서 텍스트로 검사를 받고 그대로 통과한다. `CLAUDE.md`가 `260821_05`의 그런
카드 한 장을 「빌드를 지나갔다」고 적어 둔 자리다.

2026-08-29에 낱말을 넓히고 동시에 조였다. 실측(이미지가 안 붙은 카드 3,660장):

    원래        13장
    넓힌 뒤     18장   「이 실습」·「사진에서」·「이 증례」가 새로 걸린다
    조인 뒤     14장   그중 4장이 「이 표지자」·「이 표적」·「이 표시」 오탐이었다
"""

import pytest

from quizgen.validate import RE_POINTS_AT_SOURCE as POINTS


def fires(q: str) -> bool:
    return bool(POINTS.search(q))


# ------------------------------------------------ 가리키면 잡는다

@pytest.mark.parametrize("q", [
    "이 실습은 장기마다 양성 표본과 악성 표본을 한 쌍씩 놓았다. 다섯 쌍은 각각 무엇인가?",
    "이 실습의 mixed tumor 표본은 어느 장기의 것인가?",
    "이 증례의 NGS에서 최종 확인된 fusion은?",
    "조직 사진에서 epithelial 성분을 어떻게 구분하는가?",
    "악성종양의 특성을 묻는 사진 문항에서 invasion은 무엇을 보고 고르는가?",
    "이 사진이 보여 주는 급성 염증의 양상은?",
    "이 표본에서 관찰된 것은 무엇인가?",
    "이 슬라이드가 든 예 셋은?",
])
def test_눈앞의_것을_가리키면_잡는다(q):
    assert fires(q)


@pytest.mark.parametrize("q", [
    "이 그림에서 화살표가 가리키는 것은?",
    "위 표에 따르면 생존율은 얼마인가?",
    "이 표는 무엇을 정리한 것인가?",
    "강의록이 든 유일한 예외는 무엇인가?",
])
def test_예전부터_잡던_것도_그대로_잡는다(q):
    assert fires(q)


# ------------------------------------------------ 「이 표」로 오인하지 않는다

@pytest.mark.parametrize("q", [
    "자궁경부 병변 진단에서 p16 면역조직화학이 표지자로 쓰이는 이유는?",
    "Pan-cancer Panel이 표적으로 삼는 것은?",
    "한쪽에 결실이 표시되어 있다면 어떤 질환인가?",
])
def test_표지자_표적_표시는_표가_아니다(q):
    """`표` 뒤에 조사가 와야 「그 표」다. 안 조이면 이 셋이 전부 걸린다."""
    assert not fires(q)


@pytest.mark.parametrize("q", [
    "급성 염증의 형태학적 양상 네 가지는?",
    "Marfan 증후군의 원인 유전자는?",
    "high risk HPV의 대표 type은?",
])
def test_평범한_문항은_안_걸린다(q):
    assert not fires(q)


# ------------------------------------------------ 이미지 카드는 가리켜도 된다

def test_이미지_카드는_이_검사를_안_받는다():
    """`validate`가 `card_format in IMAGE_FORMATS`면 건너뛴다.

    실측으로 이미지 카드 98장이 이 낱말에 걸리는데, 그림이 붙어 있으니 정상이다.
    검사를 형식으로 거르지 않으면 그 98장이 전부 거짓 신호가 된다.
    """
    from quizgen.schema import IMAGE_FORMATS
    assert "image_basic" in IMAGE_FORMATS and "image_occlusion" in IMAGE_FORMATS
    assert fires("이 사진이 보여 주는 양상은?")      # 낱말 자체는 걸린다


def test_예습도_같은_규칙을_쓴다():
    """규칙이 갈라지면 한쪽만 고쳐진다."""
    from quizgen.prequiz import validate as pre
    assert pre.RE_POINTS_AT_SOURCE is POINTS
