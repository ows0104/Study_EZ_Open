"""Check persisted real UI events, never create a learner assessment."""
import json
import sqlite3
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from experiment import OUT,LECTURES,write

def verify():
    db=sqlite3.connect('file:'+str(OUT/'local-app/study.db')+'?mode=ro',uri=True)
    rows=db.execute('SELECT user_id,run_id,kind,payload FROM root_event ORDER BY created_at').fetchall()
    assert not any(r[0]=='learner'for r in rows),'Human learner history must remain separate and untouched before handoff'
    results=[]
    ready={r['slug']for r in json.loads((OUT/'generation-verification.json').read_text(encoding='utf-8'))['results']}
    assert ready=={'cns-infection'},'This trial ended with CNS ready and endocarditis held; review changed readiness explicitly'
    for slug,*_ in LECTURES:
        if slug not in ready:continue
        events=[r for r in rows if r[0]=='technical-check'and r[1]==slug]
        kinds=[r[2]for r in events]
        assert 'reveal'in kinds and 'rate'in kinds and 'map'in kinds,(slug,kinds)
        for row in events:
            data=json.loads(row[3])
            if row[2]=='reveal':assert data['_request']['response'].startswith('기술 확인용'),data
            if row[2]=='rate':assert data['_request']['grade']=='missed',data
        results.append({'slug':slug,'technicalEvents':kinds,'humanEvents':0})
    write(OUT/'solve-verification.json',{'results':results,'actualAppAndPersistentDatabase':True,
        'humanLearningNotSimulated':True,'browserEvidence':'UI walkthrough and screenshots recorded separately.'})
    print(json.dumps(results,ensure_ascii=True))

if __name__=='__main__':verify()
