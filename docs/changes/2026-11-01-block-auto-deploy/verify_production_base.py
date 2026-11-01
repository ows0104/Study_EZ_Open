"""Verify that all other production source and its fixed candidate remain intact."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import workflow_scope
meta = json.loads((HERE / "isolation.json").read_text(encoding="utf-8"))
base = Path(meta["baseline_source"])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = {p.relative_to(base).as_posix(): sha(p) for p in workflow_scope.files(base, "site")}
after = {p.relative_to(ROOT).as_posix(): sha(p) for p in workflow_scope.files(ROOT, "site")}
changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
assert changed == set(meta["overlays"]), sorted(changed)
assert all(after[name] == digest for name, digest in meta["overlays"].items())
for name, digest in meta["baseline_files"].items():
    assert sha(Path(meta["baseline_artifact"]) / name) == digest
assert workflow_scope.fingerprint(base, "site") == meta["baseline_source_hash"]
print("PASS: exact current production baseline preserved; nine-file change allowlist verified")
