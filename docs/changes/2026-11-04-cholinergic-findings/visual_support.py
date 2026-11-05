"""Model-authored source crops and tool-free review of actual question images."""
import hashlib,json,os,tempfile,time
from pathlib import Path
import fitz
from studyez_contracts.learning_links.schema import obj,arr,enum,TEXT
from studyez_llm import codex,telemetry
from studyez_llm.execution import exclusive,run_process

UNIT={'type':'number','minimum':0,'maximum':1}
BOX=arr(UNIT,4);BOX['maxItems']=4;BOX.pop('uniqueItems',None)
STIMULUS=obj(question_id=TEXT,source_id=enum('S1'),page={'type':'integer','minimum':1,'maximum':35},
    crop=BOX,reason=TEXT)
def authoring_schema(bank_schema):return obj(bank=bank_schema,visual_stimuli=arr(STIMULUS))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def render(stimuli,bank,packet,out,n):
    qids={q['question_id']for q in bank['questions']};records=[]
    source=next(s for s in packet['sources']if s['id']=='S1')
    for i,row in enumerate(stimuli):
        if row['question_id']not in qids:raise ValueError('Stimulus has unknown question')
        x0,y0,x1,y1=row['crop']
        if not (0<=x0<x1<=1 and 0<=y0<y1<=1):raise ValueError('Invalid authored source crop')
        path=out/'material'/f'stimulus-{n}-{i+1}.png'
        if path.exists():raise ValueError('Refuse stimulus overwrite')
        with fitz.open(source['localPath'])as pdf:
            page=pdf[row['page']-1];rect=page.rect
            clip=fitz.Rect(x0*rect.width,y0*rect.height,x1*rect.width,y1*rect.height)
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=clip);pix.save(path)
        records.append({**row,'imageFile':path.name,'imageSha256':digest(path),'sourceSha256':source['sha256'],
            'width':pix.width,'height':pix.height})
    return records

def blind_with_images(prompt,*,schema,system,images,stage,timeout=900):
    if not images:return codex.run(prompt,schema=schema,system=system,blind=True,timeout=timeout,label='콜린성 예시 독립 정답 검수')
    selected=codex.model_name();start=time.monotonic()
    request={'prompt':prompt,'schema':schema,'blind':True,'images':[digest(p)for p in images]}
    with exclusive(request),tempfile.TemporaryDirectory(prefix='studyez-blind-images-',ignore_cleanup_errors=True)as temp:
        work=Path(temp);sp=work/'schema.json';sp.write_text(json.dumps(schema),encoding='utf-8')
        ip=work/'instructions.md';ip.write_text(system,encoding='utf-8')
        argv=codex.command(model=selected,blind=True)
        argv+=['-c',f'projects.{json.dumps(work.as_posix())}.trust_level="untrusted"',
            '-c',f'model_instructions_file={json.dumps(ip.as_posix())}','--output-schema',str(sp)]
        for path in images:argv+=['--image',str(path.resolve())]
        argv+=['-']
        proc=run_process(argv,input=prompt,cwd=work,timeout=timeout,capture_output=True,text=True,encoding='utf-8',errors='replace',
            creationflags=getattr(__import__('subprocess'),'CREATE_NO_WINDOW',0))
    (stage/'blind-events.jsonl').write_text(proc.stdout,encoding='utf-8')
    if proc.returncode:raise codex.SessionError('Blind image review failed: '+(proc.stdout+proc.stderr)[-1800:])
    info=codex.parse_events(proc.stdout,model=selected,blind=True)
    info['duration_ms']=round((time.monotonic()-start)*1000)
    telemetry.record(status='completed',model=selected,label='콜린성 예시 독립 정답 검수·문항그림 첨부',cwd=None,prompt=prompt,
        seconds=time.monotonic()-start,usage=info['usage'],session_id=info['session_id'])
    return info
