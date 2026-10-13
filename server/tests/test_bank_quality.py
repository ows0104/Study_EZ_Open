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
print("PASS legacy compatibility, literal answer disclosure and legitimate causal wording")
