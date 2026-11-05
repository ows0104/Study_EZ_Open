"""Read-only proof that the exact preview/bridge candidate reached production."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def get(url):
    result = subprocess.run(['curl.exe','-sS','--max-time','40','--retry','2','-w','\n%{http_code}',url],
                            capture_output=True,check=True)
    body, code = result.stdout.rsplit(b'\n',1)
    if code != b'200': raise RuntimeError('Unexpected public HTTP status: ' + code.decode())
    return body

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision',required=True)
    parser.add_argument('--artifact',required=True,type=Path)
    args = parser.parse_args()
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/production_smoke.py'),
                    '--revision',args.revision],check=True)
    expected_html = (args.artifact/'index.html').read_bytes()
    expected_zip = (args.artifact/'studyez-extension.zip').read_bytes()
    with zipfile.ZipFile(io.BytesIO(expected_zip)) as archive:
        assert json.loads(archive.read('manifest.json'))['version'] == '1.3.21'
        assert b'data-action="recover"' in archive.read('chatgpt-bridge.js')
    baseline = json.loads((ROOT/'runs/_development/2026-11-05-preview-bridge-deploy/baseline-verified.json').read_text(encoding='utf-8'))['files']
    changed_js = [p for p in (args.artifact/'assets').glob('*.js')
                  if baseline.get(p.relative_to(args.artifact).as_posix()) != hashlib.sha256(p.read_bytes()).hexdigest()]
    assert changed_js, 'Preview button bundle was not changed'
    assert any('기본 링크 만들기' in p.read_text(encoding='utf-8') for p in changed_js)
    origins = ['https://studyez.kr','https://study-ez-open.pages.dev',
               f'https://{args.revision[:8]}.study-ez-open.pages.dev']
    for origin in origins:
        assert get(origin+'/?release='+args.revision) == expected_html, 'Production HTML differs: '+origin
        assert get(origin+'/studyez-extension.zip?release='+args.revision) == expected_zip, 'Production ZIP differs: '+origin
    def verify_asset(path):
        name = path.relative_to(args.artifact).as_posix()
        actual = get('https://study-ez-open.pages.dev/'+name)
        assert actual == path.read_bytes(), 'Deployed bundle differs: '+name
        return name
    with ThreadPoolExecutor(max_workers=6) as pool:
        verified = list(pool.map(verify_asset,changed_js))
    print(json.dumps({'revision':args.revision,'productionHtmlExact':True,'productionZipExact':True,
                      'extensionVersion':'1.3.21','changedBundlesExact':verified,'dataWrites':False}))

if __name__ == '__main__': main()
