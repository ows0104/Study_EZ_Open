"""Explicit two-lecture experiment. Never opens production storage or queues."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT.parents[1] / 'runs/_e2e/26110507'
RUNTIME_ROOT=ROOT
if (OUT/'runtime-selection.json').exists():
    selected=json.loads((OUT/'runtime-selection.json').read_text(encoding='utf-8'))
    allowed=[ROOT.parent/name for name in ('root-authoring-recovery','root-tier-transport')]
    candidates=[path for path in allowed if Path(selected['root']).resolve()==path.resolve()]
    assert len(candidates)==1,'Unexpected experiment runtime'
    RUNTIME_ROOT=candidates[0]
sys.path.insert(0, str(RUNTIME_ROOT))
from studyez_contracts.roots.automation import packet_hash, validate_result

PRIOR = ROOT.parent / 'map-point-prompts/runs/_map-point-pilot/2026-11-06-261105_07'
REFINED = PRIOR.with_name(PRIOR.name + '-point-granularity')
LECTURES = [('endocarditis', '감염 심내막염', 2, 29, 47),
            ('cns-infection', '중추신경계감염', 30, 58, 60)]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, value): p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def prepare():
    assert not OUT.exists(), 'Existing experiment is preserved, never reset'
    OUT.mkdir(parents=True)
    inputs = OUT / 'inputs'; inputs.mkdir()
    expected = {'S1.pdf':'13da0b35f473f309d00af4120d03fb5a9fc315159cbee87f7d43e3376caa920c',
                'S2.pdf':'4f4b12276147dc4e87e56bb778682eb8629984e2e73b4a2e5204fcdec7243d9f'}
    manifest = []
    inventory = read(PRIOR/'point/input.json')['sources']
    for sid in ('S1', 'S2'):
        p = PRIOR/'material'/(sid+'.pdf')
        assert sha(p) == expected[p.name]
        shutil.copy2(p, inputs/p.name)
    for slug, title, first, last, count in LECTURES:
        folder=inputs/slug; folder.mkdir()
        for src, name in [(PRIOR/'map'/slug/'concept-map.json','concept-map.json'),
                          (REFINED/'repair-run/point'/slug/'exam-points.json','exam-points.json')]:
            shutil.copy2(src,folder/name)
            manifest.append({'path':str((folder/name).relative_to(OUT)),'sha256':sha(src),'origin':str(src)})
        points=read(folder/'exam-points.json'); assert len(points['points'])==count and points['title']==title
        run=OUT/slug;run.mkdir()
        sources=[]
        for sid in ('S1','S2'):
            p=inputs/(sid+'.pdf');original=next(s for s in inventory if s['source_id']==sid)
            sources.append({'id':sid,'filename':original['label'],'kind':'jokbo'if sid=='S2'else'notes_current',
                'sha256':sha(p),'sizeBytes':p.stat().st_size,'localPath':str(p)})
        scope=(f'두 강의 합본 중 {title}만. S1 물리{first}~{last}쪽, 1쪽은 공통 안내. '
               'S2는 전체13쪽에서 이 강의 주제 문항만 선택하며 합본 원본 물리쪽을 유지한다. '
               'conceptMap과 points는 이미 원본에서 별도로 추출한 파일이다. 이번 단계는 제공 결과의 '
               '학습 구조 정규화이므로 derived로 표시한다. 제공 points의 point_id 및 point 원문과 '
               'source_refs를 보존하여 point_id/text/evidence에 연결한다. 원본 충돌·제외·불확실성 notes를 보존한다. '
               '문항수는 실제 인출/판단 가치로 정하며 포인트 개수와 일대일로 강제하지 않는다. '
               '같은 원본/포인트 전체와 목록 밖 누락을 검수하고 실제 답한 연결·제공된 연결·해설을 구분한다.')
        packet={'subject':'map-point-e2e','runId':slug,'title':title,'scope':scope,
                'conceptMap':(folder/'concept-map.json').read_text(encoding='utf-8'),
                'points':(folder/'exam-points.json').read_text(encoding='utf-8'),
                'examDate':None,'revision':'e2e-26110507-'+slug,'sources':sources,
                'sourceAssessmentFormat':'source-assessment/2','inputMode':'provided','authoring':'cli'}
        packet['inputHash']=packet_hash(packet);write(run/'packet.json',packet)
        manifest.append({'path':str((run/'packet.json').relative_to(OUT)),'sha256':sha(run/'packet.json')})
    for name in expected: manifest.append({'path':'inputs/'+name,'sha256':expected[name]})
    write(OUT/'input-manifest.json',{'files':manifest,'originOutputsUntouched':True,
          'authorization':'Current user explicitly requested question generation and solving E2E from these approved two-lecture source/Map/final points.',
          'productionGeneration548Untouched':True})
    check_inputs()

def check_inputs():
    for row in read(OUT/'input-manifest.json')['files']:
        assert sha(OUT/row['path'])==row['sha256'],row['path']
        if 'origin'in row:assert sha(Path(row['origin']))==row['sha256']
    for slug,title,first,last,count in LECTURES:
        p=read(OUT/slug/'packet.json');assert p['inputHash']==packet_hash(p)
        points=read(OUT/'inputs'/slug/'exam-points.json')
        assert len(points['points'])==count and points['title']==title
        for item in points['points']:
            for ref in item['source_refs']:
                if ref['source_id']=='S1':assert all(n==1 or first<=n<=last for n in ref['pages'])
    print('Verified frozen sources, Maps and 47/60 points; prior outputs preserved.',flush=True)

def check_results(require_all=True):
    from runner.root_native_json import validate_all
    check_inputs();results=[]
    for slug,title,first,last,count in LECTURES:
        run=OUT/slug
        if not require_all and not(run/'result.json').exists():continue
        packet=read(run/'packet.json');result=read(run/'result.json')
        validate_result(result,packet);validate_all(run,result)
        initial=result['manifest']['initialBrief'];final=result['brief']
        original=read(OUT/'inputs'/slug/'exam-points.json')
        expected={p['point_id']:p['point']for p in original['points']}
        expected_refs={p['point_id']:p['source_refs']for p in original['points']}
        def ref_pages(refs):
            return {(r['source_id'],page)for r in refs for page in r['pages']}
        for b in (initial,final):
            actual={p['point_id']:p['text']for p in b['points']}
            assert all(actual.get(k)==v for k,v in expected.items()),'Supplied point identity/text changed'
            assert b['provenance']['independent_points']=='derived'
            for point in b['points']:
                if point['point_id']in expected:
                    refs=expected_refs[point['point_id']]
                    assert ref_pages(refs)<=ref_pages(point['evidence']),'Supplied point source/page dropped'
                    for ref in refs:
                        if ref['locator']:
                            assert any(ref['source_id']==e['source_id']and ref['locator']in(e['locator']or'')
                                for e in point['evidence']),'Supplied locator information dropped'
        doc=result['document'];assert doc['tasks']
        results.append({'slug':slug,'title':title,'points':count,'questions':len(doc['bank_snapshot']['questions']),
            'tasks':len(doc['tasks']),'repairRounds':result['manifest']['repairRounds'],
            'resultSha256':sha(run/'result.json'),'sourceIssues':result['sourceAudit']['assessment']['assessment']['issues'],
            'additionalPointCandidates':[p for p in initial['points']if p['point_id']not in expected],
            'stageDurationsMs':{name:read(run/(name+'.usage.json'))['duration_ms']
                for name,entry in read(run/'ledger.json')['stages'].items()if entry['status']=='completed'},
            'coverage':{state:sum(p['status']==state for p in doc['review']['coverage'])
                for state in ['covered','partial','gap','unknown','excluded']},
            'medicalVerdicts':{state:sum(q['verdict']==state for q in result['medical']['reviews'])
                for state in ['ok','doubt','wrong']}})
    write(OUT/'generation-verification.json',{'results':results,'complete':len(results)==len(LECTURES),'productionUntouched':True})
    print(json.dumps(results,ensure_ascii=True),flush=True)

def status():
    for slug,*_ in LECTURES:
        path=OUT/slug/'ledger.json'
        ledger=read(path)if path.exists()else{'stages':{}}
        stages=[]
        for name,entry in ledger['stages'].items():
            row={'name':name,'status':entry['status']}
            usage=OUT/slug/(name+'.usage.json')
            if usage.exists():row['durationMs']=read(usage).get('duration_ms')
            stages.append(row)
        print(json.dumps({'lecture':slug,'repairRounds':ledger.get('repairRounds',0),'stages':stages}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','inputs','results','ready-results','status']);a=p.parse_args().action
    {'prepare':prepare,'inputs':check_inputs,'results':check_results,'ready-results':lambda:check_results(False),'status':status}[a]()
