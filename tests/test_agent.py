"""러너가 하위 프로세스의 로그에서 무엇을 줍는가.

여기 있는 것 대부분은 **한 번 틀렸던 자리**다. 배선 시험에서 러너가 아무것도 안
만들고 "덱을 만들었다"를 서버에 적었다 — `prequeue`가 만들 자리를 못 찾아도 0으로
끝나기 때문이다. 그 뒤로 성공 판정을 종료 코드가 아니라 산출물로 옮겼다.
"""

import time
from pathlib import Path

from studyez import agent, deck


def test_마지막_단계를_줍는다(tmp_path):
    log = tmp_path / "prequiz.log"
    log.write_text(
        "── 자료 준비 (prep)\n어쩌고\n"
        "[건너뜀] 프롬프트 조립  (prompt.cards*.md 이미 있음)\n"
        "── ① 반드시 알아야 할 것\n",
        encoding="utf-8")
    assert agent.last_stage(log) == "① 반드시 알아야 할 것"


def test_건너뛴_단계도_단계다(tmp_path):
    # 이어 돌리면 앞 단계가 전부 `[건너뜀]`이라, 이것을 안 읽으면 화면이 빈다.
    log = tmp_path / "prequiz.log"
    log.write_text("── 자료 준비 (prep)\n[건너뜀] 예습 설명본  (note.md 이미 있음)\n", encoding="utf-8")
    assert agent.last_stage(log) == "예습 설명본"


def test_로그가_없으면_빈_문자열(tmp_path):
    assert agent.last_stage(tmp_path / "없다.log") == ""


def test_막힌_이유는_표시_다음_줄에_있다():
    lines = [
        "  2026-08-20 ✋ 260820_02    소아질환의 병태생리(2) 소아기 특이 질환",
        "      작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다",
        "",
        "  만들 것 0편 · 다시 만들 것 0편 · 이미 있는 것 0편 · 막힌 것 1편",
    ]
    assert agent.blocked_reason(lines) == "작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다"


def test_강의를_못_찾은_것도_이유가_된다():
    # 배선 시험에서 실제로 나온 줄. 표시(✋)가 안 붙는 길이라 따로 줍는다.
    lines = ["  만들 것 0편 · 막힌 것 1편",
             "      로컬에서 이 강의를 못 찾았다 — 올해 필기도 시간표 칸도 없다"]
    assert "못 찾았다" in agent.blocked_reason(lines)


def test_막히지_않았으면_빈_문자열():
    assert agent.blocked_reason(["  만들 것 1편", "    끝났다 — 28장 (웹 풀이 28장)"]) == ""


def test_만든_장수를_줍는다():
    lines = ["[1/1] 병리학/260824_02 종양의 …  — 만드는 중", "    끝났다 — 29장 (웹 풀이 29장)"]
    assert agent.first_match(lines, r"끝났다 — (.+)$") == "29장 (웹 풀이 29장)"


def test_장식_줄은_실패_사유가_아니다():
    assert agent.summary(["진짜 사유", "", "====", "── ", "   "]) == "진짜 사유"


class FakeJob(agent.Job):
    pass


def _agent_with(tmp_path: Path) -> agent.Agent:
    return agent.Agent(client=None, runs_dir=tmp_path, repo_root=tmp_path, announce=lambda *_: None)


def _seat(tmp_path: Path, prev: str, run_id: str) -> Path:
    run_dir = tmp_path / prev
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pre_target.json").write_text(
        '{"subject": "병리학", "run_id": "%s", "prev_run_id": "%s"}' % (run_id, prev),
        encoding="utf-8")
    return run_dir


def test_작년_짝을_pre_target에서_찾는다(tmp_path):
    _seat(tmp_path, "250825_02", "260824_02")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02")
    assert worker.prev_run_of(job) == "250825_02"


def test_다시_만들기는_force로_간다(tmp_path):
    """안 붙이면 `prequeue`가 이미 만든 편으로 보고 건너뛴다 — 그러면 화면에는
    아무것도 안 만든 채 「덱을 못 만들었다」가 적힌다."""
    worker = _agent_with(tmp_path)
    plain = agent.Job(id=1, subject="병리학", run_id="260824_02")
    again = agent.Job(id=2, subject="병리학", run_id="260824_02", force=True)
    assert "--force" not in worker.make_argv(plain)
    assert "--force" in worker.make_argv(again)
    # 어느 편인지는 그대로다. 다시 만드는 것도 한 편이다.
    assert worker.make_argv(again)[worker.make_argv(again).index("--run-id") + 1] == "260824_02"


def test_자리가_없으면_만든_것도_없다(tmp_path):
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02")
    assert worker.made_deck(job, time.time()) is False


def test_지난번_산출물로_속지_않는다(tmp_path):
    """다시 만들기를 눌렀는데 빌드가 조용히 건너뛴 경우."""
    run_dir = _seat(tmp_path, "250825_02", "260824_02")
    items = run_dir / "pre_items.final.json"
    items.write_text("[]", encoding="utf-8")
    old = time.time() - 3600
    import os
    os.utime(items, (old, old))

    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02")
    assert worker.made_deck(job, time.time()) is False
    # 이번 실행에서 나온 것이면 참이다.
    assert worker.made_deck(job, old - 10) is True


# ── 갈래 ──────────────────────────────────────────────────────────────
# 예습과 복습은 재료가 다르므로 만드는 명령이 다르다. 러너가 그것을 일감의
# `kind`로 받는다.


def test_갈래가_명령을_가른다(tmp_path):
    worker = _agent_with(tmp_path)
    pre = worker.make_argv(agent.Job(id=1, subject="병리학", run_id="260824_02"))
    main = worker.make_argv(
        agent.Job(id=2, subject="병리학", run_id="260824_02", kind=deck.MAIN))
    assert "prequeue" in pre and "watch" not in pre
    assert "watch" in main and "prequeue" not in main
    # 둘 다 그 강의 하나만 만든다.
    assert main[main.index("--run-id") + 1] == "260824_02"


def test_다시_만들기는_두_갈래_모두에_붙는다(tmp_path):
    worker = _agent_with(tmp_path)
    for kind in (deck.PRE, deck.MAIN):
        job = agent.Job(id=1, subject="병리학", run_id="260824_02", kind=kind, force=True)
        assert "--force" in worker.make_argv(job)


def _main_deck(tmp_path: Path, run_id: str) -> Path:
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    apkg = run_dir / "병리학.apkg"
    apkg.write_bytes(b"apkg")
    return apkg


def test_복습은_이미_있던_덱도_성공이다(tmp_path):
    """만들다 만 편이 아니라 **올리다 만 편**이 있다. 그 편에서 누르는 것도 이 버튼이다."""
    _main_deck(tmp_path, "260824_02")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02", kind=deck.MAIN)
    # `watch --run-id`가 안 만들고 넘긴 자리 — 「끝났다」 줄이 없다.
    assert worker.outcome(job, ["  이미 덱이 있다"], 0, time.time()) == "이미 있던 덱"


def test_복습은_종료_코드로_실패를_안다(tmp_path):
    """덱이 남아 있어도 만들다 죽었으면 실패다. `watch --run-id`가 0이 아닌 값을 낸다."""
    _main_deck(tmp_path, "260824_02")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02", kind=deck.MAIN)
    assert worker.outcome(job, ["실패 — 어쩌고"], 1, time.time()) == ""


def test_덱이_없으면_복습도_못_만든_것이다(tmp_path):
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260824_02", kind=deck.MAIN)
    assert worker.outcome(job, ["  만들 자리를 못 찾았다"], 0, time.time()) == ""


def test_복습을_만드는_중에_예습_로그를_읽지_않는다(tmp_path):
    """같은 강의에 예습을 이미 만들어 둔 편. `pre_target.json`이 그대로 남아 있다."""
    prev = _seat(tmp_path, "250825_02", "260824_02")
    (prev / "prequiz.log").write_text("── 지난번 예습의 마지막 단계\n", encoding="utf-8")
    run_dir = tmp_path / "260824_02"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pipeline.log").write_text("── ② 시험에 나올 것\n", encoding="utf-8")

    worker = _agent_with(tmp_path)
    wrapper = tmp_path / "agent.260824_02.log"
    wrapper.write_text("", encoding="utf-8")
    main = agent.Job(id=1, subject="병리학", run_id="260824_02", kind=deck.MAIN)
    pre = agent.Job(id=2, subject="병리학", run_id="260824_02")
    assert worker.stage_of(wrapper, main) == "② 시험에 나올 것"
    assert worker.stage_of(wrapper, pre) == "지난번 예습의 마지막 단계"


# ── 다른 편의 줄을 이유로 삼지 않는다 ─────────────────────────────────
# `prequeue`는 편 하나만 만들어도 계획은 과목 전부를 세운다. 그 경고가 로그에
# 같이 실려서, 2026-08-31 에 260831_01 을 누른 사람이 260911_01 의 경고를
# 실패 사유로 받았다.


def test_다른_편의_경고는_이유가_아니다():
    lines = [
        "  ⚠ 기생충학/260911_01 미생물학의 역사 — 작년 짝을 못 찾았다",
        "  ⚠ 기생충학/260917_01 바이러스의 증식 및 배양 — 작년 짝을 못 찾았다",
        "  만들 것 0편 · 다시 만들 것 0편 · 이미 있는 것 1편 · 막힌 것 0편",
    ]
    assert agent.blocked_reason(lines, "260831_01") == "만들 자리를 못 찾았다"
    # 그 편의 줄이면 그대로 쓴다.
    assert "260831_01" in agent.blocked_reason(
        lines + ["  ⚠ 기생충학/260831_01 총론 — 작년 짝을 못 찾았다"], "260831_01")


def test_막힌_편이_여럿이면_누른_편의_것을_읽는다():
    lines = [
        "  2026-09-11 ✋ 260911_01    미생물학의 역사",
        "      로컬에서 이 강의를 못 찾았다 — 올해 필기도 시간표 칸도 없다",
        "  2026-08-31 ✋ 260831_01    기생충학 총론 (1)",
        "      작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다",
    ]
    assert agent.blocked_reason(lines, "260831_01") == "작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다"


# ── 예습도 「이미 있던 것」이 성공이다 ─────────────────────────────────


def _queue(tmp_path: Path, run_id: str, state: str, subject: str = "병리학") -> None:
    (tmp_path / "prequeue.json").write_text(
        '{"generated_at": "2026-08-31T08:27:20", "items": [{"link": '
        '{"subject": "%s", "run_id": "%s"}, "state": "%s"}]}' % (subject, run_id, state),
        encoding="utf-8")


def test_예습도_이미_있던_문항이_성공이다(tmp_path):
    """올리다 만 편. `prequeue`가 「이미 있는 것 1편」으로 끝내고 아무것도 안 만든다 —
    그것을 실패로 적으면 화면에 「덱을 못 만들었다」가 남고 덱은 밤에 도착한다."""
    _queue(tmp_path, "260831_01", "done")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260831_01")
    assert worker.outcome(job, ["  만들 것 0편 · 이미 있는 것 1편"], 0, time.time()) == "이미 있던 문항"


def test_다시_만들기에는_안_쓴다(tmp_path):
    """`--force`가 붙었는데 아무것도 안 나왔으면 그것이 문제다. 성공으로 적으면
    옛 덱이 새것으로 올라간다."""
    _queue(tmp_path, "260831_01", "done")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260831_01", force=True)
    assert worker.outcome(job, ["  만들 것 0편 · 이미 있는 것 1편"], 0, time.time()) == ""


def test_막힌_편은_이미_있던_것이_아니다(tmp_path):
    _queue(tmp_path, "260831_01", "blocked")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260831_01")
    assert worker.outcome(job, ["  막힌 것 1편"], 0, time.time()) == ""


def test_큐에_없는_편은_이미_있던_것이_아니다(tmp_path):
    _queue(tmp_path, "260831_05", "done")
    worker = _agent_with(tmp_path)
    job = agent.Job(id=1, subject="병리학", run_id="260831_01")
    assert worker.already_made(job) is False
