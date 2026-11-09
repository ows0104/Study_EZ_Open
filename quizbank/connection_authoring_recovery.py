"""Operator-only recovery of a completed, file-receipted authoring rejection.

No model or server calls. Failed evidence and consumed rounds remain bound to the
new runtime. Ambiguous executions and provider refusals are never replayed.
"""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from . import connection_generate as g,connection_visuals as visual
from studyez_contracts.roots import generation_v2 as c,document_hash
from studyez_contracts.roots.automation import packet_hash

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def recover(packet,out,*,expected_identity,mode,reason,model=None):
    from runner import root_native_json as native
    out=Path(out);native.require_unblocked(out)
    old=read(out/'ledger.json');stages=old.get('stages',{});from studyez_contracts.roots.generation_v2 import require_legacy_ledger;require_legacy_ledger(old)
    c.require(packet_hash(packet)==packet['inputHash']and packet.get('sourceAssessmentFormat')==c.VERSION,
              'Recovery requires the unchanged version-two packet')
    c.require(old.get('identity')==expected_identity and old.get('pipelineVersion')==c.POLICY
        and not old.get('authoringRecoveries')and not old.get('normalizationRecoveries')
        and not(out/'authoring.recovery.json').exists()and not(out/'result.json').exists(),
        'Different runtime, existing result or previous recovery')
    c.require(type(reason)is str and reason.strip(),'Explicit operator reason required')
    failed=[name for name,s in stages.items()if s['status']=='failed']
    c.require(len(failed)==1 and all(s['status']in('completed','failed','blocked')for s in stages.values()),
              'Interrupted or ambiguous stages cannot be recovered')
    name=failed[0];entry=stages[name]
    c.require(name=='generate'or re.fullmatch(r'repair-[1-3]',name),'Only authoring acceptance is eligible')
    c.require(stages.get('normalize',{}).get('status')=='completed'and not(out/(name+'.json')).exists(),
              'Missing completed normalization or ambiguous accepted output')
    for stage,s in stages.items():
        if s['status']=='blocked':
            c.require(stage.startswith('medical-')and s['blockedHash']==document_hash(s['blockedReport']),
                      'Invalid blocked review archive');continue
        for suffix,key in [('.input.json','inputHash'),('.raw.json','rawOutputHash'),('.usage.json','usageHash')]:
            c.require(document_hash(read(out/(stage+suffix)))==s.get(key),'Changed archived '+stage+suffix)
        if s['status']=='completed':
            c.require(document_hash(read(out/(stage+'.json')))==s.get('outputHash'),'Changed accepted '+stage)
        native.validate_stage(out,{'name':stage,**s},model=g.codex.model_name(model))
    usage=read(out/(name+'.usage.json'))
    c.require('fileReceipt'in usage and usage['duration_ms']>0
        and all(type(usage['usage'].get(k))is int and usage['usage'][k]>0 for k in('input_tokens','output_tokens')),
        'Completed native model usage is required')
    for source in packet['sources']:
        body=Path(source['localPath']).read_bytes()
        c.require(len(body)==source['sizeBytes']and hashlib.sha256(body).hexdigest()==source['sha256'],
                  'Frozen original source changed')
    initial=read(out/'normalize.json');ctx=read(out/(name+'.input.json'));raw=read(out/(name+'.raw.json'))
    c.validate_shape(raw,c.AUTHOR,'rejected authoring2')
    c.require(initial['sources']==raw['brief']['sources']==ctx['sources']
        and initial['lecture_id']==raw['brief']['lecture_id']==packet['subject']+'/'+packet['runId'],
        'Original lecture/source inventory changed')
    findings=c.brief_findings(raw['brief']);initial_cost=int(bool(c.brief_findings(initial)))
    c.require(type(old.get('repairRounds'))is int and 0<=old['repairRounds']<=3,'Invalid prior budget')
    accepted=None
    if mode=='brief-repair':
        c.require(name=='generate'and set(stages)=={'normalize','generate'}and findings
            and old['repairRounds']==initial_cost,'Rejected-brief repair requires the first completed authoring')
        c.preserve_map_inputs(initial,raw['brief'])
    else:
        c.require(mode=='acceptance-recheck'and re.fullmatch(r'repair-[1-3]',name)
            and old['repairRounds']==int(name.split('-')[1])+initial_cost and not findings,
            'Recheck requires one completed repair with a valid brief')
        previous=ctx.get('previousAuthoring');c.require(previous is not None,'Missing original repair context')
        before,after=previous['brief']['scope'],raw['brief']['scope']
        changed={k for k in before if before[k]!=after[k]}
        c.require(changed and changed<=set(('reviewed','limitations','outside_list_review')),
                  'Only review-note acceptance changes are eligible for recheck')
        c.validate_authoring(raw,previous)
        accepted=copy.deepcopy(raw)
        accepted['bank']=visual.render(accepted['bank'],raw['visual_stimuli'],packet,out/'material')
    current=g.identity(packet,model)
    proof={'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
        'currentRuntimeHash':current,'reason':reason,'mode':mode,'stage':name,
        'rawAuthoring':raw,'findings':findings,'modelReplay':False}
    row={'proof':proof,'proofHash':document_hash(proof)}
    updated=copy.deepcopy(old);updated.update(identity=current,authoringRecoveries=[row])
    if accepted is not None:
        updated['stages'][name].update(status='completed',outputHash=document_hash(accepted),
                                     briefHash=document_hash(raw['brief']))
    c.validate_authoring_recoveries({'authoringRecoveries':[row],'inputHash':packet['inputHash'],
        'runtimeHash':current,'initialBrief':initial,
        'repairRounds':max(old['repairRounds'],initial_cost+1)if mode=='brief-repair'else old['repairRounds']},
        {k:{'name':k,**v}for k,v in updated['stages'].items()})
    # Proof first. An interrupted recovery is held rather than silently repeated.
    g.write(out/'authoring.recovery.json',row)
    if accepted is not None:g.write(out/(name+'.json'),accepted)
    g.write(out/'ledger.json',updated)
    return {'stage':name,'mode':mode,'proofHash':row['proofHash'],'repairRounds':old['repairRounds'],
        'originalModelReplayed':False,'nextRepairConsumesRound':mode=='brief-repair'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-identity',required=True)
    p.add_argument('--mode',choices=['brief-repair','acceptance-recheck'],required=True)
    p.add_argument('--reason',required=True);p.add_argument('--model');a=p.parse_args()
    print(json.dumps(recover(read(a.packet),a.out,expected_identity=a.expected_identity,
        mode=a.mode,reason=a.reason,model=a.model)))

if __name__=='__main__':main()
