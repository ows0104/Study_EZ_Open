"""러너가 하위 프로세스의 로그에서 무엇을 줍는가.

여기 있는 것 대부분은 **한 번 틀렸던 자리**다. 배선 시험에서 러너가 아무것도 안
만들고 "덱을 만들었다"를 서버에 적었다 — `prequeue`가 만들 자리를 못 찾아도 0으로
끝나기 때문이다. 그 뒤로 성공 판정을 종료 코드가 아니라 산출물로 옮겼다.
"""

import time
from pathlib import Path

from studyez import agent


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
