"""Bounded synthetic diagnostics, never accepts or publishes lecture content."""
import argparse,json,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests/contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c,document_hash

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=['minimal','author','author-plain','same-context']);p.add_argument('--timeout',type=int,default=150);a=p.parse_args()
    out=ROOT/'runs/_development/2026-11-05-root-timeout-fix/probes'/a.case
    out.mkdir(parents=True,exist_ok=False)
    small=a.case in ('minimal','same-context')
    value={'ok':True}if small else f.author()
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}if small else g.output_schema(c.AUTHOR)
    prompt='This is a synthetic transport diagnostic, with no medical content. Return exactly the following JSON without changes, commentary, tools or additional work.\n'+json.dumps(value,ensure_ascii=False)
    g.write(out/'request-summary.json',{'case':a.case,'model':g.codex.model_name(),'promptCharacters':len(prompt),'schemaCharacters':len(json.dumps(schema)),'expectedHash':document_hash(value),'timeout':a.timeout})
    options={}
    if a.case=='same-context':
        failed=ROOT/'runs/_root-generation/45ba26d191dc468a800360a366c39a55/generate.continuation.json'
        proof=json.loads(failed.read_text(encoding='utf-8'))['proof']
        options=dict(resume=proof['sessionId'],previous_usage=proof['previousKnownUsage'],cwd=Path(proof['workspace']))
        prompt='Diagnostic only. Pause the earlier authoring task. Do not inspect or modify materials, questions, medical facts or files. To test whether this existing session can return a tiny final response, reply exactly {"ok":true} and nothing else. This response is not an authoring or review result.'
    original=g.codex.run_process
    def observe(*args,**kwargs):
        result=original(*args,**kwargs)
        (out/'stdout.log').write_text(result.stdout or '',encoding='utf-8');(out/'stderr.log').write_text(result.stderr or '',encoding='utf-8')
        return result
    g.codex.run_process=observe
    print('Started diagnostic '+a.case,flush=True);start=time.monotonic()
    try:
        result=g.codex.run(prompt,blind=a.case!='same-context',timeout=a.timeout,label='Root timeout diagnostic '+a.case,
            schema=None if a.case.endswith('plain')else schema,system='Return the exact supplied synthetic JSON only.',**options)
        g.write(out/'response.json',result);decoded=json.loads(result['text'])
        if a.case!='minimal':decoded=g.decode_optional_fields(decoded,c.AUTHOR)
        summary={'status':'completed','seconds':round(time.monotonic()-start,2),'exact':decoded==value,'usage':result['usage'],'turns':result['turns'],'sessionId':result['session_id']}
    except BaseException as error:
        streams={};cause=error
        while cause:
            for field in ('output','stdout','stderr'):
                body=getattr(cause,field,None)
                if body:streams[field]=body.decode('utf-8',errors='replace')if isinstance(body,bytes)else str(body)
            cause=cause.__cause__ or cause.__context__
        for key,body in streams.items():(out/(key+'.log')).write_text(body,encoding='utf-8')
        events=[]
        for line in streams.get('output',streams.get('stdout','')).splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        summary={'status':'failed','seconds':round(time.monotonic()-start,2),'errorType':type(error).__name__,'streamCharacters':{k:len(v)for k,v in streams.items()},
            'events':[{'type':e.get('type'),'message':e.get('message','')[:300]}for e in events if e.get('type')in('thread.started','turn.started','turn.completed','turn.failed','error')]}
        (out/'traceback.log').write_text(traceback.format_exc(),encoding='utf-8')
    g.write(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
