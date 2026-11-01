"""Verify final ZIP contents, hashes, portable links and source-data parity."""
from pathlib import Path,PurePosixPath
import json,zipfile
import build_package as b

records=json.loads((b.HERE/'bundles.json').read_text(encoding='utf-8'))
assert records['source_manifest_sha256']==b.file_sha(b.OUT/'manifest.json')
counts=[]
for bundle in records['bundles']:
    path=Path(bundle['path']);assert b.file_sha(path)==bundle['sha256'] and path.stat().st_size==bundle['bytes']
    expected={x['file']:x for x in bundle['members']}
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist();assert len(names)==len(set(names))==len(expected)
        assert set(names)==set(expected)
        for info in archive.infolist():
            name=PurePosixPath(info.filename)
            assert not name.is_absolute() and '..' not in name.parts and ':' not in info.filename
            data=archive.read(info.filename)
            assert len(data)==expected[info.filename]['bytes'] and b.sha(data)==expected[info.filename]['sha256']
        if path.name.endswith('JSON_전체.zip'):
            prefix='감염과 면역_2026_JSON/'
            packaged=json.loads(archive.read(prefix+'catalog.json'))
            assert packaged==json.loads((b.OUT/'catalog.json').read_text(encoding='utf-8'))
            assert len(packaged['sections'])==69 and packaged['counts']['questions']==850
            for row in json.loads(archive.read(prefix+'manifest.json'))['files']:
                assert expected[prefix+row['file']]['sha256']==row['sha256']
        else:
            mds=[name for name in names if name.endswith('/문항.md')]
            assert len(mds)==69
            assert sum(name.endswith('.png') for name in names)==317
            for name in mds:
                content=archive.read(name).decode('utf-8');folder=PurePosixPath(name).parent
                import re
                for linked in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',content):
                    assert str(folder/linked) in expected,(name,linked)
    counts.append({'path':str(path),'files':len(expected),'bytes':bundle['bytes'],'sha256':bundle['sha256']})
result={'status':'passed','bundles':counts,'source_manifest_sha256':records['source_manifest_sha256']}
b.save_json(b.HERE/'package-verification.json',result)
print(json.dumps(result,ensure_ascii=False))
