"""Run the server's isolated per-file tests from its required working directory."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
env=os.environ.copy()
env.update(ENVIRONMENT='local-test',DATABASE_URL='sqlite://',PYTHONIOENCODING='utf-8')
raise SystemExit(subprocess.call([sys.executable,'-m','tests'],cwd=root/'server',env=env))
