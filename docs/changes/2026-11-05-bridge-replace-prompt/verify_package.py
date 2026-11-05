"""Build the local extension ZIP and verify each included source byte."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
subprocess.run(['node', 'web/scripts/pack-extension.mjs'], cwd=ROOT, check=True)
package = ROOT / 'web/public/studyez-extension.zip'
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    manifest = json.loads(archive.read('manifest.json'))
    assert manifest['version'] == '1.3.22'
    for name in archive.namelist():
        path = ROOT / 'bridge' / name
        assert path.resolve().is_relative_to((ROOT / 'bridge').resolve())
        assert archive.read(name) == path.read_bytes(), name
    files = archive.namelist()
result = dict(path=str(package), version=manifest['version'], files=files,
              sha256=hashlib.sha256(package.read_bytes()).hexdigest())
(HERE / 'package.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
