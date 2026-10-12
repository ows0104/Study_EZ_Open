"""혼합 학습의 신규 우선·완료·강의 간 되돌리기와 객관식 공개 단계를 확인한다."""
import copy
import datetime
from unittest.mock import patch

from tests.test_bank import example_bank, STUDENT as USER
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.bank_validation.schema import without_retired
from app.bank_personal import revision, same_source
from app.study_engine import empty_state, record_review
from app.study_engine.memory import DAY_MS

NOW = 1791824400000


def main():
    legacy = {"question_id": "old", "question": "원문", "answer": "원래 답"}
    classified = {**legacy, "mcq_mode": "recall_first"}
    assert same_source(legacy, classified) and revision(legacy) == revision(classified)
    assert not same_source(legacy, {**classified, "answer": "새 답"})
    Base.metadata.create_all(engine)
    banks = {}
    with SessionLocal() as db:
        for run in ("A", "B", "C"):
            bank = without_retired(example_bank())
            bank["questions"] = bank["questions"][:2]
            for q in bank["questions"]:
                q.update(retrieval_direction="direct", tier="Core", prerequisites=[])
            q = bank["questions"][1 if run == "A" else 0]
            if run in ("A", "B"):
                q.update(format="mcq", mcq_mode="recall_first" if run == "A" else "comparison",
                         question="기전 X를 담당하는 항목은?" if run == "A" else "다음 중 조건을 가장 잘 만족하는 것은?",
                         options=[{"id": "A", "text": "alpha"}, {"id": "B", "text": "beta"}],
                         correct_option_ids=["A"], answer="alpha", answer_units=["alpha"])
            banks[run] = bank
            db.add(Lecture(subject="mix", run_id=run, uid=f"mix-{run}", date=datetime.date(2026, 10, 12),
                           slot=1, slot_end=1, start_time="09:00", title=f"강의 {run}"))
            db.flush()
            db.add(QuizBank(subject="mix", run_id=run, build_id=f"build-{run}", bank=bank,
                            validation={"pass": True}, open_to_students=True))
            state = empty_state()
            if run == "A":
                state = record_review(bank, state, "Q1", "Again", NOW - DAY_MS)
            if run == "C":
                for question in bank["questions"]:
                    state = record_review(bank, state, question["question_id"], "Easy", NOW - DAY_MS)
                    state["items"][question["question_id"]]["due_at"] = NOW + 7 * DAY_MS
                    state["history"][-1]["next_due_at"] = NOW + 7 * DAY_MS
            db.add(BankState(user_id=USER.id, subject="mix", run_id=run, build_id=f"build-{run}", state=state))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    selection = {"lectures": [{"subject": "mix", "runId": run} for run in ("A", "B", "C")]}
    def post(url, data):
        result = client.post(url, json=data)
        assert result.status_code == 200, result.text
        return result.json()
    ticks = iter(range(NOW, NOW + 10000))
    sequence = []
    with patch("app.routes.bank.engine.now_ms", side_effect=lambda: next(ticks)), \
         patch("app.study_engine.batch.random.choices", side_effect=lambda population, **kw: [population[0]]), \
         patch("app.study_engine.daily_queue.random.choice", side_effect=lambda population: population[0]):
        current = post("/api/bank/batch/next", selection)
        assert current["lecture"]["runId"] == "A" and current["question"]["question_id"] == "Q2"
        assert current["batchGoal"]["total"] == 4 and current["batchGoal"]["newRemaining"] == 3
        assert current["question"]["options"] == [] and not current["choicesShown"]
        for index in range(4):
            run, qid = current["lecture"]["runId"], current["question"]["question_id"]
            sequence.append((run, qid))
            base = f"/api/lectures/mix/{run}/bank"
            token = {"reviewToken": current["reviewToken"]}
            stable = post("/api/bank/batch/next", {**selection, "resumeLecture": current["lecture"]})
            assert stable["reviewToken"] == current["reviewToken"]
            if current["question"]["mcq_mode"] == "recall_first":
                assert client.post(base + "/reveal", json=token).status_code == 409
                shown = post(base + "/options", token)
                assert shown["question"]["options"] and "answer" not in shown["question"]
                assert client.post(base + "/rate", json={**token, "rating": "Good"}).status_code == 409
                refreshed = post("/api/bank/batch/next", {**selection, "resumeLecture": current["lecture"]})
                assert refreshed["choicesShown"] and refreshed["question"]["options"] == shown["question"]["options"]
                with SessionLocal() as db:
                    served = db.get(BankState, (USER.id, "mix", run)).state["served"]
                    assert not served["revealed"] and "revealed_at" not in served
            elif current["question"]["mcq_mode"] == "comparison":
                assert current["question"]["options"] and current["choicesShown"]
            post(base + "/reveal", token)
            post(base + "/rate", {**token, "rating": "Again"})
            current = post("/api/bank/batch/next", {**selection, "resumeLecture": current["lecture"]})
            assert current["batchGoal"]["met"] == (index == 3)
            if index < 3:
                assert current["question"] is not None
        assert sequence[0] == ("A", "Q2") and set(sequence[1:3]) == {("B", "Q1"), ("B", "Q2")} and sequence[-1] == ("A", "Q1"), sequence
        assert current["question"] is None and current["batchGoal"]["remaining"] == 0
        assert current["batchGoal"]["completed"] == current["batchGoal"]["total"] == 4
        undone = post("/api/bank/batch/undo", {**selection, "reviewToken": current["undoToken"]})
        assert undone["lecture"]["runId"] == "A" and undone["answer"] is not None
        assert not undone["batchGoal"]["met"] and undone["batchGoal"]["remaining"] == 1
        repeat = post("/api/bank/batch/next", {**selection, "resumeLecture": undone["lecture"]})
        assert repeat["reviewToken"] == undone["reviewToken"]
        post("/api/lectures/mix/A/bank/rate", {"reviewToken": repeat["reviewToken"], "rating": "Hard"})
        assert post("/api/bank/batch/next", selection)["batchGoal"]["met"]
        with SessionLocal() as db:
            row = db.get(QuizBank, ("mix", "C"))
            row.open_to_students = False
            db.commit()
        assert client.post("/api/bank/batch/next", json=selection).status_code == 404
    print("PASS: mixed lectures, every new card before reviews, exact completion independent of ratings, refresh, cross-lecture undo, MCQ stages, publication")


if __name__ == "__main__":
    main()
