"""Read-only production boundaries, source lookup, and exact static asset checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SECRETS_ROOT = Path('C:\\Users\\ows01\\Documents\\Python Scripts\\Study_EZ_Open')
p = argparse.ArgumentParser()
p.add_argument('--revision', required=True)
p.add_argument('--artifact', type=Path, required=True)
args = p.parse_args()
subprocess.run([sys.executable, '-X', 'utf8', '-B', str(HERE / 'production_smoke.py'),
                '--revision', args.revision], check=True)

# This endpoint only selects metadata. GET bank-response is deliberately avoided:
# that endpoint claims work and changes the bank status.
from dotenv import dotenv_values
settings = dotenv_values(SECRETS_ROOT / 'server/.env')
url = ('https://studyez-api-97999573571.asia-northeast3.run.app/api/admin/lectures/'
       + quote('약리학') + '/261002_03/bank/source-context')
request = Request(url, headers={'Authorization': 'Bearer ' + settings['RUNNER_TOKEN']})
with urlopen(request, timeout=40) as response:
    source = json.load(response)
assert source.get('title') and any(s['kind'] == 'notes_current' for s in source['sources'])
print('PASS: authenticated read-only source lookup; bank state and review history untouched')

if (args.artifact / 'index.html').exists():
    # Candidate identity includes every file; fetch its HTML, all code/styles and
    # the canonical prompt from each production address and the exact new upload.
    files = [f for f in args.artifact.rglob('*') if f.is_file() and
             (f.suffix in ('.html', '.js', '.css') or f.name == 'bank-prompt.json')]
    origins = ['https://studyez.kr', 'https://study-ez-open.pages.dev',
               'https://' + args.revision.split('-')[0] + '.study-ez-open.pages.dev']
    def verify(item):
        origin, file = item
        name = file.relative_to(args.artifact).as_posix()
        # Use the same HTTP client as the public boundary checks. Cloudflare
        # rejects some urllib asset requests while serving the public files to curl.
        actual = subprocess.run(['curl.exe', '-f', '-sS', '-L', '--retry', '2',
                                 '--max-time', '40', origin + '/' + quote(name, safe='/')],
                                capture_output=True, check=True).stdout
        assert hashlib.sha256(actual).digest() == hashlib.sha256(file.read_bytes()).digest(), name
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(verify, [(origin, f) for origin in origins for f in files]))
    print(json.dumps({'static_files_per_origin': len(files), 'origins': origins,
                      'exact_sha256_matches': len(files) * len(origins)}))
