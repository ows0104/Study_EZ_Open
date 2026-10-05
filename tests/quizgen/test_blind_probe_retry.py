"""차단 검사(`session.verify_blind`)를 「돌리지 못했을」 때 다시 돌린다.

2026-10-04 에 예습 4편이 여기서 멈췄다 — 「출력에서 JSON 을 찾지 못했다」 셋, 300초
시간 초과 하나. 같은 날 따로 6번 돌리면 6번 다 통과했다. 한 번 흔들린 것으로 카드까지
다 만든 덱이 통째로 막혔다.

다시 돌려도 판정 방향은 그대로여야 한다 — 「뚫렸다」는 재시도하지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from quizgen import session


def _fake(answers):
    """차례로 답하는 가짜 `run_blind`. 예외면 던지고, 'TOKEN' 이면 심은 표식을 돌려준다."""
    calls = []

    def run_blind(prompt, **_):
        calls.append(prompt)
        a = answers[len(calls) - 1]
        if isinstance(a, Exception):
            raise a
        if a == "TOKEN":
            path = Path(prompt.split(" 파일을 읽어라", 1)[0])
            return {"probe": path.read_text(encoding="utf-8").strip()}, {}
        return {"probe": a}, {}

    return run_blind, calls


def test_한_번_흔들리면_다시_돌려_통과한다(monkeypatch, tmp_path):
    fake, calls = _fake([session.SessionError("출력에서 JSON 을 찾지 못했다"), "blocked"])
    monkeypatch.setattr(session, "run_blind", fake)
    ok, msg = session.verify_blind(tmp_path / "items.checked.json")
    assert ok and len(calls) == 2


def test_끝까지_못_돌리면_멈춘다(monkeypatch, tmp_path):
    fake, calls = _fake([session.SessionError("시간 초과")] * session.BLIND_PROBE_TRIES)
    monkeypatch.setattr(session, "run_blind", fake)
    ok, msg = session.verify_blind(tmp_path / "items.checked.json")
    assert not ok and "돌리지 못했다" in msg
    assert len(calls) == session.BLIND_PROBE_TRIES


def test_뚫린_것은_다시_돌리지_않는다(monkeypatch, tmp_path):
    fake, calls = _fake(["TOKEN", "blocked", "blocked"])
    monkeypatch.setattr(session, "run_blind", fake)
    ok, msg = session.verify_blind(tmp_path / "items.checked.json")
    assert not ok and "뚫렸다" in msg and len(calls) == 1


def test_표식_파일은_남지_않는다(monkeypatch, tmp_path):
    fake, _ = _fake([session.SessionError("x")] * session.BLIND_PROBE_TRIES)
    monkeypatch.setattr(session, "run_blind", fake)
    session.verify_blind(tmp_path / "items.checked.json")
    assert not (tmp_path / "canary.probe.txt").exists()
