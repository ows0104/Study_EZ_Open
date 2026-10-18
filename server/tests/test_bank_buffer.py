"""Read-only lookahead, including projections of ratings still being saved."""
import copy
import datetime
from unittest.mock import patch

from tests.test_bank import STUDENT as USER
from tests.bank_fixtures import simulation_bank
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from app.auth import get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, BankPersonalEdit, BankState, Lecture, QuizBank, SLIDE_KINDS
from app.storage import ObjectStorage


def main():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_current_user] = lambda: USER
    with SessionLocal() as db:
        for run in ("solo", "A", "B", "project"):
            bank = simulation_bank()
            bank["questions"] = [q for q in bank["questions"] if q["retrieval_direction"] == "direct"]
            db.add(Lecture(subject="buffer", run_id=run, uid=f"buffer-{run}",
                date=datetime.date(2026, 10, 16), slot=1, slot_end=1, start_time="09:00", title=run))
            db.flush()
            db.add(QuizBank(subject="buffer", run_id=run, build_id="v1", status="ready", open_to_students=True,
                bank=bank, validation={"pass": True}, pages={q['question_id']: [1] for q in bank['questions']}))
            db.flush()
            db.add(Asset(id='buffer-slide-'+run, subject='buffer', run_id=run, kind=SLIDE_KINDS['bank'],
                slide_no=1, filename='slide.png', object_key=f'buffer/{run}/slide.png'))
            first = bank['questions'][0]
            db.add(BankPersonalEdit(user_id=USER.id, subject='buffer', run_id=run,
                question_id=first['question_id'], original=copy.deepcopy(first),
                question='PRIVATE-'+run, answer='PRIVATE-ANSWER-'+run, comment=''))
        db.commit()
    client = TestClient(app)
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(1))

    def post(path, body=None):
        response = client.post(path, json=body or {})
        assert response.status_code == 200, response.text
        return response.json()

    def snapshot():
        with SessionLocal() as db:
            return {row.run_id: copy.deepcopy(row.state) for row in db.scalars(select(BankState))}

    with patch("app.routes.bank.engine.now_ms", return_value=1792112400000):
        for lectures in (None, [{"subject": "buffer", "runId": r} for r in ("A", "B")]):
            base = "/api/lectures/buffer/solo/bank"
            current = post("/api/bank/batch/next", {"lectures": lectures}) if lectures else post(base + "/next?choiceProtocol=true")
            if lectures:
                base = f"/api/lectures/buffer/{current['lecture']['runId']}/bank"
            body = {"reviewToken": current["reviewToken"], "lectures": lectures}
            before = snapshot()
            near = post(base + "/prepare-buffer", {**body, 'lookahead': 'near'})
            assert near['lookahead'] == 'near' and len(near['frames']) <= 5
            assert set(near['frames'][current['reviewToken']]['previews']) == {'Again', 'Hard', 'Good', 'Easy'}
            assert snapshot() == before, 'the short initial window wrote study state'
            queries.clear()
            with patch('app.routes.bank.ObjectStorage', wraps=ObjectStorage) as storage:
                frames = post(base + "/prepare-buffer", body)["frames"]
                assert storage.call_count == 1, 'each rating rebuilt the slide signing client'
            assert len(queries) <= 20, f"lookahead reread static data {len(queries)} times"
            assert snapshot() == before, "preloading changed exposure, choices, session or history"
            assert len(frames) <= 41
            for prepared in frames.values():
                ref = prepared['next'].get('lecture') or {'runId': 'solo'}
                urls = [slide['url'] for slide in prepared['answer']['slides']]
                assert urls and all(f"buffer/{ref['runId']}/slide.png" in url for url in urls), (ref, urls)
            assert frames[current['reviewToken']]['next']['question']['question'].startswith('PRIVATE-')
            assert frames[current['reviewToken']]['answer']['answer'].startswith('PRIVATE-ANSWER-')
            for first in ("Again", "Hard", "Good", "Easy"):
                successor = frames[current["reviewToken"]]["previews"][first]
                if successor.get("question"):
                    assert set(frames[successor["reviewToken"]]["previews"]) == {"Again", "Hard", "Good", "Easy"}, first
            assert not before[current.get("lecture", {}).get("runId", "solo")]["served"]["revealed"]
            for rating in ("Good", "Good", "Hard"):
                prepared = frames[current["reviewToken"]]
                assert prepared["answer"]["answer"]
                assert "answer" not in prepared["next"]["question"]
                expected = prepared["previews"][rating]
                token = {"reviewToken": current["reviewToken"]}
                post(base + "/reveal", {**token, "responseTimeMs": 1250})
                actual = post(base + "/rate", {**token, "rating": rating, "advance": True, "lectures": lectures})["next"]
                assert actual["question"] == expected["question"], (rating, actual, expected)
                assert actual["reviewToken"] == expected["reviewToken"]
                saved = snapshot()
                assert saved[base.split("/")[4]]["history"][-1]["response_time_sec"] == 1.25
                retry = post(base + "/rate", {**token, "rating": rating, "advance": True,
                    "lectures": lectures, "retrySafe": True})["next"]
                assert retry["reviewToken"] == actual["reviewToken"] and retry["question"] == actual["question"]
                assert snapshot() == saved, "retry duplicated or changed a saved review"
                assert client.post(base + "/rate", json={**token, "rating": "Easy", "retrySafe": True}).status_code == 409
                current = actual
                if lectures:
                    base = f"/api/lectures/buffer/{current['lecture']['runId']}/bank"
            before = snapshot()
            fresh = post(base + "/prepare-buffer", {"reviewToken": current["reviewToken"], "lectures": lectures})
            assert current["reviewToken"] in fresh["frames"] and snapshot() == before

        base = "/api/lectures/buffer/project/bank"
        current = post(base + "/next?choiceProtocol=true")
        before = snapshot()
        projected = post(base + "/prepare-buffer", {"reviewToken": current["reviewToken"], "ratings": ["Hard", "Easy"]})["frames"]
        assert snapshot() == before
        for rating in ("Hard", "Easy"):
            token = {"reviewToken": current["reviewToken"]}
            post(base + "/reveal", token)
            current = post(base + "/rate", {**token, "rating": rating, "advance": True})["next"]
        assert projected[current["reviewToken"]]["next"]["question"] == current["question"]
        assert projected[current["reviewToken"]]["previews"]["Good"]["question"]
        assert client.post(base + "/prepare-buffer", json={"reviewToken": "stale"}).status_code == 409
        assert client.post(base + "/prepare-buffer", json={"reviewToken": current["reviewToken"],
            "lectures": [{"subject": "buffer", "runId": "A"}]}).status_code == 409
        assert client.post(base + "/prepare-buffer", json={"reviewToken": current["reviewToken"], "ratings": ["Good"] * 13}).status_code == 422
    print("PASS: read-only solo/batch lookahead and pending projections match saves; retry-safe ratings never duplicate history")


if __name__ == "__main__":
    main()
