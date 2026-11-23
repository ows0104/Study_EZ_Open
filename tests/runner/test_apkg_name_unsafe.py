"""덱 **파일** 이름에 Windows가 못 쓰는 글자가 안 남는가.

CBL·TBL 시간표의 교수 칸은 「(분반) A: 김태민 (분반) B: 김범석」 꼴이다. `deck_node`는
제목만 거르고 교수 꼬리는 그대로 붙여서, 2026-11-23 261125_07 암면역 예습 덱이

    OSError: [Errno 22] Invalid argument: '...\\[261125_07] 암면역((분반) A: 김태민 ...) 예습.apkg'

로 멈췄다. 덱 **이름**(Anki 마디)은 그대로 둔다 — 홑 `:`는 Anki에서 괜찮고, 바꾸면
재개 판정과 이미 나간 덱의 마디가 어긋난다.
"""

from __future__ import annotations

import json

from runner import deck

SUBJECT = "감염과 면역"
THIS, PREV = "261125_07", "251126_15"
PROFS = ["(분반) A: 김태민 (분반) B: 김범석"]
NODE = "[261125_07] 암면역((분반) A: 김태민 (분반) B: 김범석)"


def seat(runs, built=None):
    d = runs / PREV
    d.mkdir(parents=True, exist_ok=True)
    (d / deck.TARGET_NAME).write_text(json.dumps({
        "subject": SUBJECT, "run_id": THIS, "title": "암면역",
        "professors": PROFS, "prev_run_id": PREV,
    }, ensure_ascii=False), encoding="utf-8")
    if built is not None:
        (d / "pre_run.meta.json").write_text(json.dumps({
            "deck_name": f"{SUBJECT}::{built}::예습",
        }, ensure_ascii=False), encoding="utf-8")
    return d


def test_분반_교수_칸의_콜론이_파일_이름에_안_남는다(tmp_path):
    d = seat(tmp_path)
    name = deck.calendar_name(d, PREV, "암면역", deck.PRE, subject=SUBJECT)
    assert not deck.RE_FS_UNSAFE.search(name)
    assert name == "[261125_07] 암면역((분반) A 김태민 (분반) B 김범석) 예습"
    # 실제로 만들어지는 이름인가 — 고치기 전에는 여기서 OSError였다.
    (tmp_path / f"{name}.apkg").write_bytes(b"")


def test_덱_이름은_그대로_둔다(tmp_path):
    """재개 판정(`prequiz.config.json`의 `lecture`)과 Anki 마디가 안 흔들린다."""
    d = seat(tmp_path)
    assert deck.calendar_node(tmp_path, PREV, "암면역", deck.PRE, subject=SUBJECT) == NODE
    assert deck.calendar_deck(d, PREV, "암면역", deck.PRE, SUBJECT) == f"{SUBJECT}::{NODE}::예습"


def test_이미_나간_마디에_콜론이_있어도_파일_이름은_걸러진다(tmp_path):
    """251104_01처럼 `:`가 든 이름으로 이미 나간 덱을 다시 구울 때."""
    d = seat(tmp_path, built=NODE)
    assert deck.calendar_node(tmp_path, PREV, "암면역", deck.PRE, subject=SUBJECT) == NODE
    assert not deck.RE_FS_UNSAFE.search(
        deck.calendar_name(d, PREV, "암면역", deck.PRE, subject=SUBJECT))


def test_안전한_이름은_그대로다():
    node = "[260825_01] 종양의 분자생물학(1)(전윤경)"
    assert deck.apkg_name(node, deck.PRE) == f"{node} 예습"
    assert deck.apkg_name(node, deck.MAIN) == node
