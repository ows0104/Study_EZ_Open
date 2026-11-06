"""Explicit three-item comparison trial. Never edits the prior run or learner DB."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3];MAIN=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from quizbank import connection_generate as g
from runner.root_native_json import NativeJson,validate_stage
from studyez_contracts.roots import generation_v2 as c,document_hash
from studyez_contracts.roots.source_assessment import envelope
from studyez_contracts.bank.validate import validate_bank
from studyez_contracts.roots.automation import validate_checks
OUT=MAIN/'runs/_recall/261106';PRIOR=MAIN/'runs/_e2e/26110507/cns-infection'
MODEL='gpt-6.1-sol'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare():
    assert not OUT.exists(),'Preserve existing trial; no automatic rerun'
    OUT.mkdir(parents=True);material=OUT/'material';material.mkdir()
    result=read(PRIOR/'result.json');bank=result['document']['bank_snapshot'];b=copy.deepcopy(result['brief'])
    qids={'Q012','Q019','Q032'};dids={'D012','D019','D032'}
    before=[q for q in bank['questions']if q['question_id']in qids]
    g.write(OUT/'before.json',before)
    b['targets']=[t for t in b['targets']if any(d['direction_id']in dids for d in t['directions'])]
    for t in b['targets']:
        t['directions']=[d for d in t['directions']if d['direction_id']in dids]
        t['relation_ids']=list(dict.fromkeys(r for d in t['directions']for r in d['relation_ids']))
    rels={r for t in b['targets']for r in t['relation_ids']}
    b['relations']=[r for r in b['relations']if r['relation_id']in rels]
    for node in b['concepts']:node['parent_ids']=[]
    points={'P012','P013','P015','P019','P032','P033','P034','P035','P036'}
    b['points']=[p for p in b['points']if p['point_id']in points]
    b['prerequisites']=[];b['exclusions']=[]
    b['recall_policy']='recall-units/1';b['provenance']['independent_points']='derived'
    b['provenance']['notes']='Frozen three-item subset for authorized recall-design comparison; historical full-run evidence preserved separately.'
    b['scope'].update(label='CNS 세 문항 회상 설계 비교',included=['급성/아급성 병원체와 PML 대응','두개내압상승 관련 증상','세균성/바이러스성 CSF 비교'],
        excluded=['다른 CNS 문항의 재생성','기존 은행/학습 기록 변경'],reviewed=[],limitations=['세 문항 범위의 별도 실험이며 강의 전체 완료 판정이 아니다.'],outside_list_review='Only the three approved item scopes are under comparison.')
    previous={'brief':b,'bank':copy.deepcopy(bank),'visual_stimuli':[],'clinical_conflicts':[],'map_change_reason':'Frozen three-item subset'}
    previous['bank']['questions']=copy.deepcopy(before)
    for q in previous['bank']['questions']:q['prerequisites']=[];q.pop('stimuli',None)
    previous['bank']['source_conflicts']=[]
    c.validate_authoring(previous)
    source_files={sid:MAIN/'runs/_e2e/26110507/inputs'/(sid+'.pdf')for sid in ('S1','S2')}
    # Existing frozen PDF copies are read; no mutation, retrieval or upload to a new destination.
    import fitz
    for sid,pages in [('S1',[1,31,38,41,47]),('S2',[5,6,7,8,9,11,12])]:
        source_path=source_files[sid]
        if not source_path.exists():source_path=MAIN/'runs/_e2e/26110507/inputs/sources'/(sid+'.pdf')
        assert source_path.exists(),source_path
        shutil.copyfile(source_path,material/(sid+'.pdf'))
        with fitz.open(source_path)as pdf:
            text=[]
            for page in pages:
                p=pdf[page-1];text.append(f'## {sid} physical page {page}\n'+p.get_text())
                p.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(material/f'{sid}-{page:04}.png')
            (material/(sid+'.md')).write_text('\n\n'.join(text),encoding='utf-8')
    ctx={'title':'중추신경계감염 — 세 문항 회상 설계 비교','lecture_id':b['lecture_id'],'sources':b['sources'],
        'brief':b,'previousAuthoring':previous,'bank':previous['bank'],'initialBriefErrors':[],
        'repairReasons':[{'kind':'map_fix','text':'사용자 승인: 세 목표를 실제 회상 부담에 맞게 재설계한다. 넓은 방향은 recall_units로 분할하고 기출/일반화 주의 문구는 학생 채점 목표와 분리한다. 원본 point text/ID/근거는 그대로 보존한다.','question_ids':sorted(qids),'direction_ids':sorted(dids)},
            {'kind':'question_fix','text':'Q012: 여러 경과군 목록과 PML/특정균 판단을 한 번에 요구했다. Q019: 증상 회상은 유지하고 기출 정답/다른 모든 기전을 배제하는가 같은 메타 질문은 제거한다. Q032: 여러 지표 비교는 작고 의미 있는 표/빈칸으로 답하게 한다. 기존 범위에 없는 기전·의학 내용을 추가하지 않는다.','question_ids':sorted(qids),'direction_ids':sorted(dids)}],
        'comparison_contract':{'new_question_ids':'Use new stable RU-prefixed IDs; no old learning identity transfer.',
            'formats':'Reuse Main Quiz basic/list/cloze/mcq/multi_select. For table cloze use | header |, | --- | and canonical {{c1}} placeholders with answer_units in row-major blank order. No fixed count target.',
            'boundaries':'This is a separate authorized trial of three old questions, not a reset/retry of the exhausted full-lecture ledger.',
            'content':'Only supplied materials. Inspect actual page PNGs. No network or external scope expansion. Preserve clinically necessary source conditions while moving generic review warnings out of scoring.'}}
    g.write(OUT/'author-context.json',ctx)
    g.write(OUT/'preservation.json',{'priorResultSha256':sha(PRIOR/'result.json'),
        'priorLedgerSha256':sha(PRIOR/'ledger.json'),'beforeSha256':sha(OUT/'before.json'),
        'priorDatabaseSha256AtPreparation':sha(MAIN/'runs/_e2e/26110507/local-app/study.db'),
        'materials':{p.name:sha(p)for p in material.iterdir()},'authorization':'Current explicit user approval for code changes and three-item regeneration/comparison; prior OpenAI transmission approval retained.'})
    g.write(OUT/'trial-ledger.json',{'scope':'three approved items only','oldRepairRounds':3,
        'authorCalls':0,'repairCalls':0,'stages':{},'productionChanged':False})
    print('Frozen three original questions and relevant source pages; prior run and learner DB untouched.')

def stage(name,ctx):
    ledger=read(OUT/'trial-ledger.json');assert name not in ledger['stages'],'No implicit retry'
    ledger['stages'][name]={'status':'started','inputHash':document_hash(ctx)}
    if name=='repair-1':ledger['authorCalls']+=1
    g.write(OUT/(name+'.input.json'),ctx);g.write(OUT/'trial-ledger.json',ledger)
    try:
        raw,usage=NativeJson(OUT)(name,ctx,OUT/'material',MODEL)
        stored=envelope(ctx['brief'],ctx['bank'],raw)if name.startswith('source-')else raw
        g.write(OUT/(name+'.raw.json'),stored);g.write(OUT/(name+'.usage.json'),usage)
        entry=ledger['stages'][name];entry.update(status='completed',rawOutputHash=document_hash(stored),usageHash=document_hash(usage))
        g.write(OUT/'trial-ledger.json',ledger)
        validate_stage(OUT,{'name':name,**entry},model=MODEL)
        return raw
    except BaseException as e:
        ledger['stages'][name]['status']='failed';ledger['stages'][name]['reason']=str(e)
        g.write(OUT/'trial-ledger.json',ledger);raise

def author():
    ctx=read(OUT/'author-context.json');a=stage('repair-1',ctx)
    c.validate_authoring(a,ctx['previousAuthoring']);assert a['brief'].get('recall_policy')=='recall-units/1'
    assert all(q['question_id'].startswith('RU')for q in a['bank']['questions'])
    validation=validate_bank(a['bank'],[s['source_id']for s in a['brief']['sources']],check_quality=False)
    g.write(OUT/'bank-validation.json',validation)
    assert validation['pass'],validation['errors']
    g.write(OUT/'authored.json',a);print('New authoring completed:',len(a['bank']['questions']),'questions',flush=True)

def accept_references():
    """Explicit metadata projection of a completed draft; never rewrites a question."""
    assert not (OUT/'authored.json').exists()and not(OUT/'authoring-reference-projection.json').exists()
    ctx=read(OUT/'author-context.json');raw=read(OUT/'repair-1.raw.json')
    ledger=read(OUT/'trial-ledger.json');assert ledger['authorCalls']==1
    validate_stage(OUT,{'name':'repair-1',**ledger['stages']['repair-1']},model=MODEL)
    try:c.validate_authoring(raw,ctx['previousAuthoring'])
    except ValueError as error:
        assert 'relations missing from directions'in str(error);failure=str(error)
    else:raise AssertionError('This metadata recovery is only for the recorded failed acceptance')
    projected=copy.deepcopy(raw);changes=[]
    for t in projected['brief']['targets']:
        expected=list(dict.fromkeys(r for d in t['directions']for r in d['relation_ids']))
        if set(t['relation_ids'])!=set(expected):
            assert set(expected)<=set(t['relation_ids'])
            changes.append({'target_id':t['target_id'],'before':t['relation_ids'],'after':expected})
            t['relation_ids']=expected
    assert [r['target_id']for r in changes]==['T008','T015']
    assert projected['bank']==raw['bank']and projected['clinical_conflicts']==raw['clinical_conflicts']
    c.validate_authoring(projected,ctx['previousAuthoring'])
    validation=validate_bank(projected['bank'],[s['source_id']for s in projected['brief']['sources']],check_quality=False)
    assert validation['pass'],validation['errors']
    g.write(OUT/'authoring-reference-projection.json',{'failure':failure,'changes':changes,
        'rawHash':document_hash(raw),'acceptedHash':document_hash(projected),'modelCalls':0,
        'bankUnchanged':True,'originalReceiptPreserved':True})
    g.write(OUT/'bank-validation.json',validation);g.write(OUT/'authored.json',projected)
    print('Completed provider draft retained; two derived target reference lists aligned; bank unchanged; model calls 0.')

def review():
    a=read(OUT/'authored.json');ctx={'title':'CNS 세 문항 비교','brief':a['brief'],'bank':a['bank'],
        'clinical_conflicts':a['clinical_conflicts'],
        'questionFronts':[{'question_id':q['question_id'],'question':c_text(q),'options':q['options']}for q in a['bank']['questions']],
        'stimulusFiles':[]}
    raw=stage('source-0',ctx);audit=c.compile_assessment(a['brief'],a['bank'],envelope(a['brief'],a['bank'],raw))
    g.write(OUT/'source-audit.json',audit)
    assert raw['clinical_context_status']=='consistent','Medical input separation unresolved'
    med=stage('medical-0',{'title':ctx['title'],'bank':a['bank'],'clinicalInput':c.medical_input(a['bank'],a['clinical_conflicts'])})
    validate_checks(med,a['bank']);g.write(OUT/'medical.json',med)
    doc=c.make_document(a['brief'],a['bank'],audit,revision='recall-three-261106',title=ctx['title'],exam_date=None,medical=med)
    g.write(OUT/'document.json',doc)
    from studyez_contracts.roots.recall_units import prepared_coverage
    g.write(OUT/'prepared-goals.json',prepared_coverage(audit,doc))
    print('Review completed:',len(doc['tasks']),'prepared tasks',flush=True)

def c_text(q):
    from studyez_contracts.bank.cloze import normalize_cloze
    return normalize_cloze(q)['question']

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'prepare':prepare,'author':author,'accept-references':accept_references,'review':review}[sys.argv[1]]()
