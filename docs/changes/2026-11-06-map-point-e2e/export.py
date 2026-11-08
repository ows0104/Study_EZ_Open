"""Export verified study artifacts; no PDFs or learner histories in the bundle."""
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile,ZIP_DEFLATED
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from experiment import OUT,read,sha

DEST=Path('C:/Users/ows01/.codex/visualizations/2026/11/05/01a1abe7-b685-7e30-b1bd-af49646c0cca')/'study-e2e'

def export():
    seal=read(OUT/'generation-verification.json')
    recovery=read(OUT/'recovery-evidence/final-verification.json')
    assert {r['slug']for r in seal['results']}=={'cns-infection'}
    assert next(r for r in recovery['results']if r['slug']=='endocarditis')['status']=='held-invalid-bank'
    DEST.mkdir(exist_ok=True);files=[]
    for row in seal['results']:
        slug=row['slug'];folder=DEST/slug;folder.mkdir(exist_ok=True)
        assert sha(OUT/slug/'result.json')==row['resultSha256']
        result=read(OUT/slug/'result.json')
        for name,data in [('bank.json',result['document']['bank_snapshot']),
                          ('learning.json',result['document']),
                          ('review.json',{'sourceAudit':result['sourceAudit'],'medical':result['medical']})]:
            path=folder/name;path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');files.append(path)
        for name in ('concept-map.json','exam-points.json'):
            path=folder/name;path.write_bytes((OUT/'inputs'/slug/name).read_bytes());files.append(path)
    held=DEST/'endocarditis';held.mkdir(exist_ok=True)
    authored=read(OUT/'endocarditis/repair-2.json')
    held_data={'status':'held-invalid-bank','allowedForLearning':False,'repairRounds':3,
        'reason':'Different concepts share C001/C012; final bank validation failed. Repair budget exhausted.',
        'bank':authored['bank'],'sourceAudit':read(OUT/'endocarditis/source-2.json'),
        'medical':read(OUT/'endocarditis/medical-2.json')}
    path=held/'held-draft-and-review.json'
    path.write_text(json.dumps(held_data,ensure_ascii=False,indent=2),encoding='utf-8');files.append(path)
    summary={'localExperiment':True,'productionChanged':False,'completeBothLectures':False,
        'results':seal['results'],'heldLectures':[r for r in recovery['results']if r['status']!='ready'],
        'files':{p.relative_to(DEST).as_posix():sha(p)for p in files},
        'notes':['Generated question totals differ from prepared learning tasks.',
                 'Unresolved source or medical doubts are preserved; all goals are not certified complete.',
                 'Learning records are kept in the separate local experiment database.']}
    path=DEST/'summary.json';path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');files.append(path)
    archive=DEST.parent/'study-e2e.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED)as z:
        for path in files:z.write(path,path.relative_to(DEST))
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'files':len(files)},ensure_ascii=True))

if __name__=='__main__':export()
