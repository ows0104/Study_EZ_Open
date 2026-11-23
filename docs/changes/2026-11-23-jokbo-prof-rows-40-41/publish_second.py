"""2차 족보 첨부 5개를 올해 교수 기준 PDF로 교체한다(사용자 2026-11-23 「응, 5개 고쳐줘」).

파일 이름이 바뀌므로 서버 complete_uploads가 옛 jokbo 자산 행과 객체를 지운다(SINGULAR_KINDS).
그래서 먼저 운영 객체가 v2 보관본과 바이트로 같은지 확인한다. 업로드 API(러너 토큰)만 쓰고 DB에는 직접 쓰지 않는다.

    <메인>/server/.venv/Scripts/python.exe publish_second.py <메인 체크아웃 경로>
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


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inventory():
    with SessionLocal() as db:
        assets = sorted((a.run_id, a.kind, a.filename, a.object_key, a.size_bytes) for a in db.scalars(select(Asset).where(Asset.subject == SUBJECT)))
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
    plan = json.loads((HERE / "rebuild-second-plan.json").read_text(encoding="utf-8"))
    before = inventory(); storage = ObjectStorage()
    for row in plan["lectures"]:
        meta = plan["files"][row["run_id"]]; old = meta["replaces"]
        assert sha(row["path"]) == meta["sha256"] == row["sha256"]
        live = [a for a in before[0] if a[0] == row["run_id"] and a[1] == "jokbo"]
        assert len(live) == 1 and live[0][2] == old["filename"] and live[0][3] == old["objectKey"], live
        assert sha(old["archive"]) == old["sha256"] == remote(storage, old["objectKey"]), "운영 첨부가 v2 보관본과 다르다 — 멈춘다"
        print("BEFORE VERIFIED", row["run_id"], old["filename"], old["sha256"][:12], flush=True)
    client = Client(DEFAULT_API_BASE, get_settings().runner_token, timeout=180)
    done = []
    for row in plan["lectures"]:
        meta = plan["files"][row["run_id"]]
        upload = Upload("jokbo", Path(row["path"])); payload = [upload.payload()]
        base = lecture_path(SUBJECT, row["run_id"])
        signed = client.call("POST", base + "/uploads", payload)
        key = signed["files"][0]["objectKey"]
        _put_with_retry(client, signed["files"][0]["uploadUrl"], upload)
        result = client.call("POST", base + "/uploads/complete", payload)
        assert not result.get("missing"), result
        got = remote(storage, key); assert got == meta["sha256"], (row["run_id"], got)
        done.append({"run_id": row["run_id"], "before": meta["replaces"], "after": {"filename": Path(row["path"]).name, "objectKey": key, "sha256": got}})
        print("REPLACED", row["run_id"], Path(row["path"]).name, got[:12], flush=True)
    after = inventory()
    runs = {r["run_id"] for r in plan["lectures"]}
    changed = set(before[0]) ^ set(after[0])
    assert all(a[0] in runs and a[1] == "jokbo" for a in changed), changed
    jok = {a[0]: a for a in after[0] if a[1] == "jokbo" and a[0] in runs}
    assert all(jok[d["run_id"]][2] == d["after"]["filename"] for d in done) and len(jok) == len(runs)
    assert before[1] == after[1] and before[2] == after[2]
    (HERE / "publish-second-result.json").write_text(json.dumps(
        {"status": "passed", "approval": "사용자 2026-11-23 「응, 5개 고쳐줘」", "files": done, "otherAssetsUnchanged": True,
         "lecturesUnchanged": True, "banksUnchanged": True, "planSha256": sha(HERE / "rebuild-second-plan.json")},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE", len(done))


if __name__ == "__main__":
    main()
