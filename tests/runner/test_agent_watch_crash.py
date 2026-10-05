"""감시하다 넘어져도 자식을 내린다 · 표본 자리가 없는 갈래의 진행 추정은 「모른다」다.

2026-10-05 Quiz Bank 첫 실물에서 났다. 러너가 하위 프로세스(`runner bank`)를 띄우고 20초마다
진행을 적는데, 진행 추정(`eta`)이 `bank` 갈래를 몰라 `KeyError` 로 넘어졌다. 넘어진 자리는
`_run` 의 감시 고리 안이었고, 거기서 빠져나오며 **자식을 안 내렸다.** 서버의 일감은 「도는 중」
이라 다음 일꾼이 같은 편을 또 띄웠다 — 35초마다 정리 세션(`claude -p`)이 하나씩 쌓여, 끊을 때
하위 프로세스가 14개였다.
"""

import sys
import time
from pathlib import Path

import pytest

from runner import agent, eta


class QuietClient:
    """진행을 적으면 「그대로 하라」만 돌려주는 서버."""

    base = "http://test"
    token = "t"

    def call(self, method, path, body=None):
        if method == "POST":
            return {"job": None}
        return {"job": {"id": 1, "cancelRequested": False}, "applied": True}


def test_표본_자리가_없는_갈래는_모른다로_돌려준다(tmp_path):
    guess = eta.estimate(tmp_path, agent.BANK, "정리", elapsed=20)
    assert (guess.index, guess.total, guess.eta_seconds) == (0, 0, 0)
    assert eta.samples(tmp_path, agent.BANK).order == []


def test_감시하다_넘어지면_자식을_내리고_예외를_올린다(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "STAGE_SECONDS", 0.2)
    worker = agent.Agent(client=QuietClient(), runs_dir=tmp_path, repo_root=tmp_path, announce=lambda *_: None)
    job = agent.Job(id=1, subject="약리학", run_id="261002_03", kind=agent.BANK)

    def boom(*_args, **_kwargs):
        raise KeyError("bank")

    monkeypatch.setattr(agent.eta, "estimate", boom)

    # 자식은 0.1초마다 파일을 고쳐 쓴다. 죽었으면 mtime 이 멈춘다.
    beat = tmp_path / "beat"
    child = (
        "import sys, time\n"
        "print('── 정리', flush=True)\n"
        "while True:\n"
        f"    open(r'{beat}', 'w').write(str(time.time()))\n"
        "    time.sleep(0.1)\n"
    )
    started = time.time()
    with pytest.raises(KeyError):
        worker._run([sys.executable, "-c", child], tmp_path / "agent.log", job)
    assert time.time() - started < 30

    time.sleep(0.5)
    first = Path(beat).stat().st_mtime
    time.sleep(1.0)
    assert Path(beat).stat().st_mtime == first, "자식이 아직 살아서 파일을 쓰고 있다"
