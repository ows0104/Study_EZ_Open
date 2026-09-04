"""빈칸 카드 한 장 — 번호를 가르면 카드가 갈린다.

Anki 는 **번호 하나에 카드 한 장**을 만들고, 각 카드는 나머지 번호의 답을 앞면에
그대로 인쇄한다. `c1..c4` 로 나뉜 문장은 네 장이 되고 그 넷 모두 앞면에 답 셋이
적혀 있다. 관리자 지시(2026-09-04) — *"나는 clozed가 좋은데 한번에 보였으면 좋겠어."*

2026-09-04 에 `runs/` 의 cloze 64장을 세어 보니 **39장(61%)이 번호가 갈려 있었다.**
갈린 것 대부분이 한 축이었다(amastigote→promastigote→epimastigote→trypomastigote).
계약에 「같은 축은 같은 번호」가 적혀 있었는데도 그랬다 — **지침만으로는 안 막힌다.**

재현 검사는 그 전부터 **모든 빈칸이 함께 가려진 앞면**을 채점하고 있었다
(`reproduce.front_of`). 채점한 앞면과 실제로 구워지던 앞면이 달랐다는 뜻이다.
여기서 고정하는 것은 그 둘이 같다는 것이다.
"""

import genanki

import pdf2anki.build as B
from pdf2anki.reproduce import front_of
from pdf2anki.textutil import collapse_cloze, norm_key

LID = "p260904_01"
Q = "편모충의 발육단계는 {{c1::amastigote}} → {{c2::promastigote}} → {{c3::epimastigote}} 순이다"


def test_번호가_갈려_있어도_전부_c1_로_모인다():
    assert collapse_cloze(Q).count("{{c1::") == 3
    assert "{{c2::" not in collapse_cloze(Q)


def test_빈칸_수는_줄지_않는다():
    """번호를 지우는 것이지 가린 자리를 지우는 것이 아니다 — `too_many_clozes` 가 그 수를 센다."""
    assert collapse_cloze(Q).count("::") == Q.count("::")


def test_힌트는_살아남는다():
    q = "정답은 {{c2::EGFR::수용체}} 다"
    assert collapse_cloze(q) == "정답은 {{c1::EGFR::수용체}} 다"


def test_빈칸이_없는_문장은_그대로다():
    q = "c1 은 경추 첫째 마디다"
    assert collapse_cloze(q) == q


def test_이미_c1_뿐인_문장은_바뀌지_않는다():
    """대부분의 카드가 여기 해당한다. 바뀌지 않아야 guid 도 흔들리지 않는다."""
    q = "발육단계는 {{c1::amastigote}} 와 {{c1::promastigote}} 다"
    assert collapse_cloze(q) == q


def test_guid_는_모은_뒤에도_그대로다():
    """굽는 자리에서만 모으므로 씨앗은 모델이 낸 글자 그대로다.

    이것이 깨지면 이미 임포트한 덱 위에 덮을 때 노트가 새로 생기고 **복습 이력이 날아간다.**
    """
    card = {"card_format": "cloze", "q": Q}
    before = B.guid_of(LID, norm_key(Q), card)
    after = B.guid_of(LID, norm_key(Q), card)
    assert before == after
    # 모은 글자로 씨앗을 만들면 달라진다 — 그래서 씨앗에 넣지 않는다.
    assert B.guid_of(LID, norm_key(collapse_cloze(Q)), card) != before


def test_구워진_앞면과_재현이_채점한_앞면이_같다():
    """`front_of` 는 번호와 무관하게 전부 가린다. 굽는 쪽이 c1 하나로 모여야 둘이 맞는다."""
    field = collapse_cloze(Q)
    assert field.count("{{c1::") == front_of({"card_format": "cloze", "q": Q}).count("[...]")


def test_노트가_카드_한_장으로_구워진다():
    """genanki 가 번호대로 카드를 만든다. 모으기 전에는 세 장이었다."""
    def cards(q):
        note = genanki.Note(model=B.CLOZE_MODEL, guid="g", tags=[],
                            fields=[q, "", "", "", ""])
        return len(note.cards)

    assert cards(Q) == 3
    assert cards(collapse_cloze(Q)) == 1
