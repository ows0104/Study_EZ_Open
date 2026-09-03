"""사람이 「멈추기」를 누르면 러너가 그것을 받아 자식을 내린다.

**서버는 이 프로세스를 모른다.** 만드는 것은 노트북이고 서버가 아는 것은 표 한
줄뿐이라, 멈추라는 말이 러너에게 오는 길은 진행을 적으러 갈 때 돌아오는 줄
하나다(`report` → `cancelRequested`). 그 길이 끊기면 화면만 멈추고 빈 세션 넷은
계속 돈다 — 여기서 재는 것이 그 길이다.
"""

import sys
import time

from studyez import agent, deck, publish


class StopClient:
    """무엇을 물어도 「멈춰라」가 실린 줄을 돌려주는 서버."""

    base = "http://test"
    token = "t"

    def __init__(self, cancel: bool = True):
        self.cancel = cancel
        self.puts: list[dict] = []

    def call(self, method, path, body=None):
        if method == "POST":
            return {"job": None}
        self.puts.append(dict(body or {}))
        return {"job": {"id": 1, "cancelRequested": self.cancel}, "applied": True}


def _agent(tmp_path, client) -> agent.Agent:
    return agent.Agent(client=client, runs_dir=tmp_path, repo_root=tmp_path,
                       announce=lambda *_: None)


def test_멈추라는_말은_진행을_적은_답에_실려_온다(tmp_path):
    assert agent.Agent.stop_asked({"job": {"cancelRequested": True}}) is True
    assert agent.Agent.stop_asked({"job": {"cancelRequested": False}}) is False


def test_서버에_못_닿은_것을_멈추라로_읽지_않는다(tmp_path):
    """네트워크가 잠깐 끊긴 것 때문에 45분짜리 빌드를 죽이는 것이 그 반대보다
    훨씬 나쁘다. `report`는 못 적으면 빈 사전을 돌려준다."""
    assert agent.Agent.stop_asked({}) is False
    assert agent.Agent.stop_asked({"job": None}) is False

    class Dead:
        base, token = "http://test", "t"

        def call(self, *args, **kwargs):
            raise publish.PublishError("서버가 안 뜬다")

    worker = _agent(tmp_path, Dead())
    job = agent.Job(id=1, subject="병리학", run_id="260903_01")
    assert worker.stop_asked(worker.report(job, stage="①")) is False


def test_도는_하위_프로세스를_내린다(tmp_path, monkeypatch):
    """`_run`이 그 자리에서 끊고 **사람이 멈춘 것으로** 돌려준다.

    종료 코드를 그대로 쓰지 않는 까닭이 여기 있다 — 윈도우에서 죽인 프로세스는
    1을 내고, 그러면 진짜 실패와 구별이 안 된다.
    """
    monkeypatch.setattr(agent, "STAGE_SECONDS", 0.2)
    client = StopClient()
    worker = _agent(tmp_path, client)
    job = agent.Job(id=1, subject="병리학", run_id="260903_01", kind=deck.MAIN)

    started = time.time()
    code, _lines = worker._run(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        tmp_path / "agent.log", job)

    assert code == agent.KILLED_BY_HUMAN
    # 120초짜리를 기다리지 않았다는 것 — 정말 죽였다는 뜻이다.
    assert time.time() - started < 60


def test_멈춘_실행은_실패가_아니라_취소로_적힌다(tmp_path, monkeypatch):
    """실패로 적으면 사람이 고칠 것을 찾으러 간다. 고칠 것은 없다 — 자기가 멈췄다."""
    client = StopClient()
    worker = _agent(tmp_path, client)
    monkeypatch.setattr(worker, "_run", lambda *a, **k: (agent.KILLED_BY_HUMAN, []))

    worker.handle(agent.Job(id=1, subject="병리학", run_id="260903_01", kind=deck.MAIN))

    states = [put.get("state") for put in client.puts if put.get("state")]
    assert states[-1] == "canceled"
    assert "올리는 중" not in " ".join(str(put.get("stage", "")) for put in client.puts)


def test_이미_멈춤이_걸린_편은_만들지_않는다(tmp_path, monkeypatch):
    """러너가 만드는 중에 재시작하면 그 편을 다시 집는다. **표시가 그대로 온다** —
    여기서 안 보면 사람이 멈춘 편을 처음부터 다시 만든다."""
    client = StopClient()
    worker = _agent(tmp_path, client)
    ran = []
    monkeypatch.setattr(worker, "_run", lambda *a, **k: ran.append(a) or (0, []))

    worker.handle(agent.Job(id=1, subject="병리학", run_id="260903_01",
                            kind=deck.MAIN, cancel_requested=True))

    assert ran == []
    assert [put.get("state") for put in client.puts if put.get("state")] == ["canceled"]
