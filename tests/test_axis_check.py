"""축 검사 — 「빈칸이 무엇을 묻는지 알 수 있는가」.

재현 검사는 「답이 뭐냐」를 묻는데, `cloze` 는 앞면에 문장이 있어서 **나쁜 빈칸일수록
잘 통과한다.** 2026-09-06 `260901_01` v6 에서 관리자가 「별로」라고 판정한 카드가
재현·검증·soft flag 를 전부 깨끗이 지났다. 그래서 다른 것을 묻는 세션을 따로 뒀다.

여기서 시험하는 것은 **배선**이다 — 빈 세션의 판정 자체는 못 시험한다.
"""

import json

from pdf2anki.build import AXIS_REASON, DEFECT_REASONS, REPAIR_REASONS
from pdf2anki.reproduce import build_axis, mark_axis, numbered_front


def _cloze(cid, q):
    return {"id": cid, "card_format": "cloze", "q": q, "a": "답"}


def _write(d, axes, cards):
    (d / "reproduce.axis.json").write_text(json.dumps({"axes": axes}, ensure_ascii=False),
                                           encoding="utf-8")
    (d / "items.reproduced.json").write_text(json.dumps({"cards": cards}, ensure_ascii=False),
                                             encoding="utf-8")


def _cards(d):
    return json.loads((d / "items.reproduced.json").read_text(encoding="utf-8"))["cards"]


def test_빈칸에_번호가_붙는다():
    # `front_of` 는 전부 `[...]` 라 어느 빈칸을 말하는지 가리킬 수 없다.
    c = _cloze("c1", "선충류는 {{c1::긴 원통형}}, 흡충류는 {{c1::납작한 잎}}이다.")
    assert numbered_front(c) == "선충류는 [1], 흡충류는 [2]이다."


def test_힌트도_함께_보인다():
    c = _cloze("c1", "자웅{{c1::이체::동체/이체}}이다")
    assert numbered_front(c) == "자웅[1|동체/이체]이다"


def test_축_프롬프트에_앞면만_들어간다():
    c = _cloze("c1", "선충류는 {{c1::긴 원통형}}이다")
    txt = build_axis([c], None)
    assert "긴 원통형" not in txt        # 정답이 프롬프트에 없다 — 누출이 원리적으로 없다
    assert "선충류는 [1]이다" in txt


def test_축이_안_선_카드가_수선_대상이_된다(tmp_path):
    _write(tmp_path,
           [{"id": "c1", "blanks": [{"n": 1, "told": False, "why_not": "무엇을 묻는지 모른다"}]}],
           [_cloze("c1", "선충류는 {{c1::긴 원통형}}이다")])
    assert mark_axis(tmp_path) == 1
    assert _cards(tmp_path)[0]["reproduce"]["reason"] == AXIS_REASON


def test_축이_선_카드는_그대로다(tmp_path):
    _write(tmp_path,
           [{"id": "c1", "blanks": [{"n": 1, "told": True, "asks": "몸꼴"}]}],
           [_cloze("c1", "선충류는 몸꼴이 {{c1::긴 원통형}}이다")])
    assert mark_axis(tmp_path) == 0
    assert (_cards(tmp_path)[0].get("reproduce") or {}) == {}


def test_이미_결함인_카드는_안_덮는다(tmp_path):
    # 재현 채점의 판정이 더 구체적이다. 덮으면 수선이 받을 정보가 줄어든다.
    card = _cloze("c1", "선충류는 {{c1::긴 원통형}}이다")
    card["reproduce"] = {"reason": "answer_underspecified", "note": "원래 메모"}
    _write(tmp_path, [{"id": "c1", "blanks": [{"n": 1, "told": False, "why_not": "x"}]}], [card])
    assert mark_axis(tmp_path) == 0
    assert _cards(tmp_path)[0]["reproduce"]["note"] == "원래 메모"


def test_basic_카드는_보지_않는다(tmp_path):
    card = {"id": "c1", "card_format": "basic", "q": "무엇인가?", "a": "답"}
    _write(tmp_path, [{"id": "c1", "blanks": [{"n": 1, "told": False, "why_not": "x"}]}], [card])
    assert mark_axis(tmp_path) == 0


def test_수선은_태우되_배포는_안_막는다():
    # 갈래를 둘로 둔 이유. 문지기는 DEFECT_REASONS 만 본다.
    assert AXIS_REASON in REPAIR_REASONS
    assert AXIS_REASON not in DEFECT_REASONS
