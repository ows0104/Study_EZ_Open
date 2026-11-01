"""Explicit source selection and non-disclosing staged-file publication checks."""
from pathlib import Path
import collections,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git','-c','core.safecrlf=false',*args],cwd=ROOT,stderr=subprocess.PIPE)
roots=['bridge','content','docs','quizbank','runner','scripts','server','studyez_contracts','studyez_llm','tests','web']
def audit():
    paths=[p for p in git('diff','--cached','--name-only','--diff-filter=ACM','-z').decode().split('\0') if p]
    batch=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=''.join(':'+p+'\n' for p in paths).encode(),capture_output=True,check=True).stdout
    offset=0
    issues=[];total=0
    patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
              r'\bAKIA[A-Z0-9]{16}\b',r'\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}',
              r'\bAIza[A-Za-z0-9_-]{30,}',r'eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}']
    for path in paths:
        end=batch.index(b'\n',offset);header=batch[offset:end].split();assert header[1]==b'blob'
        size=int(header[2]);data=batch[end+1:end+1+size];offset=end+size+2;total+=len(data)
        if len(data)>2_000_000:issues.append((path,'large file'))
        if any(path.startswith(p) for p in ('output/','work/','tmp/','.wrangler/','.vite/','.codex-remote-attachments/')):issues.append((path,'local data'))
        if Path(path).name.startswith('.env'):issues.append((path,'environment file'))
        text=data.decode('utf-8',errors='replace')
        for pattern in patterns:
            if re.search(pattern,text):issues.append((path,'credential pattern'))
        if re.search(r'(?m)^(?:<{7} |={7}$|>{7} )',text):issues.append((path,'merge conflict marker'))
    result={'status':'passed' if not issues else 'failed','files':len(paths),'bytes':total,'issues':issues}
    (HERE/'publication-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));assert not issues
if '--stage' in sys.argv:
    modified=git('diff','--name-only','-z').decode().split('\0')
    new=git('ls-files','--others','--exclude-standard','-z','--',*roots,'AGENTS.md').decode().split('\0')
    selected=sorted(set(p for p in modified+new if p))
    (HERE/'stage-paths.bin').write_bytes(('\0'.join(selected)+'\0').encode())
    subprocess.run(['git','-c','core.safecrlf=false','add','--pathspec-from-file='+str(HERE/'stage-paths.bin'),'--pathspec-file-nul'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
audit()
