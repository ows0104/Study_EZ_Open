"""One explicitly authorized clinical pathology pilot; no production writes."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from quizbank import connection_generate as g
from runner.root_native_json import NativeJson,validate_all,require_unblocked
from runner.parallel_status import register,refresh
from studyez_contracts.roots.automation import packet_hash,validate_result
from studyez_contracts.roots import generation_v2 as c

ORIGINAL=Path('C:/Users/ows01/Desktop/2026-2/9. 감염과 면역/필기복습/[261104_02] 감염성 질환의 병리 1(김지은)_박준원v2.pdf')
OUT=ROOT/'runs/_parallel-pilot/261104_02'


def prepare():
    assert not OUT.exists(),'Preserve prior trial; never reset the attempt'
    OUT.mkdir(parents=True);source=OUT/'source.pdf';shutil.copy2(ORIGINAL,source)
    body=source.read_bytes();digest=hashlib.sha256(body).hexdigest()
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==digest
    packet={'generationId':'pilot-261104-02','revision':'cli-parallel-pilot-261104-02','subject':'감염과 면역','runId':'261104_02',
        'title':'감염성 질환의 병리 1','owner':'local-pilot','privatePilot':True,'authoring':'cli','parallelAuthoring':True,
        'inputMode':'source','conceptMap':'','points':'','examDate':None,'sourceAssessmentFormat':c.VERSION,
        'scope':'사용자 지정 박준원v2 올해 필기 원본 전체. 원본의 교수 강조·범위·제외·연도/타교수 구분을 보존한다. 별도 족보 PDF는 제공되지 않았다. 사진·병리 소견의 실제 시각 식별 목표를 포함한다. 운영 은행 및 학습 기록을 변경하지 않는 격리 실험.',
        'sources':[{'id':'S1','assetId':'local-pathology-1','kind':'notes_current','filename':ORIGINAL.name,
            'localPath':str(source.resolve()),'sizeBytes':len(body),'sha256':digest}]}
    packet['inputHash']=packet_hash(packet);g.write(OUT/'packet.json',packet)
    sources=g.prepare(packet,OUT/'material')
    from quizbank.connection_figures import prepare as figures
    catalog=figures(packet,OUT/'material')
    register(ROOT,OUT,Path(__file__),OUT/'pilot.log')
    # Also appears in the already-open runner rooted at the original project.
    project=ROOT.parents[1]
    if (project/'runs').is_dir():register(project,OUT,Path(__file__),OUT/'pilot.log')
    (OUT/'pilot-metadata').mkdir(exist_ok=True)
    g.write(OUT/'pilot-metadata'/'preflight.json',{'sourceSha256':digest,'inputHash':packet['inputHash'],'pages':sources[0]['page_count'],
        'embeddedCandidates':len(catalog['images']),'modelCalls':0,'productionWrites':0,
        'deferredMapTrial':'[261105_1] 사슬알균(김범준)_배수성v1'})
    print(json.dumps({'prepared':str(OUT),'pages':sources[0]['page_count'],'embeddedCandidates':len(catalog['images'])},ensure_ascii=False))


def run():
    packet=json.loads((OUT/'packet.json').read_text(encoding='utf-8'))
    require_unblocked(OUT)
    (OUT/'pilot-metadata').mkdir(exist_ok=True)
    g.write(OUT/'pilot-metadata'/('started-'+str(time.time_ns())+'.json'),{'pid':os.getpid(),'startedAt':time.time(),'inputHash':packet['inputHash'],'command':'pilot.py --run'})
    try:
        result=g.run(packet,OUT,invoke=NativeJson(OUT))
        validate_all(OUT,result);validate_result(result,packet)
        bank=result['document']['bank_snapshot'];images=[q for q in bank['questions']if q.get('stimuli')]
        if not images:raise ValueError('No accepted visual question; pilot criterion not met')
        summary={'completed':True,'questionCount':len(bank['questions']),'visualQuestionCount':len(images),
            'taskCount':len(result['document']['tasks']),'repairRounds':result['manifest']['repairRounds'],
            'sourceReviews':result['sourceAudit']['question_checks'],'medicalReviews':result['medical'],
            'productionWrites':0,'status':'local-validated','finishedAt':time.time()}
        g.write(OUT/'summary.json',summary);refresh(OUT,'local-ready')
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    except BaseException as error:
        g.write(OUT/'pilot-metadata'/('failure-'+str(time.time_ns())+'.json'),{'type':type(error).__name__,'error':str(error),'automaticRetry':False,'at':time.time()})
        refresh(OUT,'failed',str(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true');a=p.parse_args()
    if a.prepare:prepare()
    elif a.run:run()
    else:p.error('Choose --prepare or --run')
