import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from runner import root_chunked_tasks as tasks,root_native_json as n
from studyez_contracts.roots import chunked as c,document_hash

def context():
    a=f.author();return {'title':'Synthetic geometry','bank':a['bank'],'brief':a['brief'],'clinical_conflicts':[]}

def fake(inp,work,schema,medical):
    t=inp['assignment'];ctx=context();a=f.assessment(ctx['brief'],ctx['bank'])
    a['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic design'}for q in ctx['bank']['questions']]
    if medical:value={'summary':'Synthetic medical','reviews':f.old.checks(ctx['bank'])['reviews'],'pool_checks':[]}
    else:value={k:a[k]for k in schema['properties']}
    if medical:text=json.dumps(value)
    else:
        (work/'result.json').write_text(json.dumps(value),encoding='utf-8')
        text=json.dumps({'path':'result.json','sha256':n.sha(work/'result.json')})
    return {'text':text,'turns':1,'session_id':'synthetic-only','usage':{},'duration_ms':1,'models':{},'cost_usd':None}

def test_all_partitions_merge_and_cached_receipts_reused_without_calls(tmp_path):
    material=tmp_path/'material';material.mkdir();(material/'S1.md').write_text('Synthetic geometry')
    source,medical,rows=tasks.run(tmp_path/'tasks',context(),material,'synthetic',invoke=fake)
    assert len(source['question_reviews'])==2 and len(medical['reviews'])==2 and len(rows)==5
    again=tasks.run(tmp_path/'tasks',context(),material,'synthetic',invoke=lambda *a:pytest.fail('No replay'))
    assert again[0]==source and again[2]==rows
    (tmp_path/'tasks/questions-1/work/material/S1.md').write_text('changed')
    with pytest.raises(ValueError,match='protected'):tasks.run(tmp_path/'tasks',context(),material,'synthetic',invoke=lambda *a:pytest.fail('No replay'))

def test_failed_partition_does_not_replay(tmp_path):
    material=tmp_path/'material';material.mkdir();(material/'S1.md').write_text('Synthetic')
    task=c.plan(context())[0]
    with pytest.raises(RuntimeError):tasks.run_one(tmp_path/'tasks',context(),task,material,'synthetic',invoke=lambda *a:(_ for _ in()).throw(RuntimeError('interrupted')))
    with pytest.raises(ValueError,match='no automatic replay'):tasks.run_one(tmp_path/'tasks',context(),task,material,'synthetic',invoke=lambda *a:pytest.fail('No replay'))

@pytest.mark.parametrize('field,key',[('question_reviews','question_id'),('design_checks','question_id'),('relation_checks','relation_id'),('target_checks','target_id'),('direction_checks','direction_id')])
def test_duplicate_or_foreign_assigned_id_rejected(field,key):
    ctx=context();kind='questions'if field in('question_reviews','design_checks')else'relations'if field=='relation_checks'else'targets'
    task=next(t for t in c.plan(ctx)if t['kind']==kind);raw=f.assessment(ctx['brief'],ctx['bank'])
    raw['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic'}for q in ctx['bank']['questions']]
    value={k:raw[k]for k in c.schema(ctx,task)['properties']};value[field][0][key]='FOREIGN'
    with pytest.raises(Exception):c.check(ctx,task,value)

def test_missing_global_and_invalid_component_cannot_be_accepted():
    ctx=context();task=c.plan(ctx)[0];a=f.assessment(ctx['brief'],ctx['bank']);a['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic'}for q in ctx['bank']['questions']]
    value={k:a[k]for k in c.schema(ctx,task)['properties']};value['direction_evidence'][0]['components']=[]
    with pytest.raises(Exception):c.check(ctx,task,value)
    with pytest.raises(ValueError,match='incomplete'):c.merge(ctx,{})

def test_global_input_includes_every_source_partition_and_blind_input_excludes_history():
    ctx=context();ctx['privateHistory']='DO_NOT_FORWARD';parts={'questions-1':{'verdict':'doubt'}}
    assert c.task_input(ctx,c.plan(ctx)[-1],parts)['completedSourceParts']==parts
    med=next(t for t in c.plan(ctx)if t['kind']=='medical');inp=c.task_input(ctx,med)
    assert 'DO_NOT_FORWARD'not in json.dumps(inp)and 'brief'not in inp and 'sourceAudit'not in inp

def frozen_result(tmp_path):
    ctx=context();material=tmp_path/'m';material.mkdir();(material/'S1.md').write_text('Synthetic')
    raw,medical,rows=tasks.run(tmp_path/'tasks',ctx,material,'synthetic',invoke=fake)
    author={'brief':ctx['brief'],'bank':ctx['bank'],'visual_stimuli':[],'clinical_conflicts':[],'map_change_reason':'No map change'}
    old={'identity':'0'*64,'repairRounds':2,'stages':{'repair-2':{'status':'completed','outputHash':document_hash(author)},'source-2':{'status':'failed','inputHash':document_hash(ctx)}}}
    meta={'runtimeHash':'0'*64,'repairRounds':2,'model':'synthetic','inputHash':'1'*64,'clinicalConflicts':[],
        'visualStimuli':[],'mapChangeReason':'No map change','stages':[{'name':'repair-2',**old['stages']['repair-2']},
        {'name':'source-2','status':'completed','inputHash':document_hash(ctx)},{'name':'medical-2','status':'completed'}]}
    proof={'policy':c.POLICY,'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':'1'*64,'context':c.clean(ctx),
        'failure':{'classification':{'kind':'model_timeout','automaticRetry':False}},'reviewRuntimeHash':tasks.code_hash(),'tasks':rows}
    row={'proof':proof,'proofHash':document_hash(proof)};meta['chunkedReview']=row
    for stage in meta['stages'][1:]:stage['chunkedProofHash']=row['proofHash']
    return {'manifest':meta,'brief':ctx['brief'],'document':{'bank_snapshot':ctx['bank']},'sourceAudit':{'assessment':{'assessment':raw}},'medical':medical}

@pytest.mark.parametrize('mutation',['budget','bank','failed_history','omitted_task','medical_verdict','global_verdict'])
def test_continuation_binds_frozen_candidate_budget_history_and_all_actual_reviews(tmp_path,mutation):
    value=frozen_result(tmp_path);c.validate_continuation(value)
    if mutation=='budget':value['manifest']['repairRounds']=0
    elif mutation=='bank':value['document']['bank_snapshot']['questions'][0]['answer']='changed'
    elif mutation=='failed_history':value['manifest']['chunkedReview']['proof']['priorLedger']['stages']['source-2']['status']='completed'
    elif mutation=='omitted_task':value['manifest']['chunkedReview']['proof']['tasks'].pop()
    elif mutation=='medical_verdict':value['medical']['reviews'][0]['verdict']='wrong'
    else:value['sourceAudit']['assessment']['assessment']['clinical_context_status']='unknown'
    with pytest.raises(ValueError):c.validate_continuation(value)
