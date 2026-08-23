"""편들을 새 파이프라인으로 다시 굽는다. 편 단위로 병렬.

이어서 돌릴 수 있다 — **`regen.log` 가 이미 있는 편은 건너뛴다.** 계정을 바꿔
이어 받거나, 중간에 끊긴 것을 다시 밀 때 그대로 다시 부르면 된다.

`prep` 은 재사용한다. prep 산출물(`prep.json`/`prep.md`/`annotated.pdf`/`clean.pdf`/
`run.config.json`/`source.json`)과 `HOLD` 는 남기고 그 뒤 단계의 산출물만 지운다.
`HOLD` 를 지우지 않는 것이 중요하다 — 그것이 야간 배포 스케줄러를 막는 유일한 장치다.

동시 실행 수 기본값은 4다. 각 편의 재현 검사가 자체적으로 세션 4개를 띄우므로
최대 동시 세션이 16을 넘지 않는다. 더 올리면 그만큼 곱해진다.

    python scripts/regen_batch.py .                 # 남은 편 전부, 동시 4
    python scripts/regen_batch.py . 2               # 동시 2
    python scripts/regen_batch.py . 4 --all         # 이미 돈 편도 다시
    python scripts/regen_batch.py . 4 --dry-run     # 무엇을 돌릴지만 본다

먼저 `python -m pdf2anki.schema -o out/schema` 가 한 번 돌아 있어야 한다.
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PY = sys.executable
PATTERN = "runs/2608*/run.config.json"
KEEP = {"prep.json", "prep.md", "annotated.pdf", "clean.pdf",
        "run.config.json", "source.json", "HOLD"}

argv = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a for a in sys.argv[1:] if a.startswith("--")}
REPO = Path(argv[0] if argv else ".").resolve()
WORKERS = int(argv[1]) if len(argv) > 1 else 4
JOKBO = REPO / "runs/_jokbo/병리학"

runs = [p.parent for p in sorted(REPO.glob(PATTERN))]
if "--all" not in flags:
    runs = [d for d in runs if not (d / "regen.log").exists()]

print(f"대상 {len(runs)}편 · 동시 {WORKERS}편", flush=True)
if "--dry-run" in flags:
    for d in runs:
        print(f"   {d.name}")
    raise SystemExit(0)
if not runs:
    raise SystemExit("돌릴 편이 없다. 이미 돈 편도 다시 돌리려면 --all 을 줘라.")


def clean(d: Path) -> int:
    n = 0
    for p in list(d.iterdir()):
        if p.name in KEEP or p.name.endswith("_image_check.pdf"):
            continue
        if p.is_dir():
            if p.name == "media":
                for f in p.rglob("*"):
                    if f.is_file():
                        f.unlink()
                        n += 1
            continue
        p.unlink()
        n += 1
    return n


def one(d: Path) -> dict:
    t0 = time.time()
    removed = clean(d)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with (d / "regen.log").open("w", encoding="utf-8") as fh:
        r = subprocess.run(
            [PY, "-m", "pdf2anki.run", "--resume", str(d), "--jokbo-dir", str(JOKBO)],
            cwd=str(REPO), env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    out = {"run": d.name, "rc": r.returncode, "removed": removed,
           "minutes": round((time.time() - t0) / 60, 1)}
    rep = d / "run.report.json"
    if rep.exists():
        try:
            out["cost"] = json.loads(rep.read_text(encoding="utf-8"))["cumulative"]["cost_usd"]
        except Exception:
            pass
    items = d / "items.reproduced.json"
    if items.exists():
        try:
            cards = json.loads(items.read_text(encoding="utf-8"))["cards"]
            out["cards"] = len(cards)
            out["jokbo"] = sum(1 for c in cards if c["source_type"] == "jokbo")
            out["hit"] = sum(1 for c in cards if c.get("exam_hit"))
        except Exception:
            pass
    print(f"[{'OK ' if r.returncode == 0 else '실패'}] {d.name}  {out['minutes']:5.1f}분  "
          f"{out.get('cards', '-')}장 (기출 {out.get('jokbo', '-')}, hit {out.get('hit', '-')})",
          flush=True)
    return out


t0 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    results = list(ex.map(one, runs))

ok = [r for r in results if r["rc"] == 0]
print(f"\n끝났다. 성공 {len(ok)}/{len(results)}편 · 벽시계 {(time.time() - t0) / 60:.0f}분", flush=True)
for r in results:
    if r["rc"]:
        print(f"  실패: {r['run']}  ({r['run']}/regen.log 를 봐라)", flush=True)

# 이어 돌린 것까지 합쳐 남긴다.
path = REPO / "runs/_regen_report.json"
prev = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
seen = {r["run"] for r in results}
path.write_text(json.dumps([r for r in prev if r["run"] not in seen] + results,
                           ensure_ascii=False, indent=2), encoding="utf-8")
print(f"요약 → {path}", flush=True)
