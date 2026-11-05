"""Recover an actual completed final JSON from its own timed-out CLI session.

No model/network/process launch. The CLI failure is never upgraded or removed.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import followup as f
import map_patch as mp
from copy import deepcopy

def normalize_classification_orientation(brief):
    """Canonicalize only a redundant opposite edge proven by authored ancestry.

    Every ID, condition, evidence, judgment, point and direction stays unchanged.
    Other cycles still fail the normal contract; no clinical fact is inferred.
    """
    value=deepcopy(brief);parents={c['concept_id']:c['parent_ids']for c in brief['concepts']};changes=[]
    def ancestor_path(child,parent,seen=()):
        if child in seen:return None
        for node in parents[child]:
            if node==parent:return [child,parent]
            path=ancestor_path(node,parent,(*seen,child))
            if path:return [child,*path]
    for row in value['relations']:
        if row['kind']!='classification':continue
        path=ancestor_path(row['from_id'],row['to_id'])
        opposite=next((r for r in brief['relations']if r['kind']=='classification'and r['from_id']==row['to_id']and r['to_id']==row['from_id']),None)
        if not path or not opposite:continue
        before=deepcopy(row);row['from_id'],row['to_id']=row['to_id'],row['from_id']
        changes.append({'relation_id':row['relation_id'],'before':before,'after':deepcopy(row),
            'authoredAncestorPath':path,'existingOppositeRelationId':opposite['relation_id'],
            'basis':'Use the already-authored parent→descendant convention for duplicate classification edges; preserve all authored factual fields.'})
    relations={r['relation_id']:r for r in value['relations']};targets={t['target_id']:t for t in value['targets']};accepted=[];rejected=[]
    for edge in value['prerequisites']:
        rel=relations[edge['relation_id']]
        valid=(rel['kind']=='prerequisite'and rel['review_status']=='reviewed'and rel['from_id']in targets[edge['before_target']]['concept_ids']and rel['to_id']in targets[edge['after_target']]['concept_ids'])
        if valid:accepted.append(edge)
        else:rejected.append({'proposal':deepcopy(edge),'relationKind':rel['kind'],'reason':'Proposal is not backed by the matching reviewed prerequisite relation required by roots/1; preserve as unadopted, do not fabricate a dependency.'})
    value['prerequisites']=accepted
    return value,changes,rejected

def extract():
    log=f.OUT/'runtime/map2-stalled-session.jsonl'
    rows=[json.loads(line)for line in log.read_text(encoding='utf-8').splitlines()if line.strip()]
    f.require(Path(rows[0]['payload']['cwd']).resolve()==(f.OUT/'stages/map-2/workspace').resolve(),'Wrong task session')
    completions=[r for r in rows if r.get('payload',{}).get('type')=='task_complete']
    f.require(len(completions)==1,'Need exactly one completed task event')
    completion=completions[0];raw=completion['payload']['last_agent_message'];patch=json.loads(raw)
    messages=[r for r in rows if r.get('type')=='response_item'and r.get('payload',{}).get('type')=='message'and r['payload'].get('role')=='assistant']
    matches=[r for r in messages if ''.join(c.get('text','')for c in r['payload'].get('content',[])if isinstance(c,dict))==raw]
    f.require(len(matches)==1 and matches[0]['payload'].get('status')=='completed','Completed assistant response mismatch')
    f.g.jsonschema.validate(patch,mp.SCHEMA)
    usages=[r for r in rows if r.get('type')=='token_usage_record'];f.require(usages,'Missing session usage')
    return raw,patch,{'source':'original completed task session, CLI later timed out','completion':completion['timestamp'],
        'duration_ms':completion['payload'].get('duration_ms'),'usageRecord':usages[-1]['payload']},completion

def run():
    old=f.read(f.OUT/'proof.json');new=f.proof();ledger=f.read(f.OUT/'ledger.json');failed=ledger['stages']['map-2']
    f.require(failed['status']=='failed'and '2400초 안에 끝나지 않았다'in failed['error'],'Not the known timed-out task')
    f.require(old==f.read(f.OUT/'runtime/proof-before-map-recovery.json')and f.sha(f.OUT/'runtime/followup-before-map-recovery.py')==old['helperHash'],'Prior runtime mismatch')
    f.require(old['limits']==new['limits'] and old['limits']['map']==2,'Recovery must not expand any call budget')
    for key in ('baselineHash','originLedgerHash','sources','runtime','prompts','visualHelperHash','publicationAllowed'):
        f.require(old[key]==new[key],'Unrelated input changed')
    f.require(not(f.OUT/'runtime/map-recovery-proof.json').exists()and 'assembly-map2'not in ledger['stages'],'Already recovered; refuse overwrite')
    raw,patch,usage,completion=extract();ctx=f.read(f.OUT/'stages/map-2/input.json');previous=ctx['previous_source_only_brief']
    authored=mp.replay(previous,patch);value,normalizations,rejected=normalize_classification_orientation(authored)
    f.validate_brief(value,previous['sources'],from_sources=True)
    a={p['point_id']:p for p in previous['points']};b={p['point_id']:p for p in value['points']};f.require(a.keys()<=b.keys(),'Original point omitted')
    for key,p in a.items():f.require(all(p[k]==b[key][k]for k in ('text','scope_status')),'Original point text/scope changed')
    f.require(value['exclusions']==previous['exclusions'],'Exclusions changed')
    proof={'before':old,'after':new,'failedStage':failed,'sessionLogHash':f.sha(f.OUT/'runtime/map2-stalled-session.jsonl'),
        'modelCompleted':True,'cliTimedOut':True,'additionalModelCalls':0,'budgetsReset':False,
        'operatorScriptHash':f.sha(Path(__file__)),'completionTimestamp':completion['timestamp'],
        'classificationOrientation':normalizations,'authoredBriefHash':f.g.document_hash(authored),'normalizedBriefHash':f.g.document_hash(value),
        'unadoptedPrerequisiteProposals':rejected,
        'reason':'Original session contains the complete assistant JSON and matching task_complete plus usage, despite CLI process wait timing out. Recover that exact response without another model call.'}
    f.g.write(f.OUT/'runtime/map-recovery-proof.json',proof)
    f.g.write(f.OUT/'runtime/map2-authored-brief.json',authored)
    stage=f.OUT/'stages/assembly-map2';stage.mkdir(parents=True,exist_ok=False)
    (stage/'raw.txt').write_text(raw,encoding='utf-8');f.g.write(stage/'output.json',patch);f.g.write(stage/'usage.json',usage)
    f.g.write(stage/'input.json',ctx);f.g.write(stage/'schema.json',mp.SCHEMA)
    (stage/'prompt.txt').write_bytes((f.OUT/'stages/map-2/prompt.txt').read_bytes())
    ledger['stages']['assembly-map2']={'status':'completed','at':f.now(),'invocationType':'deterministic-recovery','additionalModelCalls':0,
        'inputHash':f.g.document_hash(ctx),'schemaHash':f.g.document_hash(mp.SCHEMA),'promptHash':f.sha(stage/'prompt.txt'),
        'rawHash':f.sha(stage/'raw.txt'),'outputHash':f.g.document_hash(patch),'usageHash':f.sha(stage/'usage.json'),'recoveryProofHash':f.g.document_hash(proof)}
    f.g.write(f.OUT/'proof.json',new);f.g.write(f.OUT/'ledger.json',ledger)
    f.g.write(f.OUT/'brief-before-map2.json',previous);f.g.write(f.OUT/'brief-changes-before-map2.json',f.read(f.OUT/'brief-changes.json'))
    f.g.write(f.OUT/'brief.json',value);base=f.read(f.BASE/'assembled-result.json')['brief'];diff={}
    for field,key in mp.ITEMS.items():
        a={r[key]:r for r in base[field]};b={r[key]:r for r in value[field]}
        diff[field]={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':[k for k in a.keys()&b.keys()if a[k]!=b[k]]}
    a={d['direction_id']:d for t in base['targets']for d in t['directions']};b={d['direction_id']:d for t in value['targets']for d in t['directions']}
    diff['directions']={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':{k:{'before':a[k],'after':b[k],'equivalence':'not-assumed'}for k in a.keys()&b.keys()if a[k]!=b[k]}}
    diff['targetedCorrection']={'operatorScriptHash':f.sha(Path(__file__)),'authoredReasons':patch['reasons'],'beforeHash':f.g.document_hash(previous),'afterHash':f.g.document_hash(value),'originalModelStage':'map-2','additionalModelCalls':0}
    f.g.write(f.OUT/'brief-changes.json',diff)
    print(json.dumps({**{k:len(value[k])for k in mp.ITEMS},'directions':sum(len(t['directions'])for t in value['targets']),'additionalModelCalls':0},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
