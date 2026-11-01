"""Candidate, deployment receipts and post-deployment checks. No implicit publishing."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import development as dev


def manifest(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink() or root.is_junction():
        raise ValueError('Artifact must be a real directory')
    result = {}
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            p = Path(base) / name
            if p.is_symlink() or p.is_junction():
                raise ValueError('Artifact links are not allowed')
        for name in files:
            p = Path(base) / name
            if name.startswith('.env') or p.suffix in {'.db', '.sqlite', '.pyc'}:
                raise ValueError('Secrets/runtime data cannot be release artifacts')
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    if not result:
        raise ValueError('Empty artifact')
    return result


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def tree_hash(root):
    return value_hash(manifest(root))


def environment_files(target):
    return ['server/.env'] if target == 'server' else ['web/.env', 'web/.env.local', 'web/.env.production', 'web/.env.production.local']


def environment_hash(target):
    return value_hash({n: hashlib.sha256((dev.ROOT / n).read_bytes()).hexdigest()
                       if (dev.ROOT / n).exists() else None for n in environment_files(target)})


def validate_config(config):
    required = {'target', 'destination', 'health_url', 'smoke_command', 'rollback'}
    if not required <= config.keys() or config['target'] not in ('server', 'web'):
        raise ValueError('Release config needs target, destination, health_url, smoke_command, rollback')
    parsed = urlparse(config['health_url'])
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query:
        raise ValueError('Use a public HTTPS health URL without credentials/query')
    if not str(config['destination']).strip() or not str(config['rollback']).strip():
        raise ValueError('Destination and rollback must be concrete')
    if config['target'] == 'server' and config['destination'] != 'meddeck-503318/asia-northeast3/studyez-api':
        raise ValueError('Server script target must match the approved project/region/service')
    for key in ('smoke_command', 'deploy_command', 'revision_command'):
        if key in config and (not isinstance(config[key], list) or not config[key]
                              or not all(isinstance(v, str) and v for v in config[key])):
            raise ValueError(f'{key} must be a nonempty argument array')
    if config['target'] == 'web':
        if not config.get('revision_command') or not any('{artifact}' in v for v in config.get('deploy_command', [])):
            raise ValueError('Web publish needs approved deploy/revision commands using {artifact}')


def server_manifest():
    expected = {}
    for root, prefix in ((dev.ROOT / 'server/app', 'app'), (dev.ROOT / 'studyez_contracts', 'studyez_contracts')):
        for p in root.rglob('*'):
            if p.is_file() and p.suffix in ('.py', '.json', '.toml') and not any(
                    part in {'__pycache__', '.venv', 'build', 'dist'} or part.endswith('.egg-info') for part in p.parts):
                expected[prefix + '/' + p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ('Dockerfile', 'requirements.txt'):
        expected[name] = hashlib.sha256((dev.ROOT / 'server' / name).read_bytes()).hexdigest()
    return expected


def prepare(change, artifact, config):
    folder, state = dev.load(change)
    errors = dev.gate(folder, state, 'release')
    if errors:
        raise ValueError('; '.join(errors))
    validate_config(config)
    target = config['target']
    required = {target, 'contracts'}
    if not required <= set(state['required_checks']):
        raise ValueError(f'Release needs named {target} and contracts checks, not only archival checks')
    allowed = ('site', 'operations', 'contracts') + (('spotter',) if target == 'server' else ())
    if state['area'] not in allowed:
        raise ValueError('Change evidence scope does not cover this deployment target')
    before = dev.evidence(folder, state)
    entries = manifest(artifact)
    if target == 'server':
        if entries != server_manifest():
            raise ValueError('Server package differs from tested source allowlist')
    else:
        latest = [c for c in state['checks'] if c['name'] == 'web'][-1]
        if latest.get('web_artifact') != value_hash(entries) or latest.get('web_environment') != environment_hash('web'):
            raise ValueError('Web artifact was not produced by the latest successful web verification')
    # Capture environment identity without storing secret values. Evaluated only for candidate creation.
    env_files = environment_files(target)
    env_hash = environment_hash(target)
    candidate = {**before, 'config': config, 'files': entries, 'environment_hash': env_hash,
                 'environment_files': env_files, 'release_hash': dev.digest([folder / 'release.md'])}
    token = value_hash(candidate)
    dest = dev.ROOT / 'runs/_development' / change / 'candidates' / token
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(artifact, dest)
    if manifest(dest) != entries or dev.evidence(folder, dev.load(change)[1]) != before:
        raise ValueError('Source/design/artifact changed while preparing candidate')
    candidate.update(id=token, artifact=dest.relative_to(dev.ROOT).as_posix())
    dev.update(folder, lambda s: s.update(candidate=candidate))
    return candidate


def candidate_errors(folder, state):
    c = state.get('candidate')
    if not c:
        return ['Prepare an exact candidate before deployment approval']
    try:
        expected = {k: v for k, v in c.items() if k not in ('id', 'artifact')}
        if value_hash(expected) != c['id']:
            return ['Candidate metadata changed']
        artifact = (dev.ROOT / c['artifact']).resolve()
        if not artifact.is_relative_to((dev.ROOT / 'runs/_development' / state['id'] / 'candidates').resolve()):
            return ['Candidate path escapes its storage']
        if manifest(artifact) != c['files']:
            return ['Candidate artifact changed']
        current = dev.evidence(folder, state)
        if any(c.get(k) != v for k, v in current.items()) or c['release_hash'] != dev.digest([folder / 'release.md']):
            return ['Candidate source/design/release is stale']
        env_hash = value_hash({n: hashlib.sha256((dev.ROOT / n).read_bytes()).hexdigest()
                              if (dev.ROOT / n).exists() else None for n in c['environment_files']})
        if env_hash != c['environment_hash']:
            return ['Deployment environment changed; prepare and approve again']
    except (OSError, ValueError, KeyError):
        return ['Candidate is missing or invalid']
    return []


def begin(change, target):
    folder, state = dev.load(change)
    errors = dev.gate(folder, state, 'deploy')
    if errors:
        raise ValueError('; '.join(errors))
    c = state['candidate']
    if c['config']['target'] != target:
        raise ValueError('Approval is for a different target')
    attempt = {'id': str(time.time_ns()), 'started_at': dev.now(), 'status': 'running',
               'candidate': c, 'approval': state['approvals']['deploy'], 'postchecks': []}
    def add(s):
        if any(a['status'] == 'running' for a in s.get('deployments', [])):
            raise ValueError('Deployment already running; record its actual outcome first')
        if s.get('candidate') != c or s['approvals'].get('deploy') != attempt['approval']:
            raise ValueError('Candidate/approval changed')
        s.setdefault('deployments', []).append(attempt)
    dev.update(folder, add)
    return {'attempt': attempt['id'], 'artifact': str(dev.ROOT / c['artifact']), 'config': c['config']}


def receipt(change, attempt, status, revision):
    if status not in ('succeeded', 'failed') or not revision.strip():
        raise ValueError('Record an actual revision or failure reason')
    folder, _ = dev.load(change)
    def record(s):
        a = next(a for a in s.get('deployments', []) if a['id'] == attempt)
        if a['status'] != 'running':
            raise ValueError('Receipt already recorded')
        if status == 'succeeded' and manifest(dev.ROOT / a['candidate']['artifact']) != a['candidate']['files']:
            a.update(status='failed', revision=revision, reason='artifact_changed_during_deployment', finished_at=dev.now())
            return
        a.update(status=status, revision=revision, finished_at=dev.now())
    dev.update(folder, record)


def command(args, path, values=None):
    expanded = [v.replace('{artifact}', str(values['artifact'])).replace('{revision}', values['revision'])
                if values else v for v in args]
    with path.open('w', encoding='utf-8') as out:
        try:
            return subprocess.run(expanded, cwd=dev.ROOT, stdout=out, stderr=subprocess.STDOUT,
                                  shell=False, timeout=1800).returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            out.write(type(error).__name__)
            return 124 if isinstance(error, subprocess.TimeoutExpired) else 127


def postcheck(change, attempt):
    import maintenance
    folder, state = dev.load(change)
    a = next(a for a in state.get('deployments', []) if a['id'] == attempt)
    if a['status'] != 'succeeded':
        raise ValueError('Only an actual successful deployment receipt can be checked')
    c = a['candidate']; config = c['config']
    health = maintenance.observe({'url': config['health_url'], 'kind': 'api' if config['target'] == 'server' else 'web'})
    log = dev.ROOT / 'runs/_development' / change / f'{attempt}-{time.time_ns()}-smoke.log'
    code = command(config['smoke_command'], log, {'artifact': dev.ROOT / c['artifact'], 'revision': a['revision']})
    result = {'at': dev.now(), 'candidate': c['id'], 'revision': a['revision'], 'health': health,
              'smoke_exit_code': code, 'log': log.relative_to(dev.ROOT).as_posix(),
              'passed': health['status'] == 'healthy' and code == 0}
    def record(s):
        current = next(row for row in s['deployments'] if row['id'] == attempt)
        if current['revision'] != a['revision']:
            raise ValueError('Deployment receipt changed')
        current['postchecks'].append(result)
    dev.update(folder, record)
    return result


def publish_web(change):
    started = begin(change, 'web')
    config = started['config']; attempt = started['attempt']
    log = dev.ROOT / 'runs/_development' / change / f'{attempt}-publish.log'
    code = command(config['deploy_command'], log, {'artifact': started['artifact'], 'revision': ''})
    if code:
        receipt(change, attempt, 'failed', f'publish_exit_{code}')
        return 1
    try:
        r = subprocess.run(config['revision_command'], cwd=dev.ROOT, capture_output=True, text=True,
                           shell=False, timeout=60, check=True)
        revision = r.stdout.strip()
        if not revision or len(revision) > 500:
            raise ValueError('Revision command must return only the deployed version identifier')
    except (OSError, subprocess.SubprocessError, ValueError):
        receipt(change, attempt, 'failed', 'upload_finished_but_revision_unconfirmed')
        return 1
    receipt(change, attempt, 'succeeded', revision)
    return 0 if postcheck(change, attempt)['passed'] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('id'); prep.add_argument('--artifact', type=Path, required=True); prep.add_argument('--config', type=Path, required=True)
    start = sub.add_parser('begin'); start.add_argument('id'); start.add_argument('--target', choices=('server', 'web'), required=True)
    rec = sub.add_parser('record'); rec.add_argument('id'); rec.add_argument('--attempt', required=True); rec.add_argument('--status', choices=('succeeded', 'failed'), required=True); rec.add_argument('--revision', required=True)
    post = sub.add_parser('postcheck'); post.add_argument('id'); post.add_argument('--attempt', required=True)
    pub = sub.add_parser('publish-web'); pub.add_argument('id')
    args = p.parse_args(argv)
    if args.action == 'prepare': result = prepare(args.id, args.artifact, json.loads(args.config.read_text(encoding='utf-8')))
    elif args.action == 'begin': result = begin(args.id, args.target)
    elif args.action == 'record': result = receipt(args.id, args.attempt, args.status, args.revision)
    elif args.action == 'postcheck':
        result = postcheck(args.id, args.attempt); print(json.dumps(result, ensure_ascii=False)); return 0 if result['passed'] else 1
    else: return publish_web(args.id)
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError, KeyError, StopIteration) as e: raise SystemExit(str(e))
