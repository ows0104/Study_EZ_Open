"""러너가 하위 프로세스의 로그에서 무엇을 줍는가.

여기 있는 것 대부분은 **한 번 틀렸던 자리**다. 배선 시험에서 러너가 아무것도 안
만들고 "덱을 만들었다"를 서버에 적었다 — `prequeue`가 만들 자리를 못 찾아도 0으로
끝나기 때문이다. 그 뒤로 성공 판정을 종료 코드가 아니라 산출물로 옮겼다.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from runner import agent, deck


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


# ── 자식은 물을 자리가 없다 ────────────────────────────────────────────
# 2026-08-31 기생충학/260831_01 이 「필기 중심으로 만들까요? [Y/n]」에서 45분을
# 잠들어 있었다(CPU 0.2초). 러너의 stdin 을 물려받아 `isatty()` 가 참으로 나왔고,
# 답할 사람이 없으니 180분 뒤 timeout 까지 아무 일도 안 한다. 같은 일이
# 2026-08-25 병리학/260825_03 에서도 났다(그때는 실제로 끊겼다).


def test_하위_명령의_stdin을_막는다(tmp_path, monkeypatch):
    seen = {}

    class FakeProc:
        returncode = 0

        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        seen.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(agent.subprocess, "Popen", fake_popen)
    worker = _agent_with(tmp_path)

    class FakeClient:
        base = "https://example.test"
        token = "t"

    worker.client = FakeClient()
    worker._run([sys.executable, "-c", "pass"], tmp_path / "run.log")

    assert seen["stdin"] is agent.subprocess.DEVNULL


# ── 기다리면 풀리는 일과 고쳐야 하는 일은 화면에서 갈린다 ──────────────
# 2026-09-02 01:22에 복습 셋·예습 셋이 세션 한도로 죽었는데, 화면에는 종료 코드와
# 「만들 자리를 못 찾았다」만 남았다. 둘 다 사람을 엉뚱한 곳으로 보낸다.


def test_다시_만들_것_0편에_안_걸린다():
    """`"만들 것 0편" in line`으로 재던 자리. 그 글자가 바로 옆 `다시 만들 것 0편`
    안에 그대로 있어서 정상 회차마다 참이 됐다."""
    lines = ["  만들 것 1편 · 다시 만들 것 0편 · 이미 있는 것 0편 · 막힌 것 0편"]
    assert agent.blocked_reason(lines, "260902_01") == ""


def test_정말_만들_것이_없으면_그대로_말한다():
    lines = ["  만들 것 0편 · 다시 만들 것 0편 · 이미 있는 것 3편 · 막힌 것 0편"]
    assert agent.blocked_reason(lines, "260902_01") == "만들 자리를 못 찾았다"


def test_한도는_하위_로그에서_읽어_온다(tmp_path):
    """러너가 보는 것은 「quizgen가 1로 끝났다」까지다. 이유는 그 줄이 달고 오는
    로그 안에 있다."""
    child = tmp_path / "pipeline.log"
    child.write_text(
        '{"api_error_status":429,"result":"You\'ve hit your session limit '
        '· resets 5:40am (Asia/Seoul)","type":"result"}', encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child}) · 0.1분"]
    assert agent.limit_reason(lines) == "세션 한도에 걸렸다 — resets 5:40am (Asia/Seoul)"


def test_한도가_아니면_아무_말도_안_한다(tmp_path):
    child = tmp_path / "pipeline.log"
    child.write_text("멈췄다 — ②카드: 스키마가 안 맞는다", encoding="utf-8")
    assert agent.limit_reason([f"실패 — (로그: {child})"]) == ""


def test_한도는_마지막_줄을_집는다(tmp_path):
    """하위 로그는 덧붙여 쓰인다. 첫 줄을 집으면 어제 걸린 시각을 오늘 것으로 적는다 —
    이미 지난 시각이라 사람이 「풀렸는데 왜 죽지」를 묻게 된다."""
    child = tmp_path / "pipeline.log"
    child.write_text("\n".join([
        '"result":"session limit · resets 5:40am (Asia/Seoul)"',
        "── 재현 검사",
        '"result":"session limit · resets 1:40pm (Asia/Seoul)"',
    ]), encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child})"]
    assert agent.limit_reason(lines) == "세션 한도에 걸렸다 — resets 1:40pm (Asia/Seoul)"


def test_한도가_아닌_실패에_한도를_안_갖다_붙인다(tmp_path):
    """로그가 덧붙여 쓰여서 아침의 한도 줄이 남아 있다. 이번에 멈춘 자리는 다른
    곳이다 — `260901_01`이 validate 실패로 죽었는데 화면에 「세션 한도」가 떴다."""
    child = tmp_path / "pipeline.log"
    child.write_text("\n".join([
        '"result":"session limit · resets 1:40pm (Asia/Seoul)"',
        "멈췄다 — ①학습목표: claude 가 1 로 끝났다",
        "── ② 카드",
        "멈췄다 — 명령 실패: quizgen.validate items.raw.json --strategy base",
    ]), encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child})"]
    assert agent.limit_reason(lines) == ""
    assert agent.child_stop_reason(lines).startswith("명령 실패: quizgen.validate")


def test_이번에_멈춘_것이_한도면_한도로_적는다(tmp_path):
    child = tmp_path / "pipeline.log"
    child.write_text("\n".join([
        "멈췄다 — 명령 실패: 어제 죽은 자리",
        "── ① 학습목표",
        "멈췄다 — ①학습목표: claude 가 1 로 끝났다",
        '"result":"session limit · resets 6:40pm (Asia/Seoul)"',
    ]), encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child})"]
    assert agent.limit_reason(lines) == "세션 한도에 걸렸다 — resets 6:40pm (Asia/Seoul)"


# ── 한도는 실패가 아니라 기다림이다 ───────────────────────────────────
# 2026-09-02에 두 번 걸렸다(01:32·10:17). 실패로 적으면 사람이 다시 눌러야 하는데,
# 걸리는 시각이 대개 사람이 자는 때다.


def test_풀리는_시각을_읽는다():
    now = datetime(2026, 9, 2, 10, 17).astimezone()
    assert agent.resume_at("한도 — resets 1:40pm (Asia/Seoul)", now).hour == 13
    assert agent.resume_at("한도 — resets 1:40pm (Asia/Seoul)", now).minute == 40


def test_이미_지난_시각이면_내일이다():
    """밤 10시에 「resets 5:40am」을 받으면 여섯 시간을 기다려야 한다."""
    now = datetime(2026, 9, 2, 10, 17).astimezone()
    when = agent.resume_at("한도 — resets 5:40am (Asia/Seoul)", now)
    assert (when.day, when.hour) == (3, 5)


def test_시각을_못_읽으면_잠깐만_기다린다():
    """지어낸 시각을 적느니 짧게 기다린다 — 틀려도 한 번 더 부딪힐 뿐이다."""
    now = datetime(2026, 9, 2, 10, 17).astimezone()
    when = agent.resume_at("세션 한도에 걸렸다", now)
    assert 0 < (when - now).total_seconds() <= agent.BLIND_WAIT


# ── 403 인증 거절도 기다림이다 (2026-09-17) ──────────────────────────
# 09:33에 다섯 편이 1분 안에 전부 이것으로 죽었고 몇 분 뒤 저절로 풀렸다. 그때는
# 이 갈래가 없어서 다섯 다 「실패」로 적혔다 — 아침까지 그대로 서 있었다.
# 한도와 다른 점은 **풀리는 시각을 API가 안 알려 준다**는 것뿐이고, 그래서
# `AUTH_MAX_RETRIES`에서 끊는다(조직 설정이 정말 꺼진 것이면 끝없이 돈다).

AUTH_403 = ('{"is_error":true,"num_turns":1,"api_error_status":403,'
            '"result":"Your organization has disabled Claude subscription access '
            'for Claude Code · Use an Anthropic API key instead","type":"result"}')


def test_403은_하위_로그에서_읽어_온다(tmp_path):
    child = tmp_path / "pipeline.log"
    child.write_text("멈췄다 — ①학습목표: claude 가 1 로 끝났다\n" + AUTH_403,
                     encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child}) · 0.1분"]
    assert agent.auth_reason(lines).startswith("인증이 거절됐다 (403)")


def test_403이_아니면_아무_말도_안_한다(tmp_path):
    child = tmp_path / "pipeline.log"
    child.write_text("멈췄다 — ②카드: 스키마가 안 맞는다", encoding="utf-8")
    assert agent.auth_reason([f"실패 — (로그: {child})"]) == ""


def test_403이_아닌_실패에_403을_안_갖다_붙인다(tmp_path):
    """하위 로그는 덧붙여 쓰인다. 어제 튕긴 403이 그 파일에 그대로 남아 있고,
    앞에서 집으면 오늘의 진짜 실패를 인증 문제로 적는다 — 한도에서 이미 한 번
    값을 한 함정이다(`260901_01`)."""
    child = tmp_path / "pipeline.log"
    child.write_text("\n".join([
        AUTH_403,
        "멈췄다 — ①학습목표: claude 가 1 로 끝났다",
        "── ② 카드",
        "멈췄다 — 명령 실패: quizgen.validate items.raw.json",
    ]), encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child})"]
    assert agent.auth_reason(lines) == ""
    assert agent.child_stop_reason(lines).startswith("명령 실패: quizgen.validate")


def test_한도가_403을_이긴다(tmp_path):
    """둘이 같이 있으면 한도로 적는다. 한도는 풀리는 시각을 알려 주므로 그쪽이
    사람에게 더 쓸모 있고, 되돌리기 셈도 안 먹는다."""
    child = tmp_path / "pipeline.log"
    child.write_text("\n".join([
        "멈췄다 — ②카드: claude 가 1 로 끝났다",
        '"api_error_status":403',
        '"result":"session limit · resets 4:30am (Asia/Seoul)"',
    ]), encoding="utf-8")
    lines = [f"    실패 — quizgen가 1로 끝났다 (로그: {child})"]
    assert agent.limit_reason(lines) == "세션 한도에 걸렸다 — resets 4:30am (Asia/Seoul)"


def _job(run_id="260916_01", kind=deck.MAIN):
    return agent.Job(id=1, subject="미생물학", run_id=run_id, kind=kind)


def test_되돌린_횟수는_파일에_센다(tmp_path):
    """러너는 재시작한다(예약 작업이 껐다 켠다). 메모리에 세면 그때마다 0이다."""
    job = _job()
    assert agent.bump_auth_retry(tmp_path, job) == 1
    assert agent.bump_auth_retry(tmp_path, job) == 2
    assert (tmp_path / agent.RETRY_FILE).is_file()
    # 다른 프로세스가 읽어도 같은 값이 나온다.
    assert agent.read_retries(tmp_path)[agent.retry_key(job)] == 2


def test_예습과_복습은_따로_센다():
    assert agent.retry_key(_job(kind=deck.MAIN)) != agent.retry_key(_job(kind=deck.PRE))


def test_403이_아닌_결말이_나오면_셈을_버린다(tmp_path):
    """**이어진 것만 센다.** 어제 한 번 튕기고 오늘 또 한 번은 「두 번 이어졌다」가
    아니다 — 그렇게 세면 상한이 영영 안 풀린다."""
    job = _job()
    agent.bump_auth_retry(tmp_path, job)
    agent.bump_auth_retry(tmp_path, job)
    agent.clear_auth_retry(tmp_path, job)
    assert agent.read_retries(tmp_path).get(agent.retry_key(job)) is None
    assert agent.bump_auth_retry(tmp_path, job) == 1


def test_셈을_못_써도_안_죽는다(tmp_path):
    """이 값은 판정을 돕는 것이지 산출물이 아니다. 못 쓰면 다음 403이 1번째로
    세어질 뿐이고, 편이 죽어서는 안 된다."""
    bad = tmp_path / agent.RETRY_FILE
    bad.write_text("{{{ 깨진 json", encoding="utf-8")
    assert agent.read_retries(tmp_path) == {}
    assert agent.bump_auth_retry(tmp_path, _job()) == 1
