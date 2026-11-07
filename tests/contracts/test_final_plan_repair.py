import copy
import pytest
import generation_v2_fixture as f,chunked_fixture as cf
from studyez_contracts.roots import generation_v2 as c,chunked,plan_repair as p,document_hash

def completed(monkeypatch):
    bank=f.old.bank();plan=bank['retrieval_plan'].pop(0);monkeypatch.setattr(f.old,'bank',lambda:copy.deepcopy(bank))
    packet=f.packet();value=cf.result(packet,validate=False);old=copy.deepcopy(value)
    assert value['validation']['errors']==[plan['concept_id']+': 회상 계획 누락']
    bank=p.apply(value['document']['bank_snapshot'],plan);b=value['brief'];meta=value['manifest'];ctx=copy.deepcopy(meta['chunkedReview']['proof']['context']);ctx['bank']=bank
    parts={r['assignment']['name']:r['output']for r in meta['chunkedReview']['proof']['tasks']if r['assignment']['kind']not in('medical','global')}
    task=chunked.plan(ctx)[-1];output=meta['chunkedReview']['proof']['tasks'][-1]['output'];inp=chunked.task_input(ctx,task,parts);runtime='2'*64
    globalrow={'status':'completed','assignment':task,'output':output,'outputHash':document_hash(output),'inputHash':document_hash(inp),
        'model':meta['model'],'identity':document_hash({'input':inp,'model':meta['model'],'code':runtime})}
    raw=chunked.merge(ctx,{**parts,'global':output});audit=c.compile_assessment(b,bank,c.envelope(b,bank,raw))
    value['sourceAudit']=audit;value['document']=c.make_document(b,bank,audit,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate'],medical=value['medical'])
    from studyez_contracts.bank.validate import validate_bank
    value['validation']=validate_bank(bank,[s['id']for s in packet['sources']])
    author={'bank':bank,'brief':b,'visual_stimuli':[],'clinical_conflicts':[],'map_change_reason':meta['mapChangeReason']}
    medicalctx={'title':packet['title'],'bank':bank,'clinicalInput':c.medical_input(bank,[]),'_pipeline_version':c.POLICY}
    receipt={'status':'completed','outputHash':document_hash(plan),**{k:'3'*64 for k in('providerHash','inputHash','schemaHash','outputSha256')}}
    proof={'policy':p.POLICY,'consumed':{'before':2,'after':3,'maximum':3},'packetHash':packet['inputHash'],
        'oldBankHash':document_hash(old['document']['bank_snapshot']),'planRow':plan,'rowOutputHash':document_hash(plan),
        'previousMedical':value['medical'],'medicalClinicalHash':document_hash(medicalctx['clinicalInput']),
        'globalReview':globalrow,'globalRuntimeHash':runtime,'repairInputHash':'0'*64,'repairReceipt':receipt}
    row={'proof':proof,'proofHash':document_hash(proof)}
    for name,out,rawout,inhash in [('repair-3',author,author,'0'*64),('source-3',audit,audit['assessment'],document_hash(ctx)),
            ('medical-3',value['medical'],value['medical'],document_hash(medicalctx))]:
        meta['stages'].append({'name':name,'status':'completed','inputHash':inhash,'outputHash':document_hash(out),
            'rawOutputHash':document_hash(rawout),'planRepairProofHash':row['proofHash']})
    meta['stages'][-3]['briefHash']=document_hash(b);meta['stages'][-2]['clinicalContextHash']=document_hash([]);meta['stages'][-1]['reusedFrom']='medical-2'
    meta.update(planRepair=row,repairRounds=3,bankHash=document_hash(bank),sourceAssessment=audit['assessment'],medicalInputHash=document_hash(medicalctx))
    meta['briefRevisions'].append({'stage':'repair-3','brief':b,'reason':meta['mapChangeReason']})
    c.validate_result(value,packet)
    return value,packet,old

def test_full_standard_result_accepts_only_one_missing_plan_and_preserves_completed_reviews(monkeypatch):
    value,packet,old=completed(monkeypatch)
    assert value['document']['bank_snapshot']['questions']==old['document']['bank_snapshot']['questions']
    assert value['medical']==old['medical']and value['manifest']['repairRounds']==3
    assert value['manifest']['chunkedReview']==old['manifest']['chunkedReview']
    assert p.prior_view(value)['document']['bank_snapshot']==old['document']['bank_snapshot']

@pytest.mark.parametrize('mutation',['question','old_plan','budget','medical','global','missing_receipt','clinical_conflict'])
def test_no_scope_or_review_upgrade_bypass(monkeypatch,mutation):
    value,packet,old=completed(monkeypatch);meta=value['manifest'];proof=meta['planRepair']['proof']
    if mutation=='question':value['document']['bank_snapshot']['questions'][0]['answer']='changed'
    elif mutation=='old_plan':value['document']['bank_snapshot']['retrieval_plan'][0]['target_mastery']=.1
    elif mutation=='budget':meta['repairRounds']=2
    elif mutation=='medical':value['medical']['reviews'][0]['verdict']='wrong'
    elif mutation=='global':proof['globalReview']['inputHash']='0'*64
    elif mutation=='missing_receipt':proof['repairReceipt']['status']='failed'
    else:meta['clinicalConflicts']=[{'conflict_id':'new','facts':'changed'}]
    meta['planRepair']['proofHash']=document_hash(proof)
    with pytest.raises(Exception):c.validate_result(value,packet)
