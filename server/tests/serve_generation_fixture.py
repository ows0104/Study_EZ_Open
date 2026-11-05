"""Never imported by production. Own isolated DB/PDF, no model/network content."""
import os
import sys
import subprocess
from pathlib import Path
os.environ['RUNNER_TOKEN']='synthetic-runner-token'
from tests.root_support import setup
client,user,SessionLocal=setup()
from app.main import app
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
from app.models import Asset
from app.storage import ObjectStorage
from fastapi import Request
import uvicorn
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2]
# Create the synthetic PDF in the authoring environment, outside server imports.
folder=Path(os.environ['STUDYEZ_LOCAL_STORAGE_DIR']).parent
pdf=folder/'synthetic.pdf'
code="import fitz,sys;d=fitz.open();p=d.new_page();p.insert_text((50,50),'Synthetic integration source: A and B. Not medical content.');d.save(sys.argv[1])"
subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-c',code,str(pdf)],check=True)
ObjectStorage().put_bytes('lectures/test/demo/synthetic.pdf',pdf.read_bytes())
with SessionLocal() as db:
    db.add(Asset(id='synthetic-source',subject='test',run_id='demo',kind='notes_current',filename='synthetic.pdf',
        object_key='lectures/test/demo/synthetic.pdf',size_bytes=pdf.stat().st_size,content_type='application/pdf'));db.commit()
def test_user(request:Request):
    uid=request.headers.get('X-Root-Test-User','admin')
    return CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=uid=='admin',apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
app.dependency_overrides[get_current_user]=test_user
process=None
@app.post('/__test/process')
def process_job():
    global process
    if process and process.poll() is None:return {'started':False}
    process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'tests/runner/generation_fixture_worker.py'),str(folder/('worker-'+uuid4().hex[:8]))],
        cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)
    return {'started':True}
@app.post('/__test/stop')
def stop_job():
    if process and process.poll()is None:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        else:process.terminate();process.wait(timeout=10)
    return {'stopped':True}
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('GENERATION_TEST_PORT','8028')),log_level='warning')
