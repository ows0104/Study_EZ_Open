"""러너가 둘 돌지 않게 잡는 표시.

**개수가 아니라 비용의 문제다.** 둘이 붙으면 서버가 같은 `running` 일감을 둘 다에게
주고 같은 편을 두 번 만든다. 편당 빈 세션 넷이다. 실제로 한 번 그렇게 됐다 —
작업을 다시 걸다가 옛 파이썬이 살아남아 러너가 두 벌 돌았다.
"""

import os
import time

from runner import agent


def an_agent(tmp_path):
    return agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path,
                       announce=lambda *_: None)


def test_처음이면_잡는다(tmp_path):
    assert an_agent(tmp_path).take_lock() is True
    assert (tmp_path / agent.LOCK_NAME).is_file()


def test_이미_돌고_있으면_안_잡는다(tmp_path):
    first = an_agent(tmp_path)
    assert first.take_lock() is True
    said = []
    second = agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path,
                         announce=said.append)
    assert second.take_lock() is False
    assert any("이미 돌고 있다" in line for line in said), said


def test_오래된_표시는_죽은_것이다(tmp_path):
    """pid 가 아니라 시각을 본다 — pid 는 재사용되고, 그러면 영영 안 뜬다."""
    first = an_agent(tmp_path)
    first.take_lock()
    lock = tmp_path / agent.LOCK_NAME
    old = time.time() - agent.LOCK_STALE - 10
    os.utime(lock, (old, old))

    assert an_agent(tmp_path).take_lock() is True


def test_계속_만져서_살아_있다고_알린다(tmp_path):
    worker = an_agent(tmp_path)
    worker.take_lock()
    lock = tmp_path / agent.LOCK_NAME
    old = time.time() - 60
    os.utime(lock, (old, old))

    worker.touch_lock()
    assert time.time() - lock.stat().st_mtime < 5
