"""One explicitly requested local example; no production client or publisher."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime,UTC
import hashlib,json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from quizbank import connection_generate as g
from studyez_contracts.roots.source_assessment import envelope,compile_source_assessment
from studyez_contracts.roots.automation import validate_brief,validate_checks,packet_hash

ORIGIN=Path('C:/Users/ows01/Documents/Python Scripts/Study_EZ_Open/runs/_root-generation/f0a8f3b68e3642598f85bbf462e1dc55')
OUT=ROOT/'runs/_examples/cholinergic-20261104'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def preflight():
    packet=read(ORIGIN/'packet.json');ledger=read(ORIGIN/'ledger.json')
    require(packet['generationId']==ORIGIN.name and packet_hash(packet)==packet['inputHash'],'Original input changed')
    require(ledger['repairRounds']==3 and len(ledger['stages'])==13,'Original budget/evidence changed')
    for name,stage in ledger['stages'].items():
        require(stage['status']=='completed' and g.document_hash(read(ORIGIN/(name+'.json')))==stage['outputHash'],
                'Original stage changed: '+name)
    sources=[]
    for source in packet['sources']:
        path=Path(source['localPath']).resolve()
        require(path.parent==ORIGIN.resolve() and path.stat().st_size==source['sizeBytes'] and sha(path)==source['sha256'],
                'Original source changed')
        sources.append({k:source[k]for k in ('id','filename','sha256','sizeBytes')})
    brief=read(ORIGIN/'normalize.json');bank=read(ORIGIN/'repair-3.json');medical=read(ORIGIN/'medical-3.json')
    validate_brief(brief,from_sources=True);validate_checks(medical,bank)
    require(len(bank['questions'])==88,'Not the approved final bank')
    require(read(ORIGIN/'source-3.json')['review']['bank_sha256']==g.document_hash(bank),'Cached final review uses another bank')
    validation=g.validate_bank(bank,[s['id']for s in packet['sources']])
    require(g.validate_bank(bank,[s['id']for s in packet['sources']],check_quality=False)['pass'],'Bank is structurally unusable')
    proof={'schema_version':'root-example-proof/1','originGeneration':ORIGIN.name,
        'originLedgerFileHash':sha(ORIGIN/'ledger.json'),'originRuntime':ledger['identity'],
        'originRepairRounds':3,'originStageCount':13,'packetHash':packet['inputHash'],'sources':sources,
        'briefHash':g.document_hash(brief),'bankHash':g.document_hash(bank),'medicalHash':g.document_hash(medical),
        'newRuntime':g.identity(packet,None),'scriptHash':sha(Path(__file__)),
        'mode':'example-only','maxNewSourceCalls':1,'newQuestionRepairs':0,'publicationAllowed':False}
    return packet,brief,bank,medical,validation,proof

def run():
    packet,brief,bank,medical,validation,proof=preflight()
    OUT.mkdir(parents=True,exist_ok=False)
    g.write(OUT/'preflight.json',proof)
    state={'status':'preparing','startedAt':datetime.now(UTC).isoformat(),'sourceCalls':0,'questionRepairs':0,'published':False}
    g.write(OUT/'example-ledger.json',state)
    try:
        inventory=g.prepare(packet,OUT/'material')
        require(inventory==brief['sources'],'Prepared material inventory differs from frozen extraction')
        context={k:packet[k]for k in ('title','scope','conceptMap','points','examDate')}
        context.update(lecture_id=f"{packet['subject']}/{packet['runId']}",sources=inventory,
            preserved_scope=g.lecture_scope(packet['title'],packet['sources']),brief=brief,bank=bank,
            bank_sha256=g.document_hash(bank),question_hashes={q['question_id']:g.question_hash(q,bank)for q in bank['questions']})
        if packet.get('authoring')=='web':context['webResponse']=packet['webResponse']
        g.write(OUT/'input.json',context)
        schema=g.source_assessment_schema(brief,bank)
        g.write(OUT/'wire-schema.json',g.output_schema(schema))
        state.update(status='source-running',sourceCalls=1);g.write(OUT/'example-ledger.json',state)
        print('콜린성(1) 실제 원본 대조 시작 · 35쪽 PDF/족보 · 88문항 · 새 형식1회',flush=True)
        start=time.monotonic()
        with ThreadPoolExecutor(max_workers=1)as pool:
            pending=pool.submit(g.call_model,'source-example',context,OUT/'material',None)
            while True:
                try:assessment,usage=pending.result(timeout=20);break
                except TimeoutError:
                    if pending.done():raise
                    print(f'원본 대조 진행 중 · {int(time.monotonic()-start)}초',flush=True)
        raw=envelope(brief,bank,assessment)
        g.write(OUT/'assessment.raw.json',raw);g.write(OUT/'usage.json',usage)
        state.update(status='compiling',rawHash=g.document_hash(raw));g.write(OUT/'example-ledger.json',state)
        g.jsonschema.validate(assessment,schema)
        audit=compile_source_assessment(brief,bank,raw);g.write(OUT/'audit.json',audit)
        document=g.make_document(brief,bank,audit,revision='example-cholinergic-20261104',title=packet['title'],exam_date=packet['examDate'])
        g.write(OUT/'document.json',document)
        require(g.identity(packet,None)==proof['newRuntime'],'Runtime changed while example was running')
        require(sha(ORIGIN/'ledger.json')==proof['originLedgerFileHash'],'Original ledger changed')
        all_directions={d['direction_id']for t in brief['targets']for d in t['directions']}
        summary={'questions':len(bank['questions']),'targets':len(brief['targets']),'directions':len(all_directions),
            'concepts':len(brief['concepts']),'points':len(brief['points']),'tasks':len(document['tasks']),
            'unreadyDirections':sorted(all_directions-{t['direction_id']for t in document['tasks']}),
            'sourceVerdicts':dict(Counter(r['verdict']for r in audit['question_checks']['reviews'])),
            'cachedMedicalVerdicts':dict(Counter(r['verdict']for r in medical['reviews'])),
            'coverage':dict(Counter(c['status']for c in audit['review']['coverage'])),
            'inputIssues':len(audit['input_issues']),'published':False,'newSourceCalls':1,'newQuestionRepairs':0}
        bundle={'schema_version':'root-example/1','purpose':'read-only-example','proof':proof,
            'brief':brief,'bank':bank,'sourceAssessment':raw,'sourceAudit':audit,'document':document,
            'cachedMedical':{'bankHash':proof['bankHash'],'originalStage':'medical-3','originalRuntime':proof['originRuntime'],
                'outputHash':proof['medicalHash'],'review':medical},'validation':validation,'summary':summary}
        g.write(OUT/'example-result.json',bundle);g.write(OUT/'summary.json',summary)
        state.update(status='completed',finishedAt=datetime.now(UTC).isoformat(),resultHash=g.document_hash(bundle))
        g.write(OUT/'example-ledger.json',state)
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    except BaseException as error:
        state.update(status='failed',error=str(error)[:1800],finishedAt=datetime.now(UTC).isoformat())
        g.write(OUT/'example-ledger.json',state)
        raise

def check_result():
    _,brief,bank,medical,_,proof=preflight()
    require(read(OUT/'preflight.json')==proof,'Example input/runtime/script proof differs')
    state=read(OUT/'example-ledger.json');value=read(OUT/'example-result.json')
    require(state['status']=='completed' and state['sourceCalls']==1 and state['questionRepairs']==0 and not state['published'],
            'Incomplete or unexpected example call budget')
    require(state['resultHash']==g.document_hash(value),'Example result changed')
    require(value['bank']==bank and value['brief']==brief and value['cachedMedical']['review']==medical,'Original content/review changed')
    require(value['cachedMedical']['outputHash']==proof['medicalHash'] and value['cachedMedical']['bankHash']==proof['bankHash'],
            'Cached medical provenance changed')
    raw=read(OUT/'assessment.raw.json');require(raw==value['sourceAssessment'],'Raw source review changed')
    require(compile_source_assessment(brief,bank,raw)==value['sourceAudit'],'Audit compilation differs')
    require(g.make_document(brief,bank,value['sourceAudit'],revision='example-cholinergic-20261104',title=value['document']['title'],
        exam_date=value['document']['exam_date'])==value['document'],'Root task selection differs')
    require(isinstance(read(OUT/'usage.json'),dict),'Missing model usage record')
    print(json.dumps({'pass':True,**value['summary']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['--preflight','--run','--check-result'])
    # Accept named modes without shell-dependent argument parsing.
    mode=sys.argv[1]if len(sys.argv)==2 else ''
    if mode=='--preflight':print(json.dumps(preflight()[-1],ensure_ascii=False))
    elif mode=='--run':run()
    elif mode=='--check-result':check_result()
    else:p.error('Choose --preflight, --run or --check-result')
