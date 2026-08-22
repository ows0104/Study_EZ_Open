"""예습 설명본 받아오기.

ChatGPT 공유 링크 같은 최신 Next.js(App Router) 페이지는 본문을 DOM 이 아니라
`<script>` 안 RSC 페이로드에 담고, 그 안에서 **JSON 이 두 겹 이스케이프**돼 있다.
실제 링크에서 DOM 파서는 24자만 건졌고 페이로드 파서는 13,986자를 건졌다.

형식이 바뀌면 이 코드는 예외를 던지지 않고 **조용히 짧은 글을 돌려준다.**
그래서 여기에 묶는다. 아래 페이로드는 실제 응답의 구조만 본뜬 것이다.
"""

import json

import pytest

from pdf2anki.prequiz.run import _Text, from_rsc


def _payload(text: str) -> str:
    """실제 페이지의 감싸기를 흉내낸다 — JSON 을 JSON 에 담고, 다시 HTML 안 JS 문자열로."""
    inner = json.dumps(text)[1:-1]              # 한 겹: 줄바꿈이 \n 이 된다
    doubled = json.dumps(inner)[1:-1]           # 두 겹: 그 역슬래시가 다시 이스케이프된다
    return ('<!DOCTYPE html><html><body><div id="root"></div>'
            '<script>self.__next_f.push([1,"' + doubled.replace('"', '\\"') + '"])</script>'
            '</body></html>')


PROSE = ("이 강의는 암세포가 왜 정상적인 성장 조절에서 벗어나는가를 설명합니다.\n"
         "\n"
         "# 1. 큰 그림\n"
         "\n"
         "정상세포에 손상이 쌓이고 살아남은 세포가 증식하면서 여러 subclone 이 생깁니다.\n"
         "즉 mutation 이 쌓여 clonal evolution 으로 이어지는 흐름입니다.\n")


def test_DOM_파서는_이런_페이지에서_거의_못_건진다():
    """이것이 실패 모드다 — 예외가 아니라 짧은 글이 돌아온다."""
    p = _Text()
    p.feed(_payload(PROSE))
    assert len("".join(p.out).strip()) < 60


def test_페이로드에서_본문을_건진다():
    got = from_rsc(_payload(PROSE))
    assert "clonal evolution" in got
    assert "암세포가 왜 정상적인 성장 조절에서" in got


def test_줄바꿈이_실제_줄바꿈으로_풀린다():
    """두 겹을 다 안 풀면 모델이 한 줄짜리 글을 읽는다."""
    got = from_rsc(_payload(PROSE))
    assert "\\n" not in got
    assert got.count("\n") >= 4
    assert "# 1. 큰 그림" in got


def test_인용_표식만_떼고_사이의_본문은_남긴다():
    """표식 사이를 걸치는 정규식으로 지우면 본문이 통째로 사라진다 —
    실제로 15,475자가 4,520자로 줄었던 자리다."""
    cited = ("첫 문단입니다. 여기에 충분한 한글이 들어 있습니다.fileciteturn0file0\n"
             "\n가운데 문단은 반드시 살아남아야 합니다. 이 문장이 사라지면 회귀다.\n"
             "\n마지막 문단입니다.fileciteturn0file1")
    got = from_rsc(_payload(cited))
    assert "가운데 문단은 반드시 살아남아야 합니다" in got
    assert "filecite" not in got
    assert "turn0file0" not in got
    assert "" not in got


def test_짧은_UI_라벨은_줍지_않는다():
    got = from_rsc(_payload("확인") + _payload("취소"))
    assert got == ""


@pytest.mark.parametrize("dup", [1, 2, 3])
def test_같은_덩어리가_여러_번_실려도_한_번만_줍는다(dup):
    """페이로드는 문자열을 인터닝해 같은 글이 여러 번 나타난다."""
    got = from_rsc(_payload(PROSE) * dup)
    assert got.count("# 1. 큰 그림") == 1
