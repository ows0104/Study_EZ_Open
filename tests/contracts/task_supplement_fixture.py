import copy,json,hashlib
from studyez_contracts.roots import task_supplement as c, document_hash

def fixture():
    import generation_v2_fixture as f
    base=f.result(f.packet());base['manifest']['repairRounds']=3
    base['document']['review']['sources'][0]['page_count']=1
    bank=copy.deepcopy(base['document']['bank_snapshot'])
    links=[]
    for q in bank['questions']:
        links.append({'question_id':q['question_id'],'title':'Synthetic complete recall','cue':q['question'],'answer_scope':q['answer'],
            'components':[{'text':q['answer'],'answer_unit_indices':list(range(len(q['answer_units'])))}],
            'relation_fact':'Synthetic A/B association','evidence':[{'source_id':'S1','locator':'Synthetic page1','pages':[1]}],
            'importance':copy.deepcopy(base['document']['review']['targets'][0]['importance']),'requires_visual':False,'reason':'Synthetic direct recall'})
    proposal={'summary':'Synthetic fresh authoring','bank':bank,'visual_stimuli':[],'clinical_conflicts':[],'links':links}
    source={'summary':'Synthetic full source review','coverage_findings':[],'reviews':[{'question_id':q['question_id'],'source_verdict':'ok','goal_verdict':'ok',
        'visual_verdict':'not_applicable','all_answer_units_covered':True,'importance_verdict':'ok','reason':'Synthetic full recall checked'}for q in bank['questions']]}
    medical={'summary':'Synthetic fresh blind review','reviews':[{'question_id':q['question_id'],'verdict':'ok','note':'Synthetic checked','suggested_answer':''}for q in bank['questions']],'pool_checks':[]}
    return base,proposal,source,medical


def proof(name,value):
    raw=json.dumps(value);sha=hashlib.sha256(raw.encode()).hexdigest()
    provider={'session_id':'synthetic-test-only-'+name,'turns':1,'text':raw if name=='medical'else json.dumps({'path':'result.json','sha256':sha})}
    return {'status':'completed','provider':provider,'providerHash':document_hash(provider),'rawOutput':raw,'outputHash':document_hash(value),'outputSha256':sha}


def result():
    b,p,s,m=fixture()
    row={'round':0,'proposal':p,'sourceReview':s,'medicalReview':m,'execution':{n:proof(n,x)for n,x in [('author',p),('source',s),('medical',m)]}}
    v={'policy':c.POLICY,'runId':'synthetic-replacement','parentResultHash':document_hash(b),'historicalRepairRounds':3,
       'repairRounds':0,'rounds':[row],'document':c.assemble(b,p,s,m,p['bank'],'followup'),'ready':True}
    return b,v


