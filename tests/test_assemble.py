"""반복 문항 묶음이 복습 프롬프트에 실린다.

`jokbo.py` 는 `repeat_pairs` 를 계산해 두는데 복습 지침은 오래 그것을 버리고
`repeat_rate` 숫자 한 줄만 썼다. 예습 쪽만 쌍 목록을 모델에게 보여 주고 있었다.
관리자가 막아 달라고 한 것이 그 자리다 — *"어 이거 아까 봤던 거네, 선지만 바뀐듯"*.
"""

from pdf2anki.assemble import jokbo_guidance, repeat_block, repeat_clusters


def _stats(pairs, **kw):
    s = {"n_questions": 20, "repeat_rate": 0.5, "repeat_pairs": pairs,
         "professors_by_year": {"26": ["김"], "25": ["김"]}, "professor_2026": ["김"],
         "professor_changed_2026": False, "jokbo_weight_hint": "high"}
    s.update(kw)
    return s


def _qs(*keys):
    return [{"year": y, "no": n, "stem": f"{y}년 {n}번 본문"} for y, n in keys]


def test_사슬로_이어진_쌍은_한_묶음이_된다():
    """쌍으로 늘어놓으면 같은 주제가 세 번 보인다. 이어 붙여야 한 주제로 선다."""
    pairs = [{"a": "2020-68", "b": "2022-55", "jaccard": 1.0},
             {"a": "2022-55", "b": "2023-61", "jaccard": 0.67},
             {"a": "2023-61", "b": "2025-103", "jaccard": 1.0}]
    cl = repeat_clusters(_stats(pairs))
    assert len(cl) == 1
    assert cl[0]["members"] == ["2025-103", "2023-61", "2022-55", "2020-68"]


def test_대표는_가장_최근_연도다():
    pairs = [{"a": "2020-68", "b": "2023-61", "jaccard": 1.0}]
    cl = repeat_clusters(_stats(pairs), _qs(("2020", "68"), ("2023", "61")))
    assert cl[0]["members"][0] == "2023-61"
    assert cl[0]["stem"] == "2023년 61번 본문"


def test_묶음이_큰_것부터_실린다():
    pairs = [{"a": "2020-1", "b": "2023-1", "jaccard": 1.0},
             {"a": "2020-2", "b": "2022-2", "jaccard": 1.0},
             {"a": "2022-2", "b": "2023-2", "jaccard": 1.0}]
    cl = repeat_clusters(_stats(pairs))
    assert [len(c["members"]) for c in cl] == [3, 2]


def test_반복이_없으면_블록도_없다():
    assert repeat_block(_stats([]), None, True) == ""


def test_지침에_묶음과_금지가_함께_실린다():
    pairs = [{"a": "2020-68", "b": "2023-61", "jaccard": 1.0}]
    g = jokbo_guidance(_stats(pairs), "21 종양", questions=_qs(("2023", "61")))
    assert "2023-61 · 2020-68" in g
    assert "따로 카드화하지 마라" in g


def test_교수가_바뀌면_반복을_중요도로_읽지_말라고_적는다():
    """묶음 자체는 그대로 보여 준다 — 중복은 교수가 바뀌어도 중복이다."""
    pairs = [{"a": "2020-68", "b": "2023-61", "jaccard": 1.0}]
    st = _stats(pairs, professor_changed_2026=True, jokbo_weight_hint="low")
    g = jokbo_guidance(st, "16-18 소아질환", questions=_qs(("2023", "61")))
    assert "2023-61 · 2020-68" in g
    assert "중요도의 근거가 아니다" in g


def test_쌍_목록이_상한에_닿으면_잘렸다고_적는다():
    """조용히 자르지 않는다. 잘린 채로 묶으면 묶음이 덜 이어진다."""
    pairs = [{"a": f"2020-{i}", "b": f"2023-{i}", "jaccard": 1.0} for i in range(40)]
    assert "상한(40개)에 닿았다" in repeat_block(_stats(pairs), None, True)
