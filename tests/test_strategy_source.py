"""전략을 누가 정했는가 — 출처가 셋인데 하나로 뭉뚱그려져 있었다.

    CLI `--strategy`            이번에 사람이 준 것
    사람이 답해 둔 확정표         `CONFIRMED_STRATEGY_OVERRIDES`
    `run.config.json` 의 기억     재개를 한 줄로 만들려는 장치
    자동 판정

셋을 구별하지 못해 **폴더가 기억한 값을 「사람이 --strategy 로 지정했다」고 적었다.**
그 거짓 문구 때문에 08-25에 관리자가 `260819_01·02·03` 을 「기본」으로 답해 둔 것이
08-30까지 한 번도 안 먹었다 — 그 폴더들에 08-23의 「필기 중심」이 저장돼 있었기 때문이다.
그 사이 재실행한 편들은 「기출 전용 카드는 만들지 마라」 지침을 받아 기출 0장으로 나왔다.

여기서 지키는 것은 **기억이 사람의 답을 이기지 못한다**는 것이다.
"""

import json
import types

import pytest

from quizgen import run as main_run
from quizgen.assemble import CONFIRMED_STRATEGY_OVERRIDES, confirmed_strategy

# 실제로 어긋났던 편. 자동 판정은 「기본」, 폴더 기억은 「필기 중심」이었다.
CONFLICTED = "260819_02"
SOURCE = f"[{CONFLICTED}] 멘델법칙을 따르지 않는 유전자 질환(강경훈)_한준우v2.pdf"


def _args(**over):
    base = {"domain": None, "model": "", "timeout": 600, "force": False, "jobs": 4,
            "repair_rounds": 2, "note": "", "annotation_evidence": False,
            "no_annotation_evidence": False, "skip_reproduce": False, "pdf": None,
            "jokbo": None, "jokbo_dir": "없는폴더", "lecture": "", "strategy": "auto",
            "strategy_from": "auto",
            # `plan_strategy` 끝에서 `save_config` 가 쓰는 것들
            "deck": "병리학::시험용", "id": "p999999_99", "pdf_name": "lecture.pdf",
            "subject": "병리학"}
    base.update(over)
    return types.SimpleNamespace(**base)


def _runner(tmp_path, **over):
    (tmp_path / "prep.json").write_text(json.dumps(
        {"source": SOURCE, "slides": 4,
         "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                   for i in range(1, 5)]}), encoding="utf-8")
    return main_run.Runner(tmp_path, _args(**over))


def test_확정표가_이_강의를_기본으로_들고_있다():
    """이 시험 전체가 그 전제 위에 선다. 표가 바뀌면 여기서 먼저 깨진다."""
    assert CONFIRMED_STRATEGY_OVERRIDES.get(CONFLICTED) == "base"


def test_확정표를_밖에서도_물어볼_수_있다():
    assert confirmed_strategy({"source": SOURCE}) == "base"
    assert confirmed_strategy({"source": "[999999_99] 없는 강의.pdf"}) is None


# ------------------------------------------------- 출처마다 다르게 말한다

def test_사람이_준_것은_사람이_준_것이라고_말한다(tmp_path, capsys):
    r = _runner(tmp_path, strategy="필기", strategy_from="cli")
    r.plan_strategy()
    assert r.strategy == "annotation"                 # CLI 가 가장 세다
    assert "사람이 --strategy 로 지정했다" in r.strategy_why


def test_기억은_사람의_답을_이기지_못한다(tmp_path, capsys):
    """08-25의 답이 08-23의 기억에 막혀 있던 자리다."""
    r = _runner(tmp_path, strategy="필기", strategy_from="saved")
    r.plan_strategy()
    assert r.strategy == "base"                       # 확정표가 이긴다
    assert "사람이 답해 둔" in r.strategy_why
    # `strategy_why` 에도 「덮었다」가 들어 있어 그 말로는 못 가른다 — 경고 고유 문구로 본다.
    assert "⚠ 폴더가 기억한 전략" in capsys.readouterr().out


def test_기억이_지금_판정과_다르면_알린다(tmp_path, capsys):
    """확정표에 없는 강의. 기억이 이기되 어긋난 것은 말한다."""
    r = _runner(tmp_path, strategy="사진", strategy_from="saved")
    r.args.lecture = "[999999_99] 확정표에 없는 강의"
    (tmp_path / "prep.json").write_text(json.dumps(
        {"source": "[999999_99] 확정표에 없는 강의.pdf", "slides": 4,
         "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                   for i in range(1, 5)]}), encoding="utf-8")
    r.plan_strategy()
    assert r.strategy == "image"                      # 기억이 이긴다
    assert "폴더가 기억한 값을 이어 쓴다" in r.strategy_why
    assert "다르다" in capsys.readouterr().out


def test_자동_판정은_예전_그대로다(tmp_path, capsys):
    r = _runner(tmp_path, strategy="auto", strategy_from="auto")
    r.plan_strategy()
    assert r.strategy == "base"
    assert "사람이 --strategy" not in r.strategy_why
    assert "폴더가 기억한" not in r.strategy_why


# ------------------------------------------------- 필기 중심이면 필기를 근거로 쓴다

@pytest.mark.parametrize(("strategy", "expect"), [("필기", True), ("기본", False)])
def test_필기_근거_인정은_전략을_따라간다(tmp_path, strategy, expect):
    r = _runner(tmp_path, strategy=strategy, strategy_from="cli")
    r.plan_strategy()
    assert r.annotation is expect


# ------------------------------------------------- assemble 은 누가 정했는지 모른다

def test_assemble은_사람이_정했다고_단언하지_않는다():
    """`run.py` 는 자동 판정한 값도 `--strategy` 로 넘긴다. 받는 쪽은 출처를 모른다."""
    from quizgen import assemble
    src = (assemble.__file__.replace(".pyc", ".py"))
    with open(src, encoding="utf-8") as fh:
        body = fh.read()
    assert '"전략을 인자로 받았다 (부른 쪽이 정했다)"' in body
    assert 'why = "사람이 --strategy 로 지정했다"' not in body
