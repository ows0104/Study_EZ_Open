"""Deploy only a tested GitHub master candidate; never sync secrets or migrate data."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import release_evidence as release

REPOSITORY = 'ows0104/Study_EZ_Open'
PROJECT = 'meddeck-503318'
REGION = 'asia-northeast3'
SERVICE = 'studyez-api'
API = 'https://studyez-api-97999573571.asia-northeast3.run.app'


def call(args):
    result = subprocess.run(args, check=True, capture_output=True, text=True,
                            encoding='utf-8', timeout=900)
    return result.stdout


def context(env=os.environ):
    sha = env.get('GITHUB_SHA', '')
    if (env.get('GITHUB_ACTIONS') != 'true' or env.get('GITHUB_REPOSITORY') != REPOSITORY
            or env.get('GITHUB_REF') != 'refs/heads/master'
            or env.get('GITHUB_EVENT_NAME') not in ('push', 'workflow_dispatch')
            or not re.fullmatch('[a-f0-9]{40}', sha)):
        raise ValueError('Production deployment requires this repository master workflow')
    run = env.get('GITHUB_RUN_ID', '')
    attempt = env.get('GITHUB_RUN_ATTEMPT', '')
    if not run.isdecimal() or not attempt.isdecimal():
        raise ValueError('Missing GitHub run identity')
    return sha, f'{SERVICE}-release-{run}{attempt}'


def seal(artifact, receipt, env=os.environ):
    # PRs can build a candidate but cannot enter the production deployment context.
    sha = env.get('GITHUB_SHA', '')
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError('Missing exact tested Git SHA')
    files = release.manifest(artifact)
    if files != release.server_manifest():
        raise ValueError('Candidate differs from the tested source allowlist')
    value = {'sha': sha, 'run_id': env['GITHUB_RUN_ID'], 'files': files,
             'artifact_hash': release.value_hash(files)}
    receipt.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def verify_candidate(artifact, receipt, sha, env=os.environ):
    value = json.loads(receipt.read_text(encoding='utf-8'))
    files = release.manifest(artifact)
    if (value['sha'] != sha or value['run_id'] != env['GITHUB_RUN_ID']
            or files != value['files'] or release.value_hash(files) != value['artifact_hash']):
        raise ValueError('Candidate commit, run or file hash mismatch')
    return value['artifact_hash']


def service():
    return json.loads(call(['gcloud', 'run', 'services', 'describe', SERVICE,
        '--project', PROJECT, '--region', REGION, '--format=json(status)']))['status']


def assert_head(sha):
    head = call(['gh', 'api', f'repos/{REPOSITORY}/git/ref/heads/master', '--jq', '.object.sha']).strip()
    if head != sha:
        raise ValueError('This run was superseded by a newer master commit; refusing deployment')


def ready_revision(expected):
    revision = json.loads(call(['gcloud', 'run', 'revisions', 'describe', expected,
        '--project', PROJECT, '--region', REGION,
        '--format=json(metadata.name,status.conditions)']))
    conditions = {c['type']: c.get('status') for c in revision['status']['conditions']}
    if (revision['metadata']['name'] != expected or conditions.get('Ready') != 'True'
            or conditions.get('ContainerReady') != 'True'):
        raise ValueError('The exact new revision is not ready')
    if service().get('latestCreatedRevisionName') != expected:
        raise ValueError('Another revision was created; refusing traffic switch')


def verify_traffic(status, expected):
    traffic = [row for row in status.get('traffic', []) if row.get('percent', 0) > 0]
    if (status.get('latestCreatedRevisionName') != expected
            or status.get('latestReadyRevisionName') != expected or len(traffic) != 1
            or traffic[0].get('revisionName') != expected or traffic[0].get('percent') != 100):
        raise ValueError('The exact new revision does not have verified 100 percent traffic')


def probe(path):
    try:
        with urlopen(Request(API + path, headers={'Cache-Control': 'no-cache'}), timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, b''


def postcheck(sha):
    for attempt in range(6):
        try:
            code, body = probe('/api/health')
            health = json.loads(body)
            if (code == 200 and health.get('status') == 'ok'
                    and health.get('environment') == 'production' and health.get('revision') == sha
                    and all(probe(path)[0] == 401 for path in ('/api/me', '/api/timetable', '/api/spotter/db'))):
                return {'health_sha': sha, 'protected_routes': '401', 'passed': True}
        except (OSError, ValueError):
            pass
        if attempt < 5:
            time.sleep(5)
    raise ValueError('Read-only production health/revision/authentication checks failed')


def deploy(artifact, receipt, output, env=os.environ):
    sha, expected = context(env)
    record = {'sha': sha, 'expected_revision': expected, 'status': 'failed'}
    try:
        record['artifact_hash'] = verify_candidate(artifact, receipt, sha, env)
        assert_head(sha)
        before = service()
        record['previous_traffic'] = [t for t in before.get('traffic', []) if t.get('percent', 0) > 0]
        output.write_text(json.dumps(record, indent=2), encoding='utf-8')
        # Omitting IAM/env/secret/reset flags preserves existing runtime configuration.
        call(['gcloud', 'run', 'deploy', SERVICE, '--source', str(artifact),
            '--project', PROJECT, '--region', REGION, '--quiet', '--no-traffic',
            '--revision-suffix', expected.removeprefix(SERVICE + '-'),
            '--update-env-vars', f'STUDYEZ_REVISION={sha}'])
        ready_revision(expected)
        assert_head(sha)
        call(['gcloud', 'run', 'services', 'update-traffic', SERVICE,
            '--project', PROJECT, '--region', REGION, '--to-revisions', f'{expected}=100', '--quiet'])
        verify_traffic(service(), expected)
        record['postcheck'] = postcheck(sha)
        record['status'] = 'success'
    except Exception as error:
        # Do not copy cloud command output or runtime configuration into receipts/logs.
        record['error'] = type(error).__name__
        raise
    finally:
        output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seal', 'deploy'))
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'seal':
        seal(args.artifact, args.receipt)
    else:
        if not args.output:
            parser.error('--output is required for deployment')
        deploy(args.artifact, args.receipt, args.output)


if __name__ == '__main__':
    main()
