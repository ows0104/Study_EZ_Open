"""사이트에서 고친 카드를 덱에 얹는다 — 원본이 같을 때만, guid 는 그대로.

2026-09-23 관리자 지시 — 「사이트에서 고친 카드가 apkg에도 반영되게 해줘.」
규칙과 까닭은 `quizgen/site_edits.py` 머리에 있다.
"""

from quizgen import site_edits
from quizgen.build import check_guids, guid_of
from quizgen.textutil import norm_key

LID = "260921_03"


def card(cid, q, a, fmt="basic", explanation="해설"):
    return {"id": cid, "card_format": fmt, "q": q, "a": a, "explanation": explanation}


def an_edit(cid, original, action="edit", **fields):
    return {"item_id": cid, "action": action, "original": original, **fields}


BASIC = card("c002", "함께 꼽은 것은?", "morphology alteration")
CLOZE = card("c004", "먼저 {{c1::동물}}의 이동을 부른다", "동물", fmt="cloze")


def test_원본이_같으면_얹는다():
    edit = an_edit("c002", site_edits.seen_as(BASIC), stem="강의가 셋째로 꼽은 기전은?",
                   answer="morphology alteration", explanation="고친 해설")
    out, done = site_edits.apply([BASIC], [edit])

    assert out[0]["q"] == "강의가 셋째로 꼽은 기전은?"
    assert out[0]["explanation"] == "고친 해설"
    assert done["edited"] == ["c002"]
    assert BASIC["q"] == "함께 꼽은 것은?", "들어온 카드를 고쳤다"


def test_질문을_고쳐도_guid_는_원래_질문이다():
    """안 그러면 다시 임포트한 사람의 Anki 에 같은 카드가 둘이 되고 복습 이력이 끊긴다."""
    edit = an_edit("c002", site_edits.seen_as(BASIC), stem="강의가 셋째로 꼽은 기전은?")
    out, _ = site_edits.apply([BASIC], [edit])

    before = guid_of(LID, norm_key(site_edits.guid_q(BASIC)), BASIC)
    after = guid_of(LID, norm_key(site_edits.guid_q(out[0])), out[0])
    assert before == after
    # 겹침 검사도 같은 씨앗을 본다 — 한쪽만 바꾸면 없는 겹침을 잡거나 있는 것을 놓친다.
    assert check_guids(out, LID)[0] == out


def test_두_번_고쳐도_guid_는_처음_질문이다():
    edit = an_edit("c002", site_edits.seen_as(BASIC), stem="둘째 판")
    once, _ = site_edits.apply([BASIC], [edit])
    again = an_edit("c002", site_edits.seen_as(once[0]), stem="셋째 판")
    twice, _ = site_edits.apply(once, [again])
    assert twice[0]["guid_q"] == BASIC["q"]


def test_원본이_다르면_건너뛰고_센다():
    """파이프라인이 그 편을 다시 만들면 `c002` 는 다른 카드다. 옛 판정을 덮으면 멀쩡한 카드를 망친다."""
    stale = an_edit("c002", {"stem": "옛 질문", "answer": "옛 답", "explanation": "해설"},
                    stem="고친 질문")
    out, done = site_edits.apply([BASIC], [stale])
    assert out == [BASIC]
    assert done["stale"] == ["c002"]


def test_뺀다():
    out, done = site_edits.apply([BASIC, CLOZE],
                                 [an_edit("c002", site_edits.seen_as(BASIC), action="delete")])
    assert [c["id"] for c in out] == ["c004"]
    assert done["deleted"] == ["c002"]


def test_빈칸_카드는_원문을_q_에_넣는다():
    """웹에 보이는 것은 편 질문이다 — 원본 맞대기도 그것으로 한다."""
    assert site_edits.seen_as(CLOZE)["stem"] == "먼저 [____]의 이동을 부른다"
    edit = an_edit("c004", site_edits.seen_as(CLOZE),
                   stem="댐 건설은 먼저 [____]의 이동을 부른다",
                   source_stem="댐 건설은 먼저 {{c1::동물}}의 이동을 부른다")
    out, _ = site_edits.apply([CLOZE], [edit])
    assert out[0]["q"] == "댐 건설은 먼저 {{c1::동물}}의 이동을 부른다"
    assert out[0]["guid_q"] == CLOZE["q"]


def test_판정_파일이_없으면_아무것도_안_한다(tmp_path):
    assert site_edits.load(None) == []
    path = tmp_path / "site_edits.main.json"
    path.write_text('{"edits": [{"item_id": "c002", "action": "delete"}]}', encoding="utf-8")
    assert [e["item_id"] for e in site_edits.load(path)] == ["c002"]
