"""Ported authoring checks preserve legacy banks and valid causal verbs."""
import copy
from tests.test_bank import example_bank
from app.bank_validation.quality import leaked_units
from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_bank

bank = without_retired(example_bank())
assert validate_bank(bank, ["S1"])["pass"]
bank["questions"][0].update(question="Valproate를 쓰세요", answer="Valproate", answer_units=["Valproate"])
assert validate_bank(bank, ["S1"])["pass"]  # Existing 3.0 data remains usable.
bank["build_meta"]["schema_version"] = "3.1"
assert any("모든 정답 단위 노출" in e for e in validate_bank(bank, ["S1"])["errors"])
assert not leaked_units({"format": "basic", "question": "Na 통로를 억제하면 활동전위 생성은?", "answer_units": ["억제"]})
assert not leaked_units({"format": "basic", "question": "ABCG2의 기질은?", "answer_units": ["ABC"]})
assert leaked_units({"format": "list", "question": "Valproate와 Phenytoin을 쓰세요", "answer_units": ["Valproate", "Phenytoin"]})
comparison = {"format": "basic", "retrieval_direction": "discrimination",
              "question": "UFH·LMWH·fondaparinux 중 면역성 HIT 위험이 가장 높은 제제는?", "answer_units": ["UFH"]}
assert not leaked_units(comparison)
assert leaked_units({**comparison, "question": "UFH·LMWH·fondaparinux 중 가장 높은 것은 UFH입니다. 제제는?"})
assert leaked_units({**comparison, "question": "UFH·LMWH·fondaparinux를 쓰세요"})
for question, answer in (
    ('Chloramphenicol은 통상 정균제인가, 살균제인가?', '정균제'),
    ('Macrolides와 chloramphenicol 중 사람 미토콘드리아 리보솜 억제가 적은 쪽은?', 'Macrolides'),
    ('혈액배양 두 쌍 모두 MRSA가 검출된 배양을 오염과 진성 균혈증 중 어떻게 판단하는가?', '진성 균혈증'),
    ('Vancomycin은 효소와 전구체 기질 중 어디에 직접 결합하는가?', '전구체 기질'),
):
    assert not leaked_units({'format': 'basic', 'retrieval_direction': 'direct', 'question': question, 'answer_units': [answer]})
assert leaked_units({'format': 'basic', 'question': '정균제라고 설명한 약물은 정균제인가, 살균제인가?', 'answer_units': ['정균제']})
assert leaked_units({**comparison, 'question': 'UFH가 가장 위험하다. UFH·LMWH 중 가장 높은 제제는?'})
assert leaked_units({'format': 'cloze', 'question': '여름과 겨울 중 {{c1}}이 여름보다 강수량이 많다.', 'answer_units': ['겨울']})
print("PASS legacy compatibility, literal answer disclosure and legitimate causal wording")

cloze_bank = without_retired(example_bank())
cloze = cloze_bank["questions"][0]
cloze.update(format="cloze", question=" ".join("{{c1}}" for _ in range(5)),
             answer="A B C D E", answer_units=["A", "B", "C", "D", "E"])
assert validate_bank(cloze_bank, ["S1"])["pass"]
cloze["answer_units"].pop()
assert any("cloze는" in e for e in validate_bank(cloze_bank, ["S1"])["errors"])
cloze.update(question="빈칸 없는 문장", answer_units=[])
assert any("cloze는" in e for e in validate_bank(cloze_bank, ["S1"])["errors"])
print("PASS cloze count follows learning goals while blank-answer alignment remains required")
