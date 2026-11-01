"""Read-only production DB/object-store verification of the uploaded plan."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT / "server")
sys.path.insert(0, str(ROOT / "server"))
from sqlalchemy import select, func
from app.config import get_settings
from app.database import SessionLocal
from app.models import Asset, Lecture, QuizBank
from app.storage import ObjectStorage

HERE = Path(__file__).resolve().parent
plan = json.loads((HERE / "upload-plan.json").read_text(encoding="utf-8"))
expected = {(p["run_id"], u["kind"]): u for p in plan["lectures"] for u in p["uploads"]}
assert len(expected) == 138
assert not get_settings().local_test_mode
with SessionLocal() as db:
    lectures = db.scalars(select(Lecture).where(Lecture.subject == plan["subject"])).all()
    assets = db.scalars(select(Asset).where(Asset.subject == plan["subject"])).all()
    assert {l.run_id for l in lectures} == {p["run_id"] for p in plan["lectures"]}
    assert all(l.timetable_event_id for l in lectures)
    assert all(l.version is None for l in lectures)
    assert db.scalar(select(func.count()).select_from(QuizBank).where(QuizBank.subject == plan["subject"])) == 0
    assert len(assets) == 138
    assert {(a.run_id, a.kind) for a in assets} == set(expected)
    rows = [{"run_id": a.run_id, "kind": a.kind, "filename": a.filename, "object_key": a.object_key,
             "size_bytes": a.size_bytes, "content_type": a.content_type} for a in assets]

storage = ObjectStorage()
def verify(row):
    local = Path(expected[(row["run_id"], row["kind"])]["path"])
    assert row["filename"] == unicodedata.normalize("NFC", local.name)
    head = storage.head(row["object_key"])
    assert head and head["ContentLength"] == local.stat().st_size == row["size_bytes"]
    assert head.get("ContentType") == "application/pdf"
    assert row["content_type"] == "application/pdf"
    # Read the actual stored bytes, rather than trusting upload-ledger metadata.
    answer = storage.client.get_object(Bucket=storage.bucket, Key=row["object_key"])
    digest = hashlib.sha256()
    body = answer["Body"]
    try:
        for chunk in body.iter_chunks(1024 * 1024):
            digest.update(chunk)
    finally:
        body.close()
    assert digest.hexdigest() == hashlib.sha256(local.read_bytes()).hexdigest(), local
    return {**row, "sha256": digest.hexdigest(), "verified": True}

verified = []
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for row in pool.map(verify, rows):
        verified.append(row)
        print(f"VERIFIED {len(verified)}/138 {row['run_id']} {row['kind']}", flush=True)
result = {"status": "passed", "lectures": 71, "timetable_linked": 71, "quiz_banks_created": 0,
          "notes_prev": 71, "jokbo": 67, "files": verified}
(HERE / "upload-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("PASS: 71 lectures linked; 138 stored PDF byte hashes match.")
