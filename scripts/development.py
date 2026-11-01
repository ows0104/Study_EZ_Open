"""StudyEZ change records and revision-bound development gates (no deployment)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import workflow_scope

ROOT = Path(__file__).resolve().parents[1]
AREAS = ('site', 'generation', 'integration', 'contracts', 'spotter', 'operations')


def now():
    return datetime.now(UTC).isoformat()


def digest(paths):
    result = hashlib.sha256()
    for path in sorted(paths):
        result.update(path.relative_to(ROOT).as_posix().encode())
        result.update(b'\0' + path.read_bytes() + b'\0')
    return result.hexdigest()


def source_hash():
    return workflow_scope.fingerprint(ROOT)


def evidence(folder, state):
    return {'evidence_version': 2, 'source_hash': workflow_scope.fingerprint(ROOT, state['area']),
            'plan_hash': plan_hash(folder), 'inputs': workflow_scope.paths(state['area'])}


def change_dir(change_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', change_id):
        raise ValueError('ID must contain 3-80 lowercase letters, numbers or hyphens')
    return ROOT / 'docs/changes' / change_id


def load(change_id):
    folder = change_dir(change_id)
    return folder, json.loads((folder / 'state.json').read_text(encoding='utf-8'))


def save(folder, state):
    state['updated_at'] = now()
    target = folder / 'state.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(target)


def update(folder, change):
    """Merge concurrent check completions rather than replacing a stale state snapshot."""
    lock = folder / '.state.lock'
    deadline = time.monotonic() + 5
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('Change record is busy; inspect the lock before retrying')
            time.sleep(0.05)
    try:
        state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
        change(state)
        save(folder, state)
    finally:
        lock.unlink()


def plan_hash(folder):
    documents = digest([folder / name for name in ('intent.md', 'spec.md', 'plan.md')])
    state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
    checks = state['required_checks']
    if (not isinstance(checks, list) or not checks or state['area'] not in AREAS
            or any(not isinstance(c, str) or not re.fullmatch(r'[a-z0-9-]+', c) for c in checks)):
        raise ValueError('A valid area and nonempty required_checks are necessary')
    policy = [2, state['area'], checks, workflow_scope.paths(state['area'])]
    return hashlib.sha256((documents + json.dumps(policy)).encode()).hexdigest()


def create(change_id, title, area, checks):
    if area not in AREAS or not checks or any(not re.fullmatch(r'[a-z0-9-]+', c) for c in checks):
        raise ValueError('An area and named required checks are necessary')
    folder = change_dir(change_id)
    folder.mkdir(parents=True, exist_ok=False)
    for name in ('intent', 'spec', 'plan', 'release'):
        template = (ROOT / 'docs/development/templates' / f'{name}.md').read_text(encoding='utf-8')
        (folder / f'{name}.md').write_text(template.replace('{{title}}', title), encoding='utf-8')
    save(folder, {'id': change_id, 'title': title, 'area': area, 'created_at': now(),
                  'required_checks': list(dict.fromkeys(checks)), 'approvals': {}, 'checks': [], 'review': None,
                  'lifecycle': {'status': 'planning', 'events': [], 'links': []}})
    return folder


def gate(folder, state, phase):
    errors = []
    try:
        expected_plan = plan_hash(folder)
    except ValueError as error:
        return [str(error)]
    approval = state['approvals'].get('build', {})
    if approval.get('plan_hash') != expected_plan or not approval.get('evidence'):
        errors.append('Current intent/spec/plan needs human build approval')
    for name in ('intent', 'spec', 'plan'):
        if '<TODO>' in (folder / f'{name}.md').read_text(encoding='utf-8'):
            errors.append(f'{name}.md still contains <TODO>')
    if phase == 'build':
        return errors
    current = evidence(folder, state)
    for name in state['required_checks']:
        records = [c for c in state['checks'] if c['name'] == name]
        if not records or records[-1]['exit_code'] != 0 or any(records[-1].get(k) != v for k, v in current.items()):
            errors.append(f'Missing/currently failing or stale check: {name}')
    review = state.get('review') or {}
    if any(review.get(k) != v for k, v in current.items()) or not review.get('summary', '').strip():
        errors.append('Current implementation needs a recorded code review')
    if '<TODO>' in (folder / 'release.md').read_text(encoding='utf-8'):
        errors.append('release.md still contains <TODO>')
    if phase == 'deploy':
        approved = state['approvals'].get('deploy', {})
        if (any(approved.get(k) != v for k, v in current.items())
                or approved.get('release_hash') != digest([folder / 'release.md'])):
            errors.append('Current implementation and release plan need human deployment approval')
        import release_evidence
        errors.extend(release_evidence.candidate_errors(folder, state))
        if approved.get('candidate_hash') != (state.get('candidate') or {}).get('id') or not state.get('candidate'):
            errors.append('The exact release candidate needs human deployment approval')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    new = sub.add_parser('new')
    new.add_argument('id'); new.add_argument('--title', required=True)
    new.add_argument('--area', choices=AREAS, required=True)
    new.add_argument('--checks', nargs='+', required=True)
    approve = sub.add_parser('approve', help='Record an actual human approval; never infer approval')
    approve.add_argument('id'); approve.add_argument('--phase', choices=('build', 'deploy'), required=True)
    approve.add_argument('--evidence', required=True); approve.add_argument('--scope', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('id'); verify.add_argument('--check', required=True)
    review = sub.add_parser('review')
    review.add_argument('id'); review.add_argument('--summary', required=True)
    check = sub.add_parser('check')
    check.add_argument('id'); check.add_argument('--phase', choices=('build', 'release', 'deploy'), required=True)
    args, command = parser.parse_known_args(argv)
    if command and args.action != 'verify':
        parser.error('Unexpected arguments: ' + ' '.join(command))
    if args.action == 'new':
        print(create(args.id, args.title, args.area, args.checks))
        return 0
    folder, state = load(args.id)
    if args.action == 'approve':
        if not args.evidence.strip() or not args.scope.strip():
            raise ValueError('Human approval evidence and scope cannot be empty')
        state['approvals'][args.phase] = {'at': now(), 'evidence': args.evidence, 'scope': args.scope,
            **evidence(folder, state),
            'release_hash': digest([folder / 'release.md'])}
        if args.phase == 'deploy':
            import release_evidence
            errors = gate(folder, state, 'release') + release_evidence.candidate_errors(folder, state)
            if errors:
                raise ValueError('; '.join(errors))
            state['approvals'][args.phase]['candidate_hash'] = state['candidate']['id']
    elif args.action == 'verify':
        errors = gate(folder, state, 'build')
        if errors:
            raise ValueError('; '.join(errors))
        if args.check not in state['required_checks']:
            raise ValueError('Check name must be listed in required_checks')
        command = command[1:] if command[:1] == ['--'] else command
        if not command:
            raise ValueError('Provide the real test command after --')
        before = evidence(folder, state)
        import release_evidence
        before_web_env = release_evidence.environment_hash('web') if args.check == 'web' else None
        logs = ROOT / 'runs/_development' / args.id
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / f'{time.time_ns()}-{args.check}.log'
        with log.open('w', encoding='utf-8') as output:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                                        text=True, shell=False, timeout=1800)
                code = result.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                output.write(f'Check could not complete: {type(error).__name__}\n')
                code = 124 if isinstance(error, subprocess.TimeoutExpired) else 127
        try:
            _, latest = load(args.id)
            after = evidence(folder, latest)
        except (ValueError, KeyError, OSError):
            after = None
        code = code if before == after else 2
        if args.check == 'web' and before_web_env != release_evidence.environment_hash('web'):
            code = 2
        record = {'name': args.check, 'at': now(), 'command': command,
            'exit_code': code, **before, 'log': log.relative_to(ROOT).as_posix()}
        if args.check == 'web' and code == 0 and (ROOT / 'web/dist/index.html').exists():
            import release_evidence
            record['web_artifact'] = release_evidence.tree_hash(ROOT / 'web/dist')
            record['web_environment'] = before_web_env
        update(folder, lambda latest: latest['checks'].append(record))
        print(json.dumps(record, ensure_ascii=False))
        return code
    elif args.action == 'review':
        if not args.summary.strip():
            raise ValueError('Review summary cannot be blank')
        state['review'] = {'at': now(), 'summary': args.summary, **evidence(folder, state)}
    else:
        errors = gate(folder, state, args.phase)
        print(json.dumps({'phase': args.phase, 'ready': not errors, 'reasons': errors}, ensure_ascii=False))
        return 1 if errors else 0
    if args.action == 'approve':
        update(folder, lambda latest: latest['approvals'].update({args.phase: state['approvals'][args.phase]}))
    elif args.action == 'review':
        update(folder, lambda latest: latest.update(review=state['review']))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise SystemExit(str(error))
