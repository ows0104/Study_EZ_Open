"""One operator recovery of a proven no-final timeout, never a retry loop."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import followup as f
import map_patch as mp

def transition():
    old=f.read(f.OUT/'proof.json');new=f.proof();ledger=f.read(f.OUT/'ledger.json');failure=ledger['stages']['map-2']
    f.require(failure['status']=='failed' and '2400초 안에 끝나지 않았다'in failure['error'],'Not the proven timeout')
    f.require(old==f.read(f.OUT/'runtime/proof-before-map-recovery.json')and f.sha(f.OUT/'runtime/followup-before-map-recovery.py')==old['helperHash'],'Prior helper evidence changed')
    for key in ('baselineHash','originLedgerHash','sources','runtime','prompts','visualHelperHash','publicationAllowed'):
        f.require(old[key]==new[key],'Unrelated recovery input changed')
    f.require(old['limits']['map']==2 and new['limits']=={**old['limits'],'map':3},'Only one technical map attempt may be added')
    stage=f.OUT/'stages/map-2';f.require(not(stage/'output.json').exists()and not(stage/'raw.txt').exists(),'Final output exists; refuse retry')
    log=f.OUT/'runtime/map2-stalled-session.jsonl';rows=[json.loads(line)for line in log.read_text(encoding='utf-8').splitlines()if line.strip()]
    f.require(Path(rows[0]['payload']['cwd']).resolve()==(stage/'workspace').resolve(),'Wrong failed session')
    finals=[r for r in rows if r.get('type')=='response_item'and r.get('payload',{}).get('type')=='message'and r['payload'].get('role')=='assistant'and r['payload'].get('channel')=='final']
    completed=[r for r in rows if r.get('payload',{}).get('type')in ('task_complete','turn_completed')]
    f.require(not finals and not completed,'A final response exists; refuse another model call')
    proof={'before':old,'after':new,'failedStage':failure,'sessionLogHash':f.sha(log),
        'noFinalOutput':True,'noCompletedTurn':True,'budgetsReset':False,'operatorScriptHash':f.sha(Path(__file__)),
        'reason':'Explicit operator recovery once after inspecting the task session/process and the CLI2400s timeout; earlier clinical content/review budgets and every failed attempt remain preserved.',
        'successfulMapRevisionCeiling':2,'totalMapAttemptCeiling':3}
    f.require(not(f.OUT/'runtime/map-recovery-proof.json').exists(),'Recovery already recorded')
    f.g.write(f.OUT/'runtime/map-recovery-proof.json',proof);f.g.write(f.OUT/'proof.json',new)
    ledger['limits']=new['limits'];ledger['scopeAdjustments'].append({'reason':'One proven no-final map timeout recovery','consumedMapAttempts':2,'maxMapAttempts':3,'maxSuccessfulMapRevisions':2,'budgetsReset':False})
    f.g.write(f.OUT/'ledger.json',ledger);print('One operator recovery recorded; failed map2 retained, no budget reset.',flush=True)

def run():
    f.verified();proof=f.read(f.OUT/'runtime/map-recovery-proof.json');f.require(proof['operatorScriptHash']==f.sha(Path(__file__)),'Recovery operator changed')
    old=f.OUT/'stages/map-2';ctx=f.read(old/'input.json');ctx.update(recoveryProofHash=f.g.document_hash(proof),recoveryOperatorScriptHash=f.sha(Path(__file__)))
    material=f.OUT/'source-only-material'
    for row in ctx['sourceOnlyFiles']:f.require(f.sha(material/row['name'])==row['sha256'],'Source-only material changed')
    prompt=(old/'prompt.txt').read_text(encoding='utf-8').split('\n\nFull acceptance schema:',1)[0]
    patch=f.cli('map-recovery',ctx,mp.SCHEMA,prompt,material_dir=material)
    previous=ctx['previous_source_only_brief'];value=mp.replay(previous,patch);f.validate_brief(value,previous['sources'],from_sources=True)
    a={p['point_id']:p for p in previous['points']};b={p['point_id']:p for p in value['points']};f.require(a.keys()<=b.keys(),'Original point omitted')
    for key,p in a.items():f.require(all(p[k]==b[key][k]for k in ('text','scope_status')),'Original point text/scope changed')
    f.require(value['exclusions']==previous['exclusions'],'Exclusions changed')
    f.g.write(f.OUT/'brief-before-map2.json',previous);f.g.write(f.OUT/'brief-changes-before-map2.json',f.read(f.OUT/'brief-changes.json'))
    f.g.write(f.OUT/'brief.json',value);base=f.read(f.BASE/'assembled-result.json')['brief'];diff={}
    for field,key in mp.ITEMS.items():
        a={r[key]:r for r in base[field]};b={r[key]:r for r in value[field]}
        diff[field]={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':[k for k in a.keys()&b.keys()if a[k]!=b[k]]}
    a={d['direction_id']:d for t in base['targets']for d in t['directions']};b={d['direction_id']:d for t in value['targets']for d in t['directions']}
    diff['directions']={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':{k:{'before':a[k],'after':b[k],'equivalence':'not-assumed'}for k in a.keys()&b.keys()if a[k]!=b[k]}}
    diff['targetedCorrection']={'operatorScriptHash':f.sha(Path(__file__)),'authoredReasons':patch['reasons'],'beforeHash':f.g.document_hash(previous),'afterHash':f.g.document_hash(value),'recoveredCall':'map-2'}
    f.g.write(f.OUT/'brief-changes.json',diff)
    print(json.dumps({**{k:len(value[k])for k in mp.ITEMS},'directions':sum(len(t['directions'])for t in value['targets'])},ensure_ascii=False),flush=True)

if __name__=='__main__':
    if sys.argv[1:] ==['transition']:transition()
    elif sys.argv[1:] ==['run']:run()
    else:raise SystemExit('transition/run')
