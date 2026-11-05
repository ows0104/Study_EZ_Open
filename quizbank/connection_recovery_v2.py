"""Explicit acceptance recovery for a completed, archived initial source-map call.

Never invokes a model or server, edits content, or resets a correction allowance.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from . import connection_generate as g
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash,source_intake

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def recover(packet,out,*,expected_identity,reason,model=None):
    out=Path(out);old=read(out/'ledger.json');stage=old.get('stages',{}).get('normalize',{})
    c.require(packet_hash(packet)==packet['inputHash']and packet.get('inputMode')=='source','Recovery requires the unchanged source-only packet')
    c.require(old.get('identity')==expected_identity and old.get('pipelineVersion')==c.POLICY and old.get('repairRounds')==0
              and set(old.get('stages',{}))=={'normalize'}and stage.get('status')=='failed'
              and not old.get('normalizationRecoveries'),'Only failed initial acceptance can be recovered once')
    c.require(type(reason)is str and reason.strip(),'Recovery reason required')
    c.require(not(out/'normalize.json').exists()and not(out/'normalize.recovery.json').exists(),'Recovery already exists; preserve its evidence')
    ctx=read(out/'normalize.input.json');raw=read(out/'normalize.raw.json');usage=read(out/'normalize.usage.json')
    c.require(all(stage.get(k)==document_hash(v)for k,v in [('inputHash',ctx),('rawOutputHash',raw),('usageHash',usage)]),'Archived input/raw/usage changed')
    sources=ctx['sources']
    expected={**source_intake(packet,sources),'preserved_scope':g.lecture_scope(packet['title'],packet['sources']),'_pipeline_version':c.POLICY}
    c.require(ctx==expected,'Source-only model input changed')
    c.validate_shape(raw,c.BRIEF,'recovered initial brief')
    c.require(raw['sources']==sources and raw['lecture_id']==ctx['lecture_id']
              and raw['provenance']['independent_points']=='confirmed','Initial source inventory or independence changed')
    c.require(c.brief_findings(raw,sources),'Recovery requires retained initial map findings')
    inventory={s['source_id']:s for s in sources}
    c.require(set(inventory)=={s['id']for s in packet['sources']},'Source inventory changed')
    for source in packet['sources']:
        body=Path(source['localPath']).read_bytes()
        c.require(len(body)==source['sizeBytes']and hashlib.sha256(body).hexdigest()==source['sha256']
                  and inventory[source['id']]['sha256']==source['sha256']and inventory[source['id']]['label']==source['filename'],'Frozen source changed')
    counters=usage.get('usage',{})
    c.require(all(type(counters.get(k))is int and counters[k]>0 for k in('input_tokens','output_tokens'))
              and bool(usage.get('models'))and usage.get('duration_ms',0)>0,'Completed model usage evidence missing')
    current=g.identity(packet,model)
    proof={'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
           'currentRuntimeHash':current,'reason':reason,'modelReplay':False}
    row={'proof':proof,'proofHash':document_hash(proof)}
    accepted={**stage,'status':'completed','outputHash':document_hash(raw),'originRuntimeHash':expected_identity}
    updated={**old,'identity':current,'stages':{'normalize':accepted},'normalizationRecoveries':[row]}
    c.validate_normalization_recoveries({'inputHash':packet['inputHash'],'runtimeHash':current,
                                       'normalizationRecoveries':[row]},updated['stages'])
    # The failed ledger is embedded verbatim in an immutable proof written first.
    g.write(out/'normalize.recovery.json',row);g.write(out/'normalize.json',raw);g.write(out/'ledger.json',updated)
    return {'proofHash':row['proofHash'],'originRuntimeHash':expected_identity,'runtimeHash':current,'repairRounds':0,'modelReplay':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-identity',required=True)
    p.add_argument('--reason',required=True);p.add_argument('--model');a=p.parse_args()
    print(json.dumps(recover(read(a.packet),a.out,expected_identity=a.expected_identity,reason=a.reason,model=a.model)))
if __name__=='__main__':main()
