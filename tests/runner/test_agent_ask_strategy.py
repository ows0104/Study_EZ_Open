"""표시해 둔 편은 만들기 전에 사람에게 전략을 묻는다.

2026-09-24 관리자 지시 — 「표시해뒀다가 돌리게 될 때 알림이 뜨고 선택하게」.
약리학 두 편(항생제 치료의 기본원리 · 독성 약리학)이 그 까닭이다. 반복률이 높아
자동 판정이 「족보 중심」으로 가는데, 족보 문항을 낸 교수가 지금 교수가 아니다.
"""

import json
from pathlib import Path

from runner import agent, deck, watch


class Recorder:
    """서버 대신 받아 적는다."""

    def __init__(self):
        self.calls = []

    def call(self, method, path, body):
        self.calls.append((method, path, body))
        return {}


def _mark(runs: Path, subject: str, asks: dict) -> None:
    (runs / "_pairs").mkdir(parents=True, exist_ok=True)
    (runs / "_pairs" / f"{subject}.json").write_text(
        json.dumps({"_block": "약물의 이해", watch.ASK_STRATEGY_KEY: asks}, ensure_ascii=False),
        encoding="utf-8")


def _agent(runs: Path, client=None) -> agent.Agent:
    return agent.Agent(client=client, runs_dir=runs, repo_root=runs, announce=lambda *_: None)


def test_표시한_편만_묻는다(tmp_path):
    _mark(tmp_path, "약리학", {"261012_02": "족보 교수가 바뀌었다."})
    assert watch.strategy_question(tmp_path, "약리학", "261012_02") == "족보 교수가 바뀌었다."
    assert watch.strategy_question(tmp_path, "약리학", "261012_03") == ""
    assert watch.strategy_question(tmp_path, "병리학", "261012_02") == ""


def test_파일이_깨졌으면_묻지_않고_만든다(tmp_path):
    (tmp_path / "_pairs").mkdir()
    (tmp_path / "_pairs" / "약리학.json").write_text("{깨짐", encoding="utf-8")
    assert watch.strategy_question(tmp_path, "약리학", "261012_02") == ""


def test_기존_main은_전략을_묻지_않고_종료한다(tmp_path):
    _mark(tmp_path, "약리학", {"261012_02": "족보 교수가 바뀌었다."})
    client = Recorder()
    worker = _agent(tmp_path, client)
    ran = []
    worker._run = lambda *a, **k: ran.append(a) or (0, [])
    worker.handle(agent.Job(id=7, subject="약리학", run_id="261012_02", kind=deck.MAIN))
    assert ran == []
    method, path, body = client.calls[-1]
    assert path.endswith("/7") and body["state"] == "canceled" and "Quizbank" in body["message"]


def test_고른_전략이_오면_묻지_않고_그대로_넘긴다(tmp_path):
    _mark(tmp_path, "약리학", {"261012_02": "족보 교수가 바뀌었다."})
    worker = _agent(tmp_path, Recorder())
    job = agent.Job(id=7, subject="약리학", run_id="261012_02", kind=deck.MAIN, strategy="기본")
    argv = worker.make_argv(job)
    assert argv[argv.index("--strategy") + 1] == "기본"


def test_예습은_묻지_않는다(tmp_path):
    """예습 덱은 전략을 안 가른다(`docs/quizgen.md` — 교수 교체는 예습에서 전략이 아니다)."""
    _mark(tmp_path, "약리학", {"261012_02": "족보 교수가 바뀌었다."})
    client = Recorder()
    worker = _agent(tmp_path, client)
    worker._run = lambda *a, **k: (1, [])
    worker.handle(agent.Job(id=8, subject="약리학", run_id="261012_02", kind=deck.PRE))
    assert all(body.get("state") != "held" for _m, _p, body in client.calls)
    assert "--strategy" not in worker.make_argv(
        agent.Job(id=8, subject="약리학", run_id="261012_02", strategy="기본"))
