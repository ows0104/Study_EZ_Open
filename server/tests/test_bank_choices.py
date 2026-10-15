"""V1 API: actual pool variation, frozen answers, private edits and undo."""
import copy
import datetime

from tests.test_bank import example_bank, STUDENT as USER
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.bank_validation.schema import without_retired
from app.bank_validation.choices import pool_review_identity
from app.bank_validation.pool_checks import candidates
from app.bank_validation.validate import validate_bank
from app.study_engine.choices import realize_choices


def pools():
    return [{"pool_id": f"P{p}", "select_count": 4, "correct_when": "true", "candidates": [
        {"candidate_id": f"C{i}", "true_text": f"풀 {p} 항목 {i}는 참", "false_text": f"풀 {p} 항목 {i}는 거짓",
         "true_explanation": "자료에서 확인한 참 근거", "false_explanation": "거짓 부분과 정정 근거",
         "source_refs": [{"source_id": "S1", "locator": "p1"}]} for i in range(6)]} for p in range(2)]


def main():
    bank = without_retired(example_bank())
    bank["build_meta"]["schema_version"] = "3.1"
    question = bank["questions"][0]
    question.update(format="mcq", question="옳은 것은?", answer="A. 원래 참 보기",
                    options=[{"id": "A", "text": "원래 참 보기"}, {"id": "B", "text": "원래 거짓 보기"}],
                    correct_option_ids=["A"], answer_units=["A: 참 근거", "B: 거짓 정정 근거"],
                    option_explanations=[{"option_id": "A", "text": "참 근거"}, {"option_id": "B", "text": "거짓 정정 근거"}],
                    option_pools=pools())
    bank["questions"] = [question]
    assert validate_bank(bank, ["S1"])["pass"], validate_bank(bank, ["S1"])
    review = {"question_id": question["question_id"], "verdict": "ok", "note": "", "suggested_answer": "",
              "option_pool_hash": pool_review_identity(question),
              'pool_checks': [{**{k: c[k] for k in ('question_id', 'pool_id', 'candidate_id', 'content_hash')},
                              'true_verdict': 'ok', 'false_verdict': 'ok', 'criterion_verdict': 'ok',
                              'note': '테스트 후보 근거 확인'} for c in candidates(bank)]}
    previous = None
    forms, subsets = set(), set()
    for seed in range(120):
        actual = realize_choices({**question, "medicalReview": review}, str(seed), previous)
        assert len(actual["options"]) == 4 and len(actual["correct_option_ids"]) == 1
        for option in actual["options"]:
            assert (option["id"] in actual["correct_option_ids"]) == option["text"].endswith("참")
        if previous:
            assert actual["choice_variant"]["poolId"] != previous["poolId"]
        previous = actual["choice_variant"]
        forms.update((previous["poolId"], cid, form) for cid, form in previous["forms"].items())
        subsets.add((previous["poolId"], tuple(sorted(previous["forms"]))))
    assert len(forms) == 24 and len(subsets) > 20
    for override in ({"medicalReview": None}, {"medicalReview": {**review, "verdict": "wrong"}},
                     {'medicalReview': {**review, 'pool_checks': []}},
                     {'medicalReview': {**review, 'pool_checks': review['pool_checks'][:-1]}},
                     {'medicalReview': {**review, 'pool_checks': [{**r, 'content_hash': 'stale'} if i == 0 else r
                                                                for i, r in enumerate(review['pool_checks'])]}},
                     {"question": "검토 후 발문 변경", "medicalReview": review}, {"personalEdited": True, "medicalReview": review}):
        safe = realize_choices({**question, **override}, "safe")
        assert {o["text"] for o in safe["options"]} == {o["text"] for o in question["options"]}

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="choices", run_id="demo", uid="choices-demo", date=datetime.date(2026, 10, 1),
                       slot=1, slot_end=1, start_time="09:00", title="선지 변형"))
        db.flush()
        db.add(QuizBank(subject="choices", run_id="demo", build_id="choices-v1", bank=bank,
                       validation={"pass": True}, review={"reviews": [review]}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    base = "/api/lectures/choices/demo/bank"
    def post(path, body=None):
        response = client.post(base + path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()
    post("/session/start")
    first = post("/next")
    token = first["reviewToken"]
    assert len(first["question"]["options"]) == 4
    assert not {"option_pools", "choice_variant", "answer", "correct_option_ids", "option_explanations"} & first["question"].keys()
    assert post("/next")["question"] == first["question"]
    # Reclassifying priorities keeps the in-flight variant, token and progress.
    with SessionLocal() as db:
        row = db.get(QuizBank, ("choices", "demo"))
        updated = copy.deepcopy(row.bank)
        updated["questions"][0].update(tier="Important", importance=4, advanced=True)
        row.bank = updated
        state_before = copy.deepcopy(db.get(BankState, (USER.id, "choices", "demo")).state)
        db.commit()
    refreshed = post("/next")
    assert refreshed["reviewToken"] == token
    assert refreshed["question"] == {**first["question"], "tier": "Important", "importance": 4, "advanced": True, "targetMastery": .78}
    with SessionLocal() as db:
        state_after = db.get(BankState, (USER.id, "choices", "demo")).state
        assert state_after["served"] == state_before["served"]
        assert state_after["history"] == state_before["history"]
    first = refreshed
    prepared = post("/prepare", {"reviewToken": token})
    assert prepared == post("/reveal", {"reviewToken": token})
    for option in first["question"]["options"]:
        assert (option["id"] in prepared["correctOptionIds"]) == option["text"].endswith("참")
    post("/rate", {"reviewToken": token, "rating": "Good"})
    undone = post("/undo", {"reviewToken": token})
    assert undone["question"] == first["question"] and undone["answer"] == prepared
    token = undone["reviewToken"]
    assert post("/next")["question"] == first["question"]
    # A prose correction during a frozen variant remains immediately usable.
    path = base + f"/questions/{question['question_id']}/personal"
    source = client.get(path).json()
    saved = client.put(path, json={"action": "save", "revision": source["revision"],
        "question": "내 발문", "answer": "내 정답", "report": False})
    assert saved.status_code == 200, saved.text
    assert post("/next")["question"]["question"] == "내 발문"
    assert post("/reveal", {"reviewToken": token})["answer"] == "내 정답"
    with SessionLocal() as db:
        state = db.get(BankState, (USER.id, "choices", "demo")).state
        assert not state["history"]  # Undo restored the V1 schedule too.
    assert not any(path.startswith("/api/learning") for path in app.openapi()["paths"])
    print("PASS V1 pools, exact answers, no truth leaks, reload/prepare/reveal/undo, private corrections and V1 routes")


if __name__ == "__main__":
    main()
