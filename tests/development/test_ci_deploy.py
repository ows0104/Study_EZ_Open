"""Production automation failure paths, with no real cloud calls."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import ci_deploy as ci

SHA = 'a' * 40
ENV = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': ci.REPOSITORY,
       'GITHUB_REF': 'refs/heads/master', 'GITHUB_EVENT_NAME': 'push',
       'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}


@pytest.mark.parametrize('key,value', [('GITHUB_ACTIONS', 'false'), ('GITHUB_REPOSITORY', 'other/repo'),
    ('GITHUB_REF', 'refs/pull/1/merge'), ('GITHUB_EVENT_NAME', 'pull_request'),
    ('GITHUB_SHA', ''), ('GITHUB_RUN_ID', 'bad')])
def test_context_rejects_untrusted_runs(key, value):
    with pytest.raises(ValueError):
        ci.context({**ENV, key: value})


def test_candidate_modification_and_cross_run_rejected(tmp_path, monkeypatch):
    artifact = tmp_path / 'source'; artifact.mkdir(); (artifact / 'main.py').write_text('source')
    monkeypatch.setattr(ci.release, 'server_manifest', lambda: ci.release.manifest(artifact))
    receipt = tmp_path / 'candidate.json'
    ci.seal(artifact, receipt, ENV)
    ci.verify_candidate(artifact, receipt, SHA, ENV)
    with pytest.raises(ValueError):
        ci.verify_candidate(artifact, receipt, SHA, {**ENV, 'GITHUB_RUN_ID': '456'})
    (artifact / 'main.py').write_text('changed')
    with pytest.raises(ValueError):
        ci.verify_candidate(artifact, receipt, SHA, ENV)


def status(expected):
    return {'latestCreatedRevisionName': expected, 'latestReadyRevisionName': expected,
            'traffic': [{'revisionName': expected, 'percent': 100}, {'revisionName': 'old', 'tag': 'old'}]}


@pytest.mark.parametrize('mutation', [lambda s: s.update(latestCreatedRevisionName='old'),
    lambda s: s.update(latestReadyRevisionName='old'), lambda s: s['traffic'][0].update(percent=50),
    lambda s: s['traffic'][0].update(revisionName='old'), lambda s: s['traffic'][1].update(percent=10)])
def test_wrong_revision_or_split_traffic_fails(mutation):
    s = status('new'); ci.verify_traffic(s, 'new'); mutation(s)
    with pytest.raises(ValueError):
        ci.verify_traffic(s, 'new')


@pytest.mark.parametrize('failed_stage', ['candidate', 'head', 'ready', 'traffic', 'postcheck', None])
def test_deployment_failure_never_reports_success(tmp_path, monkeypatch, failed_stage):
    calls = []
    def step(name, result=None):
        def invoke(*args, **kwargs):
            calls.append(name)
            if failed_stage == name:
                raise ValueError(name)
            return result
        return invoke
    monkeypatch.setattr(ci, 'verify_candidate', step('candidate', 'hash'))
    monkeypatch.setattr(ci, 'assert_head', step('head'))
    monkeypatch.setattr(ci, 'service', lambda: status(ci.context(ENV)[1]))
    monkeypatch.setattr(ci, 'ready_revision', step('ready'))
    monkeypatch.setattr(ci, 'verify_traffic', step('traffic'))
    monkeypatch.setattr(ci, 'postcheck', step('postcheck', {'passed': True}))
    cloud = []
    monkeypatch.setattr(ci, 'call', lambda args: cloud.append(args))
    out = tmp_path / 'deployment.json'
    if failed_stage:
        with pytest.raises(ValueError):
            ci.deploy(tmp_path, tmp_path / 'candidate.json', out, ENV)
        assert json.loads(out.read_text())['status'] == 'failed'
        if failed_stage in ('candidate', 'head'):
            assert not cloud
        if failed_stage == 'ready':
            assert len(cloud) == 1
    else:
        ci.deploy(tmp_path, tmp_path / 'candidate.json', out, ENV)
        assert json.loads(out.read_text())['status'] == 'success'
        assert '--no-traffic' in cloud[0]
        assert '--update-env-vars' in cloud[0]
        assert not any('secret' in arg or 'init-db' in arg for command in cloud for arg in command)


def test_workflow_files_invalidate_release_evidence(tmp_path):
    import workflow_scope
    workflow = tmp_path / '.github/workflows/deploy.yml'; workflow.parent.mkdir(parents=True)
    workflow.write_text('before')
    before = workflow_scope.fingerprint(tmp_path)
    workflow.write_text('after')
    assert workflow_scope.fingerprint(tmp_path) != before
