"""Explicit frozen review continuation; never edits or replays the failed origin."""
import argparse
import copy
import json
import shutil
import os
from pathlib import Path
from studyez_contracts.roots import document_hash,generation_v2 as c,recall_units as recall
from studyez_contracts.roots import chunked as contract
from studyez_contracts.bank.validate import validate_bank
from quizbank import connection_generate as g
from . import root_native_json as n,root_chunked_tasks as tasks

def inventory(folder):
    folder=Path(folder)
    return {p.relative_to(folder).as_posix():n.sha(p)for p in folder.rglob('*')if p.is_file()}

def prepare(origin,out):
    origin=Path(origin).resolve();out=Path(out).resolve();n.require(origin!=out and not out.exists(),'Preserve existing origin/continuation')
    n.require(not any(origin.rglob('content-block.json')),'Provider restriction cannot be continued')
    n.require_unblocked(origin)
    ledger=n.read(origin/'ledger.json');ctx=n.read(origin/'source-2.input.json');author=n.read(origin/'repair-2.json');packet=n.read(origin/'packet.json')
    failure=n.read(origin/'.native/source-2/failure.json')
    n.require(ledger['repairRounds']==2 and ledger['stages']['source-2']['status']=='failed'
        and failure['classification']['kind']=='model_timeout','Only approved frozen round-2 timeout')
    n.require(document_hash(ctx)==ledger['stages']['source-2']['inputHash']and ctx['bank']==author['bank']and ctx['brief']==author['brief']
        and document_hash(author)==ledger['stages']['repair-2']['outputHash']and len(author['bank']['questions'])==91,'Changed original candidate')
    # Full verification of completed earlier native calls before new model calls.
    model=g.codex.model_name()
    for name,entry in ledger['stages'].items():
        if entry['status']=='completed':
            n.require(document_hash(n.read(origin/(name+'.json')))==entry['outputHash'],'Changed completed origin')
            n.validate_stage(origin,{'name':name,**entry},model=model)
    before=inventory(origin)
    shutil.copytree(origin,out,ignore=shutil.ignore_patterns('pilot.log'))
    # Preserve failed transport under its original name inside a dedicated archive;
    # no new .native/source-2 invocation is created.
    (out/'.native/source-2').rename(out/'.native/original-source-2-failed')
    capture={'origin':str(origin),'inventory':before,'inventoryHash':document_hash(before),'priorLedger':ledger,
        'failure':failure,'packetHash':packet['inputHash'],'context':contract.clean(ctx),'reviewRuntimeHash':tasks.code_hash(),
        'authorization':'2026-11-07 user: preserve91questions/repairs2of3; chunk reviews, confirm images, upload'}
    (out/'chunked').mkdir();g.write(out/'chunked/origin.json',capture)
    code=out/'chunked/runtime';code.mkdir()
    root=Path(__file__).resolve().parents[1]
    for file in tasks.runtime_files():
        target=code/file.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    print(json.dumps({'prepared':str(out),'frozenQuestions':91,'repairRounds':2,'tasks':len(contract.plan(ctx))}),flush=True)
    return capture

def validate_origin(out):
    out=Path(out);cap=n.read(out/'chunked/origin.json');origin=Path(cap['origin'])
    n.require(document_hash(cap['inventory'])==cap['inventoryHash']and inventory(origin)==cap['inventory'],'Original experiment files changed')
    n.require(n.read(origin/'ledger.json')==cap['priorLedger']and n.read(origin/'.native/source-2/failure.json')==cap['failure'],'Original failure changed')
    archive=out/'chunked/runtime'
    n.require(document_hash(inventory(archive))==cap['reviewRuntimeHash'],'Changed archived review runtime')
    return cap

def validate(out,payload):
    out=Path(out);cap=validate_origin(out);p=payload['manifest']['chunkedReview']['proof'];ctx=n.read(out/'source-2.input.json')
    n.require(p['originInventoryHash']==cap['inventoryHash']and p['priorLedger']==cap['priorLedger']and p['failure']==cap['failure'],'Changed continuation origin')
    n.require(p['reviewRuntimeHash']==cap['reviewRuntimeHash'],'Changed review runtime claim')
    outputs={r['assignment']['name']:r['output']for r in p['tasks']if r['assignment']['kind']not in('global','medical')}
    for row in p['tasks']:
        seat=out/'chunked/tasks'/row['assignment']['name']
        n.require(n.read(seat/'state.json')==row,'Changed task state')
        tasks.validate_task(seat,row,ctx,payload['manifest']['model'],outputs if row['assignment']['kind']=='global'else None)
    contract.validate_continuation(payload)

def run(out):
    out=Path(out).resolve();cap=validate_origin(out)
    n.require(tasks.code_hash()==cap['reviewRuntimeHash'],'Review code changed after freezing')
    packet=n.read(out/'packet.json');old=cap['priorLedger'];ctx=n.read(out/'source-2.input.json');author=n.read(out/'repair-2.json')
    n.require(document_hash(ctx)==old['stages']['source-2']['inputHash']and ctx['bank']==author['bank'],'Changed frozen review inputs')
    status={'pid':os.getpid(),'subject':packet['subject'],'states':{t['name']:{'title':packet['title']+' · '+t['name'],
        'subject':packet['subject'],'stage':'queued','error':''}for t in contract.plan(ctx)}}
    g.write(out/'chunked-status.json',status)
    project=Path(__file__).resolve().parents[3]
    config={'id':'chunked-review-261104-02','label':'91문항 분할 검수','owner':'Codex Main Quiz 후속','overview':True,
        'script':'runner.root_chunked_review','log':str((out/'chunked.log').relative_to(project)).replace('\\','/'),
        'outputs':str(out.relative_to(project)).replace('\\','/'),'state_file':str((out/'chunked-status.json').relative_to(project)).replace('\\','/'),
        'stages':{'queued':'대기','running':'CLI 검수 중','applied':'검수 완료','failed':'실패·기록 보존'}}
    g.write(project/'runs/status-jobs/chunked-review-261104-02.json',config)
    raw,medical,rows=tasks.run(out/'chunked/tasks',ctx,out/'material',g.codex.model_name())
    audit=c.compile_assessment(ctx['brief'],ctx['bank'],c.envelope(ctx['brief'],ctx['bank'],raw))
    n.require(raw['clinical_context_status']=='consistent','Clinical input separation not completed')
    medical_ctx={'title':packet['title'],'bank':ctx['bank'],'clinicalInput':c.medical_input(ctx['bank'],ctx['clinical_conflicts']),'_pipeline_version':c.POLICY}
    g.write(out/'medical-2.input.json',medical_ctx)
    stage_source={'status':'completed','inputHash':old['stages']['source-2']['inputHash'],'outputHash':document_hash(audit),
        'rawOutputHash':document_hash(audit['assessment']),'clinicalContextHash':document_hash(ctx['clinical_conflicts'])}
    stage_med={'status':'completed','inputHash':document_hash(medical_ctx),'outputHash':document_hash(medical),'rawOutputHash':document_hash(medical)}
    for name,entry,kind in [('source-2',stage_source,'source'),('medical-2',stage_med,'medical')]:
        usage={'policy':contract.POLICY,'tasks':[{k:r[k]for k in('assignment','providerHash','outputHash')}for r in rows
            if (r['assignment']['kind']=='medical')==(kind=='medical')]}
        g.write(out/(name+'.usage.json'),usage);entry['usageHash']=document_hash(usage)
    proof={'policy':contract.POLICY,'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
        'context':contract.clean(ctx),'failure':cap['failure'],'originInventoryHash':cap['inventoryHash'],
        'reviewRuntimeHash':cap['reviewRuntimeHash'],'tasks':rows}
    row={'proof':proof,'proofHash':document_hash(proof)}
    stage_source['chunkedProofHash']=stage_med['chunkedProofHash']=row['proofHash']
    ledger=copy.deepcopy(old);ledger['stages'].update({'source-2':stage_source,'medical-2':stage_med});ledger['chunkedReview']=row
    for name,value,raw_value in [('source-2',audit,audit['assessment']),('medical-2',medical,medical)]:
        g.write(out/(name+'.json'),value);g.write(out/(name+'.raw.json'),raw_value)
    b=author['brief'];bank=author['bank'];initial=n.read(out/'normalize.json');errors=c.brief_findings(initial)
    validation=validate_bank(bank,[s['id']for s in packet['sources']])
    doc=c.make_document(b,bank,audit,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate'],medical=medical)
    meta={'pipelineVersion':c.POLICY,'inputHash':packet['inputHash'],'briefHash':document_hash(b),'bankHash':document_hash(bank),
        'runtimeHash':old['identity'],'model':g.codex.model_name(),'webResponseHash':packet.get('webResponseHash'),
        'initialBrief':initial,'visualStimuli':author['visual_stimuli'],'clinicalConflicts':author['clinical_conflicts'],
        'mapChangeReason':author['map_change_reason'],'sourceAssessment':audit['assessment'],'repairRounds':2,
        'initialMapCorrection':{'errors':errors,'consumedRounds':int(bool(errors))},'normalizationRecoveries':old.get('normalizationRecoveries',[]),
        'briefRevisions':[{'stage':name,'brief':v['brief'],'reason':v['map_change_reason']}for name in('generate','repair-1','repair-2')for v in[n.read(out/(name+'.json'))]],
        'medicalInputHash':stage_med['inputHash'],'stages':[{'name':k,**v}for k,v in ledger['stages'].items()],
        'parallelAuthoring':old['parallelSchemaRecovery']['proof']['parallelProof'],'parallelSchemaRecovery':old['parallelSchemaRecovery'],'chunkedReview':row}
    if recall.enabled(b):meta['goalPreparation']=recall.prepared_coverage(audit,doc)
    result={'brief':b,'document':doc,'sourceAudit':audit,'medical':medical,'validation':validation,'manifest':meta}
    c.validate_result(result,packet);validate(out,result)
    n.require(doc['tasks'],'No prepared tasks')
    g.write(out/'ledger.json',ledger);g.write(out/'result.json',result)
    g.write(out/'summary.json',{'completed':True,'questions':len(bank['questions']),'visualQuestions':sum(bool(q.get('stimuli'))for q in bank['questions']),
        'tasks':len(doc['tasks']),'repairRounds':2,'productionWrites':0,'sourceVerdicts':audit['question_checks'],'medicalVerdicts':medical})
    print(json.dumps({'completed':True,'questions':91,'tasks':len(doc['tasks']),'repairRounds':2}),flush=True)

def main():
    a=argparse.ArgumentParser();a.add_argument('--origin',type=Path);a.add_argument('--out',type=Path,required=True);a.add_argument('--prepare',action='store_true');x=a.parse_args()
    if x.prepare:prepare(x.origin,x.out)
    else:run(x.out)

if __name__=='__main__':main()
