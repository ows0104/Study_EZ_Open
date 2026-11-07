"""Owned regression and real frozen-review evidence checks; no model calls."""
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/_chunked/261104_02'
PY=ROOT/'.venv/Scripts/python.exe'

def run(args,cwd=ROOT):
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONPATH=str(ROOT),TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
    for k in('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(k,None)
    subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
        stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)

def check(mode):
    if mode=='regression':
        run([PY,'-m','pytest','tests/runner/test_root_chunked_review.py','tests/contracts','tests/quizbank/test_generation_pipeline_v2.py',
            'tests/quizbank/test_authoring_recovery.py','tests/quizbank/test_connection_generate.py','tests/runner/test_root_tier_recovery.py',
            'tests/runner/test_root_native_json.py','tests/runner/test_connection_generation.py','-q','--tb=short','--basetemp','tmp/chunk-final'])
        for name in('root_reviewed_import','root_pipeline_v2','root_web_generation','root_parallel_generation'):
            run([ROOT/'server/.venv/Scripts/python.exe','-m','tests',name],ROOT/'server')
        return
    sys.path.insert(0,str(ROOT))
    from runner.root_chunked_review import validate_origin
    from runner.root_native_json import read,validate_all
    from studyez_contracts.roots import generation_v2 as c
    cap=validate_origin(OUT)
    assert len(read(OUT/'repair-2.json')['bank']['questions'])==91 and cap['priorLedger']['repairRounds']==2
    if mode=='origin':print(json.dumps({'originalFilesUnchanged':True,'fileCount':len(cap['inventory']),'repairRounds':2}));return
    assert mode in('candidate','live','published')
    result=read(OUT/'result.json');packet=read(OUT/'packet.json')
    c.validate_result(result,packet);validate_all(OUT,result)
    images=[q for q in result['document']['bank_snapshot']['questions']if q.get('stimuli')]
    assert len(result['document']['bank_snapshot']['questions'])==91 and result['manifest']['repairRounds']==2 and images
    for q in images:
        for s in q['stimuli']:
            body=base64.b64decode(s['png_base64']);assert hashlib.sha256(body).hexdigest()==s['sha256']
            assert (OUT/'material'/('stimulus-'+s['sha256']+'.png')).read_bytes()==body
    marker={'verified':True,'resultSha256':hashlib.sha256((OUT/'result.json').read_bytes()).hexdigest(),
        'reviewProofHash':result['manifest']['chunkedReview']['proofHash'],'questions':91,'visualQuestions':len(images),
        'tasks':len(result['document']['tasks']),'repairRounds':2,'originInventoryHash':cap['inventoryHash']}
    (OUT/'checked-for-publication.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf-8')
    if mode in('live','published'):
        visual=read(OUT/'visual-check.json')
        assert visual['verified']and visual['productionWrites']==0 and visual['sourceLinkVerified']
        assert visual['sourcePdfSha256']==packet['sources'][0]['sha256']and not visual['jsErrors']
    if mode=='published':assert read(OUT/'publication-receipt.json')['publishedVerified']
    status=read(OUT/'chunked-status.json')
    status['states']['publication']={'title':packet['title']+' · 이미지 확인·업로드','subject':packet['subject'],
        'stage':'applied'if mode=='published'else'waiting-existing-job','error':''}
    from quizbank.connection_generate import write
    write(OUT/'chunked-status.json',status)
    print(json.dumps(marker))

if __name__=='__main__':check(sys.argv[1])
