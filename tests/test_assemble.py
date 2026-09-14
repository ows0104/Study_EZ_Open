"""반복 문항 묶음이 복습 프롬프트에 실린다.

`jokbo.py` 는 `repeat_pairs` 를 계산해 두는데 복습 지침은 오래 그것을 버리고
`repeat_rate` 숫자 한 줄만 썼다. 예습 쪽만 쌍 목록을 모델에게 보여 주고 있었다.
관리자가 막아 달라고 한 것이 그 자리다 — *"어 이거 아까 봤던 거네, 선지만 바뀐듯"*.
"""

from quizgen.assemble import (
    ASK_ANNOTATION,
    STRATEGY_ALIAS,
    apply_confirmed_strategy,
    decide_strategy,
    guidance_without_jokbo,
    jokbo_guidance,
    photo_profile,
    repeat_block,
    repeat_clusters,
    resolve_auto_strategy,
)


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


def test_교수교체에_족보중심을_명시해도_유임이라고_쓰지_않는다():
    """족보 중심을 명시한 경우에도 교수 유임이라고 거짓 단언하지 않는다."""
    pairs = [{"a": "2020-68", "b": "2023-61", "jaccard": 1.0}]
    st = _stats(pairs, professor_changed_2026=True, jokbo_weight_hint="low")
    g = jokbo_guidance(st, "16-18 소아질환", strategy="jokbo",
                       questions=_qs(("2023", "61")))
    assert "2023-61 · 2020-68" in g
    assert "이 강의의 전략: `족보 중심`" in g
    assert "올해 담당 교수는 바뀌었지만" in g
    assert "담당 교수가 그대로" not in g
    assert "중요도의 근거가 아니다" not in g


def test_쌍_목록이_상한에_닿으면_잘렸다고_적는다():
    """조용히 자르지 않는다. 잘린 채로 묶으면 묶음이 덜 이어진다."""
    pairs = [{"a": f"2020-{i}", "b": f"2023-{i}", "jaccard": 1.0} for i in range(40)]
    assert "상한(40개)에 닿았다" in repeat_block(_stats(pairs), None, True)


def test_사진_중심은_명시적으로_고를_수_있다():
    assert STRATEGY_ALIAS["사진"] == "image"
    assert STRATEGY_ALIAS["사진 중심"] == "image"
    assert STRATEGY_ALIAS["image"] == "image"
    assert STRATEGY_ALIAS["photo"] == "image"


def test_사진_중심은_image_basic만_쓰라고_지시한다():
    """2026-08-27 관리자 지시로 오클루전이 **금지**로 뒤집혔다.

    앞면이 필기 걷힌 사진 한 장이어야 하는데 오클루전 앞면만 `annotated` 에서
    뜬다(`build.MediaMaker.occlusion`). 그래서 「라벨 회수에는 오클루전」이던
    이전 규칙이 여기서는 성립하지 않는다.
    """
    g = jokbo_guidance(_stats([]), "PRAC 실습", strategy="image")
    assert "사진 판독 덱" in g
    assert "쓸 만한 사진 하나가 카드 하나다" in g
    assert "전부 `image_basic` 으로 만든다" in g
    assert "`image_occlusion` 은 이 실습에서 쓰지 않는다" in g


def test_기출이_없어도_사진_중심_선택이_사라지지_않는다():
    g = guidance_without_jokbo("image")
    assert "이 강의의 전략: `사진 중심`" in g
    assert "기출 조각이 없으므로" in g


def test_자동_전략_우선순위는_사진실습_높은반복_확인_기본_순이다():
    high_changed = _stats([], repeat_rate=0.35, professor_changed_2026=True)
    assert decide_strategy(high_changed, practical=True, image_rich=True)[0] == "image"
    assert decide_strategy(high_changed)[0] == ASK_ANNOTATION

    high_stayed = _stats([], repeat_rate=0.35, professor_changed_2026=False)
    assert decide_strategy(high_stayed)[0] == "jokbo"

    medium = _stats([], repeat_rate=0.25, jokbo_weight_hint="normal")
    assert decide_strategy(medium, practical=True, image_rich=True)[0] == "image"

    changed = _stats([], repeat_rate=0.25, professor_changed_2026=True,
                     jokbo_weight_hint="normal")
    assert decide_strategy(changed)[0] == ASK_ANNOTATION

    low = _stats([], repeat_rate=0.19, jokbo_weight_hint="low")
    assert decide_strategy(low)[0] == ASK_ANNOTATION
    assert decide_strategy(medium)[0] == "base"


def test_사진다수는_사진_슬라이드_10장과_30퍼센트를_모두_넘어야_한다():
    prep = {"source": "[260819_05] 피부병리 실습.pdf", "slides": 30,
            "pages": [{"lecture_figures": ([{}] if i < 10 else [])} for i in range(30)]}
    p = photo_profile(prep)
    assert p["practical"] is True
    assert p["image_rich"] is True
    assert p["figure_slides"] == 10

    prep["slides"] = 40
    assert photo_profile(prep)["image_rich"] is False


def test_필기중심_확인은_yes가_기본이고_no는_기본전략이다():
    yes, _ = resolve_auto_strategy(ASK_ANNOTATION, "교수 교체", interactive=True,
                                   input_fn=lambda _: "")
    no, _ = resolve_auto_strategy(ASK_ANNOTATION, "교수 교체", interactive=True,
                                  input_fn=lambda _: "n")
    assert yes == "annotation"
    assert no == "base"


def test_물을_자리가_없으면_기본으로_간다():
    """전에는 여기서 예외를 올려 「명시적 전략을 요구」했다. 그 길이 실제로 쓰인
    적은 없다 — 러너가 자식의 stdin을 안 막아서 `isatty()`가 참으로 나왔고, 물음이
    사람 없는 자리에 떠서 `input()`이 180분 동안 잠들었다(2026-08-25 병리학/260825_03 ·
    2026-08-31 기생충학/260831_01). 이제 stdin을 막고(`studyez.agent._run`) 이 갈래가
    실제로 쓰인다 — 관리자 지시로 실패가 아니라 기본이다(2026-09-01)."""
    strategy, why = resolve_auto_strategy(ASK_ANNOTATION, "낮은 반복률", interactive=False)
    assert strategy == "base"
    # 왜 기본이 됐는지와, 사람이 고르는 길이 어디인지가 같이 남아야 한다.
    assert "낮은 반복률" in why and "--strategy" in why


def test_이미_답한_소아질환만_필기중심이고_나머지는_기본이다():
    pediatric = {"source": "[260820_03]소아질환의 병태생리(2).pdf"}
    genetic = {"source": "[260819_01]단일유전자질환.pdf"}
    assert apply_confirmed_strategy(ASK_ANNOTATION, "교수 교체", pediatric)[0] == "annotation"
    assert apply_confirmed_strategy(ASK_ANNOTATION, "교수 교체", genetic)[0] == "base"


def test_새로운_확인필요_강의는_저장된_선택을_빌리지_않는다():
    future = {"source": "[260901_01]새 강의.pdf"}
    assert apply_confirmed_strategy(ASK_ANNOTATION, "교수 교체", future)[0] == ASK_ANNOTATION


def test_읽을_것이_없어도_기본으로_간다():
    """`isatty()` 만으로는 못 가른다 — 윈도우의 `NUL` 은 문자 장치라 러너가
    `stdin=DEVNULL` 로 막아도 참으로 나온다. 2026-09-01 에 그래서 물음이 그대로
    뜨고 `EOFError` 로 죽었다(기생충학/260831_01, quizgen 종료 코드 1)."""
    def eof(_):
        raise EOFError

    strategy, why = resolve_auto_strategy(ASK_ANNOTATION, "낮은 반복률",
                                          interactive=True, input_fn=eof)
    assert strategy == "base"
    assert "--strategy" in why
