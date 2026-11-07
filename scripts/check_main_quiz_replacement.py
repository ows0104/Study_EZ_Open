"""Actual checks for the named replacement; never invokes a content model."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/_replacement/261104_02-v1'
PY=ROOT/'.venv/Scripts/python.exe'


def call(args,cwd=ROOT):
    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONPATH':str(ROOT)}
    env.pop('PYTHONHOME',None)
    subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def main(mode):
    if mode=='contracts':
        (ROOT/'tmp').mkdir(exist_ok=True)
        call([PY,'-m','pytest','tests/contracts','tests/runner/test_root_task_supplement.py','tests/runner/test_root_native_json.py',
            '-q','--tb=short','--basetemp','tmp/replacement-contracts']);return
    if mode=='server':
        for name in ('root_replacement_import','root_reviewed_import','main_quiz_entry','root_api','root_one_click'):
            call([ROOT/'server/.venv/Scripts/python.exe','-m','tests',name],ROOT/'server')
        return
    sys.path.insert(0,str(ROOT))
    from runner import root_task_supplement as r,root_native_json as n
    cap=r.origin_check(OUT)
    if mode=='origin':
        print(json.dumps({'unchangedHistoricalFiles':len(cap['originInventory']),'historicalRepairRounds':3,'newRunId':cap['replacementRunId']}));return
    value=r.validate(OUT);assert value['ready'],'Replacement is not fully prepared'
    bank=value['document']['bank_snapshot'];ids={q['question_id']for q in bank['questions']};tasks=value['document']['tasks']
    assert {t['question_id']for t in tasks}==ids and len(tasks)==len(ids)
    marker={'verified':True,'runId':value['runId'],'resultSha256':n.sha(OUT/'result.json'),'ready':True,'questions':len(ids),'tasks':len(tasks),
        'visualQuestions':sum(bool(q.get('stimuli'))for q in bank['questions']),'images':sum(len(q.get('stimuli',[]))for q in bank['questions']),
        'freshRepairRounds':value['repairRounds'],'historicalRepairRounds':3,'modelCalls':sum(len(row['execution'])for row in value['rounds'])}
    if mode in('live','published'):
        ui=n.read(OUT/'visual-check.json');assert ui['verified']and ui['productionWrites']==0 and not ui['jsErrors']and ui['sourceLinkVerified']
        assert ui['sourcePdfSha256']==n.read(OUT/'packet.json')['sources'][0]['sha256']
    if mode=='published':assert n.read(OUT/'publication-receipt.json')['publishedVerified']
    assert mode in('candidate','live','published')
    (OUT/'checked-for-publication.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(marker,ensure_ascii=False))


if __name__=='__main__':main(sys.argv[1])
