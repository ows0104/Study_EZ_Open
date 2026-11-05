from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[3]
BASE=Path(__file__).parent
WORK=ROOT/'work/cholinergic-rebuild-20261102'
manifest=json.loads((WORK/'inputs.json').read_text(encoding='utf-8'))
changed=[k for k,v in manifest.items() if hashlib.sha256(Path(v['path']).read_bytes()).hexdigest()!=v['sha256']]
assert not changed, f'Changed inputs: {changed}'
report=(BASE/'content-review.md').read_text(encoding='utf-8')
assert len(report)>3000, 'Missing or incomplete report'
info=json.loads((WORK/'result.json').read_text(encoding='utf-8'))
assert info.get('session_id') and info.get('text')==report
print(json.dumps({'inputs_preserved':len(manifest),'report_characters':len(report),
                  'session_id':info['session_id'],'medical_validation':'not_certified'},ensure_ascii=False))
