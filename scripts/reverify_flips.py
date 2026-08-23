"""O/X 를 뒤집은 카드만 재현 검사를 다시 돌린다.

`runs/_ox_flips.audit.json` 이 무엇을 고쳤는지 들고 있다. 그 id 만 --only 로 넘긴다.
나머지 카드의 판정은 그대로 살아 있고, apply 가 전체를 다시 써서 완전한 상태로 만든다.
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
audit = json.loads((REPO / "runs/_ox_flips.audit.json").read_text(encoding="utf-8"))

by_run = defaultdict(list)
for f in audit["flips"]:
    by_run[f["run"]].append(f["id"])


def one(item):
    run, ids = item
    d = REPO / "runs" / run
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with (d / "reverify.log").open("w", encoding="utf-8") as fh:
        r = subprocess.run(
            [sys.executable, "-m", "pdf2anki.reproduce", "check", str(d),
             "--only", ",".join(sorted(ids)), "--skip-canary"],
            cwd=str(REPO), env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    v = {}
    p = d / "items.reproduced.json"
    if p.exists():
        cards = {c["id"]: c for c in json.loads(p.read_text(encoding="utf-8"))["cards"]}
        v = {i: (cards.get(i, {}).get("reproduce") or {}).get("verdict") for i in sorted(ids)}
    print(f"[{'OK ' if r.returncode == 0 else '실패'}] {run}  {v}", flush=True)
    return {"run": run, "rc": r.returncode, "verdicts": v}


with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    res = list(ex.map(one, sorted(by_run.items())))

allv = [v for r in res for v in r["verdicts"].values()]
print(f"\n끝났다. {sum(1 for r in res if r['rc'] == 0)}/{len(res)}편")
print("판정:", {k: allv.count(k) for k in sorted(set(map(str, allv)))})
bad = [(r["run"], i, v) for r in res for i, v in r["verdicts"].items() if v != "same"]
if bad:
    print("\nsame 이 아닌 것 — 내가 세운 진술이 틀렸을 수 있다:")
    for b in bad:
        print("  ", b)
