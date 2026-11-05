"""Same once-only final stage with relevant original lineage, avoiding redundant banks.

No medical output edits: the final independent model authors all dispositions.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import exception as e
f=e.f

def main():
    e.configure();packet,base,_=e.verified();brief=f.read(e.OUT/'brief.json');bank=f.read(e.OUT/'bank-4.json')
    ctx=f.context(packet,brief,bank)
    # Original target definitions and issue texts are needed; a second full bank,
    # duplicate compiled audits and old medical tables are not inputs to this judge.
    baseline={'brief':base['brief'],'summary':base['summary']}
    ctx.update(authorization=e.AUTH,baselineIssues=f.read(e.OUT/'baseline-issues.json'),
        originalBaseline=baseline,priorResolution=f.read(e.OLD/'resolution.json'),
        priorConservativeAdoption=f.read(e.OLD/'presentation-audit.json'),questionChanges=f.read(e.OUT/'changes-4.json'),
        sourceAudit=f.read(e.OUT/'audit-4.json'),medical=f.read(e.OUT/'medical-4.json'),
        sourceReviewAdoption=f.read(e.OUT/'source-review-adoption.json'),
        currentTasks=f.read(e.OUT/'document-4.json')['tasks'],visualStimuli=f.read(e.OUT/'stimuli-4.json'),
        technicalEvidence=f.read(e.OLD/'presentation-audit.json')['technicalEvidence'],
        orchestration={'scriptHash':f.sha(Path(__file__)),'originalBaselineHash':f.sha(f.BASE/'assembled-result.json'),
            'originalBaselineIncludedFields':['brief','summary'],'reason':'Original goal definitions and issue history preserved; duplicate original bank/audits omitted to keep independent current-result review focused. No correction or reviewer verdict changed.'})
    value=f.cli('resolve-4',ctx,e.FINAL,(e.HERE/'resolve.md').read_text(encoding='utf-8'))
    dirs={d['direction_id']for t in brief['targets']for d in t['directions']};rows=value['direction_decisions']
    f.require(len(rows)==len(dirs)and {x['direction_id']for x in rows}==dirs,'Each current direction requires one semantic decision')
    f.require(len(value['approved_items'])==6 and len({r['item']for r in value['approved_items']})==6,'Missing approved-item disposition')
    f.require(len(value['resolution']['issues'])==20 and {r['issue_id']for r in value['resolution']['issues']}=={f'I{i:02}'for i in range(1,21)},'Missing original20')
    f.require(len(value['resolution']['directions'])==3 and {r['original_direction_id']for r in value['resolution']['directions']}=={'D10','D15','D17'},'Missing original3')
    known={q['question_id']for q in bank['questions']}
    for r in rows:f.require(set(r['question_ids'])<=known,'Unknown decision question')
    f.g.write(e.OUT/'adjudication.json',value);f.g.write(e.OUT/'resolution.json',value['resolution'])
    print(json.dumps({'approvedItems':value['approved_items'],'ready':sum(r['ready']for r in rows)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
