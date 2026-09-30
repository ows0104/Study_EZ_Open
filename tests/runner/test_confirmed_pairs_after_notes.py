"""사람이 확인한 작년 짝은 올해 필기가 올라온 뒤에도 짝이다.

2026-09-30 까지 `_pairs` 는 올해 필기가 없는 칸에만 먹었다(`ahead.plan`). 필기가
올라오면 자동 짝으로 바뀌어서, 약리학 「약물의 이해 소개(조정현)」가 작년
「약리학 소개(예상규)」를 잃고 사이트에 작년 필기가 안 붙었다. 아래 파일명은
그 꼴을 본떠 지어낸 것이다.
"""

from pathlib import Path

from runner import filenames, matching

THIS = [
    "[260929_01] 약물의 이해 소개(가나다)_라마바v1.pdf",
    "[260929_02] 약동학(1) 약물의 흡수와 분포(ADME) (사아자)_라마바v1.pdf",
]
PREV = [
    "[250926_01]약리학 소개(차카타)_파하가v1.pdf",
    "[250926_02]약동학(1) 약물의 흡수와 분포(차카타)_파하가v1.pdf",
    "[250929_01]약동학(3) 약물요법에의 통합적 적용 (차카타)_파하가v1.pdf",
]


def files(names):
    return [filenames.parse(Path(n)) for n in names]


def by_this(matches):
    return {m.this_year.key: (m.prev_year.key if m.prev_year else None, m.confident)
            for m in matches}


def test_적어_둔_짝이_자동_짝보다_먼저다():
    got = by_this(matching.match_with_confirmed(
        files(THIS), files(PREV), {"260929_01": "250926_01", "_주석": "무시"}))
    assert got["260929_01"] == ("250926_01", True)
    # 적지 않은 편은 전처럼 자동으로 붙는다
    assert got["260929_02"][0] == "250926_02"


def test_적은_짝은_자동_짝의_후보에서_빠진다():
    """한 작년 편이 두 올해 편에 붙으면 안 된다."""
    got = by_this(matching.match_with_confirmed(
        files(THIS), files(PREV), {"260929_02": "250929_01"}))
    assert got["260929_02"] == ("250929_01", True)
    assert got["260929_01"][0] != "250929_01"


def test_없는_작년_편을_적었으면_자동으로_물러난다():
    got = by_this(matching.match_with_confirmed(files(THIS), files(PREV), {"260929_02": "250101_01"}))
    assert got["260929_02"][0] == "250926_02"


def test_적은_것이_없으면_match_years_와_같다():
    a = by_this(matching.match_with_confirmed(files(THIS), files(PREV), {}))
    b = by_this(matching.match_years(files(THIS), files(PREV)))
    assert a == b
