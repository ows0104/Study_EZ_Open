"""Read-only comparison export and evidence checks; no model or DB writes."""
import json
from pathlib import Path
import sys
from zipfile import ZipFile,ZIP_DEFLATED
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from pilot import OUT,PRIOR,ROOT,MAIN,MODEL,read,sha,c,document_hash,validate_stage
from studyez_contracts.bank.cloze import normalize_cloze
from studyez_contracts.roots.recall_units import prepared_coverage

DEST=Path('C:/Users/ows01/.codex/visualizations/2026/11/05/01a1abe7-b685-7e30-b1bd-af49646c0cca')/'recall-comparison'

def export():
    authored=read(OUT/'authored.json');before=read(OUT/'before.json')
    audit=read(OUT/'source-audit.json')if (OUT/'source-audit.json').exists()else None
    medical=read(OUT/'medical.json')if (OUT/'medical.json').exists()else {'reviews':[]}
    rows=authored['bank']['questions'];groups=[]
    for title,old,did in [('병원체와 경과','Q012','D012'),('두개내압 증상','Q019','D019'),('CSF 비교','Q032','D032')]:
        oldq=next(q for q in before if q['question_id']==old)
        chosen={q['question_id']for q in rows if q['concept_id']==oldq['concept_id']}
        groups.append({'title':title,'before':[normalize_cloze(oldq)],
            'after':[normalize_cloze(q)for q in rows if q['question_id']in chosen]})
    assert set(q['question_id']for g in groups for q in g['after'])=={q['question_id']for q in rows}
    data={'groups':groups,'medical':medical,'design':audit['assessment']['assessment']['design_checks']if audit else[],
        'pendingReview':not (OUT/'document.json').exists()}
    (OUT/'comparison-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    DEST.mkdir(exist_ok=True)
    for name,value in [('comparison.json',data),('bank.json',authored['bank']),('brief.json',authored['brief'])]:
        (DEST/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    if audit and (OUT/'document.json').exists():
        (OUT/'prepared-goals.json').write_text(json.dumps(prepared_coverage(audit,read(OUT/'document.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('source-audit.json','medical.json','document.json','prepared-goals.json','verification.json','authoring-reference-projection.json'):
        if (OUT/name).exists():(DEST/name).write_bytes((OUT/name).read_bytes())
    archive=DEST.parent/'recall-comparison.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED)as z:
        for path in sorted(DEST.glob('*.json')):z.write(path,path.name)
    print(json.dumps({'groups':[(g['title'],len(g['after']))for g in groups],
        'pendingReview':data['pendingReview'],'archive':str(archive)},ensure_ascii=True))

def verify():
    preserved=read(OUT/'preservation.json');ledger=read(OUT/'trial-ledger.json')
    assert sha(PRIOR/'result.json')==preserved['priorResultSha256']
    assert sha(PRIOR/'ledger.json')==preserved['priorLedgerSha256']
    assert sha(OUT/'before.json')==preserved['beforeSha256']
    assert all(sha(OUT/'material'/name)==digest for name,digest in preserved['materials'].items())
    assert ledger['oldRepairRounds']==3 and ledger['authorCalls']==1 and ledger['repairCalls']==0
    for name,entry in ledger['stages'].items():
        assert entry['status']=='completed';validate_stage(OUT,{'name':name,**entry},model=MODEL)
    assert set(ledger['stages'])=={'repair-1','source-0','medical-0'}
    a=read(OUT/'authored.json');raw=read(OUT/'repair-1.raw.json');projection=read(OUT/'authoring-reference-projection.json')
    assert document_hash(raw)==projection['rawHash']and document_hash(a)==projection['acceptedHash']
    replay=json.loads(json.dumps(raw))
    for change in projection['changes']:
        t=next(t for t in replay['brief']['targets']if t['target_id']==change['target_id'])
        assert t['relation_ids']==change['before'];t['relation_ids']=change['after']
    assert replay==a and raw['bank']==a['bank']and projection['modelCalls']==0
    c.validate_authoring(a,read(OUT/'author-context.json')['previousAuthoring'])
    audit=read(OUT/'source-audit.json');c.validate_audit(a['brief'],a['bank'],audit)
    doc=c.make_document(a['brief'],a['bank'],audit,revision='recall-three-261106',title='CNS 세 문항 비교',exam_date=None,medical=read(OUT/'medical.json'))
    assert doc==read(OUT/'document.json')
    assert len(a['bank']['questions'])==8 and any('|'in q['question']and q['format']=='cloze'for q in a['bank']['questions'])
    assert all(q['question_id'].startswith('RU')for q in a['bank']['questions'])
    assert sha(ROOT/'content/prompts/bank/bankPrompt.md')==sha(MAIN/'content/prompts/bank/bankPrompt.md')
    for path,digest in read(OUT/'ui-checks.json').items():assert sha(ROOT/path)==digest,'UI source changed after real renderer/type checks'
    report={'oldQuestions':3,'newQuestions':8,'preparedTasks':len(doc['tasks']),
        'sourceGoalCoverage':audit['goal_coverage'],'design':audit['assessment']['assessment']['design_checks'],
        'preparedGoalCoverage':prepared_coverage(audit,doc),
        'medical':read(OUT/'medical.json')['counts'],'originalRunAndQuestionsPreserved':True,
        'oldRepairBudgetUntouched':True,'productionChanged':False,'ui':'Existing Main Quiz QuestionBody/AnswerBody with table/cloze support'}
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':{'export':export,'verify':verify}[sys.argv[1]]()
