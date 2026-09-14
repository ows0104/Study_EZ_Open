"""예습 덱과 복습 덱이 **한 마디 아래** 서는가.

두 갈래가 제목을 다른 데서 딴다 — 예습은 시간표 칸, 복습은 올해 필기의 파일명.
사람이 손으로 적는 두 글이라 띄어쓰기 하나로 갈리고, 갈리면 Anki 에서 형제로 안 서고
각자 나무를 하나씩 만든다. 2026-09-03 실측에서 짝이 선 20쌍 중 5쌍이 그랬다.

    예습  [260831_01] 기생충학 총론 (1)(최민호)
    복습  [260831_01] 기생충학 총론1(최민호)

`pre_target.json` 을 보고 맞추는 것으로는 안 된다 — 그 파일은 **올해 필기가 들어오는
순간 파일명 쪽으로 갈아탄다.** 그래서 이미 나간 예습 덱의 이름에 못을 박는다.
"""

from __future__ import annotations

import json

from runner import deck

SUBJECT = "기생충학"
THIS, PREV = "260831_01", "250915_01"
PRE_NODE = "[260831_01] 기생충학 총론 (1)(최민호)"


def seat(runs, prev=PREV, this=THIS, subject=SUBJECT, built=PRE_NODE, title="기생충학 총론1(최민호)"):
    """작년 자리 하나. `built` 를 None 으로 주면 예습 덱이 아직 안 나간 자리다."""
    d = runs / prev
    d.mkdir(parents=True, exist_ok=True)
    (d / deck.TARGET_NAME).write_text(json.dumps({
        # **이미 파일명 쪽으로 갈아탄 상태다.** 실측이 그랬다.
        "subject": subject, "run_id": this, "title": title,
        "professors": ["최민호"], "prev_run_id": prev,
    }, ensure_ascii=False), encoding="utf-8")
    if built is not None:
        (d / "pre_run.meta.json").write_text(json.dumps({
            "deck_name": f"{subject}::{built}::예습",
        }, ensure_ascii=False), encoding="utf-8")
    return d


def test_이미_나간_예습_덱의_마디를_복습이_따른다(tmp_path):
    seat(tmp_path)
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",), subject=SUBJECT)
    assert node == PRE_NODE


def test_예습_덱_파일_이름도_같은_마디에서_나온다(tmp_path):
    d = seat(tmp_path)
    assert deck.calendar_name(d, PREV, "기생충학 총론1", deck.PRE,
                              subject=SUBJECT) == f"{PRE_NODE} 예습"
    assert deck.calendar_deck(tmp_path / THIS, THIS, "기생충학 총론1", deck.MAIN,
                              SUBJECT, ("최민호",)) == f"{SUBJECT}::{PRE_NODE}"


def test_예습을_다시_구워도_이름이_안_흔들린다(tmp_path):
    """`pre_target.json` 이 파일명 쪽을 들고 있어도 나간 이름이 이긴다.

    못이 없으면 rebuild 가 예습 덱을 파일명으로 개명하고, 학생의 Anki 에는 카드가
    남은 옛 마디 옆에 빈 마디가 하나 더 선다.
    """
    d = seat(tmp_path)
    assert deck.calendar_node(tmp_path, PREV, "기생충학 총론1", deck.PRE,
                              ("최민호",), subject=SUBJECT) == PRE_NODE


def test_예습이_아직_안_나갔으면_복습은_파일명대로_선다(tmp_path):
    seat(tmp_path, built=None)
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",), subject=SUBJECT)
    assert node == "[260831_01] 기생충학 총론1(최민호)"


def test_예습_자리가_아예_없어도_선다(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",), subject=SUBJECT)
    assert node == "[260831_01] 기생충학 총론1(최민호)"


def test_같은_교시를_두_과목이_나눠_쓰면_못을_안_박는다(tmp_path):
    """어느 쪽 이름인지 코드가 모른다. 남의 강의 제목이 붙는 것보다 갈려 있는 편이 낫다."""
    seat(tmp_path, prev="250915_01", subject=SUBJECT, built=PRE_NODE)
    seat(tmp_path, prev="250915_09", subject="미생물학",
         built="[260831_01] 세균학 총론(홍길동)")
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",))     # 과목을 안 주면 둘 다 걸린다
    assert node == "[260831_01] 기생충학 총론1(최민호)"


def test_과목을_주면_자기_짝만_본다(tmp_path):
    seat(tmp_path, prev="250915_01", subject=SUBJECT, built=PRE_NODE)
    seat(tmp_path, prev="250915_09", subject="미생물학",
         built="[260831_01] 세균학 총론(홍길동)")
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",), subject=SUBJECT)
    assert node == PRE_NODE


def test_낡은_자리가_남의_편을_물고_있으면_안_따른다(tmp_path):
    """짝이 바뀐 자리. 마디에 박힌 `run_id` 로 거른다."""
    seat(tmp_path, built="[260902_05] 다른 강의(아무개)")
    node = deck.calendar_node(tmp_path, THIS, "기생충학 총론1", deck.MAIN,
                              ("최민호",), subject=SUBJECT)
    assert node == "[260831_01] 기생충학 총론1(최민호)"


def test_node_of_는_꼬리와_과목을_떼_낸다():
    assert deck.node_of("기생충학::[260831_01] 총론::예습") == "[260831_01] 총론"
    assert deck.node_of("기생충학::[260831_01] 총론") == "[260831_01] 총론"
    assert deck.node_of("[260831_01] 총론::예습") == "[260831_01] 총론"
    assert deck.node_of("") == ""


def test_짝이_바뀐_예습_자리는_옛_이름을_안_들고_간다(tmp_path):
    """`prequeue --force` 로 짝이 갈아탄 자리. `pre_target.json` 은 새 강의를 가리키는데
    `pre_run.meta.json` 은 지난번 강의의 덱을 그대로 안고 있다.

    못을 그냥 믿으면 남의 강의 이름으로 굽고, `rebuild` 가 옛 파일까지 지운다.
    """
    d = seat(tmp_path, this="260907_03", built="[260831_01] 기생충학 총론 (1)(최민호)",
             title="파동편모충증(최민호)")
    node = deck.calendar_node(tmp_path, PREV, "파동편모충증", deck.PRE,
                              ("최민호",), subject=SUBJECT)
    assert node == "[260907_03] 파동편모충증(최민호)"
