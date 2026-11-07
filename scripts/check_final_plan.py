"""Revision-bound code/origin/final visual proof checks; no authoring calls."""
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/_final-plan/261104_02';PY=ROOT/'.venv/Scripts/python.exe'

def run(args,cwd=ROOT):
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONPATH=str(ROOT),TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
    for k in('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(k,None)
    subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
        stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)

def check(mode):
    if mode=='regression':
        run([PY,'-m','pytest','tests/runner/test_root_plan_repair.py','tests/runner/test_root_chunked_review.py','tests/contracts',
            'tests/quizbank/test_generation_pipeline_v2.py','tests/quizbank/test_authoring_recovery.py','tests/quizbank/test_connection_generate.py',
            'tests/runner/test_root_tier_recovery.py','tests/runner/test_root_native_json.py','tests/runner/test_connection_generation.py',
            '-q','--tb=short','--basetemp','tmp/final-plan-regression'])
        for name in('root_reviewed_import','root_pipeline_v2','root_web_generation','root_parallel_generation'):
            run([ROOT/'server/.venv/Scripts/python.exe','-m','tests',name],ROOT/'server')
        return
    sys.path.insert(0,str(ROOT))
    from runner import root_plan_repair as r,root_native_json as n
    from studyez_contracts.roots import generation_v2 as c
    cap=r.origin_check(OUT);original=n.read(OUT/'repair-2.json')
    assert len(original['bank']['questions'])==91
    if mode=='origin':print(json.dumps({'prior22ReviewFilesUnchanged':True,'fileCount':len(cap['originInventory']),'originalQuestions':91}));return
    assert mode in('candidate','live','published')
    result=n.read(OUT/'result.json');packet=n.read(OUT/'packet.json');c.validate_result(result,packet);n.validate_all(OUT,result)
    bank=result['document']['bank_snapshot'];assert bank['questions']==original['bank']['questions']and result['brief']==original['brief']
    assert result['manifest']['repairRounds']==3 and len(bank['retrieval_plan'])==len(original['bank']['retrieval_plan'])+1
    images=[q for q in bank['questions']if q.get('stimuli')];assert len(images)==15
    for q in images:
        for s in q['stimuli']:
            body=base64.b64decode(s['png_base64']);assert hashlib.sha256(body).hexdigest()==s['sha256']
            assert (OUT/'material'/('stimulus-'+s['sha256']+'.png')).read_bytes()==body
    marker={'verified':True,'resultSha256':n.sha(OUT/'result.json'),'reviewProofHash':result['manifest']['planRepair']['proofHash'],
        'questions':91,'visualQuestions':15,'stimuli':19,'tasks':len(result['document']['tasks']),'repairRounds':3,
        'clinicalContentUnchanged':True,'originInventoryHash':cap['originInventoryHash']}
    (OUT/'checked-for-publication.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf-8')
    if mode in('live','published'):
        visual=n.read(OUT/'visual-check.json');assert visual['verified']and visual['productionWrites']==0 and visual['sourceLinkVerified']
        assert visual['sourcePdfSha256']==packet['sources'][0]['sha256']and not visual['jsErrors']
    if mode=='published':assert n.read(OUT/'publication-receipt.json')['publishedVerified']
    status=n.read(OUT/'chunked-status.json');status['states']['publication'].update(stage='applied'if mode=='published'else'waiting-existing-job',error='')
    from quizbank.connection_generate import write
    write(OUT/'chunked-status.json',status);print(json.dumps(marker))

if __name__=='__main__':check(sys.argv[1])
