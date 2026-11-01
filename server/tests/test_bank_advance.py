"""Next-question previews are read-only; combined rating saves exactly once."""
import copy
import datetime
from unittest.mock import patch

from tests.test_bank import example_bank, STUDENT as USER
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.bank_validation.schema import without_retired


def main():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_current_user] = lambda: USER
    with SessionLocal() as db:
        for run in ("A", "B", "failure", "last"):
            bank = without_retired(example_bank())
            for q in bank["questions"]:
                q.update(tier="Core", retrieval_direction="direct", prerequisites=[])
            if run == "last":
                bank["questions"] = bank["questions"][:1]
            db.add(Lecture(subject="advance", run_id=run, uid=f"advance-{run}", date=datetime.date(2026, 10, 16),
                           slot=1, slot_end=1, start_time="09:00", title=run))
            db.flush()
            db.add(QuizBank(subject="advance", run_id=run, build_id="v1", status="ready", open_to_students=True,
                            bank=bank, validation={"pass": True}, pages={}))
        db.commit()
    client = TestClient(app)

    def post(path, body=None):
        response = client.post(path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()

    def snapshot():
        with SessionLocal() as db:
            return {row.run_id: copy.deepcopy(row.state) for row in db.scalars(select(BankState))}

    def prepare(base, current, lectures=None):
        token = {"reviewToken": current["reviewToken"]}
        post(base + "/reveal", token)
        before = snapshot()
        body = {**token, **({"lectures": lectures} if lectures else {})}
        previews = post(base + "/prepare-next", body)
        assert snapshot() == before, "preview mutated study state"
        assert set(previews) == {"Again", "Hard", "Good", "Easy"}
        for preview in previews.values():
            assert not preview.get("reviewToken") and not preview.get("answer")
            if preview["question"]:
                assert "answer" not in preview["question"]
        return body, previews

    with patch("app.routes.bank.engine.now_ms", return_value=1792112400000):
        base = "/api/lectures/advance/A/bank"
        current = post(base + "/next?choiceProtocol=true")
        assert current["question"]["presentationSeed"]
        assert post(base + "/next?choiceProtocol=true")["question"]["presentationSeed"] == current["question"]["presentationSeed"]
        assert client.post(base + "/prepare-next", json={"reviewToken": current["reviewToken"]}).status_code == 409
        body, previews = prepare(base, current)
        got = post(base + "/rate", {**body, "rating": "Good", "advance": True})
        assert got["next"]["question"] == previews["Good"]["question"]
        assert got["next"]["question"]["presentationSeed"] != current["question"]["presentationSeed"]
        assert len(snapshot()["A"]["history"]) == 1
        assert client.post(base + "/rate", json={**body, "rating": "Good", "advance": True}).status_code == 409

        lectures = [{"subject": "advance", "runId": run} for run in ("A", "B")]
        current = post("/api/bank/batch/next", {"lectures": lectures, "resumeLecture": lectures[0]})
        base = f"/api/lectures/advance/{current['lecture']['runId']}/bank"
        body, previews = prepare(base, current, lectures)
        got = post(base + "/rate", {**body, "rating": "Hard", "advance": True})
        assert got["next"]["question"] == previews["Hard"]["question"]
        assert got["next"]["lecture"] == previews["Hard"]["lecture"]

        base = "/api/lectures/advance/failure/bank"
        current = post(base + "/next")
        body, _ = prepare(base, current)
        with patch("app.routes.bank_api.study._next_bank_question", side_effect=RuntimeError("selection failed")):
            got = post(base + "/rate", {**body, "rating": "Good", "advance": True})
        assert got["advanceFailed"] and len(snapshot()["failure"]["history"]) == 1
        assert post(base + "/next")["question"]
        assert len(snapshot()["failure"]["history"]) == 1

        base = "/api/lectures/advance/last/bank"
        current = post(base + "/next")
        body, previews = prepare(base, current)
        got = post(base + "/rate", {**body, "rating": "Easy", "advance": True})
        assert got["next"]["question"] is None and previews["Easy"]["question"] is None
        assert got["next"].get("summary") or got["next"].get("waiting")
    print("PASS: solo/batch prediction is read-only, matches advancement, and preserves saved ratings on failure/completion")


if __name__ == "__main__":
    main()
