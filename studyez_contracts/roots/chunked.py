"""Pure partition contracts for an explicitly authorized, frozen review continuation."""
import copy
import jsonschema
from . import generation_v2 as c
from .validate import document_hash
from studyez_contracts.learning_links.schema import obj,arr,TEXT
from studyez_contracts.learning_links.validate import require,index_by

POLICY='frozen-chunked-review/1'

def clean(v):
    if isinstance(v,dict):return {k:clean(x)for k,x in v.items()if k!='png_base64'}
    if isinstance(v,list):return [clean(x)for x in v]
    return v

def plan(ctx):
    tasks=[]
    for kind,ids,size in [('questions',[q['question_id']for q in ctx['bank']['questions']],15),
            ('relations',[r['relation_id']for r in ctx['brief']['relations']],40),
            ('targets',[t['target_id']for t in ctx['brief']['targets']],24),
            ('medical',[q['question_id']for q in ctx['bank']['questions']],15)]:
        for i in range(0,len(ids),size):tasks.append({'name':kind+'-'+str(i//size+1),'kind':kind,'ids':ids[i:i+size]})
    return tasks+[{'name':'global','kind':'global','ids':[]}]

def task_input(ctx,task,outputs=None):
    if task['kind']=='medical':
        bank={**ctx['bank'],'questions':[q for q in ctx['bank']['questions']if q['question_id']in task['ids']]}
        return {'title':ctx['title'],'clinicalInput':c.medical_input(bank,ctx['clinical_conflicts']),'assignment':task}
    result={'context':clean(ctx),'assignment':task}
    if task['kind']=='global':result['completedSourceParts']=outputs
    return result

def schema(ctx,task):
    full=c.source_schema(ctx['brief'],ctx['bank']);props=full['properties'];kind=task['kind'];ids=task['ids']
    fields={'questions':['question_reviews','design_checks','direction_evidence','prerequisite_checks','issues'],
        'relations':['relation_checks','issues'],'targets':['direction_checks','target_checks','issues'],
        'global':['schema_version','summary','issues','clinical_context_status','clinical_context_reason']}[kind]
    result=obj(**{k:copy.deepcopy(props[k])for k in fields})
    keys={'question_reviews':'question_id','design_checks':'question_id','relation_checks':'relation_id','target_checks':'target_id'}
    dids=[d['direction_id']for t in ctx['brief']['targets']if t['target_id']in ids for d in t['directions']]
    for field in fields:
        if field in keys or field=='direction_checks':
            choices=dids if field=='direction_checks'else ids
            s=result['properties'][field];s.update(minItems=len(choices),maxItems=len(choices))
            s['items']['properties'][keys.get(field,'direction_id')]={'type':'string','enum':choices}
    return result

def check(ctx,task,value):
    jsonschema.validate(value,schema(ctx,task));kind=task['kind'];ids=set(task['ids'])
    for field,key in [('question_reviews','question_id'),('design_checks','question_id'),('relation_checks','relation_id'),('target_checks','target_id')]:
        if field in value:require(set(index_by(value[field],key))==ids,'chunk: missing/duplicate assigned '+field)
    if kind=='questions':
        require(all(r['question_id']in ids for r in value['direction_evidence']),'chunk: foreign evidence')
        pairs=[(r['question_id'],r['direction_id'])for r in value['direction_evidence']]
        require(len(pairs)==len(set(pairs)),'chunk: duplicate direction evidence')
        qs={q['question_id']:q for q in ctx['bank']['questions']};ds={d['direction_id']:d for t in ctx['brief']['targets']for d in t['directions']}
        for r in value['direction_evidence']:
            require(r['direction_id']in ds,'chunk: unknown evidence direction')
            parts=index_by(r['components'],'component_id')
            require(set(parts)=={x['component_id']for x in ds[r['direction_id']]['components']},'chunk: incomplete components')
            for p in parts.values():
                ix=p['answer_unit_indices']
                require(len(ix)==len(set(ix))and all(i<len(qs[r['question_id']]['answer_units'])for i in ix)
                    and bool(ix)==(p['location']=='answer'),'chunk: invalid answer unit evidence')
        edges={(q['question_id'],p)for q in ctx['bank']['questions']if q['question_id']in ids for p in q.get('prerequisites',[])}
        actual=[(r['question_id'],r['prerequisite_id'])for r in value['prerequisite_checks']]
        require(len(actual)==len(set(actual))and set(actual)==edges,'chunk: missing/duplicate prerequisite')
    if kind=='targets':
        expected={d['direction_id']for t in ctx['brief']['targets']if t['target_id']in ids for d in t['directions']}
        require(set(index_by(value['direction_checks'],'direction_id'))==expected,'chunk: missing/duplicate direction')
    if 'issues'in value:
        index_by(value['issues'],'issue_id')
        require(all(r['issue_id'].startswith(task['name']+'-')for r in value['issues']),'chunk: issue IDs need assigned prefix')
        qs={q['question_id']for q in ctx['bank']['questions']};ds={d['direction_id']:d for t in ctx['brief']['targets']for d in t['directions']}
        for r in value['issues']:
            require(set(r['question_ids'])<=qs and set(r['direction_ids'])<=set(ds),'chunk: unknown issue reference')
            if r['kind']=='required_gap':require(r['direction_ids']and all(ds[x]['requirement']=='required'for x in r['direction_ids']),'chunk: invalid required gap')
    return value

def merge(ctx,outputs):
    tasks=[t for t in plan(ctx)if t['kind']!='medical']
    require(set(outputs)=={t['name']for t in tasks},'chunk: incomplete source tasks')
    result={k:[]for k in ('question_reviews','design_checks','direction_evidence','prerequisite_checks','relation_checks','target_checks','direction_checks','issues')}
    for task in tasks:
        v=check(ctx,task,outputs[task['name']])
        for k,val in v.items():
            if isinstance(val,list):result[k]+=copy.deepcopy(val)
            else:result[k]=val
    jsonschema.validate(result,c.source_schema(ctx['brief'],ctx['bank']))
    c.compile_assessment(ctx['brief'],ctx['bank'],c.envelope(ctx['brief'],ctx['bank'],result))
    return result

def validate_continuation(value):
    meta=value['manifest'];row=meta.get('chunkedReview')
    if row is None:return
    p=row['proof'];old=p['priorLedger'];stages={r['name']:r for r in meta['stages']}
    require(row['proofHash']==document_hash(p)and p['policy']==POLICY,'chunk: changed proof')
    require(p['priorLedgerHash']==document_hash(old)and old['identity']==meta['runtimeHash']
        and old['repairRounds']==meta['repairRounds']==2,'chunk: reset runtime/budget')
    require(old['stages']['source-2']['status']=='failed'and set(stages)==set(old['stages'])|{'medical-2'},'chunk: wrong continuation point')
    for k,v in old['stages'].items():
        if k!='source-2':require(stages[k]=={'name':k,**v},'chunk: changed earlier stage')
    require(p['failure']['classification']['kind']=='model_timeout'and p['failure']['classification']['automaticRetry']is False,'chunk: not timeout continuation')
    bank=value['document']['bank_snapshot'];ctx=copy.deepcopy(p['context']);ctx['bank']=bank
    require(document_hash(ctx)==old['stages']['source-2']['inputHash']==stages['source-2']['inputHash'],'chunk: changed frozen source input')
    require(ctx['brief']==value['brief']and ctx['clinical_conflicts']==meta['clinicalConflicts']and p['packetHash']==meta['inputHash'],'chunk: changed frozen brief/context')
    author={'brief':value['brief'],'bank':bank,'visual_stimuli':meta['visualStimuli'],'clinical_conflicts':meta['clinicalConflicts'],'map_change_reason':meta['mapChangeReason']}
    require(document_hash(author)==old['stages']['repair-2']['outputHash'],'chunk: changed original 91-question candidate')
    expected=plan(ctx);rows=p['tasks'];require([r['assignment']for r in rows]==expected,'chunk: incomplete/reordered task plan')
    outputs={};medical=[]
    parts={r['assignment']['name']:r['output']for r in rows if r['assignment']['kind']not in('global','medical')}
    for r in rows:
        require(r['outputHash']==document_hash(r['output'])and r['model']==meta['model']and r['status']=='completed','chunk: incomplete/changed task')
        inp=task_input(ctx,r['assignment'],parts if r['assignment']['kind']=='global'else None)
        require(r['inputHash']==document_hash(inp)and r['identity']==document_hash({'input':inp,'model':meta['model'],'code':p['reviewRuntimeHash']}),'chunk: altered task input/runtime')
        if r['assignment']['kind']=='medical':
            require([v['question_id']for v in r['output']['reviews']]==r['assignment']['ids'],'chunk: incomplete medical partition')
            medical+=r['output']['reviews']
        else:outputs[r['assignment']['name']]=r['output']
    raw=merge(ctx,outputs)
    require(raw==value['sourceAudit']['assessment']['assessment'],'chunk: changed merged assessment')
    require(medical==value['medical']['reviews'],'chunk: changed medical verdicts')
    require(stages['source-2']['chunkedProofHash']==stages['medical-2']['chunkedProofHash']==row['proofHash'],'chunk: missing stage proof binding')
