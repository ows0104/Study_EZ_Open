"""Test-only child CLI. Production orchestration with a synthetic model adapter."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import automation_fixture as f
from quizbank import connection_generate as generator
generator.call_model=f.model
if __name__=='__main__':raise SystemExit(generator.main())
