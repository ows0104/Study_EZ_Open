"""Nonmedical synthetic A/B example, shared by producer/consumer tests."""
import copy
import hashlib
from pathlib import Path
from studyez_contracts.bank.schema import QUESTION
from studyez_contracts.roots import document_hash
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots.automation import CORE, packet_hash, make_document,source_intake
from studyez_contracts.bank.validate import validate_bank
try:
    from .root_fixture import document
except ImportError:
    from root_fixture import document

BODY = b'A and B are synthetic labels for integration checks only.'


def packet(path=None):
    source={'id':'S1','assetId':1,'kind':'notes_current','filename':'synthetic.txt','sizeBytes':len(BODY),
        'sha256':hashlib.sha256(BODY).hexdigest(),'originalKey':'synthetic.txt','uploadedAt':'2026-11-03T00:00:00',
        'snapshotKey':'frozen/synthetic.txt'}
    if path:
        Path(path).write_bytes(BODY);source['localPath']=str(Path(path).resolve())
    value={'generationId':'a'*32,'revision':'auto-'+'a'*32,'subject':'test','runId':'demo','title':'Synthetic lecture',
        'owner':'admin','privatePilot':True,'sources':[source],'conceptMap':'A -> B','points':'Synthetic A/B point',
        'scope':'Synthetic only','examDate':'2026-11-07'}
    value['inputHash']=packet_hash(value)
    return value


def brief(sources=None):
    doc=document();review=doc['review']
    value={k:copy.deepcopy(review[k]) for k in (*CORE,'provenance')}
    value.update(schema_version='learning-brief/1',prerequisites=[],exclusions=[])
    value['targets']=value['targets'][:1];value['points']=value['points'][:1]
    value['relations']=value['relations'][:2]
    value['sources']=sources or [{'source_id':'S1','label':'synthetic.txt','sha256':hashlib.sha256(BODY).hexdigest(),
        'kind':'notes','professor':None,'year':None,'page_count':None}]
    value['provenance'].update(status='draft',independent_points='derived')
    return value


def bank():
    qs=[]
    for n in (1,2):
        q={k: [] if s['type']=='array' else False if s['type']=='boolean' else 1 if s['type'] in ('number','integer') else ''
           for k,s in QUESTION['properties'].items()}
        q.update(question_id=f'Q{n}',concept_id='A',tier='Optional',importance=2,item_difficulty=2,format='basic',
            retrieval_direction='direct' if n==1 else 'reverse',mcq_mode='none',question=f'Synthetic question {n}?',
            answer=f'Secret answer {n}',answer_units=[f'Secret answer {n}'],explanation=f'Synthetic explanation {n}',source_refs=[{'source_id':'S1','locator':'synthetic paragraph'}],learning_page=1)
        qs.append(q)
    return {'build_meta':{'schema_version':'3.2','lecture_title':'Synthetic lecture'},
        'source_summary':[{'source_id':'S1','summary':'Synthetic only'}],'source_conflicts':[],
        'concepts':[{'concept_id':'A','title':'A/B','graph_title':'A/B','core_facts':['Synthetic fact'],
            'source_refs':[{'source_id':'S1','locator':'synthetic paragraph'}],'importance':2,'importance_rationale':'synthetic',
            'concept_difficulty':2,'tier':'Optional','exam_signal_strength':'low','related_concepts':[]}],
        'retrieval_plan':[{'concept_id':'A','directions':['direct','reverse'],'repetition_budget':2,'target_mastery':0.8}],
        'questions':qs,'audit_summary':{'summary':'Synthetic only','rejected_candidate_count':0,'changes':[]},'warnings':[]}


def checks(bank, verdict='ok'):
    return {'summary':'Synthetic independent check','reviews':[{'question_id':q['question_id'],'verdict':verdict,
        'note':'Synthetic review note','suggested_answer':''} for q in bank['questions']]}


def audit(brief,bank):
    review=copy.deepcopy(document()['review'])
    for k in (*CORE,'provenance'):review[k]=copy.deepcopy(brief[k])
    review['provenance']['status']='reviewed';review['bank_sha256']=document_hash(bank)
    review['mappings']=review['mappings'][:2];review['coverage']=review['coverage'][:1]
    for row,q in zip(review['mappings'],bank['questions']):
        row['question_id']=q['question_id'];row['question_sha256']=question_hash(q,bank)
    return {'review':review,'question_checks':checks(bank),'input_issues':[]}


def model(stage,context,material,model_name):
    if context.get('_pipeline_version')=='root-generation/2':
        import generation_v2_fixture
        return generation_v2_fixture.model(stage,context,material,model_name)
    if stage=='normalize':
        value=brief(context['sources'])
        if context.get('inputMode')=='source':value['provenance']['independent_points']='confirmed'
        return value,{}
    if stage=='generate' or stage.startswith('repair-'):return web_bank() if context.get('webResponse') else bank(),{}
    if stage.startswith('source-'):return assessment(context['brief'],context['bank']),{}
    if stage.startswith('medical-'):return checks(context['bank']),{}
    raise AssertionError(stage)


def assessment(brief_value,bank_value):
    """Nonmedical independent-review fixture for the new model protocol."""
    a=audit(brief_value,bank_value)
    rows=copy.deepcopy(a['question_checks']['reviews'])
    for row in rows:
        claims={}
        for mapping in a['review']['mappings']:
            if mapping['question_id']!=row['question_id']:continue
            for role in ('tested','provided','explanation'):
                for rid in mapping[role+'_relation_ids']:
                    claim=claims.setdefault(rid,{'relation_id':rid,'role':role,'direction_ids':[],'reason':mapping['reason']})
                    assert claim['role']==role
                    if role=='tested' and mapping['direction_id'] not in claim['direction_ids']:
                        claim['direction_ids'].append(mapping['direction_id'])
        row['relations']=list(claims.values())
    return {'schema_version':'source-assessment/1','summary':a['question_checks']['summary'],'question_reviews':rows,
        'direction_checks':[{'direction_id':d['direction_id'],'status':'reviewed','reason':'Synthetic full comparison'}
            for t in brief_value['targets'] for d in t['directions']], 'input_issues':a['input_issues']}


def assessed_result(packet):
    return attach_assessment(result(packet),packet)


def attach_assessment(value,packet):
    from studyez_contracts.roots.source_assessment import envelope,compile_source_assessment,VERSION
    b=value['brief'];bank_value=value['document']['bank_snapshot']
    raw=envelope(b,bank_value,assessment(b,bank_value));a=compile_source_assessment(b,bank_value,raw)
    value['sourceAudit']=a
    value['document']=make_document(b,bank_value,a,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate'])
    value['manifest']['sourceAssessment']=raw
    source=next(s for s in value['manifest']['stages'] if s['name']=='source-0')
    source.update(outputHash=document_hash(a),rawOutputHash=document_hash(raw),sourceFormat=VERSION)
    return value


def result(packet):
    if packet.get('sourceAssessmentFormat')=='source-assessment/2':
        import generation_v2_fixture
        return generation_v2_fixture.result(packet)
    b=brief();b['lecture_id']=f"{packet['subject']}/{packet['runId']}"
    if packet.get('inputMode')=='source':b['provenance']['independent_points']='confirmed'
    b['sources']=[{'source_id':s['id'],'label':s['filename'],'sha256':s['sha256'],'kind':'notes',
        'professor':None,'year':None,'page_count':None} for s in packet['sources']]
    bank_value=web_bank() if packet.get('authoring')=='web' else bank();a=audit(b,bank_value);m=checks(bank_value)
    stages={'normalize':b,'generate':bank_value,'source-0':a,'medical-0':m}
    value={'brief':b,'document':make_document(b,bank_value,a,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate']),
        'sourceAudit':a,'medical':m,'validation':validate_bank(bank_value,['S1']),
        'manifest':{'inputHash':packet['inputHash'],'briefHash':document_hash(b),'bankHash':document_hash(bank_value),'repairRounds':0,
            **({'webResponseHash':packet['webResponseHash']} if packet.get('authoring')=='web' else {}),
            **({'sourceIntakeHash':document_hash(source_intake(packet,b['sources']))} if packet.get('inputMode')=='source' else {}),
            'runtimeHash':'0'*64,'model':'synthetic-test',
            'stages':[{'name':k,'status':'completed','outputHash':document_hash(v)} for k,v in stages.items()]}}
    return attach_assessment(value,packet) if packet.get('sourceAssessmentFormat')=='source-assessment/1' else value


def web_bank():
    value=bank()
    for i,q in enumerate(value['questions'],1):q['question_id']=f'Q{i:03}'
    return value


def web_response(generation_id,subject='test',run_id='demo'):
    import json
    meta={'schema_version':1,'subject':subject,'run_id':run_id,'prompt_version':'1.79','generation_id':generation_id,
          'question_count':2,'question_ids':['Q001','Q002'],'conflict_ids':[]}
    raw='<!-- STUDYEZ_BANK_FILE '+json.dumps(meta,ensure_ascii=False)+' -->\n'
    for q in web_bank()['questions']:
        raw+=f"\n### {q['question_id']} | basic | Optional | direct\n문제: {q['question']}\n정답: "+json.dumps(q['answer_units'])+'\n출처: S1 synthetic paragraph\n출제근거: Synthetic only\n근거: {}\n심화: false\n해설: '+json.dumps(q['explanation'])+'\n'
    raw+='\nSTUDYEZ_BANK_COMPLETE'
    return {'raw':raw,'promptVersion':'1.79','responseFile':{'filename':f'study-ez-{run_id}-bank.md',
        'byteLength':len(raw.encode()),'sha256':hashlib.sha256(raw.encode()).hexdigest()},'conversationUrl':'','shareUrl':None}
