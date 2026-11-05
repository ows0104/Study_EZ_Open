"""Complete deterministic assembly of the saved successful model response.

Never calls a model. The first compiler failure and original example ledger stay
intact; this is a separately evidenced requirement/coverage representation fix.
"""
from collections import Counter
from datetime import datetime,UTC
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import example_run as example
from studyez_contracts.roots.source_assessment import compile_source_assessment

g=example.g;OUT=example.OUT

def inputs():
    packet,brief,bank,medical,validation,current=example.preflight()
    original=example.read(OUT/'preflight.json');failed=example.read(OUT/'example-ledger.json')
    for key,value in original.items():
        if key!='newRuntime':example.require(current[key]==value,'Original input/script proof changed: '+key)
    example.require(failed['status']=='failed' and failed['sourceCalls']==1 and failed['questionRepairs']==0
        and failed['error'].startswith('assessment: point has no representable required-direction coverage: P13'),
        'Not the known completed-model/requirement-coverage assembly failure')
    raw=example.read(OUT/'assessment.raw.json')
    example.require(g.document_hash(raw)==failed['rawHash'],'Original completed model response changed')
    schema=g.source_assessment_schema(brief,bank)
    example.require(g.output_schema(schema)==example.read(OUT/'wire-schema.json'),'Model output schema changed')
    g.jsonschema.validate(raw['assessment'],schema)
    example.require(isinstance(example.read(OUT/'usage.json'),dict),'Missing original model usage')
    return packet,brief,bank,medical,validation,original,current,raw

def assemble():
    example.require(not (OUT/'assembly-ledger.json').exists(),'Already assembled; use --check, never overwrite')
    packet,brief,bank,medical,validation,original,current,raw=inputs()
    audit=compile_source_assessment(brief,bank,raw)
    document=g.make_document(brief,bank,audit,revision='example-cholinergic-20261104',title=packet['title'],exam_date=packet['examDate'])
    all_directions={d['direction_id']for t in brief['targets']for d in t['directions']}
    summary={'questions':len(bank['questions']),'targets':len(brief['targets']),'directions':len(all_directions),
        'concepts':len(brief['concepts']),'points':len(brief['points']),'tasks':len(document['tasks']),
        'unreadyDirections':sorted(all_directions-{t['direction_id']for t in document['tasks']}),
        'sourceVerdicts':dict(Counter(r['verdict']for r in audit['question_checks']['reviews'])),
        'cachedMedicalVerdicts':dict(Counter(r['verdict']for r in medical['reviews'])),
        'coverage':dict(Counter(c['status']for c in audit['review']['coverage'])),
        'inputIssues':len(audit['input_issues']),'published':False,'newSourceCalls':1,'newQuestionRepairs':0}
    postprocess={'reason':'Keep retrieval evidence independent from unresolved required-direction coverage',
        'originalModelRuntime':original['newRuntime'],'compilerRuntime':current['newRuntime'],
        'rawHash':g.document_hash(raw),'additionalModelCalls':0,'assemblerHash':example.sha(Path(__file__)),
        'originalFailureLedgerFileHash':example.sha(OUT/'example-ledger.json')}
    result={'schema_version':'root-example/1','purpose':'read-only-example','proof':original,'postprocessProof':postprocess,
        'brief':brief,'bank':bank,'sourceAssessment':raw,'sourceAudit':audit,'document':document,
        'cachedMedical':{'bankHash':original['bankHash'],'originalStage':'medical-3','originalRuntime':original['originRuntime'],
            'outputHash':original['medicalHash'],'review':medical},'validation':validation,'summary':summary}
    g.write(OUT/'assembled-audit.json',audit);g.write(OUT/'assembled-document.json',document)
    g.write(OUT/'assembled-summary.json',summary);g.write(OUT/'assembled-result.json',result)
    g.write(OUT/'assembly-ledger.json',{'status':'completed','at':datetime.now(UTC).isoformat(),'additionalModelCalls':0,
        'resultHash':g.document_hash(result),'postprocessProofHash':g.document_hash(postprocess),'published':False})
    print(json.dumps(summary,ensure_ascii=False))

def check():
    packet,brief,bank,medical,_,original,current,raw=inputs()
    result=example.read(OUT/'assembled-result.json');state=example.read(OUT/'assembly-ledger.json');proof=result['postprocessProof']
    example.require(state['status']=='completed' and state['additionalModelCalls']==0 and not state['published'],'Unexpected assembly state')
    example.require(g.document_hash(result)==state['resultHash'] and g.document_hash(proof)==state['postprocessProofHash'],'Result/proof changed')
    example.require(proof['compilerRuntime']==current['newRuntime'] and proof['originalModelRuntime']==original['newRuntime'],
        'Runtime lineage changed')
    example.require(proof['assemblerHash']==example.sha(Path(__file__)) and proof['originalFailureLedgerFileHash']==example.sha(OUT/'example-ledger.json'),
        'Assembler/original failure changed')
    example.require(result['proof']==original and result['bank']==bank and result['brief']==brief and result['sourceAssessment']==raw,
        'Original content/model response changed')
    example.require(result['cachedMedical']['review']==medical and result['cachedMedical']['outputHash']==original['medicalHash']
        and result['cachedMedical']['bankHash']==original['bankHash'],'Cached medical evidence changed')
    audit=compile_source_assessment(brief,bank,raw);example.require(audit==result['sourceAudit'],'Source audit changed')
    example.require(g.make_document(brief,bank,audit,revision='example-cholinergic-20261104',title=packet['title'],
        exam_date=packet['examDate'])==result['document'],'Root selection changed')
    print(json.dumps({'pass':True,**result['summary']},ensure_ascii=False))

if __name__=='__main__':
    if sys.argv[1:] == ['--check']:check()
    elif sys.argv[1:] == ['--assemble']:assemble()
    else:raise SystemExit('Choose --assemble or --check')
