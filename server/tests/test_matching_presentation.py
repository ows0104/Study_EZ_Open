"""Matching display order and answer orientation share one projection, including HTTP resume/undo."""
import copy
import datetime
from unittest.mock import patch

from tests.test_bank import STUDENT as USER  # sets an isolated local SQLite DB before app imports
from tests.bank_fixtures import example_bank
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.study_engine.matching import matching_presentation, ordered_items


def main():
    for original, expected in (
        (["M10", "M2", "M1"], ["M1", "M2", "M10"]),
        (["Phase III", "Phase I", "Phase II"], ["Phase I", "Phase II", "Phase III"]),
        (["제3세대", "제1세대", "제2세대"], ["제1세대", "제2세대", "제3세대"]),
        (["0.5 mg", "0.25 mg", "2 mg"], ["0.25 mg", "0.5 mg", "2 mg"]),
        (["**M2**", "**M1**"], ["**M1**", "**M2**"]),
        (["L1: M3", "L2: M1", "L3: M2"], ["L2: M1", "L3: M2", "L1: M3"]),
        (["후기", "초기", "중기"], ["초기", "중기", "후기"]),
        (["late phase", "early phase"], ["early phase", "late phase"]),
    ):
        assert ordered_items(original) == expected, original
    for unordered in (["L1: Alpha", "L2: Beta"], ["1. Apple", "2. Banana"],
                      ["2 mg", "1 g"], ["M1", "M1"], ["A1 B2", "A2 B1"],
                      ["high affinity", "low clearance"], ["Apple", "Banana"]):
        assert ordered_items(unordered) is None, unordered

    template = example_bank()
    original = {**template["questions"][0], "format": "matching", "answer": "", "answer_units": [],
                "matching_left": ["alpha", "beta", "gamma"], "matching_right": ["M3", "M1", "M2"],
                "answer_pairs": [{"left": "alpha", "right": "M2"}, {"left": "beta", "right": "M3"},
                                 {"left": "gamma", "right": "M1"}]}
    before = copy.deepcopy(original)
    projected = matching_presentation(original)
    assert projected["matching_left"] == ["M1", "M2", "M3"]
    assert projected["matching_right"] == original["matching_left"]
    assert projected["answer_pairs"] == [{"left": p["right"], "right": p["left"]} for p in original["answer_pairs"]]
    assert matching_presentation(projected) == projected and original == before
    both = {**original, "matching_left": ["N3", "N1", "N2"]}
    assert matching_presentation(both)["matching_left"] == ["N1", "N2", "N3"]
    many = copy.deepcopy(original)
    many["answer_pairs"][1]["right"] = "M2"
    assert matching_presentation(many) == many, "many-to-one cannot be inverted"
    extra = {**original, "matching_right": ["M3", "M1", "M2", "M4"]}
    assert matching_presentation(extra) == extra, "distractors cannot become required rows"

    Base.metadata.create_all(engine)
    app.dependency_overrides[get_current_user] = lambda: USER
    with SessionLocal() as db:
        for run in ("left", "right", "many"):
            q = copy.deepcopy(projected if run == "left" else many if run == "many" else original)
            q.pop("matchingOrdered", None)
            bank = {**copy.deepcopy(template), "questions": [q]}
            db.add(Lecture(subject="matching", run_id=run, uid=f"matching-{run}",
                           date=datetime.date(2026, 10, 16), slot=1, slot_end=1, start_time="09:00", title=run))
            db.flush()
            db.add(QuizBank(subject="matching", run_id=run, build_id="v1", bank=bank,
                            validation={"pass": True}, pages={}, open_to_students=True))
        db.commit()
    client = TestClient(app)

    def post(path, body=None):
        response = client.post(path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()

    with patch("app.routes.bank.engine.now_ms", return_value=1792112400000):
        for run in ("left", "right", "many"):
            base = f"/api/lectures/matching/{run}/bank"
            current = post("/api/bank/batch/next", {"lectures": [{"subject": "matching", "runId": run}]})
            q = current["question"]
            expected = matching_presentation(many if run == "many" else original)
            assert q["matching_left"] == expected["matching_left"]
            assert q["matching_right"] == expected["matching_right"]
            assert q.get("matchingOrdered", False) == (run != "many")
            assert not any(key in q for key in ("answer", "answer_pairs", "answer_units", "correct_order"))
            assert post(base + "/next")["question"] == q
            token = {"reviewToken": current["reviewToken"]}
            prepared = post(base + "/prepare", token)
            assert prepared["answerPairs"] == expected["answer_pairs"]
            frames = post(base + "/prepare-buffer", token)["frames"]
            assert frames[current["reviewToken"]]["answer"]["answerPairs"] == prepared["answerPairs"]
            revealed = post(base + "/reveal", token)
            assert revealed["answerPairs"] == prepared["answerPairs"]
            post(base + "/rate", {**token, "rating": "Good"})
            restored = post(base + "/undo", token)
            assert restored["question"] == q
            assert restored["answer"]["answerPairs"] == prepared["answerPairs"]
            with SessionLocal() as db:
                row = db.get(QuizBank, ("matching", run))
                assert "matchingOrdered" not in row.bank["questions"][0]
                snapshot = db.get(BankState, (USER.id, "matching", run)).state["served"]["question_snapshot"]
                assert snapshot["matching_left"] == row.bank["questions"][0]["matching_left"]
    print("PASS: numbered/ordinal matching order, reversible pairs, reuse/distractors, public answers, batch/resume/buffer/undo")


if __name__ == "__main__":
    main()
