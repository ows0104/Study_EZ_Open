"""Last bounded content correction, including one reported reference-only fix."""
import sys,json
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import followup as f
import round_patch as p
from studyez_contracts.learning_links.schema import obj,arr,enum,TEXT

FIX=obj(direction_id=enum('D24'),expected_relation_ids=arr(TEXT,1),relation_ids=arr(TEXT,1),reason=TEXT)
SCHEMA=obj(**{**p.PATCH['properties'],'direction_relation_fixes':arr(FIX)})

def apply_refs(brief,fixes):
    value=deepcopy(brief);directions={d['direction_id']:d for t in value['targets']for d in t['directions']};seen=set()
    for fix in fixes:
        did=fix['direction_id'];f.require(did=='D24'and did not in seen,'Unapproved/duplicate direction correction');seen.add(did)
        direction=directions[did]
        f.require(direction['relation_ids']==fix['expected_relation_ids'],'Stale direction correction')
        f.require(fix['relation_ids']and set(fix['relation_ids'])<=set(direction['relation_ids']),'Reference-only correction cannot add/invent facts')
        for rid in set(direction['relation_ids'])-set(fix['relation_ids']):
            f.require(any(rid in d['relation_ids']and d['requirement']=='required'for key,d in directions.items()if key!=did),'Correction would erase a required fact from the plan')
        direction['relation_ids']=fix['relation_ids']
    return value

def run():
    packet,_,_=f.verified();bank=f.read(f.OUT/'bank-2.json');brief=f.read(f.OUT/'brief.json');ctx=f.context(packet,brief,bank)
    ctx.update(baselineIssues=f.read(f.OUT/'baseline-issues.json'),mapChanges=f.read(f.OUT/'brief-changes.json'),
        sourceAudit=f.read(f.OUT/'audit-2.json'),medical=f.read(f.OUT/'medical-2.json'),
        previous_visual_stimuli=f.read(f.OUT/'stimuli-2.json'),validation=f.read(f.OUT/'validation-2.json'),contractErrors=[],
        operatorScriptHash=f.sha(Path(__file__)),followupRound=3,maxFollowupRounds=3,publicationAllowed=False,
        referenceOnlyCorrectionCandidate={'direction_id':'D24','diagnosis':f.read(f.OUT/'audit-2.json')['input_issues'][9]})
    prompt=f.g.PROMPTS.joinpath('repair.md').read_text(encoding='utf-8')+'\n'+f.g.item_quality_guidance()+'''
This is the FINAL third bounded content correction. Return the delta schema: complete non-question metadata, only changed/new complete questions with reasons, explicit removals, full final question_order and complete visual_stimuli set. Unchanged questions are copied exactly by code. Do not chase doubt0 or add every optional extension.
Prioritize actual required gaps in the fresh source audit, first-learning prerequisites/order and original20/3directions. Use existing questions first, reorganize overloaded comparisons instead of appending many near-duplicates. Genuine new basic retrieval objectives can be added with independent goal/reason. Preserve supported learning content and record every merge/deletion. The original unready directions were D10/D15/D17: where supported replacement directions exist, address their actual direct-recall omissions, retaining historical/clinical caveats. Never invent per-drug exact times or unverified clinical superiority. The remaining Q077 medical uncertainty is preserved, not edited away solely to get ok.
Actual source crops are displayed and attached to blind medical review. Any image-reading question must include authored source_id/page/normalized crop records and inspect those exact structures; text formulas or answer names in the stem cannot replace visual reading. Crops must show needed structure without answer annotations. Do not add drug-name identification beyond a general structure criterion unless the goal requires it.
The source audit separately identifies a reference-only mismatch in D24. The fixed cue/answer_scope may not require a relation merely provided by the stem. Only for that reported D24 you may author direction_relation_fixes, giving expected_relation_ids, corrected subset relation_ids and source-based reason. Do not change its cue/answer_scope/requirement, any clinical relation condition, point text/scope, sources or other directions. Do not remove a fact from the overall learning plan or weaken an actually required recall to improve coverage. This small binding correction is explicit post-extraction metadata, not a claim that the original independent extraction saw questions. The new source audit independently rechecks it.
Read relevant actual primary reference passages for clinical corrections. Extra reference dosing is not automatically curriculum. Source-only diagnostic/definition requests must ask the actual fact with clear historical/uncertainty conditions, not generic instructions to verify a source. Return only the patch JSON.
'''
    patch=f.cli('repair-3',ctx,SCHEMA,prompt);value=p.replay(bank,patch);new_brief=apply_refs(brief,patch['direction_relation_fixes'])
    f.validate_brief(new_brief,brief['sources'],from_sources=True)
    f.g.write(f.OUT/'brief-before-direction-fix.json',brief);f.g.write(f.OUT/'brief.json',new_brief)
    changes=f.read(f.OUT/'brief-changes.json');changes['directionReferenceFixes']={'fixes':patch['direction_relation_fixes'],
        'beforeHash':f.g.document_hash(brief),'afterHash':f.g.document_hash(new_brief),'operatorScriptHash':f.sha(Path(__file__)),
        'provenance':'Explicit model-authored reference-only correction after independent source extraction; source point texts/scope/clinical facts unchanged.'}
    f.g.write(f.OUT/'brief-changes.json',changes);f.g.write(f.OUT/'bank-3.json',value)
    stimuli=f.visual.render(patch['visual_stimuli'],value,packet,f.OUT,3);f.g.write(f.OUT/'stimuli-3.json',stimuli)
    old={q['question_id']:q for q in bank['questions']};new={q['question_id']:q for q in value['questions']}
    edits={'beforeHash':f.g.document_hash(bank),'afterHash':f.g.document_hash(value),'beforeCount':len(old),'afterCount':len(new),
        'added':sorted(new.keys()-old.keys()),'removed':sorted(old.keys()-new.keys()),
        'changed':[{'question_id':k,'beforeHash':f.g.question_hash(old[k],bank),'afterHash':f.g.question_hash(new[k],value)}for k in old.keys()&new.keys()if old[k]!=new[k]],
        'orderChanged':[q['question_id']for q in bank['questions']]!=patch['question_order'],
        'authoredReasons':value['audit_summary'],'patchReasons':{k:patch[k]for k in ('question_updates','new_questions','removals')},'replayScriptHash':f.sha(Path(__file__))}
    f.g.write(f.OUT/'changes-3.json',edits);validation=f.g.validate_bank(value,[s['id']for s in packet['sources']]);f.g.write(f.OUT/'validation-3.json',validation)
    f.require(f.g.validate_bank(value,[s['id']for s in packet['sources']],check_quality=False)['pass'],'Final BANK structural error')
    print(json.dumps({'questions':len(new),'added':edits['added'],'removed':edits['removed'],'changed':len(edits['changed']),
        'referenceFixes':patch['direction_relation_fixes'],'validationPass':validation['pass']},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
