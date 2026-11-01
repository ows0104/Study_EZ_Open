"""End-to-end workflow checks; all approval and remote responses are isolated fixtures."""
import json
import shutil
import sys
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import development as dev
import maintenance
import release_evidence as release
import workflow_lifecycle as life


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, 'ROOT', tmp_path)
    monkeypatch.setattr(maintenance, 'ROOT', tmp_path)
    templates = tmp_path / 'docs/development/templates'; templates.mkdir(parents=True)
    for name in ('intent', 'spec', 'plan', 'release'):
        (templates / f'{name}.md').write_text('{{title}}\nReady', encoding='utf-8')
    return tmp_path


def approve(name, phase='build'):
    dev.main(['approve', name, '--phase', phase, '--evidence', 'TEST FIXTURE ONLY', '--scope', 'isolated test'])


def ready(root, area='site', name='test-change', checks=('server', 'contracts')):
    f = dev.create(name, 'Fixture', area, checks)
    approve(name)
    for check in checks:
        assert dev.main(['verify', name, '--check', check, '--', sys.executable, '-c', 'pass']) == 0
    dev.main(['review', name, '--summary', 'Fixture review'])
    return f


def server_candidate(root):
    for name, data in {'server/app/main.py': 'app=1', 'studyez_contracts/bank/schema.py': 'schema=1',
                       'server/Dockerfile': 'FROM fixture', 'server/requirements.txt': '', 'server/.env': 'ENVIRONMENT=local-test'}.items():
        p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(data)
    f = ready(root)
    artifact = root/'package'; artifact.mkdir()
    for name in release.server_manifest():
        source = root/('server/'+name if name.startswith('app/') or '/' not in name else name)
        dst = artifact/name; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dst)
    config = {'target': 'server', 'destination': 'meddeck-503318/asia-northeast3/studyez-api',
              'health_url': 'https://example.invalid/api/health', 'smoke_command': [sys.executable, '-c', 'pass'],
              'rollback': 'restore fixture previous revision'}
    c = release.prepare('test-change', artifact, config)
    return f, c


@pytest.mark.parametrize('name,area', [('spotter/scripts/build_web.py', 'spotter'), ('data/timetable/semester.json', 'site'), ('uv.lock', 'site')])
def test_previously_omitted_inputs_invalidate_evidence(root, name, area):
    p=root/name; p.parent.mkdir(parents=True, exist_ok=True);p.write_text('before')
    f=ready(root,area); before=dev.source_hash();p.write_text('after')
    assert dev.source_hash()!=before
    assert dev.gate(f,dev.load('test-change')[1],'release')


def test_unrelated_spotter_change_preserves_site_evidence_but_shared_change_does_not(root):
    f=ready(root); p=root/'spotter/scripts/tool.py';p.parent.mkdir(parents=True);p.write_text('new')
    assert not dev.gate(f,dev.load('test-change')[1],'release')
    p=root/'platform/session/session.js';p.parent.mkdir(parents=True);p.write_text('changed')
    assert dev.gate(f,dev.load('test-change')[1],'release')


def test_design_reapproval_does_not_reuse_tests_or_review(root):
    f=ready(root);(f/'spec.md').write_text('New acceptance criteria');approve('test-change')
    assert dev.gate(f,dev.load('test-change')[1],'release')


def test_design_change_during_command_records_failure(root):
    f=dev.create('test-change','Fixture','site',['unit']);approve('test-change')
    command=f"from pathlib import Path; Path({str(f/'spec.md')!r}).write_text('Changed')"
    assert dev.main(['verify','test-change','--check','unit','--',sys.executable,'-c',command])==2


def test_legacy_checks_do_not_silently_migrate(root):
    f=ready(root);_,s=dev.load('test-change');s['checks'][-1].pop('plan_hash');dev.save(f,s)
    assert dev.gate(f,s,'release')


def test_candidate_approval_sealing_and_postcheck_to_incident_closure(root,monkeypatch):
    f,c=server_candidate(root)
    assert dev.gate(f,dev.load('test-change')[1],'deploy')
    approve('test-change','deploy')
    started=release.begin('test-change','server')
    with pytest.raises(ValueError,match='already running'): release.begin('test-change','server')
    release.receipt('test-change',started['attempt'],'succeeded','actual-fixture-revision')
    incident=maintenance.incident({'id':'api','url':'https://example.invalid'},{'status':'failed','reason':'http_500'},'2026-10-26T00:00:00Z',1)
    with pytest.raises(ValueError,match='postchecks'): life.transition(incident,'resolved','fixture','test-change')
    monkeypatch.setattr(maintenance,'observe',lambda probe:{'status':'healthy','reason':'ok'})
    assert release.postcheck('test-change',started['attempt'])['passed']
    life.transition(incident,'resolved','Validated fixture deployment','test-change')
    _,state=dev.load(incident)
    assert state['lifecycle']['resolution']['revision']=='actual-fixture-revision'
    assert incident in dev.load('test-change')[1]['lifecycle']['links']
    (root/c['artifact']/'app/main.py').write_text('changed')
    assert dev.gate(f,dev.load('test-change')[1],'deploy')


@pytest.mark.parametrize('mutation',['release','environment','config','source'])
def test_candidate_changes_invalidate_approval(root,mutation):
    f,c=server_candidate(root);approve('test-change','deploy')
    if mutation=='release':(f/'release.md').write_text('new target')
    elif mutation=='environment':(root/'server/.env').write_text('ENVIRONMENT=changed')
    elif mutation=='source':(root/'server/app/main.py').write_text('new app')
    else:
        _,state=dev.load('test-change');state['candidate']['config']['rollback']='different';dev.save(f,state)
    assert dev.gate(f,dev.load('test-change')[1],'deploy')


def test_archival_checks_cannot_authorize_site_deployment(root):
    f=ready(root,area='operations',checks=['archive-integrity'])
    p=root/'package';p.mkdir();(p/'index.html').write_text('fixture')
    config={'target':'server','destination':'meddeck-503318/asia-northeast3/studyez-api',
            'health_url':'https://example.invalid','smoke_command':[sys.executable,'-c','pass'],'rollback':'previous'}
    with pytest.raises(ValueError,match='named server and contracts'):release.prepare('test-change',p,config)


def test_changed_package_and_wrong_target_rejected(root):
    f,c=server_candidate(root)
    (root/'package/app/main.py').write_text('not tested')
    with pytest.raises(ValueError,match='differs'):release.prepare('test-change',root/'package',c['config'])
    approve('test-change','deploy')
    with pytest.raises(ValueError,match='different target'):release.begin('test-change','web')


def test_failed_latest_postcheck_prevents_resolution(root,monkeypatch):
    f,c=server_candidate(root);approve('test-change','deploy');a=release.begin('test-change','server')
    release.receipt('test-change',a['attempt'],'succeeded','v1')
    monkeypatch.setattr(maintenance,'observe',lambda p:{'status':'healthy','reason':'ok'})
    assert release.postcheck('test-change',a['attempt'])['passed']
    monkeypatch.setattr(maintenance,'observe',lambda p:{'status':'unknown','reason':'observation_failed'})
    assert not release.postcheck('test-change',a['attempt'])['passed']
    with pytest.raises(ValueError,match='postchecks'):life.transition('test-change','resolved','fixture','test-change')


def test_maintenance_persists_recovery_without_erasing_investigation(root,monkeypatch):
    config=root/'monitor.json';config.write_text(json.dumps({'consecutive_failures':2,'probes':[{'id':'api','url':'https://example.invalid','kind':'api'}]}))
    result={'status':'unknown','reason':'observation_failed'}
    monkeypatch.setattr(maintenance,'observe',lambda p:result.copy())
    assert maintenance.main(['--config',str(config)])==1
    assert maintenance.main(['--config',str(config)])==1
    state=json.loads((root/'runs/_maintenance/state.json').read_text());incident=state['api']['incident']
    f,s=dev.load(incident);(f/'spec.md').write_text('Human investigation')
    maintenance.incident({'id':'api','url':'https://example.invalid'},result,state['api']['observed_at'],1)
    assert (f/'spec.md').read_text()=='Human investigation'
    result.update(status='healthy',reason='ok');assert maintenance.main(['--config',str(config)])==0
    _,s=dev.load(incident);assert s['lifecycle']['observation']=='recovered'
    assert not s['approvals'] and s['lifecycle']['status']!='resolved'
    life.transition(incident,'resolved','Transient observation recovered; no fix deployed')
    assert dev.load(incident)[1]['lifecycle']['resolution']['kind']=='observation_only'


def test_feedback_link_keeps_fingerprint_and_no_approval(root):
    f=dev.create('test-change','Fixture','site',['unit'])
    life.link('test-change',feedback='site:12',fingerprint='current-revision')
    _,s=dev.load('test-change');assert s['feedback_refs']==[{'id':'site:12','fingerprint':'current-revision'}]
    assert s['approvals']=={}


def test_web_publish_uses_verified_artifact_and_records_receipt(root,monkeypatch):
    dist=root/'web/dist';dist.mkdir(parents=True);(dist/'index.html').write_text('<html><script>fixture</script></html>')
    f=ready(root,checks=['web','contracts'])
    config={'target':'web','destination':'fixture-pages','health_url':'https://example.invalid/',
            'smoke_command':[sys.executable,'-c','pass'], 'rollback':'previous fixture',
            'deploy_command':[sys.executable,'-c','import pathlib,sys; assert (pathlib.Path(sys.argv[1])/"index.html").exists()','{artifact}'],
            'revision_command':[sys.executable,'-c','print("actual-web-fixture-v1")']}
    c=release.prepare('test-change',dist,config);approve('test-change','deploy')
    monkeypatch.setattr(maintenance,'observe',lambda p:{'status':'healthy','reason':'ok'})
    assert release.publish_web('test-change')==0
    a=dev.load('test-change')[1]['deployments'][-1]
    assert a['revision']=='actual-web-fixture-v1' and a['postchecks'][-1]['passed']
    (root/'web/.env.production').write_text('VITE_TEST=changed')
    with pytest.raises(ValueError,match='latest successful'):release.prepare('test-change',dist,config)


@pytest.mark.parametrize('fail_publish',[False,True])
def test_server_deploy_script_with_only_fake_cloud_calls(root,fail_publish):
    shell=shutil.which('pwsh')
    if not shell: pytest.skip('PowerShell required')
    scripts=root/'scripts';scripts.mkdir()
    for p in SCRIPTS.glob('*.py'):
        if p.name in ('development.py','release_evidence.py','workflow_scope.py','workflow_lifecycle.py'):
            shutil.copyfile(p,scripts/p.name)
    (scripts/'maintenance.py').write_text('def observe(probe): return {"status":"healthy","reason":"fixture"}')
    f,c=server_candidate(root)
    deploy=root/'server/deploy.ps1'
    shutil.copyfile(SCRIPTS.parent/'server/deploy.ps1',deploy)
    shutil.copyfile(SCRIPTS.parent/'server/deploy-revision.ps1',deploy.with_name('deploy-revision.ps1'))
    # deploy.ps1 is governed source; reverify after adding the actual wrapper.
    for check in ('server','contracts'):
        assert dev.main(['verify','test-change','--check',check,'--',sys.executable,'-c','pass'])==0
    dev.main(['review','test-change','--summary','Fixture wrapper reviewed'])
    release.prepare('test-change',root/'package',c['config']);approve('test-change','deploy')
    stub=root/'fake-cloud.ps1'
    fail="throw 'fixture deployment failure'" if fail_publish else 'return'
    stub.write_text(f'''$ErrorActionPreference='Stop'
function global:gcloud {{
  $global:LASTEXITCODE=0
  if ($args[0] -eq 'secrets' -and $args[1] -eq 'list') {{ return }}
  if ($args[0] -eq 'projects') {{ return '123' }}
  if ($args[0] -eq 'run' -and $args[1] -eq 'deploy') {{
    $args | ConvertTo-Json | Set-Content -LiteralPath '{root.as_posix()}/fake-cloud-args.json'
    $script:revision='studyez-api-'+$args[([array]::IndexOf($args,'--revision-suffix')+1)]
    {fail}
  }}
  if ($args[0] -eq 'run' -and $args[1] -eq 'revisions') {{
    return @{{metadata=@{{name=$script:revision}};status=@{{conditions=@(@{{type='Ready';status='True'}},@{{type='ContainerReady';status='True'}})}}}} | ConvertTo-Json -Depth 6 -Compress
  }}
  if ($args[0] -eq 'run' -and $args[1] -eq 'services' -and $args[2] -eq 'update-traffic') {{
    if ($args -notcontains ($script:revision+'=100')) {{ throw 'Wrong traffic target' }}
    return
  }}
  if ($args[0] -eq 'run' -and $args[1] -eq 'services' -and $args[2] -eq 'describe') {{
    return @{{status=@{{latestCreatedRevisionName=$script:revision;latestReadyRevisionName=$script:revision;traffic=@(@{{revisionName=$script:revision;percent=100}})}}}} | ConvertTo-Json -Depth 6 -Compress
  }}
  throw 'Unexpected cloud command in fixture'
}}
& '{deploy.as_posix()}' -ChangeId test-change -GatePython '{Path(sys.executable).as_posix()}'
''',encoding='utf-8')
    result=subprocess.run([shell,'-NoProfile','-File',str(stub)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=40)
    a=dev.load('test-change')[1]['deployments'][-1]
    if fail_publish:
        assert result.returncode!=0 and a['status']=='failed',result.stdout+result.stderr
    else:
        assert result.returncode==0 and a['postchecks'][-1]['passed'],result.stdout+result.stderr
        args=json.loads((root/'fake-cloud-args.json').read_text(encoding='utf-8-sig'))
        assert args[args.index('--source')+1]==str(root/a['candidate']['artifact'])
        assert '--no-traffic' in args
        assert a['revision']=='studyez-api-'+args[args.index('--revision-suffix')+1]


def test_artifact_changed_during_deploy_cannot_be_completed(root):
    f,c=server_candidate(root);approve('test-change','deploy');a=release.begin('test-change','server')
    (root/c['artifact']/'app/main.py').write_text('tampered')
    release.receipt('test-change',a['attempt'],'succeeded','actual-fixture')
    assert dev.load('test-change')[1]['deployments'][-1]['status']=='failed'
    with pytest.raises(ValueError,match='successful deployment'):release.postcheck('test-change',a['attempt'])
