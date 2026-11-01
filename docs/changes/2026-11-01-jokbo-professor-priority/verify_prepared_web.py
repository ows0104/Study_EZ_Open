"""Recheck the isolated source and repeat its production build for current evidence."""
from pathlib import Path
import hashlib, io, json, subprocess, zipfile
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
meta=json.loads((HERE/'web-source-manifest.json').read_text(encoding='utf-8'))
source=Path(meta['isolated_source'])
sha=lambda data:hashlib.sha256(data).hexdigest()
for name,digest in meta['overlay_files'].items():
    assert sha((ROOT/name).read_bytes())==sha((source/name).read_bytes())==digest
archive=subprocess.check_output(['git','archive','--format=zip',meta['base_revision'],'web','content','bridge','platform'],cwd=ROOT)
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    for name in z.namelist():
        if name.endswith('/') or name in meta['overlay_files'] or name in ('web/public/bank-prompt.json','web/public/studyez-extension.zip'):continue
        assert z.read(name)==(source/name).read_bytes(), 'Unexpected candidate change: '+name
subprocess.run(['node','--test','tests/review-professor.test.cjs','tests/bank-prompt-current.test.cjs'],cwd=source/'web',check=True)
subprocess.run(['npm.cmd','run','build'],cwd=source/'web',check=True)
def manifest(folder):return {p.relative_to(folder).as_posix():sha(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}
assert manifest(ROOT/'web/dist')==manifest(source/'web/dist')
print('PASS: exact deployed base plus reviewed overlays; no other uncommitted changes.')
