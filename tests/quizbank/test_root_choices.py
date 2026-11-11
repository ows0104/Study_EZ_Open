"""Main-Quiz 선지 작성: 오답만 받아 계약 검사를 통과한 문항만 싣는다(모델은 가짜)."""
import json

from quizbank import root_choices
from studyez_contracts.roots import choices as contract


def _q(qid, fmt="basic", answer="몸니", units=None):
    return {"question_id": qid, "format": fmt, "question": f"{qid} 매개체는?", "answer": answer,
            "answer_units": units or [answer], "explanation": "해설", "options": [], "correct_option_ids": [], "source_refs": []}


def _document(count=3):
    questions = [_q(f"Q{i}", answer=f"정답{i}") for i in range(count)]
    questions.append({**_q("QC"), "format": "cloze"})
    return {"revision": "rev-1", "title": "리케치아", "bank_snapshot": {"questions": questions}}


def _wrong(qid, n=3):
    return [{"text": f"{qid} 오답{k}", "why_wrong": "다른 균의 매개체"} for k in range(n)]


def test_통과한_문항만_싣고_나머지는_이유와_함께_건너뛴다(tmp_path):
    document, seen = _document(), []

    def call(prompt, schema, work, model, label):
        data = json.loads((work / "input.json").read_text(encoding="utf-8"))
        seen.append([q["question_id"] for q in data["questions"]])
        assert all("candidate_pool" in q for q in data["questions"]) and "오답" in prompt
        return {"proposals": [
            {"question_id": "Q0", "wrong": _wrong("Q0"), "skip_reason": ""},
            {"question_id": "Q1", "wrong": [], "skip_reason": "헷갈리는 항목이 없음"},
            {"question_id": "Q2", "wrong": _wrong("Q2", 1), "skip_reason": ""},
            {"question_id": "QX", "wrong": _wrong("QX"), "skip_reason": ""},
        ]}, {"seconds": 1.0}

    asset = root_choices.build(document, tmp_path, "261110_03", call=call)
    assert seen == [["Q0", "Q1", "Q2"]]  # 빈칸 문항은 보내지 않는다
    assert list(asset["questions"]) == ["Q0"]
    assert asset["skipped"]["Q1"] == "헷갈리는 항목이 없음" and asset["skipped"]["Q2"].startswith("검사 탈락")
    assert asset["counts"] == {"eligible": 3, "written": 1, "skipped": 2, "failedBatches": 0}
    contract.validate(json.loads((tmp_path / "choices.json").read_text(encoding="utf-8")), document)


def test_묶음_실패는_한_번_다시_부르고_그_묶음만_비운다(tmp_path, monkeypatch):
    monkeypatch.setattr(root_choices, "BATCH", 2)
    document, calls = _document(4), []

    def call(prompt, schema, work, model, label):
        calls.append(work.name)
        if work.name == "batch-0":
            raise RuntimeError("시간 초과")
        ids = [q["question_id"] for q in json.loads((work / "input.json").read_text(encoding="utf-8"))["questions"]]
        return {"proposals": [{"question_id": i, "wrong": _wrong(i), "skip_reason": ""} for i in ids]}, {}

    asset = root_choices.build(document, tmp_path, "r", call=call)
    assert calls == ["batch-0", "batch-0", "batch-1"]
    assert sorted(asset["questions"]) == ["Q2", "Q3"] and asset["counts"]["failedBatches"] == 1
    assert asset["skipped"]["Q0"].startswith("묶음 호출 실패")


def test_같은_입력으로_받은_묶음은_다시_부르지_않는다(tmp_path):
    document, calls = _document(2), []

    def call(prompt, schema, work, model, label):
        calls.append(1)
        return {"proposals": [{"question_id": q, "wrong": _wrong(q), "skip_reason": ""} for q in ("Q0", "Q1")]}, {}

    first = root_choices.build(document, tmp_path, "r", call=call)
    second = root_choices.build(document, tmp_path, "r", call=call)
    assert len(calls) == 1 and first["questions"] == second["questions"]


def test_대상이_없으면_호출하지_않는다(tmp_path):
    document = {"revision": "rev-1", "bank_snapshot": {"questions": [{**_q("QC"), "format": "cloze"}]}}
    asset = root_choices.build(document, tmp_path, "r", call=lambda *a: (_ for _ in ()).throw(AssertionError))
    assert asset["questions"] == {} and asset["counts"]["eligible"] == 0
