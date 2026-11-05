"""Preview cloze answers are positioned only in revealed/saved answer responses."""
import os
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

_TMP = Path(tempfile.mkdtemp(prefix="studyez-preview-cloze-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
                  RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture
from app.quiz_cloze import revealed_cloze
from app.routes.cards import plain_stem

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
BASE = "/api/lectures/cloze/261102_01"
SOURCE = "**定義**: {{c1::alpha, beta::用語}}と{{c1::gamma}}。\n{{c9::delta\nepsilon::複数行}}。"
PARTS = [{"text": "**定義**: "}, {"text": "alpha, beta", "blank": True}, {"text": "と"},
         {"text": "gamma", "blank": True}, {"text": "。\n"},
         {"text": "delta\nepsilon", "blank": True}, {"text": "。"}]


def main():
    # Source compatibility includes hints, repeated ids and multiline answers.
    assert revealed_cloze(SimpleNamespace(qtype="cloze", source_stem=SOURCE,
                                         stem=plain_stem(SOURCE))) == {"clozeParts": PARTS}
    for source in ("{{c1::x}} {{c2::}}", "{{c1::x::{{bad}}}}", "{{c1::{{c2::x}}}}"):
        assert not revealed_cloze(SimpleNamespace(qtype="cloze", source_stem=source,
                                                  stem=plain_stem(source))), source
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="cloze", run_id="261102_01", uid="261102_01#cloze", date=date(2026, 11, 2),
                       slot=1, slot_end=1, start_time="09:00", title="Cloze", professors=[], author="", version=1))
        db.commit()
    items = [
        {"id": "c1", "qtype": "cloze", "stem": plain_stem(SOURCE), "source_stem": SOURCE, "answer": "Separate answer"},
        {"id": "c2", "qtype": "cloze", "stem": "Old [____]", "answer": "Legacy"},
        {"id": "c3", "qtype": "cloze", "stem": "Edited [____]", "source_stem": "Other {{c1::hidden}}", "answer": "Edited"},
        {"id": "c4", "qtype": "cloze", "stem": "Malformed", "source_stem": "{{c1::}}", "answer": "Fallback"},
        {"id": "c5", "qtype": "basic", "stem": "Basic", "source_stem": SOURCE, "answer": "Basic answer"},
        {"id": "c6", "qtype": "ox", "stem": "OX", "source_stem": SOURCE, "answer": "O"},
        {"id": "c7", "qtype": "cloze", "stem": plain_stem(SOURCE), "source_stem": SOURCE, "answer": "Extra",
         "learning_support": {"study_track": "extra"}},
    ]
    client = TestClient(app)
    for kind, rows in (("pre", items), ("main", items[:1])):
        response = client.put(f"/api/admin/lectures/cloze/261102_01/{kind}-items", json={"items": rows}, headers=RUNNER)
        assert response.status_code == 200, response.text
    assert client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c1"}).status_code == 401
    front = client.get(f"{BASE}/prequiz", headers=USER)
    assert front.status_code == 200
    for row in front.json()["items"]:
        assert not {"sourceStem", "source_stem", "clozeParts", "answer"}.intersection(row)
    assert "alpha" not in front.text and "hidden" not in front.text
    assert front.json()["items"][0]["stem"] == plain_stem(SOURCE)
    preload = client.post(f"{BASE}/prequiz/slides", json={"itemIds": ["c1"]}, headers=USER)
    assert preload.json() == {"urls": []}
    result = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c1"}, headers=USER).json()
    assert result["clozeParts"] == PARTS and result["answer"] == "Separate answer"
    assert client.get(f"{BASE}/prequiz", headers=USER).json()["answered"] == 0
    for item in items[1:6]:
        result = client.post(f"{BASE}/prequiz/reveal", json={"itemId": item["id"]}, headers=USER).json()
        assert "clozeParts" not in result and result["answer"] == item["answer"], result
    assert "clozeParts" not in client.post(f"{BASE}/mainquiz/reveal", json={"itemId": "c1"}, headers=USER).json()
    for item in items:
        response = client.post(f"{BASE}/prequiz/check", json={"itemId": item["id"], "understood": item["id"] not in ("c1", "c7")}, headers=USER)
        assert response.status_code == 200, response.text
    # A fresh load of the completed screen gets the same positioned answers.
    saved = client.get(BASE, headers=USER).json()["prequiz"]
    assert [row["itemId"] for row in saved["missed"]] == ["c1"]
    assert saved["missed"][0]["clozeParts"] == PARTS
    assert saved["extraMissed"][0]["clozeParts"] == PARTS
    undone = client.post(f"{BASE}/prequiz/undo", headers=USER).json()
    assert undone["itemId"] == "c7" and undone["attempt"] is None and undone["clozeParts"] == PARTS
    assert client.get(BASE, headers=USER).json()["prequiz"]["extraMissed"] == []
    print("PASS: positioned reveal/undo/missed/extraMissed, hidden fronts/preloads, fallback, basic/OX/main compatibility")


if __name__ == "__main__":
    main()
