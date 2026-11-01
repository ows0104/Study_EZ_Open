"""Assert current-production preservation and the exact four-file overlay."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'));import workflow_scope
meta=json.loads((HERE/'isolation.json').read_text(encoding='utf-8'))
base=Path(meta['baseline_source'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={p.relative_to(base).as_posix():sha(p) for p in workflow_scope.files(base,'site')}
after={p.relative_to(ROOT).as_posix():sha(p) for p in workflow_scope.files(ROOT,'site')}
changed={name for name in before.keys()|after.keys() if before.get(name)!=after.get(name)}
assert changed==set(meta['overlays']),changed
for name,digest in meta['overlays'].items():assert after[name]==digest
baseline=meta['production_baseline'];assert baseline['status']=='passed'
for name,digest in baseline['files'].items():
    target=Path(meta['baseline_artifact'])/name
    assert sha(target)==digest
print('PASS: exact current-production baseline and only four approved source/test changes.')
