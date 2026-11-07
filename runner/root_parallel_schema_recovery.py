"""Recheck a completed opted-in image-ID file rejected by the old host schema.

Never changes clinical content, replays models, accepts interrupted calls or resets budget.
"""
import copy
from pathlib import Path
import jsonschema
from quizbank import connection_generate as g,connection_visuals as visual
from quizbank.connection_parallel import validate_completed,preserved_bank
from studyez_contracts.roots import generation_v2 as c,document_hash
from studyez_contracts.roots.parallel import validate_schema_recovery
from . import root_native_json as n


def validate_recovery(out,row):
    out=Path(out);p=row['proof'];a=out/'.parallel-schema-recovery'
    n.require(row['proofHash']==document_hash(p)and n.read(out/'parallel.schema-recovery.json')==row,'Changed parallel schema recovery')
    capture=n.read(a/'capture.json')
    n.require(all(p[k]==v for k,v in capture.items()),'Changed original schema-failure capture')
    n.require(all(n.sha(a/'runtime-before'/name)==digest for name,digest in p['oldCode'].items()),'Changed original runtime archive')
    n.require(all(n.sha(a/name)==digest for name,digest in p['originalFileHashes'].items()),'Changed original rejection archive')
    for name in ('generate.raw.json','generate.usage.json','generate.input.json','normalize.json'):
        n.require(n.sha(out/name)==p['originalFileHashes'][name],'Recovery changed completed output/input/usage')
    ledger=n.read(out/'ledger.json')
    validate_schema_recovery({'parallelSchemaRecovery':row,'parallelAuthoring':p['parallelProof'],
        'inputHash':p['packetHash'],'runtimeHash':ledger['identity']},{k:{'name':k,**v}for k,v in ledger['stages'].items()})
    n.require(n.sha(a/'recovery.py')==p['toolSha256'],'Changed recovery tool archive')


def recover(out):
    out=Path(out)
    with g.exclusive({'connection-generation':str(out.resolve())}):
        n.require_unblocked(out);packet=n.read(out/'packet.json');old=n.read(out/'ledger.json')
        a=out/'.parallel-schema-recovery';capture=n.read(a/'capture.json')
        n.require(packet.get('parallelAuthoring')is True and packet.get('authoring')=='cli'
            and old==capture['priorLedger']and not(out/'parallel.schema-recovery.json').exists()
            and not(out/'generate.json').exists()and not(out/'result.json').exists(),'Only the captured original host failure')
        raw=n.read(out/'generate.raw.json');ctx=n.read(out/'generate.input.json');usage=n.read(out/'generate.usage.json')
        jsonschema.validate(raw,c.PARALLEL_AUTHOR)
        n.require(not jsonschema.Draft202012Validator(c.AUTHOR).is_valid(raw)
            and any(s.get('image_id')for s in raw['visual_stimuli']),'No opted-in image-ID schema mismatch')
        for spec in raw['visual_stimuli']:
            without_id={k:v for k,v in spec.items()if k!='image_id'};jsonschema.validate(without_id,c.CROP)
        for name in ('normalize','generate'):
            entry=old['stages'][name]
            n.require(document_hash(n.read(out/(name+'.input.json')))==entry['inputHash']
                and document_hash(n.read(out/(name+'.raw.json')))==entry['rawOutputHash']
                and document_hash(n.read(out/(name+'.usage.json')))==entry['usageHash'],'Changed original call evidence')
            n.validate_stage(out,{'name':name,**entry},model=g.codex.model_name())
        n.check_file('generate',out/'.native/generate/work')
        n.require('fileReceipt'in usage and usage['duration_ms']>0,'Missing actual completed Native usage')
        n.require(raw['brief']==n.read(out/'normalize.json'),'Source-only brief changed')
        preserved_bank(ctx['independentBank']['bank'],raw['bank'])
        validate_completed(out,capture['parallelProof'])
        accepted=copy.deepcopy(raw);accepted['bank']=visual.render(raw['bank'],raw['visual_stimuli'],packet,out/'material')
        proof={**capture,'currentRuntimeHash':g.identity(packet,None),'reason':'Completed Native parallel image-ID output was accepted by its original opted-in schema but the host used legacy AUTHOR. Recheck the identical bytes under the already-dispatched schema.',
            'modelReplay':False,'acceptedHash':document_hash(accepted),'briefHash':document_hash(raw['brief']),
            'toolSha256':n.sha(__file__)}
        row={'proof':proof,'proofHash':document_hash(proof)};updated=copy.deepcopy(old)
        updated.update(identity=proof['currentRuntimeHash'],parallelSchemaRecovery=row)
        updated['stages']['generate'].update(status='completed',outputHash=proof['acceptedHash'],briefHash=proof['briefHash'])
        validate_schema_recovery({'parallelSchemaRecovery':row,'parallelAuthoring':proof['parallelProof'],
            'inputHash':packet['inputHash'],'runtimeHash':updated['identity']},{k:{'name':k,**v}for k,v in updated['stages'].items()})
        (a/'recovery.py').write_bytes(Path(__file__).read_bytes())
        g.write(out/'parallel.schema-recovery.json',row);g.write(out/'generate.json',accepted);g.write(out/'ledger.json',updated)
        validate_recovery(out,row)
        return {'modelCalls':0,'repairRounds':updated['repairRounds'],'originalRawUnchanged':True,'proofHash':row['proofHash']}


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(recover(a.out)))
