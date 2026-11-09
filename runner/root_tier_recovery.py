"""Explicit recovery of one completed canonical tier-alias transport rejection.

No model calls, content editing, tier re-evaluation or correction-budget reset.
"""
import argparse
import copy
import json
import re
from pathlib import Path
import jsonschema
from quizbank import connection_generate as g,connection_visuals as visual
from studyez_contracts.roots import generation_v2 as c,document_hash
from studyez_contracts.roots.automation import packet_hash
from . import root_native_json as n

def recover(packet,out,*,stage,expected_identity,reason,model=None):
    with g.exclusive({'connection-generation':str(Path(out).resolve())}):
        return _recover(packet,out,stage=stage,expected_identity=expected_identity,reason=reason,model=model)


def _recover(packet,out,*,stage,expected_identity,reason,model=None):
    out=Path(out);n.require_unblocked(out);old=n.read(out/'ledger.json');from studyez_contracts.roots.generation_v2 import require_legacy_ledger;require_legacy_ledger(old)
    n.require(packet_hash(packet)==packet['inputHash']and packet.get('sourceAssessmentFormat')==c.VERSION
        and old['identity']==expected_identity and old.get('pipelineVersion')==c.POLICY,'Different tier recovery input/runtime')
    n.require(re.fullmatch(r'generate|repair-[1-3]',stage)and stage in old['stages']
        and old['stages'][stage]['status']=='failed'and not old.get('formatRecoveries')
        and not(out/'tier.recovery.json').exists()and not(out/'.tier-recovery').exists()
        and not(out/'result.json').exists(),'Only one failed authoring transport may be recovered')
    n.require(reason.strip()and type(old['repairRounds'])is int and 0<=old['repairRounds']<=3,'Missing reason or invalid budget')
    historical_failed={'generate'}if old.get('authoringRecoveries')and old['authoringRecoveries'][0]['proof']['mode']=='brief-repair'else set()
    n.require(all(s['status']in('completed','failed','blocked')for s in old['stages'].values())
        and {k for k,s in old['stages'].items()if s['status']=='failed'}=={stage}|historical_failed,
        'Other interrupted or failed stages are not eligible')
    for source in packet['sources']:
        path=Path(source['localPath'])
        n.require(path.stat().st_size==source['sizeBytes']and n.sha(path)==source['sha256'],'Original PDF/source changed')
    n.require(not any((out/(stage+s)).exists()for s in('.json','.raw.json','.usage.json')),'Ambiguous accepted authoring artifacts')
    seat=out/'.native'/stage;work=seat/'work';journal=n.read(seat/'journal.json')
    n.require(journal['status']=='failed'and not(seat/'receipt.json').exists(),'Original Native call is not a rejected receipt')
    prior=journal['proof'];ctx=n.read(out/(stage+'.input.json'));schema=n.schema_for(stage,ctx)
    n.require(prior['inputHash']==old['stages'][stage]['inputHash']==document_hash(ctx)
        and prior['cleanInputHash']==document_hash(n.clean(ctx))and prior['schemaHash']==document_hash(schema)
        and prior['model']==g.codex.model_name(model),'Changed Native input/schema/model')
    n.require(n.read(work/'input.json')==n.clean(ctx)and n.read(work/'acceptance.schema.json')==schema
        and n.sha(seat/'adapter.py')==prior['adapterSha256']
        and all(n.sha(work/k)==v for k,v in prior['protectedFiles'].items()),'Changed original Native archive')
    n.require(n.inventory(work/'material')==prior['materialHashes']
        and all(n.sha(out/'material'/k)==v for k,v in prior['materialHashes'].items()),'Changed original material')
    provider=n.read(seat/'provider.json');failure=n.read(seat/'failure.json')
    n.require(type(provider.get('turns'))is int and provider['turns']>0 and provider.get('session_id')
        and failure['completedTurns']==provider['turns']and failure['sessionId']==provider['session_id']
        and failure['classification']['kind']=='execution_failed'and failure['partialUsageUnknown']is False,
        'A completed, nonrestricted provider call is required')
    n.require(provider['duration_ms']>0 and provider['models']
        and all(type(provider['usage'].get(k))is int and provider['usage'][k]>0 for k in('input_tokens','output_tokens')),
        'Actual completed provider usage is required')
    receipt=n.loads(provider['text']);body,value=n.artifact(work,receipt)
    n.require((seat/'output.json').read_bytes()==body,'Provider file archive changed')
    raw=g.decode_optional_fields(value,schema);decoded,projection=c.tier_projection(raw)
    n.require(projection is not None,'No canonical tier alias to recover')
    n.require(not jsonschema.Draft202012Validator(schema).is_valid(raw),'Original authoring was not a schema rejection')
    jsonschema.validate(decoded,schema)
    n.check_file(stage,work)
    accepted=copy.deepcopy(decoded)
    accepted['bank']=visual.render(accepted['bank'],decoded['visual_stimuli'],packet,out/'material')
    for name,entry in old['stages'].items():
        if name==stage or entry['status']=='blocked':continue
        n.require(document_hash(n.read(out/(name+'.input.json')))==entry['inputHash'],'Changed reused input')
        n.require(document_hash(n.read(out/(name+'.raw.json')))==entry['rawOutputHash']
            and document_hash(n.read(out/(name+'.usage.json')))==entry['usageHash'],'Changed reused call archive')
        if entry['status']=='completed':n.require(document_hash(n.read(out/(name+'.json')))==entry['outputHash'],'Changed reused output')
        n.validate_stage(out,{'name':name,**entry},model=g.codex.model_name(model))
    current=g.identity(packet,model)
    proof={'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
        'currentRuntimeHash':current,'reason':reason,'stage':stage,'rawAuthoring':raw,'projection':projection,
        'nativeJournalSha256':n.sha(seat/'journal.json'),'recoveryToolSha256':n.sha(__file__),'modelReplay':False}
    row={'proof':proof,'proofHash':document_hash(proof)}
    native_proof={**prior,'nativeSessionId':provider['session_id'],'providerHash':document_hash(provider),
        'outputSha256':receipt['sha256'],'rawHash':document_hash(decoded),'tierProjection':projection}
    native_row={'proof':native_proof,'proofHash':document_hash(native_proof)}
    info={k:provider[k]for k in('usage','cost_usd','duration_ms','models')};info['fileReceipt']=native_row
    updated=copy.deepcopy(old);updated.update(identity=current,formatRecoveries=[row])
    entry=updated['stages'][stage]
    entry.update(status='completed',rawOutputHash=document_hash(decoded),usageHash=document_hash(info),
                 outputHash=document_hash(accepted),briefHash=document_hash(decoded['brief']))
    meta={'formatRecoveries':[row],'authoringRecoveries':updated.get('authoringRecoveries',[]),
        'initialBrief':n.read(out/'normalize.json'),'inputHash':packet['inputHash'],
        'runtimeHash':current,'repairRounds':old['repairRounds']}
    stages={k:{'name':k,**v}for k,v in updated['stages'].items()}
    c.validate_format_recoveries(meta,stages);c.validate_authoring_recoveries(meta,stages)
    archive=out/'.tier-recovery';archive.mkdir()
    (archive/'journal-before.json').write_bytes((seat/'journal.json').read_bytes())
    (archive/'ledger-before.json').write_bytes((out/'ledger.json').read_bytes())
    (archive/'recovery.py').write_bytes(Path(__file__).read_bytes())
    g.write(out/'tier.recovery.json',row)
    g.write(seat/'receipt.json',native_row);g.write(seat/'journal.json',{'status':'completed','proofHash':native_row['proofHash']})
    g.write(out/(stage+'.raw.json'),decoded);g.write(out/(stage+'.usage.json'),info)
    g.write(out/(stage+'.json'),accepted);g.write(out/'ledger.json',updated)
    n.validate_stage(out,{'name':stage,**entry},model=g.codex.model_name(model));validate_recovery(out,row,model=g.codex.model_name(model))
    return {'stage':stage,'aliases':projection['changes'],'repairRounds':old['repairRounds'],'modelCalls':0,'proofHash':row['proofHash']}

def validate_recovery(out,row,*,model):
    out=Path(out);p=row['proof'];stage=p['stage'];archive=out/'.tier-recovery'
    n.require(row['proofHash']==document_hash(p)and n.read(out/'tier.recovery.json')==row,'Changed tier recovery proof')
    n.require(n.sha(archive/'journal-before.json')==p['nativeJournalSha256']
        and n.sha(archive/'recovery.py')==p['recoveryToolSha256']
        and n.read(archive/'ledger-before.json')==p['priorLedger'],'Changed original rejection archive')
    journal=n.read(archive/'journal-before.json');n.require(journal['status']=='failed','Original Native rejection missing')
    seat=out/'.native'/stage;ctx=n.read(out/(stage+'.input.json'))
    raw=g.decode_optional_fields(n.read_model(seat/'output.json'),n.schema_for(stage,ctx))
    n.require(raw==p['rawAuthoring'],'Changed original tier spelling')
    decoded,projection=c.tier_projection(raw)
    n.require(projection==p['projection']and n.read(out/(stage+'.raw.json'))==decoded,'Changed projected authoring')
    n.validate_stage(out,{'name':stage,**n.read(out/'ledger.json')['stages'][stage]},model=model)


def revalidate_runtime(packet,out,*,expected_identity,reason,model=None):
    """Recheck unchanged completed caches after the deterministic-note fix."""
    out=Path(out)
    with g.exclusive({'connection-generation':str(out.resolve())}):
        n.require_unblocked(out);old=n.read(out/'ledger.json');from studyez_contracts.roots.generation_v2 import require_legacy_ledger;require_legacy_ledger(old)
        n.require(old['identity']==expected_identity and old.get('formatRecoveries')
            and not old.get('runtimeRevalidations')and old['repairRounds']==3
            and not(out/'runtime.revalidation.json').exists()and not(out/'.runtime-revalidation').exists()
            and not(out/'result.json').exists()and packet_hash(packet)==packet['inputHash']and reason.strip(),
            'Only the unchanged final completed tier recovery may be revalidated')
        for source in packet['sources']:
            path=Path(source['localPath'])
            n.require(path.stat().st_size==source['sizeBytes']and n.sha(path)==source['sha256'],'Original source changed')
        for name,entry in old['stages'].items():
            n.require(entry['status']in('completed','failed','blocked'),'An active/interrupted stage cannot be rebound')
            if entry['status']=='blocked':continue
            for suffix,key in(('.input.json','inputHash'),('.raw.json','rawOutputHash'),('.usage.json','usageHash')):
                n.require(document_hash(n.read(out/(name+suffix)))==entry[key],'Cached execution evidence changed')
            n.validate_stage(out,{'name':name,**entry},model=g.codex.model_name(model))
            if entry['status']=='completed':
                value=n.read(out/(name+'.json'));n.require(document_hash(value)==entry['outputHash'],'Cached accepted output changed')
                if name.startswith('source-'):
                    ctx=n.read(out/(name+'.input.json'));c.validate_audit(ctx['brief'],ctx['bank'],value)
        for row in old['formatRecoveries']:validate_recovery(out,row,model=g.codex.model_name(model))
        stages={k:{'name':k,**v}for k,v in old['stages'].items()}
        meta={'formatRecoveries':old['formatRecoveries'],'authoringRecoveries':old.get('authoringRecoveries',[]),
            'inputHash':packet['inputHash'],'runtimeHash':old['identity'],'repairRounds':3,
            'initialBrief':n.read(out/'normalize.json')}
        c.validate_format_recoveries(meta,stages);c.validate_authoring_recoveries(meta,stages)
        proof={'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
            'currentRuntimeHash':g.identity(packet,model),'reason':reason,'toolSha256':n.sha(__file__),'modelReplay':False}
        row={'proof':proof,'proofHash':document_hash(proof)}
        updated=copy.deepcopy(old);updated.update(identity=proof['currentRuntimeHash'],runtimeRevalidations=[row])
        meta.update(runtimeHash=updated['identity'],runtimeRevalidations=[row])
        c.validate_runtime_revalidations(meta,stages);c.validate_format_recoveries(meta,stages);c.validate_authoring_recoveries(meta,stages)
        archive=out/'.runtime-revalidation';archive.mkdir()
        (archive/'ledger-before.json').write_bytes((out/'ledger.json').read_bytes())
        (archive/'recovery.py').write_bytes(Path(__file__).read_bytes())
        g.write(out/'runtime.revalidation.json',row);g.write(out/'ledger.json',updated)
        return {'modelCalls':0,'repairRounds':3,'priorRuntime':expected_identity,'runtime':updated['identity'],'proofHash':row['proofHash']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',required=True)
    p.add_argument('--expected-identity',required=True);p.add_argument('--reason',required=True);p.add_argument('--model')
    p.add_argument('--revalidate-runtime',action='store_true')
    a=p.parse_args()
    result=(revalidate_runtime(n.read(a.packet),a.out,expected_identity=a.expected_identity,reason=a.reason,model=a.model)
        if a.revalidate_runtime else recover(n.read(a.packet),a.out,stage=a.stage,expected_identity=a.expected_identity,reason=a.reason,model=a.model))
    print(json.dumps(result))

if __name__=='__main__':main()
