"""Run the documented server suite with an isolated environment."""
import os, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='studyez-release-') as tmp:
    env=dict(os.environ, ENVIRONMENT='local-test', DATABASE_URL='sqlite:///'+(Path(tmp)/'safe.db').as_posix(),
             STUDYEZ_LOCAL_STORAGE_DIR=str(Path(tmp)/'storage'), RUNNER_TOKEN='release-test-only',
             PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONPATH=str(root))
    raise SystemExit(subprocess.run([sys.executable,'-B','-m','tests'],cwd=root/'server',env=env).returncode)
