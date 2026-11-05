"""Real native file-protocol smoke with synthetic A/B data, no API publication."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests/contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from runner import root_native_json as n
from studyez_contracts.roots import generation_v2 as c

out=ROOT/'runs/_development/2026-11-05-root-timeout-fix/native-smoke';out.mkdir(parents=True,exist_ok=False)
packet=f.packet(out/'source.txt');sources=g.prepare(packet,out/'material');brief=f.brief(sources)
ctx={k:packet[k]for k in('title','scope','conceptMap','points','examDate')}
ctx.update(lecture_id=brief['lecture_id'],sources=sources,preserved_scope=g.lecture_scope(packet['title'],packet['sources']),
    brief=brief,initialBriefErrors=[],webResponse=f.old.web_response(packet['generationId']),_pipeline_version=c.POLICY)
g.write(out/'generate.input.json',ctx);start=time.monotonic()
value,info=n.NativeJson(out)('generate',ctx,out/'material',None)
c.validate_authoring(value);assert value['brief']==brief
g.write(out/'generate.raw.json',value);g.write(out/'generate.usage.json',info)
entry={'name':'generate','status':'completed','inputHash':g.document_hash(ctx),'usageHash':g.document_hash(info)}
n.validate_stage(out,entry,model=g.codex.model_name())
summary={'status':'completed','seconds':round(time.monotonic()-start,2),'questions':len(value['bank']['questions']),
    'nativeFinalCharacters':len(n.read(out/'.native/generate/provider.json')['text']),'actualJsonBytes':(out/'.native/generate/output.json').stat().st_size,'usage':info['usage']}
g.write(out/'smoke-summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
