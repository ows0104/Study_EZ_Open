"""기출 ref 검사의 갈래.

조각이 판정할 수 있는 자리와 그렇지 않은 자리를 가른다. 갈래를 두기 전에는 하나였고,
28편 실측에서 하드 삭제된 기출 카드 17장이 **전부** 조각이 판정할 수 없는 자리였다 —
필기자가 강의록 뒤에 조각보다 오래된 기출을 직접 붙여 놓기 때문이다.
"""

from pdf2anki.validate import validate


def _prep(n_slides=10):
    return {"slides": n_slides,
            "pages": [{"slide": i, "lecture_figures": [], "occlusion_candidates": []}
                      for i in range(1, n_slides + 1)]}


def _jokbo(*keys):
    return {"questions": [{"year": y, "no": n} for y, n in keys]}


def _card(q, **kw):
    c = {"q": q, "a": "답", "explanation": "왜 그런지", "card_format": "basic",
         "card_type": "fact", "importance": "core", "source_type": "lecture",
         "evidence_type": "lecture_text", "exam_hit": False, "slide_no": 1}
    c.update(kw)
    return c


def _jokbo_card(q, year, no, **kw):
    kw.setdefault("evidence_type", "jokbo_question")
    return _card(q, source_type="jokbo", slide_no=None,
                 jokbo_ref={"year": year, "no": no, "role": "source"}, **kw)


def _codes(s):
    return [d["code"] for d in s["dropped"]]


def test_조각에_있는_문항을_가리키면_그냥_통과한다():
    raw = {"cards": [_jokbo_card("기출이 물은 것은?", "2022", "58")]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert len(kept) == 1
    assert "jokbo_ref_outside_slice" not in s["flag_counts"]


def test_조각이_그_연도를_드는데_번호가_없으면_지운다():
    """지어낸 번호는 여전히 근거 없음이다. 이 갈래는 살려 둔다."""
    raw = {"cards": [_jokbo_card("기출이 물은 것은?", "2022", "999")]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert kept == []
    assert _codes(s) == ["jokbo_ref_not_found"]


def test_조각이_안_드는_연도면_지우지_않고_표시한다():
    """필기 부록에서 온 기출이다. 조각은 이 연도를 판정할 수 없다."""
    raw = {"cards": [_jokbo_card("기출이 물은 것은?", "2018", "주4",
                                 evidence_type="jokbo_objection")]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert len(kept) == 1
    assert "jokbo_ref_outside_slice" in kept[0]["review_flags"]
    assert s["dropped"] == []


def test_조각이_없으면_기출_ref_를_맞추지_않는다():
    raw = {"cards": [_jokbo_card("기출이 물은 것은?", "2018", "주4")]}
    kept, s = validate(raw, _prep(), None)
    assert len(kept) == 1
    assert not [f for f in kept[0]["review_flags"] if f.startswith("jokbo_ref")]


def test_강의록_카드의_exam_hit_근거도_맞춰_본다():
    """카드의 근거는 슬라이드이므로 떨어뜨리지 않는다. 표시만 한다.

    이 검사가 없던 동안 28편에서 강의록 카드에 달린 ref 649개 중 52개가 조각에
    없었고 아무도 몰랐다.
    """
    raw = {"cards": [
        _card("강의록이 가르친 것은?", exam_hit=True,
              jokbo_ref={"year": "2022", "no": "999", "role": "exam_hit_evidence"}),
        _card("다른 것은?", exam_hit=True,
              jokbo_ref={"year": "2018", "no": "20", "role": "exam_hit_evidence"}),
    ]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert len(kept) == 2 and s["dropped"] == []
    assert "jokbo_ref_not_found" in kept[0]["review_flags"]
    assert "jokbo_ref_outside_slice" in kept[1]["review_flags"]


# ── 기출 파트의 외부 의학지식 ─────────────────────────────────────

def test_기출_카드는_외부_의학지식을_근거로_쓸_수_있다():
    """기출은 복원된 것이라 문항도 정답도 어긋날 수 있다. 그 자리를 메운다."""
    raw = {"cards": [_jokbo_card("정답이 무엇인가?", "2022", "58",
                                 evidence_type="medical_knowledge",
                                 review_note="족보 정답표는 3번인데 선지 3은 …")]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert len(kept) == 1 and s["dropped"] == []
    assert "corrected_without_note" not in kept[0]["review_flags"]


def test_강의록_카드에_붙으면_떨어뜨린다():
    """강의록은 정본이다. 밖에서 메우기 시작하면 근거 위계가 무너진다."""
    raw = {"cards": [_card("강의록이 가르친 것은?", evidence_type="medical_knowledge")]}
    kept, s = validate(raw, _prep(), None)
    assert kept == []
    assert _codes(s) == ["medical_knowledge_on_lecture"]


def test_고친_것을_안_적으면_표시한다():
    """카드는 살린다 — 무엇이 고쳐졌는지는 기계가 모른다."""
    raw = {"cards": [_jokbo_card("정답이 무엇인가?", "2022", "58",
                                 evidence_type="medical_knowledge")]}
    kept, s = validate(raw, _prep(), _jokbo(("2022", "58")))
    assert len(kept) == 1
    assert "corrected_without_note" in kept[0]["review_flags"]
