"""Read-only compact status for the single authorized live pilot."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'runs/_root-generation/45ba26d191dc468a800360a366c39a55'
d=json.loads((p/'ledger.json').read_text(encoding='utf-8'))
last=next(reversed(d['stages']))
status={'repairRounds':d['repairRounds'],'stages':{k:v['status']for k,v in d['stages'].items()},
        'lastStageMinutes':round((time.time()-(p/(last+'.input.json')).stat().st_mtime)/60,1)}
if (p/'normalize.json').exists():
    b=json.loads((p/'normalize.json').read_text(encoding='utf-8'))
    status['briefCounts']={k:len(b.get(k,[]))for k in ('concepts','targets','relations','points')}
for name in reversed(d['stages']):
    if (name=='generate'or name.startswith('repair-'))and(p/(name+'.json')).exists():
        a=json.loads((p/(name+'.json')).read_text(encoding='utf-8'));status['questionCount']=len(a['bank']['questions']);break
if (p/'result.json').exists():
    r=json.loads((p/'result.json').read_text(encoding='utf-8'))
    status.update(result=True,tasks=len(r['document']['tasks']),targets=len(r['brief']['targets']),questions=len(r['document']['bank_snapshot']['questions']))
status['publishedLocally']=(p/'published.json').exists()
print(json.dumps(status,ensure_ascii=False))
log=ROOT/'runs/agent.261102_03.log'
print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-3:]))
