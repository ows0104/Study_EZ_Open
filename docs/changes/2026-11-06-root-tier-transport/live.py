"""Verify actual recovery evidence and final reviews, without any model calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from runner.root_native_json import validate_all
from studyez_contracts.bank.validate import validate_bank
from studyez_contracts.roots import generation_v2 as contract
from studyez_contracts.roots.automation import validate_result
from studyez_contracts.roots import document_hash
from quizbank.connection_generate import identity
from studyez_contracts.roots.generation_v2 import tier_projection

OUT=ROOT.parents[1]/'runs/_e2e/26110507'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify():
    frozen=read(OUT/'recovery-evidence/inputs.json');results=[]
    for row in frozen['experiments']:
        folder=OUT/row['slug'];packet=read(folder/'packet.json')
        assert sha(OUT/'recovery-evidence'/(row['slug']+'-prior-ledger.json'))==row['ledgerArchiveSha256']
        for name,digest in row['files'].items():assert sha(folder/name)==digest,(row['slug'],name)
        ledger=read(folder/'ledger.json')
        result=read(folder/'result.json')if (folder/'result.json').exists()else None
        if result:
            validate_result(result,packet);manifest=result['manifest']
        else:
            assert row['slug']=='endocarditis'
            manifest={'stages':[{'name':k,**v}for k,v in ledger['stages'].items()],
                'model':'gpt-6.1-sol','inputHash':packet['inputHash'],'runtimeHash':ledger['identity'],
                'initialBrief':read(folder/'normalize.json'),'repairRounds':ledger['repairRounds'],
                **{k:ledger.get(k,[])for k in ('authoringRecoveries','formatRecoveries','runtimeRevalidations')}}
            indexed={s['name']:s for s in manifest['stages']}
            contract.validate_runtime_revalidations(manifest,indexed)
            contract.validate_format_recoveries(manifest,indexed)
            contract.validate_authoring_recoveries(manifest,indexed)
        validate_all(folder,{'manifest':manifest})
        assert manifest['repairRounds']==ledger['repairRounds']==3
        recovery=manifest['authoringRecoveries'][0]['proof']
        assert recovery['priorLedgerHash']==row['priorLedgerHash']
        assert recovery['priorLedger']['repairRounds']==1
        final_round=2 if row['slug']=='endocarditis'else 3
        for name in ('source-'+str(final_round),'medical-'+str(final_round)):
            assert ledger['stages'][name]['status']=='completed',name
        if row['slug']=='endocarditis':
            assert manifest['runtimeHash']==identity(packet,None)
            proof=read(folder/'tier.recovery.json')['proof']
            raw=proof['rawAuthoring'];projected,projection=tier_projection(raw)
            assert projection['changes']==[{'question_id':'Q010','from':'Must-Know','to':'Essential'}]
            assert projection==proof['projection'] and projected==read(folder/'repair-2.raw.json')
            assert proof['modelReplay']is False
            revalidation=read(folder/'runtime.revalidation.json')['proof']
            assert revalidation['modelReplay']is False and revalidation['priorLedger']['repairRounds']==3
            assert ledger['stages']['generate']['status']=='failed'
        bank=result['document']['bank_snapshot']if result else read(folder/'repair-2.json')['bank']
        hard_validation=validate_bank(bank,[s['id']for s in packet['sources']],check_quality=False)
        if not result:
            assert hard_validation['pass']is False
            assert hard_validation['errors']==['concepts: ID/값 중복','retrieval_plan: ID/값 중복']
        results.append({'slug':row['slug'],'preservedOriginalFiles':len(row['files']),
            'questions':len(bank['questions']),'preparedTasks':len(result['document']['tasks'])if result else 0,
            'status':'ready'if result else 'held-invalid-bank','repairRounds':3,
            'finalSourceAndMedicalReviewsCompleted':True,'hardValidationErrors':hard_validation['errors'],
            'resultSha256':sha(folder/'result.json')if result else None})
    report={'results':results,'recoveryModelReplay':False,'productionChanged':False,
        'originalFailureEvidencePreserved':True,'sameRepairBudget':True}
    (OUT/'recovery-evidence/final-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':verify()
