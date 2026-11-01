"""Apply the verified 2026 exam assets, leaving existing lecture notes intact."""
from pathlib import Path
import dataclasses
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from runner import ahead,publish
from runner.cycle import runner_token

HERE=Path(__file__).resolve().parent
plan_path=HERE/"upload-plan.json"
plan=json.loads(plan_path.read_text(encoding="utf-8"))
verification=json.loads((HERE/"materials-verification.json").read_text(encoding="utf-8"))
assert verification["status"]=="passed"
assert hashlib.sha256(plan_path.read_bytes()).hexdigest()==verification["plan_sha256"]
before=json.loads((HERE/"remote-before.json").read_text(encoding="utf-8"))
existing={r["run_id"]:r for r in before["lectures"]}
new=[r["lecture_payload"] for r in plan["lectures"] if r["run_id"] not in existing]
assert len(new)==9
cells={c.key:c for c in ahead.read_cells(ROOT/"data/timetable/2026_본1_2학기_시간표.json")}
client=publish.Client(publish.DEFAULT_API_BASE,runner_token(None),timeout=180)
with (HERE/"upload.log").open("a",encoding="utf-8") as handle:
    def log(message):
        print(message,flush=True);handle.write(message+"\n");handle.flush()
    response=client.call("POST","/api/admin/lectures",new)
    assert response["linked"]==9 and response["unlinked"]==0,response
    log("9 additional timetable seats registered; existing 71 lecture records retained.")
    ledger=publish.load_ledger(ROOT/"runs",client.base)
    report=publish.Report(lectures=80,linked=80)
    for row in plan["lectures"]:
        item=dataclasses.replace(cells[row["run_id"]].as_lecture(),title=row["lecture_payload"]["title"])
        lecture=publish.LecturePlan(subject=plan["subject"],run_id=row["run_id"],item=item,ahead=True,
                                    uploads=[publish.Upload("jokbo",Path(row["path"]))])
        try:
            publish._publish_one(lecture,client,ledger,report,force=False,log=log)
        except Exception as error:
            report.failures.append(f"{row['run_id']}: {type(error).__name__}: {error}")
            log(report.failures[-1])
        finally:
            publish.save_ledger(ROOT/"runs",client.base,ledger)
    result={**dataclasses.asdict(report),"plan_sha256":verification["plan_sha256"]}
    (HERE/"upload-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log(json.dumps(result,ensure_ascii=False))
    assert not report.failures,result
