"""Pin tested runner code; reuse original state/config without starting any jobs."""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OPERATING=ROOT.parents[1]

def call(args,**kwargs):return subprocess.check_output(args,text=True,encoding='utf-8',**kwargs).strip()

def install(sha):
    assert len(sha)==40 and all(c in '0123456789abcdef'for c in sha)
    assert call(['git','rev-parse','HEAD'],cwd=ROOT)==sha
    target=OPERATING/'.runtime'/('main-quiz-'+sha[:12]);assert not target.exists(),'Preserve existing runtime'
    target.mkdir(parents=True);archive=target/'code.zip'
    paths=['runner','quizbank','quizgen','studyez_contracts','studyez_llm','content','scripts','data/timetable','server/app','server/requirements.txt','platform','pyproject.toml','requirements.txt']
    subprocess.run(['git','archive','--format=zip','-o',str(archive),sha,*paths],cwd=ROOT,check=True)
    with zipfile.ZipFile(archive)as z:
        for info in z.infolist():
            dest=(target/info.filename).resolve();assert dest.is_relative_to(target.resolve())
            if info.is_dir():dest.mkdir(parents=True,exist_ok=True)
            else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
    links={'runs':OPERATING/'runs','.venv':OPERATING/'.venv','server/.venv':OPERATING/'server/.venv',
        'server/local_test_data':OPERATING/'server/local_test_data'}
    for name,dest in links.items():
        assert dest.is_dir();folder=target/name;folder.parent.mkdir(parents=True,exist_ok=True)
        cmd="New-Item -ItemType Junction -Path '"+str(folder).replace("'","''")+"' -Target '"+str(dest).replace("'","''")+"' | Out-Null"
        subprocess.run(['powershell','-NoProfile','-Command',cmd],check=True)
    launcher=target/'launch-runner.pyw'
    text='import os,sys,runpy\nfrom dotenv import load_dotenv\n'
    text+='load_dotenv('+repr(str(OPERATING/'server/.env'))+')\n'
    text+="os.environ['STUDYEZ_RUNNER_TOKEN']=os.getenv('RUNNER_TOKEN','')\n"
    text+="os.environ['PYTHONPATH']="+repr(str(target))+"\nos.environ['PYTHONSAFEPATH']='1'\n"
    text+="for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):os.environ.pop(key,None)\n"
    text+='sys.path.insert(0,'+repr(str(target))+')\n'
    text+="sys.argv=['runner.desktop','--runs',"+repr(str(OPERATING/'runs'))+"]\nrunpy.run_module('runner.desktop',run_name='__main__')\n"
    launcher.write_text(text,encoding='utf-8')
    desktop=Path(call(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"]))
    shortcut=desktop/'Study EZ 러너.lnk';backup=target/'shortcut-before.lnk'
    if shortcut.exists():shutil.copy2(shortcut,backup)
    temporary=desktop/('studyez-main-quiz-'+sha[:12]+'.lnk')
    assert temporary.parent.resolve()==shortcut.parent.resolve()==desktop.resolve()
    config={'shortcut':str(shortcut),'temporary':str(temporary),'pythonw':str(OPERATING/'server/.venv/Scripts/pythonw.exe'),'arguments':'"'+str(launcher)+'"','workingDirectory':str(target)}
    assert Path(config['pythonw']).is_file()
    (target/'shortcut-config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
    ps="$c=Get-Content -LiteralPath '"+str(target/'shortcut-config.json').replace("'","''")+"' -Raw -Encoding UTF8 | ConvertFrom-Json; $s=New-Object -ComObject WScript.Shell; $l=$s.CreateShortcut($c.temporary); $l.TargetPath=$c.pythonw; $l.Arguments=$c.arguments; $l.WorkingDirectory=$c.workingDirectory; $l.Description='Study EZ CLI Main Quiz'; $l.Save(); Move-Item -LiteralPath $c.temporary -Destination $c.shortcut -Force"
    subprocess.run(['powershell','-NoProfile','-Command',ps],check=True)
    assert shortcut.is_file()
    record={'revision':sha,'runtime':str(target),'shortcut':str(shortcut),'backup':str(backup)if backup.exists()else None,
        'operatingRuns':str(OPERATING/'runs'),'jobsStarted':0,'oldCodeUnchanged':True,'shortcutSha256':hashlib.sha256(shortcut.read_bytes()).hexdigest()}
    (ROOT/'runs/_final-plan/261104_02/runtime-install.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);install(p.parse_args().revision)
