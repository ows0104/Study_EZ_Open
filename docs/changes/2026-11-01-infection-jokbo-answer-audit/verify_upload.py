"""Read-only verification of 2026 exam files and preservation of prior notes."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[3]
os.chdir(ROOT/"server")
sys.path.insert(0,str(ROOT/"server"))
from sqlalchemy import select,func
from app.config import get_settings
from app.database import SessionLocal
from app.models import Asset,Lecture,QuizBank
from app.storage import ObjectStorage

HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/"upload-plan.json").read_text(encoding="utf-8"))
before=json.loads((HERE/"remote-before.json").read_text(encoding="utf-8"))
assert get_settings().environment=="production"
expected={r["run_id"]:r for r in plan["lectures"]}
oldnotes={r["run_id"]:r for r in before["assets"] if r["kind"]=="notes_prev"}
assert len(expected)==80 and len(oldnotes)==71
with SessionLocal() as db:
    lectures=db.scalars(select(Lecture).where(Lecture.subject==plan["subject"])).all()
    assets=db.scalars(select(Asset).where(Asset.subject==plan["subject"])).all()
    assert {l.run_id for l in lectures}==set(expected)
    assert all(l.timetable_event_id for l in lectures)
    assert db.scalar(select(func.count()).select_from(QuizBank).where(QuizBank.subject==plan["subject"]))==before["quiz_banks"]==0
    assert len(assets)==151
    assert sum(a.kind=="jokbo" for a in assets)==80
    assert sum(a.kind=="notes_prev" for a in assets)==71
    for a in assets:
        assert a.kind in ("jokbo","notes_prev")
        if a.kind=="notes_prev":
            old=oldnotes[a.run_id]
            assert a.id==old["id"] and a.object_key==old["object_key"] and a.filename==old["filename"] and a.size_bytes==old["size_bytes"]
    rows=[{"run_id":a.run_id,"kind":a.kind,"filename":a.filename,"object_key":a.object_key,"size_bytes":a.size_bytes,"content_type":a.content_type} for a in assets if a.kind=="jokbo"]
    original={r["run_id"]:r for r in before["lectures"]}
    for l in lectures:
        if l.run_id not in original:continue
        old=original[l.run_id]
        for key in ("uid","title","slot","slot_end","start_time","professors","author","version","timetable_event_id"):
            assert getattr(l,key)==old[key],(l.run_id,key)
        assert str(l.date)==old["date"]

storage=ObjectStorage()
def check(row):
    wanted=expected[row["run_id"]]
    local=Path(wanted["path"])
    assert row["filename"]==local.name
    head=storage.head(row["object_key"])
    assert head and head["ContentLength"]==local.stat().st_size==row["size_bytes"]
    assert head.get("ContentType")==row["content_type"]=="application/pdf"
    answer=storage.client.get_object(Bucket=storage.bucket,Key=row["object_key"])
    digest=hashlib.sha256();body=answer["Body"]
    try:
        for chunk in body.iter_chunks(1024*1024):digest.update(chunk)
    finally:body.close()
    assert digest.hexdigest()==plan["files"][wanted["section"]]["sha256"]
    return {**row,"sha256":digest.hexdigest(),"verified":True}

verified=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for row in pool.map(check,rows):
        verified.append(row);print(f"VERIFIED {len(verified)}/80 {row['run_id']}",flush=True)
result={"status":"passed","lectures":80,"timetable_linked":80,"jokbo_2026":80,"previous_notes_unchanged":71,
        "quiz_banks_unchanged":0,"files":verified}
(HERE/"upload-verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PASS: 80 exam files match; 71 existing notes and lecture records retained.")
