"""갈린 슬라이드의 카드만 갈아 끼운다 — 무엇을 남기고 무엇을 다시 쓰는가.

이 기능이 있는 이유는 돈이 아니라 **복습 이력**이다. guid 가 `(강의 ID, 정규화한
질문)` 에서 나와서, 통째로 다시 만들면 질문이 새로 쓰이고 이력이 죽는다.
`260903_05` 의 v1(53장)·v2(50장)를 실제 `guid_of` 로 맞대 보니 **7장(13%)만**
살아남았다. 그러니 여기서 지킬 것은 하나다 — **옮기는 카드의 질문에 손대지 않는다.**
"""

import json
import types

from quizgen import revise
from quizgen.build import guid_of
from quizgen.textutil import norm_key

# 앞에 한 장이 껴서 4·5 가 밀렸고, 3번은 갈렸고, 6번은 새 판에서 없어졌다.
DIFF = {"carry_map": {"1": 1, "2": 2, "4": 5, "5": 6},
        "slide_map": {"1": 1, "2": 2, "3": 3, "4": 5, "5": 6},
        "changed_slides": [3, 4]}


def card(cid, slide, q="질문", fmt="basic", media=None, source="lecture", **extra):
    c = {"id": cid, "q": q, "a": "답", "card_format": fmt, "card_type": "fact",
         "importance": "core", "source_type": source, "evidence_type": "lecture_text",
         "exam_hit": False, "slide_no": slide}
    if media:
        c["media"] = media
    c.update(extra)
    return c


# ── 카드를 세 갈래로 가른다 ────────────────────────────────────

def test_안_갈린_자리는_그대로_갈린_자리는_모델에게():
    cards = [card("c001", 1), card("c002", 3), card("c003", 4), card("c004", 6)]
    keep, review, orphan = revise.split_cards(cards, DIFF)
    assert [c["id"] for c in keep] == ["c001", "c003"]
    assert [c["id"] for c in review] == ["c002"]      # 3번은 갈렸다 — 버리지 않고 묻는다
    assert [c["id"] for c in orphan] == ["c004"]      # 6번은 새 판에 없다


def test_갈린_자리의_카드도_번호는_밀어_준다():
    """갈렸다고 번호를 안 밀면, 그대로 두기로 판정된 카드가 엉뚱한 지면을 가리킨다."""
    diff = {"carry_map": {}, "slide_map": {"4": 5}, "changed_slides": [5]}
    _, review, _ = revise.split_cards([card("c003", 4)], diff)
    assert review[0]["slide_no"] == 5


def test_옮긴_카드의_guid_가_그대로다():
    """이 하나가 이 기능의 전부다. 질문이 같으면 Anki 가 같은 노트로 받는다."""
    before = card("c003", 4, q="폐흡충의 성충은 어디에서 자리잡는가")
    keep, _, _ = revise.split_cards([before], DIFF)
    assert keep[0]["slide_no"] == 5                     # 번호는 밀렸는데
    assert guid_of("p260902_02", norm_key(keep[0]["q"]), keep[0]) == \
           guid_of("p260902_02", norm_key(before["q"]), before)      # guid 는 같다


def test_기출_카드는_강의록이_갈려도_그대로_둔다():
    cards = [card("c090", None, source="jokbo", evidence_type="jokbo_question")]
    keep, review, orphan = revise.split_cards(cards, DIFF)
    assert len(keep) == 1 and not review and not orphan


def test_옮길_때_계약에_없는_키를_떨군다():
    """`items.reproduced.json` 의 카드는 `reproduce` 를 달고 있다. 계약은
    `additionalProperties: false` 라 그대로 옮기면 검증이 통째로 떨어뜨린다."""
    keep, _, _ = revise.split_cards([card("c001", 1, reproduce={"verdict": "same"})], DIFF)
    assert "reproduce" not in keep[0]


def test_밀린_슬라이드는_그림_id_도_같이_민다():
    media = {"figure_id": "fig_p04_01", "occlusion_ids": ["occ_p04_02"]}
    keep, _, _ = revise.split_cards([card("c003", 4, fmt="image_basic", media=media)], DIFF)
    assert keep[0]["media"]["figure_id"] == "fig_p05_01"
    assert keep[0]["media"]["occlusion_ids"] == ["occ_p05_02"]


def test_밀리지_않은_슬라이드의_그림_id_는_안_건드린다():
    media = {"figure_id": "fig_p01_01"}
    keep, _, _ = revise.split_cards([card("c001", 1, fmt="image_basic", media=media)], DIFF)
    assert keep[0]["media"]["figure_id"] == "fig_p01_01"


# ── 계획 ───────────────────────────────────────────────────────

def test_갈린_슬라이드의_목표는_안_내린다():
    """그 자리에서 살아남은 카드의 `objective_id` 가 없는 목표를 가리키면 끈이 끊긴다.
    내리는 것은 슬라이드 자체가 없어진 목표뿐이다."""
    plan = {"objectives": [
        {"id": "o01", "objective": "A", "retrieval_targets": ["a"], "slides": [1, 2]},
        {"id": "o02", "objective": "B", "retrieval_targets": ["b"], "slides": [3]},
        {"id": "o03", "objective": "C", "retrieval_targets": ["c"], "slides": [4, 5]},
        {"id": "o04", "objective": "D", "retrieval_targets": ["d"], "slides": [6]},
    ], "jokbo_objectives": [{"id": "j01", "objective": "기출"}]}
    kept, dropped = revise.split_plan(plan, DIFF)
    assert [o["id"] for o in kept["objectives"]] == ["o01", "o02", "o03"]
    assert [o["id"] for o in dropped] == ["o04"]            # 6번 슬라이드가 없어졌다
    assert kept["objectives"][2]["slides"] == [5, 6]        # 번호도 같이 민다
    assert kept["jokbo_objectives"]                          # 기출 목표는 그대로


# ── 새 카드의 번호 ─────────────────────────────────────────────

def test_새_카드는_지워진_카드의_번호를_피한다(tmp_path):
    """옛 채점 결과는 지운 카드의 id 를 들고 있다. 번호를 다시 쓰면 `apply` 가
    **없어진 카드의 채점을 새 카드에 붙인다.**"""
    (tmp_path / "reproduce.grades.json").write_text(json.dumps(
        {"grades": [{"id": "c009", "verdict": "different"}]}), encoding="utf-8")
    keep = [card("c001", 1), card("c002", 2)]
    assert revise.next_number(revise.used_ids(tmp_path, keep), "c") == 10


def test_목표_번호는_남은_목표_다음부터():
    assert revise.next_number(["o01", "o07", None, "j03"], "o") == 8


# ── 합치기 ─────────────────────────────────────────────────────

def _runner(tmp_path, changed):
    args = types.SimpleNamespace(model="", timeout=60, force=False, note="",
                                 domain=None, jobs=1, annotation_evidence=False)
    r = revise.ReviseRunner(tmp_path, args)
    r.diff = {"changed_slides": changed}
    return r


def _stage(tmp_path, keep, plan, fresh, review=()):
    (tmp_path / "items.carry.json").write_text(json.dumps({"cards": keep}), encoding="utf-8")
    (tmp_path / "items.review.json").write_text(json.dumps({"cards": list(review)}),
                                                encoding="utf-8")
    (tmp_path / "plan.carry.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "revise.out.json").write_text(json.dumps(fresh), encoding="utf-8")


def test_합칠_때_새_카드에만_새_번호를_준다(tmp_path):
    keep = [card("c001", 1), card("c007", 5)]
    plan = {"objectives": [{"id": "o01", "objective": "A",
                            "retrieval_targets": ["a"], "slides": [1]}]}
    fresh = {"objectives": [{"id": "n1", "objective": "새 목표",
                             "retrieval_targets": ["x"], "slides": [3]}],
             "cards": [card(None, 3, q="새 질문", objective_id="n1")]}
    _stage(tmp_path, keep, plan, fresh)

    r = _runner(tmp_path, [3])
    r.merge_back()

    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    assert [c["id"] for c in merged] == ["c001", "c008", "c007"]   # 슬라이드 순서로 선다
    assert r.new_ids == ["c008"]
    got = json.loads((tmp_path / "plan.approved.json").read_text(encoding="utf-8"))
    assert [o["id"] for o in got["objectives"]] == ["o01", "o02"]
    assert merged[1]["objective_id"] == "o02"            # 임시 id 를 진짜 번호로 바꾼다


def test_갈린_슬라이드_밖의_새_카드는_안_받는다(tmp_path):
    """받으면 그 자리에 이미 있는 카드와 같은 것을 두 번 묻게 된다."""
    _stage(tmp_path, [card("c001", 1)], {"objectives": []},
           {"objectives": [], "cards": [card(None, 3, q="맞는 자리"),
                                        card(None, 1, q="남의 자리")]})
    r = _runner(tmp_path, [3])
    r.merge_back()
    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    assert [c["q"] for c in merged] == ["질문", "맞는 자리"]


# ── 처분 ───────────────────────────────────────────────────────
#
# 6쌍 실측에서 갈린 슬라이드의 카드 16장 중 8장이 **오타·형광펜** 때문에 걸렸다.
# 그 카드들을 다시 쓰면 이력만 죽는다. 그래서 갈래를 셋으로 두고 기본을 keep 으로 뒀다.

def test_오타는_그대로_두면_카드가_한_글자도_안_바뀐다(tmp_path):
    review = [card("c010", 3, q="D. pacificum 의 유행 지역은?"),
              card("c011", 3, q="충낭 안에는 무엇이 있는가?")]
    fresh = {"slides": [{"slide": 3, "change_kind": "typo", "note": "facificum→pacificum"}],
             "verdicts": [{"id": "c010", "verdict": "keep", "why": "카드는 이미 pacificum"},
                          {"id": "c011", "verdict": "keep", "why": "무관"}],
             "cards": []}
    _stage(tmp_path, [card("c001", 1)], {"objectives": []}, fresh, review)
    r = _runner(tmp_path, [3])
    r.merge_back()

    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    assert [c["id"] for c in merged] == ["c001", "c010", "c011"]
    assert merged[1]["q"] == "D. pacificum 의 유행 지역은?"
    assert r.new_ids == []                 # 다시 검사할 것도 없다 — 돈이 안 든다


def test_내용이_갈리면_그_카드만_고쳐_끼운다(tmp_path):
    review = [card("c045", 3, q="자충이 정기출현성을 보이지 않는 이유는?"),
              card("c046", 3, q="매개체는 무엇인가?")]
    fixed = card("c045", 3, q="자충이 정기출현성을 보이지 않는 이유는?")
    fixed["a"] = "microfilaria 가 혈액으로 잘 나오지 않기 때문이다"
    fresh = {"slides": [{"slide": 3, "change_kind": "content", "note": "교수 질의 답변"}],
             "verdicts": [{"id": "c045", "verdict": "revise", "why": "옛 필기가 근거였다"},
                          {"id": "c046", "verdict": "keep", "why": "무관"}],
             "cards": [fixed]}
    _stage(tmp_path, [], {"objectives": []}, fresh, review)
    r = _runner(tmp_path, [3])
    r.merge_back()

    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    got = {c["id"]: c for c in merged}
    assert got["c045"]["a"].startswith("microfilaria")
    assert got["c046"]["a"] == "답"                    # 옆 카드는 안 건드린다
    assert r.new_ids == ["c045"]                       # 글자가 달라진 것만 다시 검사한다


def test_버리라고_하면_뺀다(tmp_path):
    review = [card("c050", 3)]
    fresh = {"verdicts": [{"id": "c050", "verdict": "drop", "why": "근거가 사라졌다"}],
             "cards": []}
    _stage(tmp_path, [], {"objectives": []}, fresh, review)
    r = _runner(tmp_path, [3])
    r.merge_back()
    assert json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"] == []


def test_처분을_안_말한_카드는_그대로_두고_적어_둔다(tmp_path):
    """모델이 빠뜨린 카드를 버리는 쪽으로 두면 이력이 조용히 죽는다.
    남기되 **조용히 남기지는 않는다.**"""
    _stage(tmp_path, [], {"objectives": []}, {"verdicts": [], "cards": []}, [card("c060", 3)])
    r = _runner(tmp_path, [3])
    r.merge_back()
    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    assert [c["id"] for c in merged] == ["c060"]
    report = json.loads((tmp_path / "revise.report.json").read_text(encoding="utf-8"))
    assert report["silent"] == ["c060"]
    assert report["counts"] == {"carried": 0, "reviewed": 1, "kept": 1, "revised": 0,
                                "dropped": 0, "added": 0, "total": 1}


def test_고친다고_해_놓고_카드를_안_내면_원본이_남는다(tmp_path):
    _stage(tmp_path, [], {"objectives": []},
           {"verdicts": [{"id": "c070", "verdict": "revise", "why": "…"}], "cards": []},
           [card("c070", 3, q="원래 질문")])
    r = _runner(tmp_path, [3])
    r.merge_back()
    merged = json.loads((tmp_path / "items.raw.json").read_text(encoding="utf-8"))["cards"]
    assert [c["q"] for c in merged] == ["원래 질문"]
    assert r.new_ids == []
