"""Regression checks for the actual October 11 authoring failures."""
import copy

from tests.test_learning import learning_bank
from app.bank_validation.quality import leaked_units
from app.bank_validation.validate import validate_bank, validate_dropping
from app.bank_edits import with_edits


def current_bank():
    bank = learning_bank()
    bank["build_meta"]["schema_version"] = "4.1"
    bank["exam_design"] = [{"question_id": q["question_id"], "basis_refs": [{"source_id": "S1", "locator": "p10"}],
                            "changed_dimension": "condition", "novelty": "약물명이 아닌 변화 조건에서 결과를 예측한다."}
                           for q in bank["questions"] if q["role"] == "exam"]
    return bank


def basic(q, *, fmt="basic", question="표적 이름은?", units=None):
    q.update(format=fmt, question=question, answer="답", answer_units=units or ["수송체"],
             options=[], correct_option_ids=[], option_explanations=[])


def main():
    bank = current_bank()
    assert validate_bank(bank, ["S1"])["pass"]
    old = learning_bank()
    old["questions"].append({**old["questions"][0], "question_id": "other", "question": "다른 사실은?"})
    assert validate_bank(old, ["S1"])["pass"]  # Existing banks keep their contract.
    bundled = copy.deepcopy(bank)
    bundled["questions"].append({**bundled["questions"][0], "question_id": "other", "question": "다른 사실은?"})
    assert any("정확히 하나" in e for e in validate_bank(bundled, ["S1"])["errors"])
    missing = copy.deepcopy(bank); missing["questions"].pop(0)
    assert not validate_dropping(missing, ["S1"])[1]["pass"]
    bad_comparison = copy.deepcopy(bank); basic(bad_comparison["questions"][0])
    assert any("비교·구별" in e for e in validate_bank(bad_comparison, ["S1"])["errors"])
    no_choices = copy.deepcopy(bank)
    for o in no_choices["learning_objectives"]: o["kind"] = "fact"
    for q in no_choices["questions"]:
        if q["role"] == "learning": basic(q, question=f"{q['question_id']}의 표적은?")
    assert any("대표 학습용 객관식" in e for e in validate_bank(no_choices, ["S1"])["errors"])
    print("PASS one representative, comparison practice and legacy compatibility")

    disclosure = {"format": "list", "question": "초점발작의 주요 초기 치료 후보 중 carbamazepine·phenytoin·lamotrigine·valproate 계열에 해당하는 네 약물을 적어라.",
                  "answer_units": ["Carbamazepine", "Phenytoin", "Lamotrigine", "Valproate"]}
    assert len(leaked_units(disclosure)) == 4
    assert not leaked_units({**disclosure, "question": "강의 표에서 초점발작의 일차 치료 후보로 제시한 네 약물은?"})
    assert not leaked_units({**disclosure, "format": "mcq"})
    assert not leaked_units({"format": "basic", "question": "ABCG2의 기질은?", "answer_units": ["ABC"]})
    assert not leaked_units({"format": "basic", "question": "A는 무엇인가?", "answer_units": ["A"]})
    assert leaked_units({"format": "basic", "question": "**Valproate**를 쓰세요", "answer_units": ["Valproate"]})
    leaking = copy.deepcopy(bank)
    basic(leaking["questions"][3], fmt="list", question=disclosure["question"], units=disclosure["answer_units"])
    result = validate_bank(leaking, ["S1"])
    assert any("모든 정답 단위 노출" in e for e in result["errors"])
    assert not validate_dropping(leaking, ["S1"])[1]["pass"]  # No silent first-pass gap after dropping.
    print("PASS literal answer disclosure without rejecting legitimate choice candidates")

    for field, value in (("novelty", ""), ("basis_refs", [{"source_id": "missing", "locator": "p1"}]),
                         ("basis_refs", [{"source_id": "EXT", "locator": "외부 지식"}])):
        bad = copy.deepcopy(bank); bad["exam_design"][0][field] = value
        assert not validate_bank(bad, ["S1"])["pass"]
    for designs in ([], bank["exam_design"] + [bank["exam_design"][0]]):
        bad = copy.deepcopy(bank); bad["exam_design"] = designs
        assert not validate_bank(bad, ["S1"])["pass"]
    broken_exam = copy.deepcopy(bank)
    broken_exam["questions"][2]["correct_option_ids"] = ["missing"]
    clean, checked = validate_dropping(broken_exam, ["S1"])
    assert checked["pass"] and len(clean["exam_design"]) == 3
    original = bank["questions"][2]
    clean, checked = with_edits(bank, {}, {original["question_id"]: {"action": "delete", "original": original}}, ["S1"])
    assert checked["pass"] and len(clean["exam_design"]) == 3
    excluded = copy.deepcopy(bank)
    for field in ("questions", "concepts", "learning_objectives", "retrieval_plan", "exam_design"): excluded[field] = []
    excluded["coverage_inventory"] = [{"title": "도입", "source_refs": [{"source_id": "S1", "locator": "p1"}],
                                       "status": "excluded", "reason": "시험 제외 명시", "objective_ids": []}]
    assert validate_bank(excluded, ["S1"])["pass"]
    print("PASS exam design completeness, removal synchronization and excluded lectures")


if __name__ == "__main__": main()
