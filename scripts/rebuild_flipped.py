"""O/X 를 뒤집은 편의 덱 파일만 다시 굽는다. LLM 을 부르지 않아 돈이 들지 않는다."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
JOKBO = REPO / "runs/_jokbo/병리학"
audit = json.loads((REPO / "runs/_ox_flips.audit.json").read_text(encoding="utf-8"))
runs = sorted({f["run"] for f in audit["flips"]})

env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
fail = []
for run in runs:
    d = REPO / "runs" / run
    cfg = json.loads((d / "run.config.json").read_text(encoding="utf-8"))
    r = subprocess.run(
        [sys.executable, "-m", "pdf2anki.build", str(d),
         "--deck", cfg["deck"], "--id", cfg["id"], "--jokbo-dir", str(JOKBO)],
        cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-1:] or [(r.stderr or "")[-160:]]
    print(f"[{'OK ' if r.returncode == 0 else '실패'}] {run}  {tail[0][:100]}", flush=True)
    if r.returncode:
        fail.append(run)
        (d / "rebuild.log").write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")

print(f"\n{len(runs) - len(fail)}/{len(runs)}편 다시 구웠다.")
for f in fail:
    print(f"  실패: {f}  (runs/{f}/rebuild.log)")
