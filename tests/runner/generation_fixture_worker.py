"""Test-only live worker; real HTTP/storage/subprocess, synthetic model child."""
import sys
import os
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from runner import connection_generation as worker
from runner.bank_flow import execution
from runner.transport import Client
def child(argv,**kwargs):
    if argv[2] in('quizbank.root_evidence','quizbank.root_choices'):return subprocess.CompletedProcess(argv,1)  # 근거·선지는 이 합성 판에서 실행하지 않는다
    assert argv[1]=='-m' and argv[2] in ('quizbank.connection_generate','runner.root_native_json')
    return subprocess.run([sys.executable,str(ROOT/'tests/quizbank/generation_fixture_cli.py'),*argv[3:]],**kwargs)
worker.run_forwarded=child
if __name__=='__main__':
    client=Client('http://127.0.0.1:'+os.environ.get('GENERATION_TEST_PORT','8028'),'synthetic-runner-token')
    job=client.call('POST','/api/admin/prequiz-jobs/claim?worker=gen-test')['job']
    assert job and job['kind']=='bank'
    raise SystemExit(execution.run(client,ROOT,'test','demo','2026','2025',Path(sys.argv[1])))
