"""Main-Quiz 선지 작성: 오답만 받아 의학 검토 한 번·계약 검사를 통과한 문항만 싣는다(모델은 가짜)."""
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
    return [{"text": f"{qid} 오답{k}", "why_wrong": "다른 균의 매개체", "why_tempting": "같은 단원의 매개체라서"} for k in range(n)]


def _read(work):
    return json.loads((work / "input.json").read_text(encoding="utf-8"))["questions"]


def _fake(write, review=None, log=None):
    """schema로 작성 호출과 검토 호출을 구분한다. review가 없으면 모두 문제없음."""
    def call(prompt, schema, work, model, label):
        if log is not None:
            log.append(str(work.relative_to(work.parents[1] if work.name == "review" else work.parent)).replace("\\", "/"))
        if "reviews" in schema["properties"]:
            rows = _read(work)
            assert all("why_wrong" not in json.dumps(q, ensure_ascii=False) for q in rows)  # 쓴 쪽의 이유는 주지 않는다
            return (review(rows) if review else {"reviews": [{"question_id": q["question_id"], "invalid": []} for q in rows]}), {}
        return write(_read(work), work), {"seconds": 1.0}
    return call


def test_통과한_문항만_싣고_나머지는_이유와_함께_건너뛴다(tmp_path):
    document, seen = _document(), []

    def write(rows, work):
        seen.append([q["question_id"] for q in rows])
        assert all("candidate_pool" in q for q in rows)
        return {"proposals": [
            {"question_id": "Q0", "wrong": _wrong("Q0"), "skip_reason": ""},
            {"question_id": "Q1", "wrong": [], "skip_reason": "같은 범주의 틀린 답이 없음"},
            {"question_id": "Q2", "wrong": _wrong("Q2", 1), "skip_reason": ""},
            {"question_id": "QX", "wrong": _wrong("QX"), "skip_reason": ""},
        ]}

    asset = root_choices.build(document, tmp_path, "261110_03", call=_fake(write))
    assert seen == [["Q0", "Q1", "Q2"]]  # 빈칸 문항은 보내지 않는다
    assert list(asset["questions"]) == ["Q0"]
    assert asset["skipped"]["Q1"] == "같은 범주의 틀린 답이 없음" and asset["skipped"]["Q2"].startswith("검사 탈락")
    assert asset["counts"] == {"eligible": 3, "written": 1, "skipped": 2, "failedBatches": 0, "removedByReview": 0}
    assert asset["medicalReview"] == {"policy": "choices-medical/1", "questions": {"Q0": {"removed": [], "kept": 3}}}
    contract.validate(json.loads((tmp_path / "choices.json").read_text(encoding="utf-8")), document)


def test_의학_검토가_지적한_오답은_빼고_모자라면_문항을_비운다(tmp_path):
    document = _document(3)

    def write(rows, work):
        return {"proposals": [{"question_id": q["question_id"], "wrong": _wrong(q["question_id"], 4), "skip_reason": ""} for q in rows]}

    def review(rows):
        assert [q["question_id"] for q in rows] == ["Q0", "Q1", "Q2"] and rows[0]["correct"] == ["정답0"]
        return {"reviews": [
            {"question_id": "Q0", "invalid": [{"text": "Q0 오답1", "reason": "조건에 따라 정답이 될 수 있다"}]},
            {"question_id": "Q1", "invalid": [{"text": "Q1  오답0", "reason": "정답의 동의어"}, {"text": "Q1 오답2", "reason": "불확실"}]},
        ]}  # Q2는 검토 줄이 없다

    asset = root_choices.build(document, tmp_path, "r", call=_fake(write, review))
    assert list(asset["questions"]) == ["Q0"]
    texts = [c["text"] for c in asset["questions"]["Q0"]["choices"]]
    assert "Q0 오답1" not in texts and len(texts) == 4
    assert asset["skipped"]["Q1"].startswith("의학 검토 뒤 오답 부족") and asset["skipped"]["Q2"] == "의학 검토를 받지 못함"
    assert asset["counts"]["removedByReview"] == 3
    assert asset["medicalReview"]["questions"]["Q0"]["removed"] == [{"text": "Q0 오답1", "reason": "조건에 따라 정답이 될 수 있다"}]


def test_왜_헷갈리는지_못_쓴_오답은_빼고_모자라면_문항을_비운다(tmp_path):
    document = _document(2)

    def write(rows, work):
        weak = _wrong("Q0", 4)
        weak[0]["why_tempting"] = ""
        bad = _wrong("Q1")
        bad[2]["why_tempting"] = " "
        return {"proposals": [{"question_id": "Q0", "wrong": weak, "skip_reason": ""},
                              {"question_id": "Q1", "wrong": bad, "skip_reason": ""}]}

    asset = root_choices.build(document, tmp_path, "r", call=_fake(write))
    assert list(asset["questions"]) == ["Q0"] and len(asset["questions"]["Q0"]["choices"]) == 4
    assert "Q0 오답0" not in [c["text"] for c in asset["questions"]["Q0"]["choices"]]
    assert asset["skipped"]["Q1"].startswith("검사 탈락")


def test_의학_검토_호출이_실패하면_그_묶음은_싣지_않는다(tmp_path):
    document = _document(2)

    def write(rows, work):
        return {"proposals": [{"question_id": q["question_id"], "wrong": _wrong(q["question_id"]), "skip_reason": ""} for q in rows]}

    def review(rows):
        raise RuntimeError("시간 초과")

    asset = root_choices.build(document, tmp_path, "r", call=_fake(write, review))
    assert asset["questions"] == {} and asset["counts"]["failedBatches"] == 1
    assert asset["skipped"]["Q0"].startswith("의학 검토 호출 실패")


def test_묶음_실패는_한_번_다시_부르고_그_묶음만_비운다(tmp_path, monkeypatch):
    monkeypatch.setattr(root_choices, "BATCH", 2)
    document, calls = _document(4), []

    def write(rows, work):
        if work.name == "batch-0":
            raise RuntimeError("시간 초과")
        return {"proposals": [{"question_id": q["question_id"], "wrong": _wrong(q["question_id"]), "skip_reason": ""} for q in rows]}

    asset = root_choices.build(document, tmp_path, "r", call=_fake(write, log=calls))
    assert calls == ["batch-0", "batch-0", "batch-1", "batch-1/review"]
    assert sorted(asset["questions"]) == ["Q2", "Q3"] and asset["counts"]["failedBatches"] == 1
    assert asset["skipped"]["Q0"].startswith("묶음 호출 실패")


def test_같은_입력으로_받은_묶음은_다시_부르지_않는다(tmp_path):
    document, calls = _document(2), []

    def write(rows, work):
        return {"proposals": [{"question_id": q, "wrong": _wrong(q), "skip_reason": ""} for q in ("Q0", "Q1")]}

    first = root_choices.build(document, tmp_path, "r", call=_fake(write, log=calls))
    second = root_choices.build(document, tmp_path, "r", call=_fake(write, log=calls))
    assert calls == ["batch-0", "batch-0/review"] and first["questions"] == second["questions"]


def test_대상이_없으면_호출하지_않는다(tmp_path):
    document = {"revision": "rev-1", "bank_snapshot": {"questions": [{**_q("QC"), "format": "cloze"}]}}
    asset = root_choices.build(document, tmp_path, "r", call=lambda *a: (_ for _ in ()).throw(AssertionError))
    assert asset["questions"] == {} and asset["counts"]["eligible"] == 0
