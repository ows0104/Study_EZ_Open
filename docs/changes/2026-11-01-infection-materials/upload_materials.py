"""Publish only the fixed and verified notes_prev/jokbo material plan."""
import dataclasses
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runner import ahead, publish
from runner.cycle import runner_token

HERE = Path(__file__).resolve().parent
plan_path = HERE / "upload-plan.json"
verification = json.loads((HERE / "materials-verification.json").read_text(encoding="utf-8"))
assert verification["status"] == "passed"
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == verification["plan_sha256"]
raw = json.loads(plan_path.read_text(encoding="utf-8"))
inventory = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))
cells = {c.key: c for c in ahead.read_cells(Path(inventory["timetable"]))}
plans = []
for row in raw["lectures"]:
    item = dataclasses.replace(cells[row["run_id"]].as_lecture(), title=row["lecture_payload"]["title"])
    plan = publish.LecturePlan(subject=row["subject"], run_id=row["run_id"], item=item, ahead=True,
                               uploads=[publish.Upload(u["kind"], Path(u["path"])) for u in row["uploads"]])
    assert plan.payload == row["lecture_payload"]
    assert all(u.kind in ("notes_prev", "jokbo") for u in plan.uploads)
    plans.append(plan)
assert len(plans) == 71
token = runner_token(None)
assert token
log_path = HERE / "upload.log"
with log_path.open("a", encoding="utf-8") as handle:
    def log(message):
        print(message, flush=True)
        handle.write(message + "\n")
        handle.flush()
    client = publish.Client(publish.DEFAULT_API_BASE, token, timeout=180)
    log(f"START approved material upload: {len(plans)} lectures, 138 files")
    report = publish.publish(plans, client, ROOT / "runs", log=log)
    result = dataclasses.asdict(report)
    result["plan_sha256"] = verification["plan_sha256"]
    (HERE / "upload-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(json.dumps(result, ensure_ascii=False))
    if report.failures or report.unlinked or report.linked != 71:
        raise SystemExit(1)
