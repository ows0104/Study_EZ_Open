"""Display stored authored content and review results; never authors medicine."""
import base64,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from studyez_contracts.bank.cloze import normalize_cloze
OUT=ROOT/'runs/_examples/cholinergic-findings-20261104'
VIS=Path('C:/Users/ows01/.codex/visualizations/2026/11/03/01a19f97-9412-7273-bf02-f60649c4c87c')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    value=read(OUT/'result.json');brief=value['brief'];presentation=read(OUT/'presentation-audit.json')
    data={'summary':value['summary'],'concepts':brief['concepts'],'relations':brief['relations'],'targets':brief['targets'],'points':brief['points'],
        'questions':[{**{k:q[k] for k in ('question_id','question','answer','explanation','options','source_refs','format')},
            'displayQuestion':normalize_cloze(q)['question']} for q in value['bank']['questions']],
        'sourceReviews':value['sourceAudit']['question_checks']['reviews'],'medicalReviews':value['medical']['reviews'],
        'directionChecks':value['sourceAssessment']['assessment']['direction_checks'],
        'coverage':value['sourceAudit']['review']['coverage'],'tasks':presentation['reviewedTasks'],'sourceTasks':value['document']['tasks'],'presentation':presentation,
        'resolution':value['resolution'],'baselineIssues':read(OUT/'baseline-issues.json'),
        'inputIssues':value['sourceAudit']['input_issues'],'sources':brief['sources'],'scope':brief['scope'],
        'visualStimuli':[{**s,'dataUrl':'data:image/png;base64,'+base64.b64encode((OUT/'material'/s['imageFile']).read_bytes()).decode('ascii')}for s in value['visualStimuli']],
        'unadoptedPrerequisites':value['technicalRecoveryProof']['unadoptedPrerequisiteProposals']}
    body=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    template=VIS/'cholinergic-corrected.template.html';target=VIS/'cholinergic-corrected.html'
    text=template.read_text(encoding='utf-8');assert text.count('__CHOLINERGIC_CORRECTED_DATA__')==1
    text=text.replace('__CHOLINERGIC_CORRECTED_DATA__',body);assert len(text.encode('utf-8'))<1024*1024
    target.write_text(text,encoding='utf-8')
    proof={'resultHash':hashlib.sha256((OUT/'result.json').read_bytes()).hexdigest(),
        'templateHash':hashlib.sha256(template.read_bytes()).hexdigest(),'previewHash':hashlib.sha256(target.read_bytes()).hexdigest(),
        'preview':str(target),'dataCounts':{k:len(data[k]) for k in ('concepts','targets','questions','tasks')},
        'builderHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'preview-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False))
if __name__=='__main__':main()
