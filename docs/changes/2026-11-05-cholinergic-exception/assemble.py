"""Materialize explicit independent source review into relation review metadata.

No clinical wording, question verdict, assessment claim or scope is edited.
Author raw unreviewed status and original assessment binding remain archived.
"""
import sys,json
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import exception as e
f=e.f
ORIGINAL_REPLAY=e.replay_brief

def source_reviewed(brief,patch):
    value=ORIGINAL_REPLAY(brief,patch)
    record=f.read(e.OUT/'source-review-adoption.json')
    f.require(f.g.document_hash(value)==record['beforeBriefHash'],'Authoring brief changed')
    rel=next(r for r in value['relations']if r['relation_id']=='R35')
    f.require(rel['review_status']=='unreviewed','Unexpected original review status')
    rel['review_status']='reviewed'
    f.require(f.g.document_hash(value)==record['afterBriefHash'],'Source adoption changed facts')
    return value

def configure():
    e.configure();e.replay_brief=source_reviewed

def materialize():
    e.configure();packet,_,_=e.verified()
    f.require(not(e.OUT/'source-review-adoption.json').exists(),'Never overwrite source adoption')
    brief=f.read(e.OUT/'brief.json');bank=f.read(e.OUT/'bank-4.json');raw=f.read(e.OUT/'assessment-4.json')
    stage=e.OUT/'stages/source-4';source_input=f.read(stage/'input.json');assessment=f.read(stage/'output.json')
    f.require(raw==f.envelope(brief,bank,assessment)and source_input['brief']==brief and source_input['bank']==bank,'Raw source input binding mismatch')
    d=next(d for t in brief['targets']for d in t['directions']if d['direction_id']=='D10')
    check=next(r for r in assessment['direction_checks']if r['direction_id']=='D10')
    q=next(r for r in assessment['question_reviews']if r['question_id']=='Q077')
    claims=[r for r in q['relations']if r['relation_id']=='R35'and r['role']=='tested'and r['direction_ids']==['D10']]
    f.require(d['relation_ids']==['R35']and check['status']=='reviewed'and q['verdict']=='ok'and len(claims)==1,'Missing explicit independent source acceptance')
    value=deepcopy(brief);rel=next(r for r in value['relations']if r['relation_id']=='R35')
    f.require(rel['review_status']=='unreviewed','Only pending R35 metadata can be adopted')
    rel['review_status']='reviewed'
    normalized=f.envelope(value,bank,assessment)
    audit=f.compile_source_assessment(value,bank,normalized)
    doc=f.make_document(value,bank,audit,revision='example-findings-4',title=packet['title'],exam_date=packet['examDate'])
    f.g.write(e.OUT/'brief-before-review-adoption.json',brief)
    f.g.write(e.OUT/'assessment-before-review-adoption.json',raw)
    proof={'schema_version':'source-review-adoption/1','reason':'Materialize the separate source reviewer’s explicit D10 reviewed + Q077 ok + R35 tested/D10 acceptance into the pending relation metadata. This is source-review completion, not a new clinical judgment or correction call.',
        'changedField':'relations[R35].review_status','before':'unreviewed','after':'reviewed',
        'beforeBriefHash':f.g.document_hash(brief),'afterBriefHash':f.g.document_hash(value),
        'originalAssessmentHash':f.g.document_hash(raw),'reviewedAssessmentHash':f.g.document_hash(normalized),
        'sourceStageOutputHash':f.g.document_hash(assessment),'evidence':{'questionReview':q,'directionCheck':check,'testedClaim':claims[0]},
        'assessmentPayloadUnchanged':True,'additionalModelCalls':0,'clinicalFactsChanged':False,'builderHash':f.sha(Path(__file__))}
    f.g.write(e.OUT/'source-review-adoption.json',proof)
    f.g.write(e.OUT/'brief.json',value);f.g.write(e.OUT/'assessment-4.json',normalized)
    f.g.write(e.OUT/'audit-4.json',audit);f.g.write(e.OUT/'document-4.json',doc)
    print(json.dumps({'sourceVerdicts':dict(e.Counter(r['verdict']for r in assessment['question_reviews'])),'tasks':len(doc['tasks']),
        'metadataOnlyReviewAdoption':True,'additionalModelCalls':0},ensure_ascii=False),flush=True)

def bundle():
    configure();e.bundle()
    value=f.read(e.OUT/'result.json');value['sourceReviewAdoption']=f.read(e.OUT/'source-review-adoption.json')
    f.g.write(e.OUT/'result.json',value)
    ledger=f.read(e.OUT/'ledger.json');ledger['resultHash']=f.g.document_hash(value);f.g.write(e.OUT/'ledger.json',ledger)
    pres=f.read(e.OUT/'presentation-audit.json');pres['resultHash']=f.sha(e.OUT/'result.json');f.g.write(e.OUT/'presentation-audit.json',pres)
    e.check()

if __name__=='__main__':
    if sys.argv[1]=='source':materialize()
    elif sys.argv[1]=='bundle':bundle()
    elif sys.argv[1]=='check':configure();e.check()
    else:raise SystemExit('source/bundle/check')
