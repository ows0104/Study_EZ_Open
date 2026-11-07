import copy
import pytest
from studyez_contracts.roots.parallel import validate_schema_recovery
from studyez_contracts.roots import document_hash


def fixture():
    code={'original.py':'a'*64};packet='b'*64;model='synthetic'
    old={'identity':document_hash({'input':packet,'model':model,'code':code}),'repairRounds':0,
        'stages':{'normalize':{'status':'completed','outputHash':'c'*64},
            'generate':{'status':'failed','inputHash':'d'*64,'rawOutputHash':'e'*64,'usageHash':'f'*64}}}
    parallel={'policy':'parallel-source-authoring/1','identity':'1'*64}
    proof={'priorLedger':old,'priorLedgerHash':document_hash(old),'oldCode':code,'packetHash':packet,
        'model':model,'currentRuntimeHash':'2'*64,'modelReplay':False,'reason':'Known host schema mismatch',
        'parallelProof':parallel,'acceptedHash':'3'*64,'briefHash':'4'*64}
    row={'proof':proof,'proofHash':document_hash(proof)}
    meta={'parallelSchemaRecovery':row,'parallelAuthoring':parallel,'inputHash':packet,'runtimeHash':'2'*64}
    stages={'normalize':{'name':'normalize',**old['stages']['normalize']},
        'generate':{'name':'generate',**old['stages']['generate'],'status':'completed','outputHash':'3'*64,'briefHash':'4'*64}}
    return meta,stages


def test_one_completed_host_recheck_preserves_raw_usage_and_budget():
    meta,stages=fixture();validate_schema_recovery(meta,stages)


@pytest.mark.parametrize('problem',['budget','interrupted','replay','wrong_packet','changed_normalization','changed_raw','different_outputs','repeat'])
def test_recovery_rejects_semantic_scope_changes_even_with_recomputed_hashes(problem):
    meta,stages=fixture();row=meta['parallelSchemaRecovery'];p=row['proof']
    if problem=='budget':p['priorLedger']['repairRounds']=1
    elif problem=='interrupted':p['priorLedger']['stages']['generate']['status']='started'
    elif problem=='replay':p['modelReplay']=True
    elif problem=='wrong_packet':meta['inputHash']='0'*64
    elif problem=='changed_normalization':stages['normalize']['outputHash']='0'*64
    elif problem=='changed_raw':stages['generate']['rawOutputHash']='0'*64
    elif problem=='different_outputs':meta['parallelAuthoring']={'identity':'0'*64}
    elif problem=='repeat':p['priorLedger']['parallelSchemaRecovery']={'prior':'recovery'}
    p['priorLedgerHash']=document_hash(p['priorLedger']);row['proofHash']=document_hash(p)
    with pytest.raises(ValueError):validate_schema_recovery(meta,stages)
