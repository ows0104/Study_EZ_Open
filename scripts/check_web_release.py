"""Build with existing env files and reject leakage of the local-test auth branch."""
import os, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
result=subprocess.run(['npm.cmd','--prefix','web','run','build'],cwd=root)
if result.returncode: raise SystemExit(result.returncode)
tokens=[]
for name in ('.env','.env.local','.env.production','.env.production.local'):
    path=root/'web'/name
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('VITE_LOCAL_TEST_TOKEN='):
                token=line.split('=',1)[1].strip().strip('\"\'')
                if token: tokens.append(token)
if os.environ.get('VITE_LOCAL_TEST_TOKEN'): tokens.append(os.environ['VITE_LOCAL_TEST_TOKEN'])
assert tokens, 'Exercise the production build with a nonempty local-test setting'
for path in (root/'web/dist/assets').glob('*.js'):
    body=path.read_text(encoding='utf-8')
    assert all(token not in body for token in tokens), 'Local test credential leaked into production JavaScript'
    assert 'user:{email:"local-test"}' not in body, 'Local fake-auth branch remains'
print('PASS: production bundle excludes local test token and fake session with local settings present')
