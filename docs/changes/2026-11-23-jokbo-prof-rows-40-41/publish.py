"""정정한 두 족보 PDF로 261118_05·261118_02의 jokbo 첨부만 교체한다(사용자 2026-11-23 「응, 교체해줘」).

파일 이름이 같아 저장소의 같은 키를 덮어쓴다. 그래서 먼저 운영 객체가 이전 export(v2) 파일과 바이트로 같은지 확인한다.
v2 파일이 보관본이다. 강의·다른 자산·은행은 건드리지 않았는지 전후로 비교한다. DB에는 쓰지 않는다(업로드 API만).

    <메인>/server/.venv/Scripts/python.exe publish.py <메인 체크아웃 경로>   (cwd = <메인>/server)
"""
from pathlib import Path
import hashlib, json, os, sys

HERE = Path(__file__).resolve().parent
MAIN = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(MAIN)); sys.path.insert(0, str(MAIN / "server")); os.chdir(MAIN / "server")
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset, Lecture, QuizBank
from app.storage import ObjectStorage
from app.config import get_settings
from runner.transport import Client, Upload, DEFAULT_API_BASE, _put_with_retry, lecture_path

SUBJECT = "감염과 면역"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    with SessionLocal() as db:
        assets = sorted(((a.run_id, a.kind, a.filename, a.object_key, a.size_bytes) for a in
                         db.scalars(select(Asset).where(Asset.subject == SUBJECT))))
        lectures = sorted(((l.run_id, l.title, l.professors) for l in db.scalars(select(Lecture).where(Lecture.subject == SUBJECT))), key=str)
        banks = sorted(((b.run_id, b.build_id) for b in db.scalars(select(QuizBank).where(QuizBank.subject == SUBJECT))), key=str)
    return assets, lectures, banks


def remote(storage, key):
    body = storage.client.get_object(Bucket=storage.bucket, Key=key)["Body"]; h = hashlib.sha256()
    try:
        for chunk in body.iter_chunks(1 << 20): h.update(chunk)
    finally:
        body.close()
    return h.hexdigest()


def main():
    plan = json.loads((HERE / "rebuild-plan.json").read_text(encoding="utf-8"))
    rows = []
    for row in plan["lectures"]:
        meta = plan["files"][row["file_key"]]
        assert sha(row["path"]) == meta["sha256"] == row["sha256"]
        assert sha(meta["replaces"]["path"]) == meta["replaces"]["sha256"]
        rows.append((row, meta))
    before = inventory()
    storage = ObjectStorage()
    keys = {}
    for row, meta in rows:
        live = [a for a in before[0] if a[0] == row["run_id"] and a[1] == "jokbo"]
        assert len(live) == 1 and live[0][2] == Path(row["path"]).name, live
        keys[row["run_id"]] = live[0][3]
        assert remote(storage, live[0][3]) == meta["replaces"]["sha256"], "운영 첨부가 v2와 다르다 — 멈춘다"
        print("BEFORE VERIFIED", row["run_id"], meta["replaces"]["sha256"][:12], flush=True)
    client = Client(DEFAULT_API_BASE, get_settings().runner_token, timeout=180)
    done = []
    for row, meta in rows:
        upload = Upload("jokbo", Path(row["path"])); payload = [upload.payload()]
        base = lecture_path(SUBJECT, row["run_id"])
        signed = client.call("POST", base + "/uploads", payload)
        assert signed["files"][0]["objectKey"] == keys[row["run_id"]]
        _put_with_retry(client, signed["files"][0]["uploadUrl"], upload)
        result = client.call("POST", base + "/uploads/complete", payload)
        assert not result.get("missing"), result
        got = remote(storage, keys[row["run_id"]])
        assert got == meta["sha256"], (row["run_id"], got)
        done.append({"run_id": row["run_id"], "filename": Path(row["path"]).name, "objectKey": keys[row["run_id"]],
                     "before": meta["replaces"]["sha256"], "after": got, "archive": meta["replaces"]["path"]})
        print("REPLACED", row["run_id"], got[:12], flush=True)
    after = inventory()
    changed = set(before[0]) ^ set(after[0])
    assert all(a[0] in keys and a[1] == "jokbo" for a in changed), changed
    assert before[1] == after[1] and before[2] == after[2]
    (HERE / "publish-result.json").write_text(json.dumps(
        {"status": "passed", "approval": "사용자 2026-11-23 「응, 교체해줘」", "files": done,
         "otherAssetsUnchanged": True, "lecturesUnchanged": True, "banksUnchanged": True,
         "rebuildPlanSha256": sha(HERE / "rebuild-plan.json")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE", len(done))


if __name__ == "__main__":
    main()
