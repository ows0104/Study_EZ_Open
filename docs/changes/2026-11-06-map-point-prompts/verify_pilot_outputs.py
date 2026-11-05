"""Read-only final evidence check for the two-call, four-file lecture pilot."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / 'runs/_map-point-pilot/2026-11-06-261105_07'
spec = importlib.util.spec_from_file_location('pilot', Path(__file__).with_name('pilot_extract.py'))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
fmt_spec = importlib.util.spec_from_file_location('formats', Path(__file__).with_name('verify_formats.py'))
formats = importlib.util.module_from_spec(fmt_spec)
fmt_spec.loader.exec_module(formats)


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))


summaries = []
for kind in ('map', 'point'):
    work = PILOT / kind
    report = read(work / 'postcheck.json')
    assert report['status'] == 'verified_existing_outputs' and report['additionalModelCalls'] == 0
    original = read(work / 'state.json')
    assert original['status'] == 'failed' and original['error'] == 'Model modified input file'
    assert read(work / 'input-hashes.json') == original['inputHashes']
    assert sha(work / 'before-lecture-split/input-hashes.json') == original['inputHashes']['input-hashes.json']
    for name, expected in original['inputHashes'].items():
        if name != 'input-hashes.json': assert sha(work / name) == expected
    for name, expected in read(PILOT / 'material-hashes.json').items():
        assert sha(work / 'material' / name) == expected
    info = read(work / 'model-response.json')
    receipts = {r['path']: r['sha256'] for r in json.loads(info['text'])['files']}
    ctx = read(work / 'input.json')
    sources = {s['source_id']: s['page_count'] for s in ctx['sources']}
    assert len(report['results']) == 2
    for item in report['results']:
        path = Path(item['file'])
        rel = path.relative_to(work).as_posix()
        assert item['sha256'] == receipts[rel] == sha(path)
        value = formats.read(path)
        formats.validate(kind, value, sources)
        lecture = next(l for l in pilot.LECTURES if l['title'] == value['title'])
        assert rel == lecture['slug'] + '/' + pilot.FILES[kind]
        def refs(v):
            if isinstance(v, list):
                for x in v: refs(x)
            elif isinstance(v, dict):
                if set(v) == {'source_id', 'pages', 'locator'} and v['source_id'] == 'S1':
                    assert all(p in lecture['source_pages'] or p == 1 for p in v['pages'])
                for x in v.values(): refs(x)
        refs(value)
        summaries.append({'kind': kind, 'lecture': value['title'], 'sha256': sha(path)})
print(json.dumps({'verifiedFiles': len(summaries), 'modelCalls': 2, 'additionalModelCalls': 0,
                  'originalFailuresPreserved': True, 'sourceAndPromptHashesPreserved': True,
                  'lectureScopesSeparated': True, 'medicalReviewCompleted': False, 'files': summaries}, ensure_ascii=True))
