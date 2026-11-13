"""객관식 모드 선지: 모든 형식에 오답(block·subtle)만 받아 의학 검토·계약 검사를 통과한 문항만 싣는다(모델은 가짜)."""
import json

import pytest

from quizbank import root_mcq
from studyez_contracts.roots import mcq as contract


def _q(qid, fmt="basic", answer="몸니", units=None, question=None, **extra):
    return {"question_id": qid, "format": fmt, "question": question or f"{qid} 매개체는?", "answer": answer,
            "answer_units": units if units is not None else [answer], "explanation": "해설", "options": [],
            "correct_option_ids": [], "source_refs": [], "sequence_items": [], "correct_order": [], **extra}


def _document():
    return {"revision": "rev-1", "title": "리케치아", "bank_snapshot": {"questions": [
        _q("B1", answer="Fe2+"),
        _q("L1", "list", "몸니, 벼룩", ["몸니", "벼룩"]),
        _q("C1", "cloze", "a", ["Fe2+", "산화"], question="{{c1}} 이온이 {{c2}}된다"),
        _q("C2", "cloze", "Fe2+", ["Fe2+"], question="{{c1}} 이온"),
        _q("S1", "sequence", "", [], sequence_items=["흡착", "침입", "복제"], correct_order=["흡착", "침입", "복제"]),
        _q("O1", "ox", "O", ["O"]),
        {**_q("M1", "mcq", "A"), "options": [{"id": "A", "text": "x"}, {"id": "B", "text": "y"}], "correct_option_ids": ["A"]},
    ]}}


def _w(text="", parts=(), kind="subtle", basis="Fe2+→Fe3+"):
    return {"text": text, "parts": list(parts), "kind": kind, "basis": basis, "why_wrong": "틀림"}


def _good(qid):
    return {
        "B1": [_w("Fe3+"), _w("Cu2+", kind="block", basis="Wilson"), _w("Zn2+", kind="block", basis="다른 균"), _w("Mg2+")],
        "L1": [_w("털진드기", kind="block", basis="쯔쯔가무시"), _w("모기", kind="block", basis="말라리아"), _w("참진드기")],
        "C1": [{**_w(parts=["Fe3+", "산화"])}, _w(parts=["Fe2+", "환원"]), _w(parts=["Fe3+", "환원"])],
        "C2": [_w("Fe3+"), _w("Cu2+"), _w("Zn2+")],
        "S1": [_w(parts=["침입", "흡착", "복제"]), _w(parts=["흡착", "복제", "침입"]), _w(parts=["복제", "흡착", "침입"])],
    }[qid]


def _fake(write, review=None, seen=None):
    def call(prompt, schema, work, model, label):
        rows = json.loads((work / "input.json").read_text(encoding="utf-8"))
        if "reviews" in schema["properties"]:
            text = json.dumps(rows, ensure_ascii=False)
            assert "basis" not in text and "why_wrong" not in text and "kind" not in text  # 쓴 쪽의 근거는 주지 않는다
            qs = rows["questions"]
            return (review(qs) if review else {"reviews": [{"question_id": q["question_id"], "invalid": []} for q in qs]}), {}
        if seen is not None:
            seen.append(rows)
        return write(rows), {"seconds": 1.0}
    return call


def test_형식별_대상과_정답_선지():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert [qid for qid, q in doc.items() if contract.eligible(q)] == ["B1", "L1", "C1", "C2", "S1"]
    assert contract.correct_texts(doc["C1"]) == ["Fe2+ / 산화"]
    assert contract.correct_texts(doc["C2"]) == ["Fe2+"]
    assert contract.correct_texts(doc["S1"]) == ["흡착 → 침입 → 복제"]
    assert contract.parts_needed(doc["C1"]) == 2 and contract.parts_needed(doc["C2"]) == 0
    entry = contract.entry(doc["L1"], _good("L1"))
    assert len(entry["choices"]) == 5 and len(entry["correct_ids"]) == 2
    assert {m["kind"] for m in entry["wrong"].values()} == {"block", "subtle"}
    assert contract.entry_errors(doc["L1"], entry) == []


def test_종류_근거_없는_오답과_순서_아닌_오답은_거절():
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert any("종류" in e for e in contract.wrong_errors(doc["B1"], [_w("Fe3+", kind="other"), _w("a"), _w("b")]))
    assert any("근거" in e for e in contract.wrong_errors(doc["B1"], [_w("Fe3+", basis=""), _w("a"), _w("b")]))
    assert contract.wrong_errors(doc["S1"], [_w(parts=["흡착", "침입", "X"]), *_good("S1")[1:]])
    assert any("칸" in e for e in contract.wrong_errors(doc["C1"], [_w(parts=["Fe3+"]), *_good("C1")[1:]]))


def test_모두_통과하면_전부_싣는다(tmp_path):
    document, seen = _document(), []
    write = lambda rows: {"proposals": [{"question_id": q["question_id"], "wrong": _good(q["question_id"]),
                                         "skip_reason": ""} for q in rows["questions"]]}
    context = {"block": "감염과 면역", "lectures": [{"title": "포도알균", "facts": ["coagulase"]}]}
    asset = root_mcq.build(document, tmp_path, "261110_03", context=context, call=_fake(write, seen=seen))
    assert sorted(asset["questions"]) == ["B1", "C1", "C2", "L1", "S1"]
    assert asset["counts"]["written"] == 5 and asset["skipped"] == {}
    assert seen[0]["block_pool"] == context["lectures"] and seen[0]["block"] == "감염과 면역"
    contract.validate(json.loads((tmp_path / "mcq.json").read_text(encoding="utf-8")), document)


def test_검토가_뺀_문항은_이유를_주고_한_번_더_쓴다(tmp_path):
    document, seen = _document(), []
    calls = {"n": 0}

    def write(rows):
        calls["n"] += 1
        return {"proposals": [{"question_id": q["question_id"], "wrong": _good(q["question_id"]), "skip_reason": ""}
                              for q in rows["questions"]]}

    def review(qs):
        first = calls["n"] == 1
        return {"reviews": [{"question_id": q["question_id"], "invalid": (
            [{"text": "Fe3+", "reason": "정답일 수 있음"}, {"text": "Mg2+", "reason": "불확실"}]
            if first and q["question_id"] == "B1" else [])} for q in qs]}

    asset = root_mcq.build(document, tmp_path, "r", call=_fake(write, review, seen))
    assert len(seen) == 2 and [q["question_id"] for q in seen[1]["questions"]] == ["B1"]
    assert {r["text"] for r in seen[1]["questions"][0]["previous_rejected"]} == {"Fe3+", "Mg2+"}
    assert "B1" in asset["questions"]


def test_실패한_묶음은_빠지고_나머지는_싣는다(tmp_path):
    def write(rows):
        raise RuntimeError("끊김")
    asset = root_mcq.build(_document(), tmp_path, "r", call=_fake(write), rounds=1)
    assert asset["questions"] == {} and asset["counts"]["failedBatches"] == 1


def test_서버용_attachable은_지문이_다르면_None():
    document = _document()
    doc = {q["question_id"]: q for q in document["bank_snapshot"]["questions"]}
    asset = {"schema": contract.SCHEMA, "revision": "rev-1", "questions": {"B1": contract.entry(doc["B1"], _good("B1"))},
             "skipped": {}}
    assert contract.attachable(asset, "rev-1", doc["B1"]) is not None
    assert contract.attachable(asset, "rev-2", doc["B1"]) is None
    assert contract.attachable(asset, "rev-1", {**doc["B1"], "question": "바뀜"}) is None


@pytest.mark.parametrize("fmt", ["ox", "mcq"])
def test_자체_선지_형식은_대상이_아니다(fmt):
    doc = {q["question_id"]: q for q in _document()["bank_snapshot"]["questions"]}
    assert not contract.eligible(doc["O1" if fmt == "ox" else "M1"])
