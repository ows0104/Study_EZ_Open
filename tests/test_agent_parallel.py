"""일꾼이 둘이 된 뒤의 러너.

2026-08-31에 한 편이 「필기 중심으로 만들까요?」에서 45분을 잠들어 있었는데, 그
동안 **큐에 선 편도 올릴 것도 아무것도 안 움직였다.** 한 실이 `claim`·`handle`·
쓸기를 차례로 했기 때문이다. 여기서 재는 것은 그 자리가 갈렸는가다.
"""

import json
import threading
import time

from studyez import agent, deck, gate, prequeue


class FakeClient:
    """서버 흉내. `claim`이 부를 때마다 큐에서 하나씩 준다."""

    base = "http://test"
    token = "t"

    def __init__(self, jobs):
        self.queue = list(jobs)
        self.running: dict[str, dict] = {}
        self.puts: list[tuple[int, dict]] = []
        self.guard = threading.Lock()

    def call(self, method, path, body=None):
        if method == "POST":
            slot = path.partition("worker=")[2] or "w1"
            with self.guard:
                mine = self.running.get(slot)
                if mine is not None:
                    return {"job": mine}
                if not self.queue:
                    return {"job": None}
                row = self.queue.pop(0)
                self.running[slot] = row
                return {"job": row}
        self.puts.append((int(path.rsplit("/", 1)[-1]), dict(body or {})))
        return {"applied": True}


def _job(run_id: str, kind: str = deck.PRE, job_id: int = 1) -> dict:
    return {"id": job_id, "subject": "병리학", "runId": run_id, "kind": kind}


def _agent(tmp_path, client, **kw) -> agent.Agent:
    return agent.Agent(client=client, runs_dir=tmp_path, repo_root=tmp_path,
                       announce=lambda *_: None, **kw)


def test_일꾼_이름이_claim에_실린다(tmp_path):
    """서버가 이 이름으로 「누가 무엇을 잡고 있나」를 든다. 안 실으면 끊겼다 붙은
    일꾼이 남의 편을 받아 같은 편을 두 번 만든다."""
    seen = []

    class Spy(FakeClient):
        def call(self, method, path, body=None):
            if method == "POST":
                seen.append(path)
            return {"job": None}

    _agent(tmp_path, Spy([])).claim("w2")
    assert seen == [f"{agent.CLAIM}?worker=w2"]


def test_같은_편을_둘이_잡지_않는다(tmp_path):
    """서버가 막는 자리지만 러너도 막는다 — 옛 러너가 같이 떠 있거나 표가
    어긋나면 그쪽이 뚫린다. 편당 빈 세션 넷이다."""
    worker = _agent(tmp_path, FakeClient([]))
    job = agent.Job(id=1, subject="병리학", run_id="260831_01")
    assert worker.take(job, "w1") is True
    assert worker.take(job, "w2") is False
    worker.release(job)
    assert worker.take(job, "w2") is True


def test_잡힌_편은_만들지_않고_넘긴다(tmp_path):
    """`tick`이 그 편을 받아도 `handle`까지 가면 안 된다."""
    client = FakeClient([_job("260831_01")])
    worker = _agent(tmp_path, client)
    worker.building["260831_01"] = "w1"
    worker.handle = lambda job: (_ for _ in ()).throw(AssertionError("만들면 안 된다"))
    assert worker.tick("w2") is False


def test_만드는_중_표시가_파일로_남는다(tmp_path):
    """쓸기는 하위 프로세스라 러너의 메모리를 못 본다. 반쯤 쓰인 덱을 올리지
    않으려면 표시가 파일이어야 한다."""
    worker = _agent(tmp_path, FakeClient([]))
    job = agent.Job(id=1, subject="병리학", run_id="260831_01")
    worker.mark_building(job)
    marker = tmp_path / "260831_01" / gate.BUILDING_FILE
    assert marker.is_file()
    assert gate.hold_reason(tmp_path / "260831_01").startswith("지금 만드는 중")
    worker.clear_building(job)
    assert not marker.exists()
    assert gate.hold_reason(tmp_path / "260831_01") == ""


def test_예습은_작년_자리에도_표시한다(tmp_path):
    """예습 산출물은 작년 run 자리에 쌓인다. 거기를 안 막으면 쓸기가 만드는 중인
    예습 덱을 올린다."""
    prev = tmp_path / "250825_02"
    prev.mkdir()
    (prev / "pre_target.json").write_text(
        '{"subject": "병리학", "run_id": "260831_01"}', encoding="utf-8")
    worker = _agent(tmp_path, FakeClient([]))
    worker.mark_building(agent.Job(id=1, subject="병리학", run_id="260831_01"))
    assert (prev / gate.BUILDING_FILE).is_file()


def test_오래된_표시는_안_믿는다(tmp_path):
    """러너가 그 편을 놓고 죽으면 표시만 남는다. 그대로 믿으면 그 편이 영영
    안 올라간다."""
    import os

    run_dir = tmp_path / "260831_01"
    run_dir.mkdir()
    marker = run_dir / gate.BUILDING_FILE
    marker.write_text("Pre-Quiz 병리학/260831_01", encoding="utf-8")
    old = time.time() - gate.BUILDING_STALE - 60
    os.utime(marker, (old, old))
    assert gate.building_reason(run_dir) == ""


def test_쓸기는_빌드를_기다리지_않는다(tmp_path):
    """한 편을 만드는 45분 동안 아무것도 안 올라가던 자리. 지금은 실이 다르다."""
    worker = _agent(tmp_path, FakeClient([]), sweep_seconds=1)
    swept = threading.Event()
    worker.sweep = swept.set
    thread = threading.Thread(target=worker.sweep_loop, daemon=True)
    thread.start()
    assert swept.wait(5), "쓸기가 돌지 않았다"
    worker._stop.set()
    thread.join(timeout=5)


def test_일꾼이_넘어져도_러너는_산다(tmp_path):
    """한 일꾼에서 샌 예외 하나가 러너를 통째로 세우면 고친 것이 도로 무너진다."""
    worker = _agent(tmp_path, FakeClient([]))
    calls = []

    def boom(slot="w1"):
        calls.append(slot)
        if len(calls) == 1:
            raise RuntimeError("첫 바퀴에서 넘어졌다")
        worker._stop.set()
        return False

    worker.tick = boom
    worker.work_loop("w1", poll=0)
    assert len(calls) >= 2


# ── 판정은 편마다 자기 자리에 ─────────────────────────────────────────
# `runs/prequeue.json`은 실행마다 통째로 다시 쓰인다. 러너가 `--run-id`로 한 편씩
# 부르므로 늘 마지막 한 편만 남고(2026-08-31의 그 파일에 한 줄뿐이었다), 일꾼이
# 둘이 되면 두 편이 같은 초에 덮어쓴다. 그것을 읽던 자리가 `already_made`다.


def _seat(tmp_path, prev: str, run_id: str, subject: str = "기생충학"):
    run_dir = tmp_path / prev
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pre_target.json").write_text(
        json.dumps({"subject": subject, "run_id": run_id, "prev_run_id": prev}),
        encoding="utf-8")
    return run_dir


def _state(run_dir, run_id: str, state: str, subject: str = "기생충학"):
    (run_dir / prequeue.STATE_NAME).write_text(
        json.dumps({"subject": subject, "run_id": run_id, "prev_run_id": run_dir.name,
                    "state": state, "source": "https://chatgpt.com/share/x"}),
        encoding="utf-8")


def test_옆_편이_큐를_덮어써도_판정이_남는다(tmp_path):
    """덱은 멀쩡한데 화면에 「덱을 못 만들었다」가 뜨던 자리."""
    run_dir = _seat(tmp_path, "250915_01", "260901_01")
    _state(run_dir, "260901_01", prequeue.DONE)
    # 옆 일꾼이 자기 편만 담아 큐를 다시 썼다.
    (tmp_path / prequeue.QUEUE_NAME).write_text(
        json.dumps({"generated_at": "2026-09-01T10:00:00", "items": [
            {"link": {"subject": "기생충학", "run_id": "260901_02"}, "state": "done"}]}),
        encoding="utf-8")

    worker = _agent(tmp_path, FakeClient([]))
    assert worker.already_made(agent.Job(id=1, subject="기생충학", run_id="260901_01")) is True


def test_그_자리의_판정이_남의_편이면_안_믿는다(tmp_path):
    """같은 교시에 다른 과목이 돌면 한 자리를 두 강의가 나눠 쓴다."""
    run_dir = _seat(tmp_path, "250915_01", "260901_01")
    _state(run_dir, "260901_09", prequeue.DONE)
    worker = _agent(tmp_path, FakeClient([]))
    assert worker.already_made(agent.Job(id=1, subject="기생충학", run_id="260901_01")) is False


def test_옛_편은_큐로_물러선다(tmp_path):
    """2026-09-01 이전에 만든 편에는 편별 판정이 없다. 그 편들에는 큐가 유일한 답이다."""
    _seat(tmp_path, "250915_01", "260901_01")
    (tmp_path / prequeue.QUEUE_NAME).write_text(
        json.dumps({"generated_at": "2026-08-31T08:27:20", "items": [
            {"link": {"subject": "기생충학", "run_id": "260901_01"}, "state": "done"}]}),
        encoding="utf-8")
    worker = _agent(tmp_path, FakeClient([]))
    assert worker.already_made(agent.Job(id=1, subject="기생충학", run_id="260901_01")) is True


def test_판정을_그_편의_자리에_적는다(tmp_path):
    target = prequeue.Target(
        link=prequeue.Link(subject="기생충학", run_id="260901_01", date="2026-09-01",
                           title="총론", share_url="https://chatgpt.com/share/x"),
        prev_run_id="250915_01", state=prequeue.DONE)
    path = prequeue.save_state(target, tmp_path)
    assert path == tmp_path / "250915_01" / prequeue.STATE_NAME
    assert prequeue.state_of(tmp_path, "250915_01", "기생충학", "260901_01") == prequeue.DONE


def test_자리가_없는_편은_적을_곳이_없다(tmp_path):
    """`BLOCKED`은 만들 자리를 못 세운 것이라 판정할 산출물도 없다."""
    target = prequeue.Target(
        link=prequeue.Link(subject="기생충학", run_id="260901_01", date="2026-09-01",
                           title="총론", share_url=""),
        state=prequeue.BLOCKED, reason="작년 짝이 없다")
    assert prequeue.save_state(target, tmp_path) is None
