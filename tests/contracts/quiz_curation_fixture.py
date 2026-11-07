import copy
from task_supplement_fixture import result,proof
from studyez_contracts.roots import task_supplement as r,quiz_curation as c,document_hash


def fixture():
    base,candidate=result();last=candidate['rounds'][-1]
    last['sourceReview']['reviews'][0].update(importance_verdict='doubt',reason='Synthetic priority evidence is unconfirmed')
    last['sourceReview']['coverage_findings']=['Synthetic omitted unsafe item needs an explicit bounded scope']
    last['medicalReview']['reviews'][1].update(verdict='doubt',note='Synthetic medical uncertainty')
    last['execution']={n:proof(n,x)for n,x in [('author',last['proposal']),('source',last['sourceReview']),('medical',last['medicalReview'])]}
    candidate['document']=r.assemble(base,last['proposal'],last['sourceReview'],last['medicalReview'],last['proposal']['bank'],'full-held')
    candidate['ready']=False;r.validate(base,candidate)
    selected,held,priority=c.selection(candidate)
    approval={'approved':True,'full_source_coverage':False,'summary':'Synthetic bounded original scope checked','selected_ids':selected,
        'held_questions':[{'question_id':qid,'reason':'Synthetic medical uncertainty retained'}for qid in held],
        'unverified_priority':[{'question_id':qid,'reason':'Synthetic priority claim not used'}for qid in priority],
        'published_scope':['Synthetic verified item only'],'deferred_topics':['Synthetic uncertain item is not covered'],
        'scope_limits':['Synthetic scope has explicit omitted items and unverified priority'],'execution_notes':[],
        'coverage_dispositions':[{'index':0,'status':'explicitly_deferred','reason':'Synthetic excluded uncertain item'}]}
    inp={'candidateHash':document_hash(candidate),'sourceReview':last['sourceReview'],'medicalReview':last['medicalReview'],
        'bank':c.clean(candidate['document']['bank_snapshot']),'links':last['proposal']['links'],'independentOriginalMapPoints':base['brief']}
    execution=proof('scope',approval);execution['inputHash']=document_hash(inp)
    value={'policy':c.POLICY,'runId':'c'*32,'candidate':candidate,'parentResultHash':candidate['parentResultHash'],
        'repairRounds':candidate['repairRounds'],'historicalRepairRounds':3,'approval':approval,'execution':execution,'inputHash':document_hash(inp),
        'reviewInput':inp,'document':c.project(candidate,approval,'curated-toy'),'ready':True}
    return base,value
