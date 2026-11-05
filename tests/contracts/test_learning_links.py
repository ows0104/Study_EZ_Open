import copy
import hashlib
import json

import pytest

from studyez_contracts.learning_links import (
    HASH_POLICY, SCHEMA_VERSION, LinkValidationError, question_hash, validate_review,
)


def synthetic_inputs():
    """Abstract A/B/C facts only: never an authored medical question bank."""
    source = b"Synthetic source: A relates to B; B relates to C; D is unresolved."
    digest = hashlib.sha256(source).hexdigest()
    ref = {"source_id": "S1", "locator": "synthetic paragraph 1", "pages": []}
    bank = {"questions": [{"question_id": "Q1", "question": "A→B가 주어졌을 때 B→?",
                            "answer": "C", "explanation": "합성 자료의 B→C 관계",
                            "options": [], "source_refs": [{"source_id": "S1", "locator": "paragraph 1"}]}],
            "validation": {"pass": False, "note": "synthetic only"}}
    relations = [{"relation_id": f"R{i}", "from_id": a, "to_id": b, "kind": "association",
                  "condition": "합성 예시", "evidence": [copy.deepcopy(ref)],
                  "review_status": "reviewed" if i < 3 else "unreviewed", "reason": "검토 상태 예시"}
                 for i, a, b in [(1, "A", "B"), (2, "B", "C"), (3, "C", "D")]]
    targets, points, coverage = [], [], []
    for i, role in [(1, "root"), (2, "leaf"), (3, "leaf")]:
        importance = {axis: {"status": "insufficient", "reason": "근거 부족은 중요도 0이 아님", "evidence": []}
                      for axis in ("structural", "exam", "clinical")}
        axis = "structural" if i == 1 else "clinical"
        if i < 3:
            importance[axis] = {"status": "supported", "reason": "합성 근거",
                                "evidence": [{"kind": f"{axis}_rationale", "reason": "합성 판단 근거",
                                              "refs": [copy.deepcopy(ref)]}]}
        targets.append({"target_id": f"T{i}", "title": f"관계 R{i} 회상", "concept_ids": [chr(64 + i)],
                        "relation_ids": [f"R{i}"], "role": role, "reason": "구조적 역할은 중요도와 별개",
                        "evidence": [copy.deepcopy(ref)], "importance": importance,
                        "directions": [{"direction_id": f"D{i}", "cue": chr(64 + i),
                                        "answer_scope": f"R{i}의 상대 개념", "requirement": "required",
                                        "relation_ids": [f"R{i}"]}]})
        points.append({"point_id": f"P{i}", "text": f"원본 포인트 {i}", "evidence": [copy.deepcopy(ref)],
                       "target_ids": [f"T{i}"], "scope_status": "included", "reason": "합성 범위"})
        coverage.append({"point_id": f"P{i}", "status": {1: "gap", 2: "covered", 3: "unknown"}[i],
                         "confirmed_direction_ids": [f"D{i}"] if i == 2 else [],
                         "partial_direction_ids": [], "missing_direction_ids": [f"D{i}"] if i == 1 else [],
                         "unknown_direction_ids": [f"D{i}"] if i == 3 else [],
                         "reason": "합성 대조 결과", "exclusion_basis": None})
    mappings = [{"question_id": "Q1", "question_sha256": question_hash(bank["questions"][0], bank),
                 "target_id": f"T{i}", "direction_id": f"D{i}",
                 "tested_relation_ids": ["R2"] if i == 2 else [], "provided_relation_ids": ["R1"],
                 "explanation_relation_ids": [], "reason": "A→B는 제공하고 B→C만 시험"} for i in (1, 2)]
    review = {"schema_version": SCHEMA_VERSION, "lecture_id": "synthetic-lecture", "bank_sha256": "b" * 64,
              "hash_policy": HASH_POLICY,
              "scope": {"label": "합성 연결 검토 — 실제 강의 아님", "included": ["A/B/C/D"], "excluded": [],
                        "reviewed": ["합성 사례"], "limitations": ["의학 내용 검토 아님"],
                        "outside_list_review": "원본 전체 검토를 대체하지 않는 합성 사례"},
              "provenance": {"status": "draft", "method": "synthetic fixture", "reviewer": "test fixture",
                             "independent_points": "unverified", "notes": "기존 자료에서 추출한 결과가 아님"},
              "sources": [{"source_id": "S1", "label": "합성 원본", "sha256": digest, "kind": "other",
                           "professor": None, "year": None, "page_count": None}],
              "concepts": [{"concept_id": c, "label": c, "parent_ids": [] if c == "A" else ["A"]}
                           for c in "ABCD"],
              "relations": relations, "targets": targets, "points": points, "mappings": mappings, "coverage": coverage}
    return review, bank, source


def check(review, bank):
    return validate_review(review, bank, bank_sha256="b" * 64,
                           source_hashes={"S1": hashlib.sha256(synthetic_inputs()[2]).hexdigest()})


def materialize(folder):
    folder.mkdir(parents=True, exist_ok=True)
    review, bank, source = synthetic_inputs()
    (folder / "source.txt").write_bytes(source)
    bank_raw = (json.dumps(bank, ensure_ascii=False, indent=2) + "\n").encode()
    (folder / "bank.json").write_bytes(bank_raw)
    review["bank_sha256"] = hashlib.sha256(bank_raw).hexdigest()
    (folder / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    inventory = {"schema_version": "learning-link-sources/1",
                 "sources": [{"source_id": "S1", "path": "source.txt", "sha256": hashlib.sha256(source).hexdigest()}]}
    (folder / "sources.json").write_text(json.dumps(inventory), encoding="utf-8")
    return review, bank


def test_valid_review_keeps_unknown_roots_leaves_and_does_not_mutate():
    review, bank, _ = synthetic_inputs()
    before = copy.deepcopy((review, bank))
    result = check(review, bank)
    assert result == review and result is not review
    assert (review, bank) == before
    assert [c["status"] for c in result["coverage"]] == ["gap", "covered", "unknown"]
    assert result["targets"][0]["importance"]["exam"]["status"] == "insufficient"


@pytest.mark.parametrize("mode", ["provided", "explanation"])
def test_provided_or_explanation_never_satisfies_recall(mode):
    review, bank, _ = synthetic_inputs()
    if mode == "explanation":
        for mapping in review["mappings"]:
            mapping["explanation_relation_ids"] = ["R1"]
            mapping["provided_relation_ids"] = []
    review["coverage"][0].update(status="covered", confirmed_direction_ids=["D1"], missing_direction_ids=[])
    with pytest.raises(LinkValidationError, match="not directly tested"):
        check(review, bank)


def test_same_question_cannot_provide_and_test_a_relation_in_separate_mappings():
    review, bank, _ = synthetic_inputs()
    review["mappings"][0].update(tested_relation_ids=["R1"], provided_relation_ids=[])
    with pytest.raises(LinkValidationError, match="inconsistent relation role"):
        check(review, bank)


def test_explicit_bank_lecture_mismatch_is_rejected():
    review, bank, _ = synthetic_inputs()
    bank["lecture_id"] = "another-lecture"
    with pytest.raises(LinkValidationError, match="lecture mismatch"):
        check(review, bank)


def test_partial_relation_within_one_direction_is_not_covered():
    review, bank, _ = synthetic_inputs()
    target = review["targets"][1]
    target["relation_ids"].append("R1")
    target["directions"][0]["relation_ids"].append("R1")
    with pytest.raises(LinkValidationError, match="not directly tested"):
        check(review, bank)
    review["coverage"][1].update(status="partial", confirmed_direction_ids=[], partial_direction_ids=["D2"])
    assert check(review, bank)["coverage"][1]["status"] == "partial"


def test_missing_second_required_direction_prevents_covered():
    review, bank, _ = synthetic_inputs()
    d = copy.deepcopy(review["targets"][1]["directions"][0])
    d.update(direction_id="D2reverse", cue="C", answer_scope="B")
    review["targets"][1]["directions"].append(d)
    review["coverage"][1]["missing_direction_ids"] = ["D2reverse"]
    with pytest.raises(LinkValidationError, match="required directions not covered"):
        check(review, bank)
    review["coverage"][1]["status"] = "partial"
    check(review, bank)
    d["requirement"] = "optional"
    review["coverage"][1]["status"] = "covered"
    check(review, bank)
    d["requirement"] = "undecided"
    with pytest.raises(LinkValidationError, match="undecided"):
        check(review, bank)


@pytest.mark.parametrize("mutation, message", [
    (lambda r: r.update(learner_mastery=1), "unknown fields"),
    (lambda r: r["concepts"].append(dict(r["concepts"][0], label="duplicate")), "duplicate A"),
    (lambda r: r["relations"][0].update(from_id="absent"), "unknown references"),
    (lambda r: r["targets"][0]["directions"][0].update(relation_ids=["R2"]), "unknown references"),
    (lambda r: r["points"].pop(), "targets missing"),
    (lambda r: r["coverage"].pop(), "every point"),
    (lambda r: r["coverage"][0].update(unknown_direction_ids=["D1"]), "overlapping"),
    (lambda r: r["coverage"][2].update(status="gap"), "reviewed absence"),
    (lambda r: r["mappings"][0].update(question_id="missing"), "unknown/mismatched"),
    (lambda r: r["mappings"][1].update(direction_id="D1"), "unknown/mismatched"),
    (lambda r: r["mappings"][1].update(provided_relation_ids=["R2"]), "disjoint"),
    (lambda r: r["relations"][1].update(review_status="unreviewed"), "unreviewed relation"),
    (lambda r: r["sources"][0].update(page_count=True), "expected"),
    (lambda r: r["targets"][0]["importance"]["exam"].update(status="supported"), "needs evidence"),
    (lambda r: r["relations"][0]["evidence"][0].update(source_id="absent"), "unknown source"),
    (lambda r: r["relations"][0]["evidence"][0].update(pages=[99]), "page_count"),
    (lambda r: r["sources"][0].update(sha256="c" * 64), "revision mismatch"),
    (lambda r: r.update(bank_sha256="c" * 64), "revision mismatch"),
])
def test_invalid_contracts_are_rejected(mutation, message):
    review, bank, _ = synthetic_inputs()
    mutation(review)
    with pytest.raises(LinkValidationError, match=message):
        check(review, bank)


@pytest.mark.parametrize("field", ["answer", "question", "explanation", "options", "source_refs", "answer_pairs"])
def test_changed_question_fields_invalidate_prior_mapping(field):
    review, bank, _ = synthetic_inputs()
    bank["questions"][0][field] = "changed"
    with pytest.raises(LinkValidationError, match="revision mismatch"):
        check(review, bank)


def test_changed_bank_validation_and_personal_variant_invalidate_mapping():
    for field in ("validation", "personal_edit"):
        review, bank, _ = synthetic_inputs()
        bank[field] = {"changed": True}
        with pytest.raises(LinkValidationError, match="revision mismatch"):
            check(review, bank)


@pytest.mark.parametrize("kind, allowed", [("comparison", True), ("causal", True),
                                            ("prerequisite", False), ("classification", False)])
def test_cycle_rules_follow_relation_type(kind, allowed):
    review, bank, _ = synthetic_inputs()
    review["relations"][0].update(kind=kind)
    reverse = copy.deepcopy(review["relations"][0])
    reverse.update(relation_id="R4", from_id="B", to_id="A")
    review["relations"].append(reverse)
    if allowed:
        check(review, bank)
    else:
        with pytest.raises(LinkValidationError, match="cycle"):
            check(review, bank)


def test_shared_map_locations_do_not_duplicate_targets_and_hierarchy_cycles_fail():
    review, bank, _ = synthetic_inputs()
    review["targets"][0]["concept_ids"].append("D")
    assert len(check(review, bank)["targets"]) == 3
    review["concepts"][0]["parent_ids"] = ["B"]
    with pytest.raises(LinkValidationError, match="hierarchy: cycle"):
        check(review, bank)


def test_exclusion_requires_a_scope_basis_and_cannot_hide_targets():
    review, bank, _ = synthetic_inputs()
    review["points"].append({"point_id": "PX", "text": "범위 밖 합성 문장", "evidence": [],
                              "target_ids": [], "scope_status": "excluded", "reason": "명시적 범위 밖"})
    review["coverage"].append({"point_id": "PX", "status": "excluded", "reason": "범위 밖",
                               "confirmed_direction_ids": [], "partial_direction_ids": [],
                               "missing_direction_ids": [], "unknown_direction_ids": [], "exclusion_basis": "out_of_scope"})
    check(review, bank)
    review["coverage"][-1]["exclusion_basis"] = None
    with pytest.raises(LinkValidationError, match="exclusion basis"):
        check(review, bank)


def test_contract_package_is_registered_and_has_no_runtime_dependencies():
    import ast
    import pathlib
    import tomllib
    root = pathlib.Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "studyez_contracts/pyproject.toml").read_text())
    assert "studyez_contracts.learning_links" in config["tool"]["setuptools"]["packages"]
    allowed = {"__future__", "copy", "hashlib", "json", "re", "collections"}
    for path in (root / "studyez_contracts/learning_links").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(item.name.split(".")[0] in allowed for item in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert node.module.split(".")[0] in allowed
