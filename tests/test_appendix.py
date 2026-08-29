"""필기본 뒤 족보 부록에 자리를 준다.

이 구간을 코드가 휴리스틱으로 찾을 필요가 없다 — **모델이 이미 짚고 있었다.**
28편의 꼬리 거절 48건 중 42건(24편)이 스스로 "필기자가 붙인 기출 문항 이미지"
같은 말을 적고 있었고, 사유가 없어서 `out_of_scope` 로 흘렀을 뿐이다.

`jokbo_appendix` 는 나머지 여섯 사유와 성격이 다르다 — "안 낸다" 가 아니라
**"여기서는 안 낸다, 기출 파트 소관이다"** 이다. 그래서 검토지에서도 갈라 놓고,
커버리지에서도 따로 센다.
"""

from pdf2anki.review import render
from pdf2anki.schema import PLAN_SCHEMA, REJECT_REASONS
from pdf2anki.validate import validate

from jsonschema import Draft202012Validator


def _prep(n_slides=10):
    return {"source": "테스트 강의", "slides": n_slides,
            "pages": [{"slide": i, "lecture_text": "", "annotations": [],
                       "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _plan(**kw):
    p = {"objectives": [{"objective": "무엇을 식별한다", "retrieval_targets": ["가"],
                         "slides": [1], "importance": "core"}],
         "rejected_candidates": [
             {"candidate": "표지", "reason": "decorative", "slides": [2]},
             {"candidate": "필기자가 붙인 기출 문항 이미지",
              "reason": "jokbo_appendix", "slides": [8, 9, 10]}]}
    p.update(kw)
    return p


def test_사유_목록에_자리가_있다():
    assert "jokbo_appendix" in REJECT_REASONS


def test_계획_스키마가_그_사유를_받는다():
    """스키마가 안 받으면 모델이 적어도 통째로 떨어진다."""
    errs = list(Draft202012Validator(PLAN_SCHEMA).iter_errors(_plan()))
    assert errs == [], errs


def test_커버리지가_부록_슬라이드를_따로_센다():
    raw = {"cards": [], "learning_plan": _plan()}
    _, s = validate(raw, _prep(), None)
    assert s["coverage"]["jokbo_appendix_slides"] == [8, 9, 10]


def test_부록은_누락_신호로_잡히지_않는다():
    """제외 기록이므로 '카드도 없고 기록도 없는 슬라이드' 가 아니다."""
    raw = {"cards": [], "learning_plan": _plan()}
    _, s = validate(raw, _prep(), None)
    assert not set([8, 9, 10]) & set(s["coverage"]["untouched_undeclared"])


def test_검토지가_뺀_것과_넘긴_것을_갈라_놓는다():
    md, _ = render(_plan(), _prep())
    assert "## 일부러 뺀 것" in md and "## 기출 파트로 넘긴 구간" in md
    # 부록은 '뺀 것' 목록에 섞이지 않는다
    dropped_block = md.split("## 일부러 뺀 것")[1].split("##")[0]
    assert "기출 문항 이미지" not in dropped_block


def test_부록이_없으면_그_절도_없다():
    plan = _plan(rejected_candidates=[{"candidate": "표지", "reason": "decorative",
                                       "slides": [2]}])
    md, _ = render(plan, _prep())
    assert "기출 파트로 넘긴 구간" not in md
