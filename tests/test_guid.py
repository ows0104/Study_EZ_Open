"""노트 guid — 어느 카드가 어느 카드와 같은가.

Anki 는 guid 로 노트의 정체를 잡는다. 두 카드의 guid 가 같으면 **나중 것을 기존 노트의
수정으로 처리한다.** 덱에 한 장이 조용히 사라지는 것으로만 드러나고, 카드 수를 세지
않으면 알 수 없다. 실제로 28강에서 4장이 그러고 있었다.

반대로 guid 가 흔들리면 이미 임포트한 덱 위에 덮을 때 노트가 통째로 새로 생긴다.
그래서 **바뀌어야 할 때만 바뀌는 것**을 여기 고정해 둔다.
"""

import genanki
import pytest

from pdf2anki.build import GuidClash, check_guids, guid_of
from pdf2anki.prequiz.build import guid_seed
from pdf2anki.textutil import norm_key

LID = "p260821_02"
Q = "이 육안 소견은 어떤 종류의 경색이며, 조직의 성상은 어떠해야 하는가"


def image(fid, crop=None, occ=None, fmt="image_basic", q=Q):
    c = {"card_format": fmt, "q": q, "media": {"figure_id": fid}}
    if crop:
        c["media"]["crop"] = crop
    if occ:
        c["media"]["occlusion_ids"] = occ
    return c


def text(q=Q, fmt="basic"):
    return {"card_format": fmt, "q": q}


# ── 이미지 카드: 그림이 다르면 다른 카드다 ──────────────────────

def test_질문이_같아도_그림이_다르면_guid_가_다르다():
    """이게 안 지켜지면 한 장이 다른 장을 덮는다. 이 저장소에서 실제로 일어난 일이다."""
    a = guid_of(LID, norm_key(Q), image("fig_p32_01"))
    b = guid_of(LID, norm_key(Q), image("fig_p32_02"))
    assert a != b


def test_같은_그림을_다르게_자르면_다른_카드다():
    a = guid_of(LID, norm_key(Q), image("fig_p12_01", crop=[0, 0, 0.72, 1]))
    b = guid_of(LID, norm_key(Q), image("fig_p12_01", crop=[0.28, 0, 1, 1]))
    assert a != b


def test_가린_상자가_다르면_다른_카드다():
    a = guid_of(LID, Q, image("fig_p05_01", occ=["occ_1"], fmt="image_occlusion"))
    b = guid_of(LID, Q, image("fig_p05_01", occ=["occ_2"], fmt="image_occlusion"))
    assert a != b


def test_가린_상자_순서는_정체를_바꾸지_않는다():
    a = guid_of(LID, Q, image("f", occ=["occ_1", "occ_2"], fmt="image_occlusion"))
    b = guid_of(LID, Q, image("f", occ=["occ_2", "occ_1"], fmt="image_occlusion"))
    assert a == b


def test_같은_그림_같은_크롭_같은_질문이면_같은_카드다():
    """그림까지 같으면 그건 정말로 중복이다. 접히는 것이 맞다."""
    a = guid_of(LID, norm_key(Q), image("fig_p32_01"))
    b = guid_of(LID, norm_key(Q), image("fig_p32_01"))
    assert a == b


# ── 텍스트 카드: 예전 값 그대로여야 한다 ────────────────────────

@pytest.mark.parametrize("fmt", ["basic", "ox", "cloze"])
def test_그림이_없으면_씨앗을_건드리지_않는다(fmt):
    """빈 문자열이라도 덧붙이면 텍스트 카드 **전부**의 guid 가 바뀐다.

    `genanki.guid_for` 는 인자를 `__` 로 이어 해싱하므로 빈 인자도 해시를 바꾼다.
    """
    assert guid_of(LID, norm_key(Q), text(fmt=fmt)) == genanki.guid_for(LID, norm_key(Q))


def test_media_키가_비어_있어도_텍스트_카드로_본다():
    c = {"card_format": "basic", "q": Q, "media": None}
    assert guid_of(LID, norm_key(Q), c) == genanki.guid_for(LID, norm_key(Q))


# ── 예습과 복습은 여전히 갈린다 ─────────────────────────────────

def test_예습과_복습은_같은_그림을_물어도_안_섞인다():
    c = image("fig_p32_01")
    assert guid_of(LID, norm_key(Q), c) != guid_of(guid_seed(LID), norm_key(Q), c)


# ── 겹쳤을 때 조용하지 않은가 ──────────────────────────────────
#
# 씨앗을 아무리 촘촘히 해도 겹칠 수 있는 카드는 언제든 나온다. 씨앗을 늘리는 것과
# 별개로, 겹쳤을 때 **덱이 그냥 만들어지지 않는 것**이 마지막 방어선이다.

def card(q, a, fmt="basic", media=None):
    return {"card_format": fmt, "q": q, "a": a, "media": media}


def test_내용이_다른데_guid_가_겹치면_덱을_만들지_않는다():
    cards = [card("같은 질문", "답 하나"), card("같은 질문", "답 둘")]
    with pytest.raises(GuidClash) as e:
        check_guids(cards, LID)
    assert "조용히 사라진다" in str(e.value)
    assert "답 하나" in str(e.value) and "답 둘" in str(e.value)


def test_질문_답_그림이_전부_같으면_접는다():
    """이건 정말 중복이다. 접히는 것이 맞고, 몇 장을 접었는지 보고한다."""
    kept, folded = check_guids([card("q", "a"), card("q", "a"), card("다른 q", "a")], LID)
    assert len(kept) == 2 and folded == 1


def test_겹치지_않으면_그대로_통과한다():
    cards = [card("q1", "a"), card("q2", "a"), image("fig_1"), image("fig_2")]
    kept, folded = check_guids(cards, LID)
    assert len(kept) == 4 and folded == 0


def test_그림이_다르면_같은_질문이어도_통과한다():
    """이 저장소에서 실제로 사라지던 네 쌍이 이 모양이었다."""
    kept, folded = check_guids([image("fig_p32_01"), image("fig_p32_02")], LID)
    assert len(kept) == 2 and folded == 0
