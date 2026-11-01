"""HTTP 경유 일반·모아풀기의 순서, 페이지 메타데이터, 새로고침·되돌리기 검증."""
import copy
import datetime
from unittest.mock import patch

from tests.test_bank import STUDENT as USER
from tests.test_question_order import make_bank, NOW
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, QuizBank
from app.study_engine.memory import DAY_MS


def main():
    Base.metadata.create_all(engine)
    standalone = make_bank([("A-reverse", "CA", "reverse", 50, ["A"]),
                            ("A", "CA", "direct", 20, [])] +
                           [(f"B{i}", f"CB{i}", "direct", 30 + i, []) for i in range(5)])
    # The first slide is Optional+Advanced. Core/Important fillers must not jump ahead.
    standalone["questions"][1].update(tier="Optional", advanced=True)
    for i, q in enumerate(standalone["questions"][2:]):
        q.update(tier="Important" if i % 2 else "Core", advanced=bool(i % 2))
    mixed_a = copy.deepcopy(standalone)
    mixed_a["questions"] = mixed_a["questions"][:2]
    mixed_b = make_bank([(f"B{i}", "CA", "direct", i + 1, []) for i in range(4)])
    # Stored slide positions take precedence over the source-ref fallback.
    pages = {"A": [1], "A-reverse": [1], **{f"B{i}": [i + 2] for i in range(5)}}
    with SessionLocal() as db:
        for name, bank in (("single", standalone), ("A", mixed_a), ("B", mixed_b)):
            db.add(Lecture(subject="order", run_id=name, uid=f"order-{name}", date=datetime.date(2026, 10, 12),
                           slot=1, slot_end=1, start_time="09:00", title=name))
            db.flush()
            db.add(QuizBank(subject="order", run_id=name, build_id=name, bank=bank, pages=pages if name != "B" else {},
                            validation={"pass": True}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)

    def post(url, payload=None):
        response = client.post(url, json=payload or {})
        assert response.status_code == 200, response.text
        return response.json()

    def rate(current):
        lecture = current.get("lecture") or {"runId": "single"}
        base = f"/api/lectures/order/{lecture['runId']}/bank"
        token = {"reviewToken": current["reviewToken"]}
        post(base + "/reveal", token)
        return post(base + "/rate", {**token, "rating": "Again"})

    ticks = iter(range(NOW, NOW + 10000))
    with patch("app.routes.bank.engine.now_ms", side_effect=lambda: next(ticks)):
        sequence = []
        base = "/api/lectures/order/single/bank"
        for _ in standalone["questions"]:
            current = post(base + "/next?shuffle=true")
            sequence.append(current["question"]["question_id"])
            assert post(base + "/next")["reviewToken"] == current["reviewToken"]
            rate(current)
            if len(sequence) == 3:
                restored = post(base + "/undo", {"reviewToken": current["reviewToken"]})
                assert restored["question"]["question_id"] == current["question"]["question_id"]
                assert post(base + "/next")["reviewToken"] == restored["reviewToken"]
                rate(restored)
        assert sequence == ["A", "B0", "B1", "B2", "B3", "A-reverse", "B4"], sequence
        assert post(base + "/next")["lectureGoal"]["met"]
        selection = {"lectures": [{"subject": "order", "runId": name} for name in ("A", "B")]}
        sequence = []
        for _ in range(6):
            current = post("/api/bank/batch/next", selection)
            sequence.append((current["lecture"]["runId"], current["question"]["question_id"]))
            assert post("/api/bank/batch/next", {**selection, "resumeLecture": current["lecture"]})["reviewToken"] == current["reviewToken"]
            rate(current)
            if len(sequence) == 4:
                # Cross-lecture undo also removes that answer from the global interval count.
                restored = post("/api/bank/batch/undo", {**selection, "reviewToken": current["reviewToken"]})
                assert restored["lecture"]["runId"] == current["lecture"]["runId"]
                rate(restored)
        assert sequence == [("A", "A"), ("B", "B0"), ("B", "B1"), ("B", "B2"), ("B", "B3"), ("A", "A-reverse")], sequence
        assert post("/api/bank/batch/next", selection)["batchGoal"]["met"]
    # Both HTTP paths use weighted review selection, including candidates from all lectures.
    with patch("app.routes.bank.engine.now_ms", return_value=NOW + DAY_MS), \
         patch("app.study_engine.ordering.random.choices", side_effect=lambda pool, **kw: [pool[-1]]) as draw:
        post(base + "/session/start")
        assert post(base + "/next")["question"]["question_id"] == "B4"
        assert draw.call_count == 1 and len(draw.call_args.args[0]) == 7
        current = post("/api/bank/batch/next", selection)
        assert current["lecture"]["runId"] == "B"
        assert draw.call_count == 2 and len(draw.call_args.args[0]) == 6
    print("PASS: ordinary and batch HTTP order, stored slides, shared spacing, refresh, undo, weighted reviews")


if __name__ == "__main__":
    main()
