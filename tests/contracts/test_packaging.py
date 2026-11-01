import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_cloud_source_includes_shared_contracts_and_only_allowed_files(tmp_path):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell packaging requires pwsh or Windows PowerShell')
    target = tmp_path / 'cloud-source'
    subprocess.run([shell, '-NoProfile', '-File', str(ROOT / 'server/prepare-build.ps1'),
                    '-Destination', str(target)], check=True, capture_output=True)
    assert (target / 'app/main.py').is_file()
    assert (target / 'studyez_contracts/bank/schema.py').read_bytes() == (
        ROOT / 'studyez_contracts/bank/schema.py').read_bytes()
    assert (target / 'app/bank_validation/schema.py').read_bytes() == (
        ROOT / 'server/app/bank_validation/schema.py').read_bytes()
    assert '-e ../studyez_contracts' in (target / 'requirements.txt').read_text()
    assert 'COPY studyez_contracts /studyez_contracts' in (target / 'Dockerfile').read_text()
    assert not any(p.name.startswith('.env') or p.suffix in {'.db', '.sqlite', '.pyc'}
                   or 'tests' in p.parts for p in target.rglob('*'))


def test_deploy_without_change_id_stops_before_cloud_or_environment_access():
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell deploy guard requires pwsh or Windows PowerShell')
    env = os.environ.copy()
    env.pop('STUDYEZ_CHANGE_ID', None)
    result = subprocess.run([shell, '-NoProfile', '-File', str(ROOT / 'server/deploy.ps1')],
                            env=env, capture_output=True, timeout=20)
    assert result.returncode != 0
    assert b'docs/development/README.md' in result.stderr + result.stdout
