"""Execute the real PowerShell traffic verifier against isolated fake cloud responses."""
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_exact_revision_and_traffic_failures():
    result=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(Path(__file__).with_name('check_deploy_revision.ps1')),'-Helper',
        str(ROOT/'server/deploy-revision.ps1')],capture_output=True,text=True)
    assert result.returncode==0, result.stdout+result.stderr
    assert '12 isolated' in result.stdout

def test_default_python_resolves_in_script_body(tmp_path):
    # No Python is installed in this fixture. The script must reach its explicit
    # environment guard, rather than fail while binding its default parameter.
    script=tmp_path/'deploy.ps1';shutil.copyfile(ROOT/'server/deploy.ps1',script)
    stub=tmp_path/'guard.ps1'
    stub.write_text("try { & $args[0] -ChangeId fixture } catch { if ($_.Exception.Message -match 'Join-Path') { exit 2 }; Write-Output 'BODY_GUARD'; exit 0 }; exit 3",encoding='utf-8-sig')
    result=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(stub),str(script)],capture_output=True,text=True)
    assert result.returncode==0, result.stdout+result.stderr
    assert 'BODY_GUARD' in result.stdout
