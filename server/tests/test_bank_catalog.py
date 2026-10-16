"""Catalog order, private scope, publication gate and zero study-state writes."""
import copy
import datetime

from tests.test_bank import STUDENT  # establishes an isolated temporary SQLite DB
from tests.bank_fixtures import example_bank
from fastapi.testclient import TestClient
from app.auth import CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, BankPersonalEdit, BankState, Lecture, QuizBank
from app import bank_personal, study_engine


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    q1, q2, q3 = bank["questions"]
    q1["source_refs"] = [{"source_id": "S1", "locator": "p.1"}]
    q2.update(tier="Optional", advanced=True)
    q3["prerequisites"] = ["Q1"]
    q4 = {**copy.deepcopy(q1), "question_id": "Q4", "question": "같은 쪽 후속 문제", "tier": "Essential"}
    q5 = {**copy.deepcopy(q1), "question_id": "Q5", "source_refs": [{"source_id": "S2", "locator": "p.1"}]}
    q6 = {**copy.deepcopy(q1), "question_id": "Q6", "source_refs": [{"source_id": "S1", "locator": "p.20-21"}],
          "format": "mcq", "options": [{"id": "A", "text": "오답"}, {"id": "B", "text": "정답"}],
          "correct_option_ids": ["B"], "answer": "B. 정답", "answer_units": ["B: 정답 설명"]}
    bank["questions"] = [q3, q1, q2, q4, q5, q6]
    pages = {"Q1": [12, 14], "Q2": [2], "Q3": [9], "Q4": [2]}
    personal = bank_personal.added_question("PQ_1", "나만의 문제", "나만의 답", "Essential", "개인 해설")
    with SessionLocal() as db:
        db.add(Lecture(subject="catalog", run_id="one", uid="catalog-one", title="목록 검증 강의",
                       date=datetime.date(2026, 10, 16), slot=1, slot_end=1, start_time="09:00"))
        db.flush()
        db.add(QuizBank(subject="catalog", run_id="one", build_id="b1", bank=bank, pages=pages,
                        validation={"pass": True}, open_to_students=True,
                        review={"reviews": [{"question_id": "Q1", "verdict": "doubt", "note": "남은 검토", "suggested_answer": ""}]}))
        db.add(Asset(id="catalog-slide", subject="catalog", run_id="one", kind="bank_media", slide_no=2,
                     filename="one_s002.png", object_key="catalog/one_s002.png"))
        db.add(BankPersonalEdit(user_id=STUDENT.id, subject="catalog", run_id="one", question_id="Q1",
                               original=q1, question="내가 고친 문제", answer=q1["answer"]))
        db.add(BankPersonalEdit(user_id=STUDENT.id, subject="catalog", run_id="one", question_id="PQ_1",
                               original=personal, question=personal["question"], answer=personal["answer"]))
        db.add(BankPersonalEdit(user_id="someone-else", subject="catalog", run_id="one", question_id="Q2",
                               original=q2, question="다른 사람의 비밀", answer="다른 사람의 답"))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(app)
    base = "/api/lectures/catalog/one/bank/catalog"
    def get(path=""):
        response = client.get(base + path)
        assert response.status_code == 200, response.text
        return response.json()
    catalog = get()
    assert [item["question"]["question_id"] for item in catalog["questions"]] == ["Q2", "Q4", "Q3", "Q1", "Q6", "Q5", "PQ_1"]
    assert [item["pages"] for item in catalog["questions"]] == [[2], [2], [9], [12, 14], [20, 21], [], []]
    assert len(catalog["slides"]) == 1 and catalog["slides"][0]["page"] == 2
    assert catalog["questions"][3]["question"]["question"] == "내가 고친 문제"
    assert "다른 사람" not in str(catalog)
    for item in catalog["questions"]:
        assert not {"answer", "answer_units", "correct_option_ids", "option_pools"} & item["question"].keys()
    detail = get("/Q6?buildId=b1")
    assert detail["question"]["options"][1]["id"] == detail["answer"]["correctOptionIds"][0] == "B"
    assert get("/PQ_1?buildId=b1")["answer"]["answer"] == "나만의 답"
    assert get("/Q1?buildId=b1")["answer"]["medicalReview"]["verdict"] == "doubt"
    with SessionLocal() as db:
        assert db.get(BankState, (STUDENT.id, "catalog", "one")) is None
        state = study_engine.empty_state()
        state.update(suspended_question_ids=["Q4"], question_tiers={"Q2": "Essential"},
                     served={"question_id": "Q1", "token": "active-token"}, history=[{"keep": "history"}])
        db.add(BankState(user_id=STUDENT.id, subject="catalog", run_id="one", build_id="b1", state=state,
                         previous={"keep": "previous"}))
        db.commit()
    catalog = get()
    assert catalog["questions"][1]["suspended"]
    assert catalog["questions"][0]["question"]["tier"] == "Essential"
    assert get("/Q2?buildId=b1")["question"]["tier"] == "Essential"
    assert client.get(base + "/Q1?buildId=old").status_code == 409
    assert client.get(base + "/missing?buildId=b1").status_code == 404
    assert client.get(base + "/Q1").status_code == 422
    with SessionLocal() as db:
        saved = db.get(BankState, (STUDENT.id, "catalog", "one"))
        assert saved.state == state and saved.previous == {"keep": "previous"}
        row = db.get(QuizBank, ("catalog", "one"))
        assert row.bank == bank
        row.open_to_students = False
        db.commit()
    assert client.get(base).status_code == 404
    assert client.get(base + "/Q1?buildId=b1").status_code == 404
    admin = CurrentUser(id="admin", email="admin@example.com", is_admin=True, apps=STUDENT.apps)
    app.dependency_overrides[get_current_user] = lambda: admin
    assert len(get()["questions"]) == 6  # never another person's added card
    with SessionLocal() as db:
        row = db.get(QuizBank, ("catalog", "one"))
        row.validation = {"pass": False, "errors": ["broken bank"]}
        db.commit()
    assert client.get(base).status_code == 409
    assert client.get(base + "/Q1?buildId=b1").status_code == 409
    print("PASS: slide catalog order, all cards, private scope, canonical choices, publication and read-only state")


if __name__ == "__main__":
    main()
