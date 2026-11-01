"""Reproduce verified production and overlay only the approved block switch."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "output/releases/jokbo-web-deploy"
OUT = ROOT / "output/releases/block-auto-deploy"
OVERLAYS = ("web/CLAUDE.md", "web/src/bank/StudyOverview.tsx", "web/src/bank/studyBlocks.ts",
            "web/src/bank/useStudyCourse.ts", "web/src/calendar/entries.ts", "web/src/notices/GuidePage.tsx",
            "web/tests/study-blocks.test.cjs", "web/tests/study-block-transition.html",
            "web/tests/study-block-transition.tsx")
EXPECTED = "0ca1ec7b-bdc2-4775-8916-4b1dca98563d"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

assert not OUT.exists(), "Preserve an existing release source"
state = json.loads((BASE / "docs/changes/2026-11-01-jokbo-web-deploy/state.json").read_text(encoding="utf-8"))
deploy = next(d for d in state["deployments"] if d.get("revision") == EXPECTED)
assert deploy["status"] == "succeeded" and deploy["postchecks"][-1]["passed"]
candidate = deploy["candidate"]
sys.path.insert(0, str(BASE / "scripts"))
import workflow_scope
assert workflow_scope.fingerprint(BASE, "site") == candidate["source_hash"], "Production source changed"
baseline = BASE / candidate["artifact"]
ignore = shutil.ignore_patterns("node_modules", ".venv", "dist", "runs", "output", "__pycache__",
                               ".pytest_cache", ".wrangler", "local_test_data", "release", ".env*", "*.pyc", "*.tsbuildinfo")
OUT.mkdir(parents=True)
for name in (*workflow_scope.paths("site"), "runner", "quizgen", "quizbank"):
    source, dest = BASE / name, OUT / name
    if source.is_dir():
        shutil.copytree(source, dest, ignore=ignore)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
shutil.copytree(BASE / "web/node_modules", OUT / "web/node_modules")
for name in (".env", ".env.local", ".env.production", ".env.production.local"):
    if (BASE / "web" / name).exists():
        shutil.copyfile(BASE / "web" / name, OUT / "web" / name)
subprocess.run(["npm.cmd", "run", "build"], cwd=OUT / "web", check=True)
manifest = lambda folder: {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()}
expected = manifest(baseline)
assert manifest(OUT / "web/dist") == expected, "Production baseline was not reproduced exactly"
for name in OVERLAYS:
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, target)
meta = {"baseline_revision": EXPECTED, "baseline_source": str(BASE), "baseline_artifact": str(baseline),
        "baseline_source_hash": candidate["source_hash"], "baseline_files": expected,
        "overlays": {name: sha(ROOT / name) for name in OVERLAYS}, "verification_root": str(OUT)}
(HERE / "isolation.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
shutil.copytree(HERE, OUT / "docs/changes" / HERE.name)
print("PASS: production reproduced exactly; only nine approved source/document/test files overlaid")
