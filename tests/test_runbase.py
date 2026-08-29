"""복습·예습이 같이 쓰는 배관(`pdf2anki/runbase.py`)이 양쪽에서 같게 도는가.

**이 파일이 지키는 것은 「합친 것」과 「안 합친 것」의 경계다.**

두 파이프라인은 목적 함수가 다르다(`CLAUDE.md` 첫 절). 그래서 합친 것은 판단이
하나도 없는 배관뿐이다 — 산출물이 있으면 건너뛰기, 원장 기록, 하위 프로세스 띄우기,
결함 카드 고르기. 반대로 `repair`(예습만 계약 위반도 고친다)·`reproduce`(예습만
`--skip-reproduce` 를 받는다)·`prep`(실패 메시지가 다르다)은 각자 갖는다.

프롬프트에 무엇을 덧붙이냐도 갈린다 — 복습은 채널 위계 변경과 `--note`, 예습은
`--hint`. 몸통은 같아서 `prompt_extra()` 훅으로만 갈라 뒀고, 아래에서 그 훅이
갈라내기 전과 **글자까지 같은지** 확인한다.
"""

import json
import types

import pytest

from pdf2anki import run as main_run
from pdf2anki import runbase
from pdf2anki.prequiz import run as pre_run
from pdf2anki.runbase import BaseRunner, Failed

# 갈라내기 전 두 `agent()` 가 프롬프트 뒤에 붙이던 머리말. 글자가 바뀌면 모델이
# 받는 지시가 바뀐다.
HEADER = "\n\n## 이 강의에 대한 사용자 지시 (프롬프트보다 우선한다)\n\n"


def _args(**over):
    base = {"domain": None, "model": "", "timeout": 600, "force": False, "jobs": 4,
            "repair_rounds": 2, "note": "", "hint": "", "annotation_evidence": False,
            "skip_reproduce": False, "pdf": None}
    base.update(over)
    return types.SimpleNamespace(**base)


# ------------------------------------------------------- 무엇을 합쳤나

def test_두_러너가_같은_배관을_쓴다():
    assert issubclass(main_run.Runner, BaseRunner)
    assert issubclass(pre_run.Runner, BaseRunner)


def test_Failed는_예전_자리에서도_불린다():
    """`from ..run import Failed` 를 쓰는 곳이 있다. 옮겨도 그 이름은 살아 있어야 한다."""
    assert main_run.Failed is Failed


@pytest.mark.parametrize("mod", [main_run, pre_run])
def test_공통_상태가_양쪽에_다_선다(tmp_path, mod):
    r = mod.Runner(tmp_path, _args())
    for attr in ("out", "args", "cost", "t0", "sid", "run",
                 "pend_cost", "pend_usage", "pend_sessions", "pend_models"):
        assert hasattr(r, attr), attr
    assert r.args.domain == "medical_ko"        # 안 주면 채워진다


def test_각자의_상태는_각자_갖는다(tmp_path):
    m = main_run.Runner(tmp_path, _args())
    p = pre_run.Runner(tmp_path, _args())
    assert (m.strategy, m.strategy_why, m.annotation) == ("base", "", False)
    assert (p.stayed, p.prof, p.slice_path, p.contract_broken) == (True, "미상", None, False)


# ------------------------------------------------------- 무엇을 안 합쳤나

def test_프롬프트에_얹는_것은_갈라져_있다(tmp_path):
    """복습은 채널 위계 변경과 --note, 예습은 --hint. 여기가 합쳐지면 안 된다."""
    assert main_run.Runner(tmp_path, _args()).prompt_extra() == ""
    assert pre_run.Runner(tmp_path, _args()).prompt_extra() == ""

    assert main_run.Runner(tmp_path, _args(note="메모")).prompt_extra() == HEADER + "메모\n"
    assert pre_run.Runner(tmp_path, _args(hint="힌트")).prompt_extra() == HEADER + "힌트\n"

    policy = main_run.Runner.ANNOTATION_POLICY
    assert main_run.Runner(tmp_path, _args(annotation_evidence=True)).prompt_extra() == policy
    # 순서도 갈라내기 전과 같다 — 정책이 먼저, 사용자 지시가 뒤.
    both = main_run.Runner(tmp_path, _args(annotation_evidence=True, note="메모"))
    assert both.prompt_extra() == policy + HEADER + "메모\n"


def test_예습은_채널_위계_변경을_모른다():
    """복습만의 개념이다. 베이스로 새어 나가면 예습 프롬프트가 오염된다."""
    assert not hasattr(pre_run.Runner, "ANNOTATION_POLICY")


@pytest.mark.parametrize(
    ("mod", "flag", "value"),
    [(main_run, "note", "메모"), (pre_run, "hint", "힌트")])
def test_얹은_것이_실제로_모델까지_간다(tmp_path, monkeypatch, mod, flag, value):
    """**훅을 만들어 두고 부르지 않으면 조용히 사라진다.**

    `prompt_extra()` 가 무엇을 돌려주는지만 보면 이 실패를 못 잡는다 — `agent()` 가
    그걸 프롬프트에 안 붙여도 훅 자체는 멀쩡하기 때문이다. 그래서 모델이 받는
    문자열을 가로채서 본다.
    """
    seen = {}

    def fake(prompt, **kwargs):
        seen["prompt"] = prompt
        return {"cost_usd": 0.0, "usage": {}, "models": {}, "text": ""}

    monkeypatch.setattr(runbase, "run_agent", fake)
    mod.Runner(tmp_path, _args(**{flag: value})).agent("본문", "라벨")
    assert seen["prompt"].startswith("본문")
    assert HEADER + value in seen["prompt"]


@pytest.mark.parametrize("name", ["prep", "reproduce", "repair"])
def test_판단이_갈리는_셋은_각자_갖는다(name):
    """베이스로 올리면 한쪽 규칙이 다른 쪽에 새어 든다."""
    assert name in main_run.Runner.__dict__
    assert name in pre_run.Runner.__dict__


# ------------------------------------------------------- 배관이 실제로 도는가

def test_made는_산출물을_별표로도_찾는다(tmp_path):
    r = main_run.Runner(tmp_path, _args())
    assert r.made(None) is False
    assert r.made("없다.json") is False
    (tmp_path / "있다.json").write_text("{}", encoding="utf-8")
    assert r.made("있다.json") is True
    # 프롬프트는 커지면 파트로 갈린다. 그때도 「만들어졌다」로 읽어야 재개가 공짜다.
    (tmp_path / "prompt.cards.1of2.md").write_text("x", encoding="utf-8")
    assert r.made("prompt.cards.*.md") is True


def test_step은_산출물이_있으면_건너뛴다(tmp_path):
    (tmp_path / "있다.json").write_text("{}", encoding="utf-8")
    r = main_run.Runner(tmp_path, _args())
    ran = []
    r.step("이미 있음", "있다.json", lambda: ran.append(1))
    assert ran == []


def test_step은_force면_있어도_다시_돈다(tmp_path):
    (tmp_path / "있다.json").write_text("{}", encoding="utf-8")
    r = main_run.Runner(tmp_path, _args(force=True))
    ran = []
    r.step("강제", "있다.json", lambda: ran.append(1))
    assert ran == [1]


def test_step은_원장에_단계를_적는다(tmp_path):
    r = main_run.Runner(tmp_path, _args())
    r.step("새로 만듦", "새것.json",
           lambda: (tmp_path / "새것.json").write_text("{}", encoding="utf-8"))
    rows = [json.loads(x) for x in
            (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [x.get("step") for x in rows] == ["새로 만듦"]


def test_step은_산출물이_안_생기면_멈춘다(tmp_path):
    """조용히 지나가면 다음 단계가 없는 파일을 읽는다."""
    r = main_run.Runner(tmp_path, _args())
    with pytest.raises(Failed, match="안생김.json"):
        r.step("안 만듦", "안생김.json", lambda: None)


def test_sh는_실패하면_멈추고_예습은_넓힐_수_있다(tmp_path):
    """예습의 validate 는 계약 위반에 2 를 낸다. 그것까지 죽으면 한 줄 실행이 깨진다."""
    m = main_run.Runner(tmp_path, _args())
    with pytest.raises(Failed):
        m.sh("pdf2anki_없는모듈_확실히")
    p = pre_run.Runner(tmp_path, _args())
    assert p.sh("pdf2anki_없는모듈_확실히", ok=(0, 1)) == 1


@pytest.mark.parametrize("mod", [main_run, pre_run])
def test_defects는_카드_결함만_고른다(tmp_path, mod):
    """`genuinely_wrong` 은 카드가 아니라 사람이 볼 것이다. 수선 대상이 아니다."""
    (tmp_path / "items.reproduced.json").write_text(json.dumps({"cards": [
        {"id": "c1", "reproduce": {"reason": "needs_options"}},
        {"id": "c2", "reproduce": {"reason": "genuinely_wrong"}},
        {"id": "c3", "reproduce": {"reason": "question_ambiguous"}},
        {"id": "c4"},
    ]}), encoding="utf-8")
    got = [c["id"] for c in mod.Runner(tmp_path, _args()).defects()]
    assert got == ["c1", "c3"]


def test_defects는_파일이_없으면_빈_목록(tmp_path):
    assert main_run.Runner(tmp_path, _args()).defects() == []
