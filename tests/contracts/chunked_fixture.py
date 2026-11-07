"""Synthetic geometry only: a complete, immutable round-2 review continuation."""
import copy
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as c,chunked as part,document_hash

def result(packet):
    value=f.result(packet);meta=value['manifest'];bank=value['document']['bank_snapshot'];b=value['brief']
    ctx={'title':packet['title'],'bank':bank,'brief':b,'clinical_conflicts':[],'_pipeline_version':c.POLICY}
    raw=f.assessment(b,bank);raw['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic design'}for q in bank['questions']]
    old={'identity':meta['runtimeHash'],'pipelineVersion':c.POLICY,'repairRounds':2,
        'stages':{s['name']:{k:v for k,v in s.items()if k!='name'}for s in meta['stages']}}
    author={'bank':bank,'brief':b,'visual_stimuli':[],'clinical_conflicts':[],'map_change_reason':meta['mapChangeReason']}
    for n in (1,2):
        old['stages']['repair-'+str(n)]=copy.deepcopy(old['stages']['generate'])
        if n==1:
            for kind in('source','medical'):old['stages'][kind+'-1']=copy.deepcopy(old['stages'][kind+'-0'])
    old['stages']['source-2']={'status':'failed','inputHash':document_hash(ctx)}
    rows=[];parts={};runtime='2'*64
    for task in part.plan(ctx):
        medical=task['kind']=='medical'
        output={k:raw[k]for k in part.schema(ctx,task)['properties']}if not medical else {k:value['medical'][k]for k in('summary','reviews')}
        inp=part.task_input(ctx,task,copy.deepcopy(parts)if task['kind']=='global'else None)
        rows.append({'assignment':task,'output':output,'outputHash':document_hash(output),'inputHash':document_hash(inp),
            'identity':document_hash({'input':inp,'model':meta['model'],'code':runtime}),'model':meta['model'],'status':'completed'})
        if task['kind']not in('global','medical'):parts[task['name']]=output
    audit=c.compile_assessment(b,bank,c.envelope(b,bank,raw));value['sourceAudit']=audit
    value['document']=c.make_document(b,bank,audit,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate'],medical=value['medical'])
    proof={'policy':part.POLICY,'priorLedger':old,'priorLedgerHash':document_hash(old),'packetHash':packet['inputHash'],
        'context':part.clean(ctx),'failure':{'classification':{'kind':'model_timeout','automaticRetry':False}},'reviewRuntimeHash':runtime,'tasks':rows}
    row={'proof':proof,'proofHash':document_hash(proof)}
    stages=copy.deepcopy(old['stages']);stages['source-2']={'status':'completed','inputHash':document_hash(ctx),'outputHash':document_hash(audit),
        'rawOutputHash':document_hash(audit['assessment']),'clinicalContextHash':document_hash([]),'chunkedProofHash':row['proofHash']}
    stages['medical-2']=copy.deepcopy(old['stages']['medical-0']);stages['medical-2']['chunkedProofHash']=row['proofHash']
    meta.update(repairRounds=2,sourceAssessment=audit['assessment'],chunkedReview=row,
        stages=[{'name':k,**v}for k,v in stages.items()],briefRevisions=meta['briefRevisions']+[
            {'stage':'repair-'+str(i),'brief':b,'reason':meta['mapChangeReason']}for i in(1,2)])
    c.validate_result(value,packet)
    return value
