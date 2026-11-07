"""A single model-authored legacy plan row; clinical and original review data stay exact."""
import copy
import jsonschema
from . import generation_v2 as c,chunked
from .validate import document_hash
from studyez_contracts.bank.schema import BANK
from studyez_contracts.bank.validate import validate_bank
from studyez_contracts.learning_links.validate import require

POLICY='one-plan-final-repair/1'

def missing_plan(bank):
    planned={r['concept_id']for r in bank['retrieval_plan']}
    missing=[r['concept_id']for r in bank['concepts']if r['concept_id']not in planned]
    require(len(missing)==1,'plan repair: exactly one missing plan required')
    cid=missing[0];directions=list(dict.fromkeys(q['retrieval_direction']for q in bank['questions']if q['concept_id']==cid))
    require(directions,'plan repair: existing authored questions required')
    check=validate_bank(bank,[s['source_id']for s in bank['source_summary']],check_quality=False)
    require(check['errors']==[cid+': 회상 계획 누락'],'plan repair: unrelated structural errors')
    return cid,directions

def schema(bank):
    cid,directions=missing_plan(bank);s=copy.deepcopy(BANK['properties']['retrieval_plan']['items'])
    s['properties']['concept_id']['enum']=[cid]
    s['properties']['directions'].update(minItems=len(directions),maxItems=len(directions),uniqueItems=True)
    s['properties']['directions']['items']['enum']=directions
    s['properties']['repetition_budget'].update(minimum=1,maximum=100)
    s['properties']['target_mastery'].update(minimum=.1,maximum=1)
    return s

def apply(bank,row):
    jsonschema.validate(row,schema(bank));cid,directions=missing_plan(bank)
    require(row['directions']==directions,'plan repair: authored directions/order changed')
    result=copy.deepcopy(bank);result['retrieval_plan'].append(copy.deepcopy(row))
    require(validate_bank(result,[s['source_id']for s in result['source_summary']],check_quality=False)['pass'],'plan repair: not structurally valid')
    return result

def prior_view(value):
    """Restore the exact round-2 view solely for verifying its original proof."""
    p=value['manifest']['planRepair']['proof'];old=value['manifest']['chunkedReview']['proof']
    result=copy.deepcopy(value);bank=result['document']['bank_snapshot']
    bank['retrieval_plan']=copy.deepcopy(old['context']['bank']['retrieval_plan'])
    ctx=copy.deepcopy(old['context']);ctx['bank']=bank
    outputs={r['assignment']['name']:r['output']for r in old['tasks']if r['assignment']['kind']!='medical'}
    result['sourceAudit']=c.compile_assessment(ctx['brief'],bank,c.envelope(ctx['brief'],bank,chunked.merge(ctx,outputs)))
    result['medical']=copy.deepcopy(p['previousMedical'])
    result['manifest'].pop('planRepair');result['manifest']['repairRounds']=2
    result['manifest']['stages']=[s for s in result['manifest']['stages']if s['name']not in('repair-3','source-3','medical-3')]
    return result

def validate(value):
    meta=value['manifest'];row=meta['planRepair'];p=row['proof']
    require(row['proofHash']==document_hash(p)and p['policy']==POLICY,'plan repair: altered proof')
    receipt=p['repairReceipt']
    require(receipt['status']=='completed'and receipt['outputHash']==p['rowOutputHash']and
        all(type(receipt[k])is str and len(receipt[k])==64 for k in('providerHash','inputHash','schemaHash','outputSha256')),
        'plan repair: missing completed actual row receipt')
    require(meta['repairRounds']==3 and p['consumed']=={'before':2,'after':3,'maximum':3},'plan repair: budget reset')
    old=prior_view(value);oldbank=old['document']['bank_snapshot'];bank=value['document']['bank_snapshot']
    require(apply(oldbank,p['planRow'])==bank,'plan repair: changed clinical content or other metadata')
    require(p['packetHash']==meta['inputHash']and p['oldBankHash']==document_hash(oldbank),'plan repair: changed origin')
    require(p['previousMedical']==value['medical']and c.medical_input(oldbank,meta['clinicalConflicts'])==c.medical_input(bank,meta['clinicalConflicts']),
        'plan repair: changed blind medical input/verdicts')
    stages={r['name']:r for r in meta['stages']};oldstages={r['name']:r for r in old['manifest']['stages']}
    require(stages['medical-2']['outputHash']==document_hash(p['previousMedical'])and stages['medical-3']['reusedFrom']=='medical-2',
        'plan repair: missing actual medical reuse')
    require(p['medicalClinicalHash']==document_hash(c.medical_input(bank,meta['clinicalConflicts'])),'plan repair: different clinical projection')
    oldctx=copy.deepcopy(meta['chunkedReview']['proof']['context']);oldctx['bank']=oldbank
    ctx=copy.deepcopy(oldctx);ctx['bank']=bank
    parts={r['assignment']['name']:r['output']for r in meta['chunkedReview']['proof']['tasks']if r['assignment']['kind']not in('global','medical')}
    global_row=p['globalReview'];task=chunked.plan(ctx)[-1];inp=chunked.task_input(ctx,task,parts)
    require(global_row['status']=='completed'and global_row['assignment']==task and global_row['model']==meta['model']
        and global_row['inputHash']==document_hash(inp)and global_row['outputHash']==document_hash(global_row['output'])
        and global_row['identity']==document_hash({'input':inp,'model':meta['model'],'code':p['globalRuntimeHash']}),
        'plan repair: missing actual new global review')
    raw=chunked.merge(ctx,{**parts,'global':global_row['output']})
    require(raw==value['sourceAudit']['assessment']['assessment']and stages['source-3']['inputHash']==document_hash(ctx),
        'plan repair: altered final source judgments/input')
    require(all(stages[n]['planRepairProofHash']==row['proofHash']for n in('repair-3','source-3','medical-3')),'plan repair: missing stage bindings')
    require(stages['repair-3']['inputHash']==p['repairInputHash']and p['rowOutputHash']==document_hash(p['planRow']),
        'plan repair: missing actual row binding')
    return old
