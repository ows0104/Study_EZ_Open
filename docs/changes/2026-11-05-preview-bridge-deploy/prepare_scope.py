"""Reproduce the deployed web before overlaying only the approved preview fix."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import workflow_scope
import release_evidence

BASE = ROOT / 'tmp/root-web'
DEST = ROOT / 'tmp/preview-bridge-20261105'
CHANGE = '2026-11-05-preview-bridge-deploy'
PREVIOUS = '57fe6571-2415-4250-9895-e5f2bb903171'
DOCS = Path('docs/changes') / CHANGE
AUDIT = DEST / 'runs/_development' / CHANGE
OVERLAY = '''bridge/PRIVACY.md
bridge/README.md
bridge/background.js
bridge/chatgpt-bridge.js
bridge/manifest.json
bridge/protocol.js
tests/bridge/test_autosend.cjs
tests/bridge/test_link_recovery.cjs
tests/bridge/test_web_versions.cjs
web/src/calendar/PreviewAction.tsx
web/tests/preview-actions.test.cjs
scripts/preview_bridge_smoke.py'''.splitlines()

def hashes():
    return {p.relative_to(DEST).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workflow_scope.files(DEST, 'site')}

def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

def baseline_candidate():
    state = json.loads((BASE / 'docs/changes/2026-11-04-root-duplicate-identity/state.json').read_text(encoding='utf-8'))
    matches = [d for d in state['deployments'] if d.get('revision') == PREVIOUS and d['status'] == 'succeeded']
    if len(matches) != 1: raise ValueError('Previous production receipt missing')
    return matches[0]['candidate']

def main(action):
    if action == 'stage':
        if DEST.exists(): raise ValueError('Scoped directory already exists; preserve its evidence')
        DEST.mkdir(parents=True)
        for source in workflow_scope.files(BASE, 'site'):
            copy_file(source, DEST / source.relative_to(BASE))
        for name in ('CLAUDE.md', 'web/CLAUDE.md', 'bridge/CLAUDE.md', 'docs/map.md'):
            copy_file(BASE / name, DEST / name)
        for name in ('tests/fixtures/bank-file-valid.md', 'tests/fixtures/bank-file-cases.json'):
            copy_file(BASE / name, DEST / name)
        for source in (ROOT / DOCS).iterdir():
            if source.is_file(): copy_file(source, DEST / DOCS / source.name)
        for name in ('web/.env','web/.env.local','web/.env.production','web/.env.production.local'):
            if (BASE / name).exists(): copy_file(BASE / name, DEST / name)
        main('dependencies')
    elif action == 'dependencies':
        if not (DEST/'web/src/calendar/PreviewAction.tsx').is_file(): raise ValueError('Stage source first')
        for name in ('web/node_modules','server/.venv','.venv'):
            target = DEST / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if not target.is_junction() or target.resolve() != (ROOT/name).resolve(): raise ValueError('Unexpected dependency path')
                continue
            quote = lambda x: "'" + str(x).replace("'", "''") + "'"
            subprocess.run(['powershell','-NoProfile','-Command',
                f'New-Item -ItemType Junction -Path {quote(target)} -Target {quote(ROOT/name)}'],
                check=True, capture_output=True)
        AUDIT.mkdir(parents=True, exist_ok=True)
        (AUDIT / 'baseline-source.json').write_text(json.dumps(hashes(), indent=2), encoding='utf-8')
        print('Staged isolated production source:', DEST)
    elif action == 'check-baseline':
        expected = baseline_candidate()
        actual = release_evidence.manifest(DEST / 'web/dist')
        if actual != expected['files']:
            different = sorted(k for k in set(actual)|set(expected['files']) if actual.get(k) != expected['files'].get(k))
            raise ValueError('Production baseline rebuild differs: ' + ', '.join(different[:20]))
        (AUDIT / 'baseline-verified.json').write_text(json.dumps({'revision':PREVIOUS,'candidate':expected['id'],
            'artifactHash':release_evidence.value_hash(actual),'files':actual},indent=2),encoding='utf-8')
        print('Baseline rebuild exactly matches previous production candidate:', expected['id'])
    elif action == 'overlay':
        if not (AUDIT / 'baseline-verified.json').exists(): raise ValueError('Verify baseline first')
        for name in OVERLAY: copy_file(ROOT / name, DEST / name)
        guide = DEST / 'web/src/notices/GuidePage.tsx'
        old = '            개인 링크는 확장 카드에서 자료와 프롬프트를 확인한 뒤 직접 전송합니다. 기본 링크의 <b>자동전송</b>은 관리자에게만 보입니다.'
        current = (ROOT / 'web/src/notices/GuidePage.tsx').read_text(encoding='utf-8')
        start = current.index('            개인 링크는 확장 카드에서 자료와 프롬프트를 확인한 뒤 직접 전송합니다.')
        end = current.index('            Main-Quiz 앞의', start)
        replacement = current[start:end].rstrip('\n')
        content = guide.read_text(encoding='utf-8')
        if content.count(old) != 1: raise ValueError('Expected production guide hunk missing')
        guide.write_text(content.replace(old,replacement),encoding='utf-8')
        main('audit')
    elif action == 'audit':
        baseline = json.loads((AUDIT / 'baseline-source.json').read_text(encoding='utf-8'))
        actual = hashes()
        changed = sorted(k for k in set(baseline)|set(actual) if baseline.get(k) != actual.get(k))
        allowed = set(OVERLAY) | {'web/src/notices/GuidePage.tsx'}
        if set(changed) - allowed: raise ValueError('Unexpected scoped changes: ' + str(set(changed)-allowed))
        for name in OVERLAY:
            if (ROOT/name).read_bytes() != (DEST/name).read_bytes(): raise ValueError('Overlay source mismatch: ' + name)
        (AUDIT/'overlay-audit.json').write_text(json.dumps({'previous':PREVIOUS,'changed':changed},indent=2),encoding='utf-8')
        print('Approved overlay only:', ', '.join(changed))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['stage','dependencies','check-baseline','overlay','audit'])
    main(parser.parse_args().action)
