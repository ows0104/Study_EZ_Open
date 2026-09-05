"""빈칸의 셋째 칸(힌트)은 누출이 아니다.

`{{c1::답::갈림}}` 의 셋째 칸은 Anki 가 앞면에 보여 주는 힌트다. 갈림을 보이는 힌트는
**정의상 답을 품는다** — `{{c1::이체::동체/이체}}`. 그것을 누출로 세면 의도한 카드가
hard 로 사라진다.

2026-09-06 에 관리자가 이 꼴을 손으로 그려 왔을 때 발견했다. 코드·웹 렌더·Anki 는
이미 셋째 칸을 다루고 있었는데 계약에만 없어서 모델이 쓸 줄 몰랐고, 막상 쓰면
`cloze_unmasked` 가 지웠다. **짧은 답으로 시험하면 안 보인다** — 문턱이 4글자다.
"""

from pdf2anki.reproduce import front_of, leaks
from pdf2anki.textutil import collapse_cloze
from studyez.deck import plain_stem


def _card(q):
    return {"id": "c001", "card_format": "cloze", "q": q, "a": "답", "explanation": ""}


def _unmasked(q):
    return [l for l in leaks("", [_card(q)]) if l["kind"] == "cloze_unmasked"]


def test_갈림_힌트는_누출이_아니다():
    # 답(사상유충)이 힌트 안에 그대로 있지만 문장 본문에는 없다.
    assert not _unmasked("감염형은 {{c1::사상유충::간상유충/사상유충}}이다")


def test_짧은_답으로는_이_버그가_안_보인다():
    # 문턱이 4글자라 「이체」로 시험하면 고치기 전에도 통과했다.
    assert not _unmasked("자웅{{c1::이체::동체/이체}}이다")


def test_본문에_맨몸으로_또_있으면_여전히_잡는다():
    assert _unmasked("감염형은 {{c1::사상유충}}이며 사상유충을 먹어 감염된다")


def test_힌트는_앞면에만_보이고_답은_안_보인다():
    q = "자웅{{c1::이체::동체/이체}}이다"
    assert front_of(_card(q)) == "자웅[...|동체/이체]이다"
    assert plain_stem(_card(q)) == "자웅[동체/이체]이다"


def test_번호를_모아도_힌트가_살아남는다():
    # 굽는 직전 `collapse_cloze` 가 번호만 c1 로 모은다. 셋째 칸은 건드리지 않는다.
    assert collapse_cloze("수컷{{c2::<::>/<}}암컷") == "수컷{{c1::<::>/<}}암컷"
