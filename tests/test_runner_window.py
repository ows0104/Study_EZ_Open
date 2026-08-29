"""야간 러너가 「무엇을 만들지」의 창을 어떻게 여는가.

이 자리는 사람이 안 본다 — 21:30과 04:00에 혼자 돈다. 그래서 **틀린 쪽으로
넓게 여는 것**이 제일 위험하다. 시간표가 오늘을 못 읽는 날에 구간 없이 스캔하면
지난 학기 필기가 통째로 딸려 오고, 그걸 밤새 만든다.

`resolve_window`는 그럴 때 아무것도 세우지 않고 사람을 부르기로 되어 있다.
여기서 지키는 것이 그 약속이다 — **못 정하면 넓게 여는 게 아니라 닫는다.**
"""

import types
from datetime import date as Date

import pytest

from studyez import blocks, runner


def _args(**over):
    base = {"all_dates": False, "since": None, "until": None, "today": None,
            "timetable": None, "within_days": 0}
    base.update(over)
    return types.SimpleNamespace(**base)


def _block(start="2026-08-12", end="2026-08-28"):
    return blocks.Block(name="질병의 병리학적 이해", start=Date.fromisoformat(start),
                        end=Date.fromisoformat(end), events=11, days=11)


# ------------------------------------------------------------------ 못 정하면 닫는다

def test_시간표를_못_찾으면_큐를_세우지_않는다(monkeypatch):
    def missing(*_a, **_k):
        raise FileNotFoundError("timetable.json")

    monkeypatch.setattr(blocks, "find", missing)
    since, until, code = runner.resolve_window(_args(today="2026-08-29"))
    assert (since, until) == (None, None)
    assert code == 2                      # 0이면 러너가 그대로 스캔을 돈다


def test_오늘이_어느_블럭에도_없으면_큐를_세우지_않는다(monkeypatch, tmp_path):
    found = blocks.Found(block=None, ended=False, table=[_block()],
                         source=tmp_path / "timetable.json")
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: found)
    since, until, code = runner.resolve_window(_args(today="2027-01-01"))
    assert (since, until) == (None, None)
    assert code == 2


# ------------------------------------------------------------------ 열 때는 이유가 있다

def test_all_dates는_구간을_열되_실패가_아니다(monkeypatch):
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: pytest.fail("물어보면 안 된다"))
    since, until, code = runner.resolve_window(_args(all_dates=True))
    assert (since, until) == (None, None)
    assert code == 0                      # 사람이 일부러 연 것이라 0이다


def test_손으로_준_구간이_시간표를_이긴다(monkeypatch):
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: pytest.fail("물어보면 안 된다"))
    since, until, code = runner.resolve_window(
        _args(since="2026-08-01", until="2026-08-05"))
    assert (since, until, code) == ("2026-08-01", "2026-08-05", 0)


def test_한쪽만_줘도_시간표에_안_물어본다(monkeypatch):
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: pytest.fail("물어보면 안 된다"))
    since, until, code = runner.resolve_window(_args(until="2026-08-05"))
    assert (since, until, code) == (None, "2026-08-05", 0)


def test_블럭을_찾으면_그_구간으로_좁힌다(monkeypatch, tmp_path):
    found = blocks.Found(block=_block(), ended=False, table=[_block()],
                         source=tmp_path / "timetable.json")
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: found)
    since, until, code = runner.resolve_window(_args(today="2026-08-20"))
    assert (since, until, code) == ("2026-08-12", "2026-08-28", 0)


def test_블럭이_끝난_뒤에도_직전_블럭으로_만든다(monkeypatch, tmp_path):
    """늦게 올라온 필기를 받으려고 물러난 자리다. 여기서 닫으면 그 필기를 잃는다."""
    found = blocks.Found(block=_block(), ended=True, table=[_block()],
                         source=tmp_path / "timetable.json")
    monkeypatch.setattr(blocks, "find", lambda *_a, **_k: found)
    since, until, code = runner.resolve_window(_args(today="2026-08-29"))
    assert (since, until, code) == ("2026-08-12", "2026-08-28", 0)


# ------------------------------------------------------------------ 얼마나 앞까지 만드나

def test_제한이_없으면_빈_문자열이다(monkeypatch):
    assert runner.within_days_until(_args(within_days=0)) == ""


def test_N일이면_오늘부터_N일_뒤까지다(monkeypatch):
    assert runner.within_days_until(
        _args(within_days=2, today="2026-08-29")) == "2026-08-31"


def test_달을_넘어가도_날짜로_센다(monkeypatch):
    assert runner.within_days_until(
        _args(within_days=3, today="2026-08-30")) == "2026-09-02"
