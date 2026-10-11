"""Actual truth-pair sampling, frozen scoring, review binding and legacy safety."""
import copy

from tests.test_learning import learning_bank, USER, NOW
from app.bank_validation.choices import pool_review_identity
from app.bank_validation.learning import question_identity
from app.bank_validation.validate import validate_bank, validate_dropping
from app.study_engine.choices import realize_choices
from app.study_engine.learning import catalog_unit, grade


def pools():
    return [{"pool_id": f"P{p}", "select_count": 4, "correct_when": "true", "candidates": [
        {"candidate_id": f"C{i}", "true_text": f"풀 {p}의 항목 {i}는 기준을 충족한다.",
         "false_text": f"풀 {p}의 항목 {i}는 기준 밖에 있다.",
         "true_explanation": f"원본에서 항목 {i}가 기준 안에 있음을 확인한다.",
         "false_explanation": f"항목 {i}는 기준 밖이 아니라 기준 안에 있다.",
         "source_refs": [{"source_id": "S1", "locator": f"p{p*6+i+1}"}]} for i in range(6)]} for p in range(2)]


def reviewed(q):
    return {"question_id": q["question_id"], "verdict": "ok", "note": "", "suggested_answer": "",
            "option_pool_hash": pool_review_identity(q)}


def main():
    bank = learning_bank()
    q = bank["questions"][0]
    q["option_pools"] = pools()
    assert validate_bank(bank, ["S1"])["pass"]
    original = copy.deepcopy(q)
    q = {**q, "medicalReview": reviewed(q)}
    forms, subsets, pool_ids, previous = set(), set(), set(), None
    for seed in range(150):
        actual = realize_choices(q, str(seed), previous)
        assert len(actual["options"]) == 4 and len(actual["correct_option_ids"]) == 1
        assert len({o["text"] for o in actual["options"]}) == 4
        assert [o["id"] for o in actual["options"]] == list("ABCD")
        assert {e["option_id"] for e in actual["option_explanations"]} == set("ABCD")
        assert grade(actual, {"selected": actual["correct_option_ids"]})
        for o in actual["options"]:
            correct = o["id"] in actual["correct_option_ids"]
            explanation = next(e["text"] for e in actual["option_explanations"] if e["option_id"] == o["id"])
            assert correct == ("충족한다" in o["text"]) == explanation.startswith("참")
            if not correct: assert not grade(actual, {"selected": [o["id"]]})
        variant = actual["choice_variant"]
        if previous: assert variant["poolId"] != previous["poolId"]
        pool_ids.add(variant["poolId"])
        forms.update((variant["poolId"], c, form) for c, form in variant["forms"].items())
        subsets.add((variant["poolId"], tuple(sorted(variant["forms"]))))
        previous = variant
    assert len(pool_ids) == 2 and len(forms) == 24 and len(subsets) > 20
    assert bank["questions"][0] == original
    assert len(catalog_unit("s", "r", "t", bank, "v")) == 4
    # False-selecting multi-choice still uses one form per proposition and
    # preserves the authored number of correct selections.
    multi = copy.deepcopy(q)
    multi.update(format="multi_select", question="옳지 않은 것을 모두 고르세요.", correct_option_ids=["A", "B"])
    for pool in multi["option_pools"]: pool["correct_when"] = "false"
    multi["medicalReview"] = reviewed(multi)
    actual = realize_choices(multi, "multi")
    assert len(actual["correct_option_ids"]) == 2 and grade(actual, {"selected": actual["correct_option_ids"]})
    assert all((o["id"] in actual["correct_option_ids"]) == ("기준 밖" in o["text"]) for o in actual["options"])
    # Missing/stale/adverse reviews or personal edits must not use new truths.
    for change in ({"medicalReview": None}, {"medicalReview": {**reviewed(q), "verdict": "doubt"}},
                   {"question": "발문의 조건이 바뀜"}, {"personalEdited": True}):
        guarded = realize_choices({**q, **change}, "guarded")
        assert {o["text"] for o in guarded["options"]} == {o["text"] for o in q["options"]}
    assert realize_choices(q, "exam", use_pools=False)["choice_variant"]["poolId"] == ""
    # Legacy option letters rotate but medical meanings/identity do not.
    legacy = bank["questions"][1]
    first = realize_choices(legacy, "legacy")
    second = realize_choices(legacy, "legacy", first["choice_variant"])
    assert first["options"] != second["options"]
    assert question_identity(first) == question_identity(second) == question_identity(legacy)
    assert grade(first, {"selected": first["correct_option_ids"]})
    for mutate in (lambda p: p.update(select_count=6),
                   lambda p: p["candidates"][0].update(false_text=p["candidates"][0]["true_text"]),
                   lambda p: p["candidates"][0].update(source_refs=[]),
                   lambda p: p["candidates"][0].update(false_explanation="")):
        invalid = copy.deepcopy(bank); mutate(invalid["questions"][0]["option_pools"][0])
        cleaned, result = validate_dropping(invalid, ["S1"])
        assert result["pass"] and len(cleaned["learning_objectives"]) == 4
        assert q["question_id"] not in {item["question_id"] for item in cleaned["questions"]}
    print("PASS two rotating pools, varying subsets/truths, unique propositions, exact scoring, review guards, stable objectives and legacy shuffle")

    from fastapi.testclient import TestClient
    from app.auth import get_current_user
    from app.database import Base, SessionLocal, engine
    from app.main import app
    from app.models import Lecture, QuizBank
    from app.models.learning import LearningSession
    from datetime import date
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="course", run_id="lecture", uid="choice-test", slot=1, slot_end=1,
                       start_time="09:00", title="선지 풀 검증", date=date(2026, 10, 1)))
        db.flush()
        db.add(QuizBank(subject="course", run_id="lecture", build_id="choices", bank=bank,
                       validation={"pass": True}, open_to_students=True,
                       review={"reviews": [reviewed(bank["questions"][0])] })); db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    def post(path, body=None):
        response = client.post("/api/learning" + path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()
    def get(path):
        response = client.get("/api/learning" + path)
        assert response.status_code == 200, response.text
        return response.json()
    # Scope the session to one objective so we can submit/undo its exact variant.
    sid = post("/sessions", {"mode": "extra", "subject": "course", "runId": "lecture", "count": 1})["sessionId"]
    first = get(f"/sessions/{sid}")
    assert first["optionsShown"] and len(first["question"]["options"]) == 4
    assert not ({"option_pools", "choice_variant", "answer", "correct_option_ids"} & first["question"].keys())
    assert get(f"/sessions/{sid}")["question"] == first["question"]
    with SessionLocal() as db:
        existing = db.get(LearningSession, sid)
        old_session = copy.deepcopy(existing.data); old_session["served"]["optionsShown"] = False
        existing.data = old_session; db.commit()
    assert get(f"/sessions/{sid}")["optionsShown"] and get(f"/sessions/{sid}")["question"] == first["question"]
    with SessionLocal() as db:
        frozen = copy.deepcopy(db.get(LearningSession, sid).data["served"]["question"])
        row = db.get(QuizBank, ("course", "lecture"))
        modified = copy.deepcopy(bank); modified["questions"][0]["option_pools"] = []
        row.bank, row.build_id = modified, "replaced"; db.commit()
    assert get(f"/sessions/{sid}")["question"] == first["question"]
    feedback = post(f"/sessions/{sid}/submit", {"token": first["token"], "answer": {"selected": frozen["correct_option_ids"]}})
    assert feedback["feedback"]["correct"] and feedback["feedback"]["optionExplanations"] == frozen["option_explanations"]
    assert feedback["feedback"]["sourceRefs"] == frozen["source_refs"]
    post(f"/sessions/{sid}/acknowledge", {"token": first["token"], "reviewRating": "Good"})
    undone = post(f"/sessions/{sid}/undo")
    assert undone["question"] == first["question"] and undone["token"] != first["token"]
    assert get("/dashboard")["workload"]["unseen"] == 4
    # Classic question endpoints also must not disclose the paired truth data.
    from app.routes.bank import _public
    assert "option_pools" not in _public(bank["questions"][0])
    print("PASS actual API: visible choices, no truth leaks, reload/rebuild freeze, exact feedback, undo retains variant and counts")


if __name__ == "__main__": main()
