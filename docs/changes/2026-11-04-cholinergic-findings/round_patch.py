"""Bounded delta authoring; replays exact model edits, never authors content."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import followup as f
from studyez_contracts.bank.schema import QUESTION
from studyez_contracts.learning_links.schema import obj,arr,TEXT

META=obj(**{k:v for k,v in f.g.BANK['properties'].items()if k!='questions'})
EDIT=obj(question=QUESTION,reason=TEXT)
PATCH=obj(metadata=META,question_updates=arr(EDIT),new_questions=arr(EDIT),
    removals=arr(obj(question_id=TEXT,reason=TEXT)),question_order=arr(TEXT,1),visual_stimuli=arr(f.visual.STIMULUS))

def replay(bank,patch):
    known={q['question_id']:q for q in bank['questions']};updates={r['question']['question_id']:r['question']for r in patch['question_updates']}
    new={r['question']['question_id']:r['question']for r in patch['new_questions']};removed={r['question_id']for r in patch['removals']}
    f.require(len(updates)==len(patch['question_updates']) and len(new)==len(patch['new_questions']) and len(removed)==len(patch['removals']),'Duplicate patch edits')
    f.require(set(updates)<=known.keys() and removed<=known.keys() and not(set(new)&known.keys()),'Patch IDs conflict')
    f.require(not(set(updates)&removed),'Patch updates and removes same question')
    final={**{k:v for k,v in known.items()if k not in removed},**updates,**new};order=patch['question_order']
    f.require(len(order)==len(set(order)) and set(order)==final.keys(),'Patch order must contain every surviving/new question exactly once')
    return {**patch['metadata'],'questions':[final[k]for k in order]}

def repair(n):
    f.require(n in (2,3),'Patch only follows the first complete correction')
    packet,_,_=f.verified();bank=f.read(f.OUT/f'bank-{n-1}.json');brief=f.read(f.OUT/'brief.json')
    ctx=f.context(packet,brief,bank)
    ctx.update(baselineIssues=f.read(f.OUT/'baseline-issues.json'),mapChanges=f.read(f.OUT/'brief-changes.json'),
        sourceAudit=f.read(f.OUT/f'audit-{n-1}.json'),medical=f.read(f.OUT/f'medical-{n-1}.json'),
        previous_visual_stimuli=f.read(f.OUT/f'stimuli-{n-1}.json'),validation=f.read(f.OUT/f'validation-{n-1}.json'),
        contractErrors=[],operatorScriptHash=f.sha(Path(__file__)),originalBudgetConsumed=3,followupRound=n,
        publicationAllowed=False,referenceManifest=f.read(f.OUT/'references/manifest.json'))
    prompt=f.g.PROMPTS.joinpath('repair.md').read_text(encoding='utf-8')+'\n'+f.g.item_quality_guidance()
    prompt+='''
This is the same explicitly authorized bounded followup, using delta output to preserve unchanged questions exactly.
Return the requested patch schema, overriding the old full-BANK output sentence. metadata contains the complete non-question BANK fields. question_updates are complete replacement questions only where an actual change is needed; new_questions require an independent goal and reason; removals require a specific preserved-content/duplicate rationale. question_order lists every surviving/new ID exactly once. Unmentioned questions are copied byte-for-byte as data, with no editorial rewrite by the orchestration code.
Address actual fresh source/medical findings and original20, not every optional expansion. A map relation can bundle several facts: a question mentioning some facts does not test its whole condition or direction answer_scope. Fix genuine required omissions and direct-recall gaps using existing questions first. Keep unsupported dose/time generalizations explicitly bounded; never turn uncertainty into fabricated clinical facts. Separate recalling what the lecture claims from endorsing it clinically in the actual stem, not only the explanation. Preserve raw earlier judgments; new reviews follow.
Actual original-source crop images are supported. visual_stimuli is the complete current set of model-authored normalized crops (source_id S1, page1..35, crop[left,top,right,bottom], reason). Inspect actual old stimuli and original pages; remove answer-label fragments without cutting structural information. Preserve explicit question-image order. Both independent source and tool-free medical review see the exact images. No arbitrary drawing, relabeling, or parent-authored clinical image interpretation occurs.
Reference E17/E18 are added official clinical labels for the two fresh missing-direct-evidence findings; read actual relevant sections. These do not widen lecture scope or require off-source dosing. Primary labels/research are clinical verification only. Do not claim historical aggregate counts from memory: actual baseline source rows are ok76/doubt12, baseline medical ok87/doubt1; previous new round values are in actual input artifacts.
'''
    patch=f.cli(f'repair-{n}',ctx,PATCH,prompt)
    value=replay(bank,patch);f.g.write(f.OUT/f'bank-{n}.json',value)
    stimuli=f.visual.render(patch['visual_stimuli'],value,packet,f.OUT,n);f.g.write(f.OUT/f'stimuli-{n}.json',stimuli)
    old={q['question_id']:q for q in bank['questions']};new={q['question_id']:q for q in value['questions']}
    changes={'beforeHash':f.g.document_hash(bank),'afterHash':f.g.document_hash(value),'beforeCount':len(old),'afterCount':len(new),
        'added':sorted(new.keys()-old.keys()),'removed':sorted(old.keys()-new.keys()),
        'changed':[{'question_id':k,'beforeHash':f.g.question_hash(old[k],bank),'afterHash':f.g.question_hash(new[k],value)}for k in old.keys()&new.keys()if old[k]!=new[k]],
        'orderChanged':[q['question_id']for q in bank['questions']]!=patch['question_order'],
        'authoredReasons':value['audit_summary'],'patchReasons':{k:patch[k]for k in ('question_updates','new_questions','removals')},
        'replayScriptHash':f.sha(Path(__file__))}
    f.g.write(f.OUT/f'changes-{n}.json',changes)
    validation=f.g.validate_bank(value,[s['id']for s in packet['sources']]);f.g.write(f.OUT/f'validation-{n}.json',validation)
    f.require(f.g.validate_bank(value,[s['id']for s in packet['sources']],check_quality=False)['pass'],'Patched BANK structural errors')
    print(json.dumps({'questions':len(new),'changed':len(changes['changed']),'added':changes['added'],'removed':changes['removed'],'validationPass':validation['pass']},ensure_ascii=False),flush=True)

def source(n):
    packet,_,_=f.verified();brief=f.read(f.OUT/'brief.json');bank=f.read(f.OUT/f'bank-{n}.json')
    ctx=f.context(packet,brief,bank);ctx.update(visualStimuli=f.read(f.OUT/f'stimuli-{n}.json'),operatorScriptHash=f.sha(Path(__file__)))
    prompt=f.g.PROMPTS.joinpath('source.md').read_text(encoding='utf-8')+'\n'+f.g.item_quality_guidance()
    prompt+='''
Important precision of the existing meaning contract: relation_id membership is not proof that every fact in a broad relation.condition is tested. For a composite relation, assign a direction_id only when that question actually retrieves all factual components of that relation needed by the direction cue/answer_scope. If it tests only part of a composite relation, preserve role=tested with direction_ids=[] and explain precisely what is tested and missing; do not award the whole direction from a partial subfact. With multiple relation_ids, independently assign only fully tested relations; code may then distinguish partial coverage. A whole-direction task requires the whole answer_scope in one question. Provided facts, reference-table presence, explanations and untested caveats are not recalled facts. Do not use unknown to hide a known missing required recall. This rule is generic, not a supplied clinical verdict. Review the actual bank/source/crops from scratch, with no prior source judgments supplied.
'''
    value=f.cli(f'source-{n}',ctx,f.source_assessment_schema(brief,bank),prompt)
    raw=f.envelope(brief,bank,value);f.g.write(f.OUT/f'assessment-{n}.json',raw)
    audit=f.compile_source_assessment(brief,bank,raw);f.g.write(f.OUT/f'audit-{n}.json',audit)
    doc=f.make_document(brief,bank,audit,revision=f'example-findings-{n}',title=packet['title'],exam_date=packet['examDate']);f.g.write(f.OUT/f'document-{n}.json',doc)
    print(json.dumps({'source':dict(f.Counter(r['verdict']for r in value['question_reviews'])),'issues':len(value['input_issues']),
        'tasks':len(doc['tasks']),'unready':[d['direction_id']for t in brief['targets']for d in t['directions']if d['direction_id']not in {x['direction_id']for x in doc['tasks']}]},ensure_ascii=False),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='repair':repair(int(sys.argv[2]))
    elif sys.argv[1]=='source':source(int(sys.argv[2]))
    else:raise SystemExit('repair/source ROUND')
