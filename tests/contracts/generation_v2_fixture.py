"""Nonmedical, lesson-independent fixtures for the new public pipeline."""
import copy
import automation_fixture as old
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash

def packet(path=None):
    p=old.packet(path);p['sourceAssessmentFormat']=c.VERSION;p['inputHash']=packet_hash(p);return p

def brief(sources=None):
    b=old.brief(sources);b['schema_version']='learning-brief/2'
    for t in b['targets']:
        for d in t['directions']:
            d.update(components=[{'component_id':'fact','text':'Synthetic required recall '+d['direction_id']}],requires_visual=False)
    return b

def author(b=None,web=False):
    bank=old.web_bank()if web else old.bank()
    for q in bank['questions']:q.pop('stimuli',None)
    return {'bank':bank,'brief':copy.deepcopy(b or brief()),'visual_stimuli':[],'clinical_conflicts':[],'map_change_reason':'No map change'}

def assessment(b,bank):
    value=old.assessment(c.legacy_brief(b),bank);value.pop('input_issues');value['schema_version']=c.VERSION
    for row in value['direction_checks']:row['scope_status']='consistent'
    ds={d['direction_id']:d for t in b['targets']for d in t['directions']}
    evidence=[]
    for q in value['question_reviews']:
        for claim in q['relations']:
            for did in claim['direction_ids']:
                evidence.append({'question_id':q['question_id'],'direction_id':did,
                    'components':[{'component_id':p['component_id'],'location':'answer','answer_unit_indices':[0],'reason':'Synthetic answer recall'}for p in ds[did]['components']],
                    'visual_verdict':'ok'if ds[did]['requires_visual']else'not_applicable','reason':'Synthetic complete goal'})
    value.update(direction_evidence=evidence,relation_checks=[{'relation_id':r['relation_id'],'status':'supported','reason':'Synthetic source check'}for r in b['relations']],
        target_checks=[{'target_id':t['target_id'],'status':'consistent','reason':'Synthetic evidence check'}for t in b['targets']],
        prerequisite_checks=[{'question_id':q['question_id'],'prerequisite_id':p,'status':'supported','reason':'Synthetic necessary basic'}for q in bank['questions']for p in q.get('prerequisites',[])],
        issues=[],clinical_context_status='consistent',clinical_context_reason='Synthetic complete clinical projection')
    return value

def model(stage,ctx,material,model_name):
    if stage=='normalize':
        b=brief(ctx['sources'])
        if ctx.get('inputMode')=='source':b['provenance']['independent_points']='confirmed'
        if any(s['page_count']for s in ctx['sources']):b['targets'][0]['directions'][0]['requires_visual']=True
        return b,{}
    if stage=='generate'or stage.startswith('repair-'):
        a=author(ctx['brief'],bool(ctx.get('webResponse')))
        if ctx['brief']['targets'][0]['directions'][0]['requires_visual']:
            a['visual_stimuli']=[{'question_id':a['bank']['questions'][0]['question_id'],'source_id':ctx['sources'][0]['source_id'],
                'page':1,'crop':[0.05,0.05,0.4,0.4],'reason':'Synthetic source crop; never a student caption'}]
            a['bank']['questions'][0]['prerequisites']=[a['bank']['questions'][1]['question_id']]
        return a,{}
    if stage.startswith('source-'):return assessment(ctx['brief'],ctx['bank']),{}
    if stage.startswith('medical-'):return old.checks(ctx['bank']),{}
    raise AssertionError(stage)

def result(p):
    from studyez_contracts.roots.source_assessment import envelope
    from studyez_contracts.roots import document_hash
    from studyez_contracts.bank.validate import validate_bank
    b=brief();b['lecture_id']=p['subject']+'/'+p['runId']
    b['sources']=[{'source_id':s['id'],'label':s['filename'],'sha256':s['sha256'],'kind':'notes','professor':None,'year':None,'page_count':None}for s in p['sources']]
    if p.get('inputMode')=='source':b['provenance']['independent_points']='confirmed'
    authored=author(b,p.get('authoring')=='web');bank=authored['bank'];raw=envelope(b,bank,assessment(b,bank));audit=c.compile_assessment(b,bank,raw);medical=old.checks(bank)
    outputs={'normalize':b,'generate':authored,'source-0':audit,'medical-0':medical}
    stages=[{'name':name,'status':'completed','inputHash':'0'*64,'outputHash':document_hash(v),
        'rawOutputHash':document_hash(raw if name=='source-0'else v)}for name,v in outputs.items()]
    next(s for s in stages if s['name']=='generate')['briefHash']=document_hash(b)
    next(s for s in stages if s['name']=='source-0')['clinicalContextHash']=document_hash([])
    med_input=document_hash({'title':p['title'],'bank':bank,'clinicalInput':c.medical_input(bank,[]),'_pipeline_version':c.POLICY})
    next(s for s in stages if s['name']=='medical-0')['inputHash']=med_input
    return {'brief':b,'document':c.make_document(b,bank,audit,revision=p['revision'],title=p['title'],exam_date=p['examDate'],medical=medical),
        'sourceAudit':audit,'medical':medical,'validation':validate_bank(bank,[s['id']for s in p['sources']]),
        'manifest':{'pipelineVersion':c.POLICY,'inputHash':p['inputHash'],'briefHash':document_hash(b),'bankHash':document_hash(bank),
            'runtimeHash':'0'*64,'model':'synthetic','webResponseHash':p.get('webResponseHash'),'initialBrief':b,
            'visualStimuli':[],'clinicalConflicts':[],'mapChangeReason':'No map change','sourceAssessment':raw,'repairRounds':0,
            'briefRevisions':[{'stage':'generate','brief':b,'reason':'No map change'}],
            'medicalInputHash':med_input,'stages':stages}}
