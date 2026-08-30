"""계획과 카드를 잇는 끈.

두 방향을 본다.

    ① 목표를 세웠는데 카드가 안 갔다   `objectives_without_card`
    ② 카드가 어느 목표에도 안 닿는다   `off_plan`

**①은 있었지만 죽어 있었다.** 「그 슬라이드에 카드가 하나라도 있으면 맞혔다」로
세는 절이 있어서 39편 전부에서 0을 찍었다. 위치가 아니라 내용으로 봐야 한다.
그 절을 뺀 뒤 실측은 목표 1,283개 중 277개(21.6%)다.

**②는 아예 없었다.** `cards.md` 가 「계획에 없는 내용을 추가하지 않는다」고 적고
있었는데 아무도 확인하지 않았다. 실측 109장.

가장 좋은 길은 **카드가 자기 목표의 id 를 적는 것**이다(`objective_id`). 그러면
둘 다 추측이 아니라 사실이 된다. 2026-08-30 이전 편에는 그 칸이 없어서 글자
유사도로 물러난다 — 아래에서 두 길을 다 건다.
"""

import pytest

from pdf2anki.review import stamp_ids
from pdf2anki.validate import validate

MECH = "세포자멸사에서 caspase 연쇄가 어떻게 시작되는지 설명한다"
TARGET = "내인성 경로: mitochondria 에서 cytochrome c 가 나온다"


def _prep(n_slides=10):
    """1번 슬라이드에만 그림 하나를 둔다 — 이미지 카드가 hard 로 안 떨어지게."""
    pages = [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
             for i in range(1, n_slides + 1)]
    pages[0]["lecture_figures"] = [{"id": "fig_p01_01"}]
    pages[0]["occlusion_candidates"] = [{"id": "occ_p01_01", "figure_id": "fig_p01_01",
                                         "label": "라벨"}]
    return {"slides": n_slides, "pages": pages}


def _plan(**kw):
    o = {"objective": MECH, "retrieval_targets": [TARGET], "slides": [1, 2]}
    o.update(kw)
    return {"objectives": [o]}


def _card(q, a="답", **kw):
    c = {"q": q, "a": a, "explanation": "왜 그런지", "card_format": "basic",
         "card_type": "fact", "importance": "core", "source_type": "lecture",
         "evidence_type": "lecture_text", "exam_hit": False, "slide_no": 1}
    c.update(kw)
    return c


def _run(cards, plan=None):
    return validate({"cards": cards, "learning_plan": plan or _plan()}, _prep(), None)


# ------------------------------------------------- 목표에 id 를 찍는다

def test_승인할_때_목표에_id를_찍는다():
    plan = {"objectives": [{"objective": "a", "retrieval_targets": ["x"], "slides": [1]},
                           {"objective": "b", "retrieval_targets": ["y"], "slides": [2]}],
            "jokbo_objectives": [{"objective": "c", "retrieval_targets": ["z"],
                                  "jokbo_refs": ["2024-1"]}]}
    stamp_ids(plan)
    assert [o["id"] for o in plan["objectives"]] == ["o01", "o02"]
    assert [o["id"] for o in plan["jokbo_objectives"]] == ["j01"]


def test_두_번_찍어도_안_바뀐다():
    """승인을 다시 돌려도 이미 나간 카드의 `objective_id` 가 어긋나면 안 된다."""
    plan = _plan()
    stamp_ids(plan)
    first = plan["objectives"][0]["id"]
    stamp_ids(plan)
    assert plan["objectives"][0]["id"] == first


# ------------------------------------------------- ① 목표에 카드가 갔는가

def test_같은_슬라이드에_있다고_목표를_맞힌_것이_아니다():
    """이 절 때문에 계수기가 39편 내내 0을 찍었다. 위치는 내용의 근거가 아니다."""
    kept, s = _run([_card("전혀 다른 것을 묻는다. 병리학의 역사는?", slide_no=1)])
    assert len(kept) == 1
    assert s["coverage"]["objectives_without_card"] == [MECH]


def test_내용이_닿으면_맞힌_것이다():
    kept, s = _run([_card(f"{MECH} 중 {TARGET} 은 무엇인가?", a=TARGET)])
    assert s["coverage"]["objectives_without_card"] == []


def test_objective_id가_있으면_그것으로_잇는다():
    """글자가 하나도 안 겹쳐도 카드가 스스로 목표를 대면 맞힌 것이다."""
    plan = _plan(id="o01")
    kept, s = _run([_card("전혀 다른 글자", objective_id="o01")], plan)
    assert s["coverage"]["objectives_without_card"] == []


def test_id를_쓰는_편에서는_글자로_물러나지_않는다():
    """한 장이라도 id 를 적었으면 그 편은 id 로만 센다 — 절반만 적으면 드러나야 한다."""
    plan = _plan(id="o01")
    kept, s = _run([_card(f"{MECH} 은?", a=TARGET, objective_id="o99")], plan)
    assert s["coverage"]["objectives_without_card"] == [MECH]


# ------------------------------------------------- ② 계획에 없는 것을 물었는가

def test_계획에서_먼_카드는_표시한다():
    kept, s = _run([_card("Rokitansky 가 베토벤을 부검해 확인한 뼈 질환은?",
                          a="Paget disease of bone")])
    assert "off_plan" in kept[0]["review_flags"]


def test_계획에_닿는_카드는_표시하지_않는다():
    kept, s = _run([_card(f"{TARGET} 는 어느 경로인가?", a=MECH)])
    assert "off_plan" not in kept[0]["review_flags"]


@pytest.mark.parametrize("fmt", ["ox", "image_basic", "image_occlusion"])
def test_질문이_짧은_형식은_글자로_재지_않는다(fmt):
    """O/X·이미지는 질문이 짧아 유사도가 무조건 낮다 — 실측 25~34%가 문턱 아래인데
    대부분 정상 카드였다. 형식으로 거르지 않으면 그 전부가 거짓 신호가 된다."""
    kw = {"card_format": fmt}
    if fmt == "ox":
        kw["a"] = "O"
    if fmt == "image_basic":
        kw["evidence_type"] = "lecture_figure"
        kw["media"] = {"figure_id": "fig_p01_01"}
    if fmt == "image_occlusion":
        kw["evidence_type"] = "lecture_figure"
        kw["media"] = {"figure_id": "fig_p01_01", "occlusion_ids": ["occ_p01_01"]}
        kw["a"] = "라벨"          # 가린 라벨은 답에 있어야 한다 (별도 hard 검사)
    kept, s = _run([_card("전혀 다른 짧은 물음", **kw)])
    assert kept, "카드가 hard 로 떨어지면 이 시험의 뜻이 없다"
    assert "off_plan" not in kept[0]["review_flags"]


def test_없는_목표를_대면_형식과_무관하게_표시한다():
    """id 가 있으면 글자를 안 보므로 O/X 도 잡힌다."""
    plan = _plan(id="o01")
    kept, s = _run([_card("짧은 물음", a="O", card_format="ox", objective_id="o77")], plan)
    assert "off_plan" in kept[0]["review_flags"]


def test_기출_카드는_강의록_계획으로_재지_않는다():
    """기출은 계획이 따로다(`jokbo_objectives`). 여기서 재면 전부 계획 밖이 된다."""
    kept, s = _run([_card("기출이 물은 것은?", source_type="jokbo", slide_no=None,
                          evidence_type="jokbo_question",
                          jokbo_ref={"year": "2024", "no": "12", "role": "source"})])
    assert kept
    assert "off_plan" not in kept[0]["review_flags"]

def test_승인이_id를_찍어_파일로_쓴다(tmp_path):
    """`--approve` 가 `copyfile` 이 아니라 JSON 을 쓰게 바뀌었다.

    형제 키를 잃으면 `rejected_candidates`(제외 근거)가 통째로 날아간다.
    """
    import json

    from pdf2anki import review

    plan = {"objectives": [{"objective": MECH, "retrieval_targets": [TARGET],
                            "slides": [1]}],
            "rejected_candidates": [{"slides": [9], "candidate": "표지 슬라이드",
                                     "reason": "표지"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan, ensure_ascii=False),
                                        encoding="utf-8")
    prep = _prep()
    prep["source"] = "강의록.pdf"               # review 는 훑어보기 표를 만드느라 더 읽는다
    for page in prep["pages"]:
        page.update(lecture_text="", annotations=[])
    (tmp_path / "prep.json").write_text(json.dumps(prep), encoding="utf-8")

    assert review.main([str(tmp_path), "--approve"]) == 0
    got = json.loads((tmp_path / "plan.approved.json").read_text(encoding="utf-8"))
    assert got["objectives"][0]["id"] == "o01"
    assert got["rejected_candidates"] == plan["rejected_candidates"]
