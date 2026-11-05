import os
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
env={**os.environ,'PYTHONIOENCODING':'utf-8'}
for pattern in ('connections','route_contract','usage','bank_personal'):
    result=subprocess.run([str(root/'server/.venv/Scripts/python.exe'),'-m','tests',pattern],cwd=root/'server',env=env)
    if result.returncode: sys.exit(result.returncode)
