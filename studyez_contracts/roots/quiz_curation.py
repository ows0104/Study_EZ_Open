"""Verified subset publication. No question editing or promotion of uncertain facts."""
import copy
from . import task_supplement as original
from .validate import document_hash,validate_document
from studyez_contracts.learning_links.schema import obj,arr,enum,TEXT
from studyez_contracts.learning_links.validate import require,validate_shape,question_hash
from studyez_contracts.bank.validate import validate_bank

POLICY='verified-main-quiz-curation/1'
NOTE=obj(question_id=TEXT,reason=TEXT)
APPROVAL=obj(approved={'type':'boolean'},full_source_coverage={'type':'boolean'},summary=TEXT,selected_ids=arr(TEXT,1),
    held_questions=arr(NOTE),unverified_priority=arr(NOTE),published_scope=arr(TEXT,1),
    deferred_topics=arr(TEXT,1),scope_limits=arr(TEXT,1),execution_notes=arr(TEXT),
    coverage_dispositions=arr(obj(index={'type':'integer','minimum':0},
        status=enum('confirmed_within_scope','explicitly_deferred','unresolved'),reason=TEXT)))


def clean(value):
    if isinstance(value,dict):return {k:clean(v)for k,v in value.items()if k!='png_base64'}
    if isinstance(value,list):return [clean(v)for v in value]
    return value


def selection(candidate):
    last=candidate['rounds'][-1];bank=candidate['document']['bank_snapshot'];source={r['question_id']:r for r in last['sourceReview']['reviews']}
    med={r['question_id']:r for r in last['medicalReview']['reviews']};qs={q['question_id']:q for q in bank['questions']}
    selected=[]
    for q in bank['questions']:
        qid=q['question_id'];r=source[qid]
        if (r['source_verdict']==r['goal_verdict']=='ok'and r['all_answer_units_covered']and med[qid]['verdict']=='ok'
            and r['visual_verdict']==('ok'if q.get('stimuli')else'not_applicable')):selected.append(qid)
    while True:
        keep=[qid for qid in selected if set(qs[qid]['prerequisites'])<=set(selected)]
        if keep==selected:break
        selected=keep
    return (selected,[q['question_id']for q in bank['questions']if q['question_id']not in selected],
        [qid for qid in selected if source[qid]['importance_verdict']!='ok'])


def check_approval(candidate,approval):
    validate_shape(approval,APPROVAL,'curation scope approval');selected,held,priority=selection(candidate)
    require(approval['full_source_coverage']is False,'curation: bounded scope must not claim full-source mastery')
    require(approval['selected_ids']==selected and [r['question_id']for r in approval['held_questions']]==held
        and [r['question_id']for r in approval['unverified_priority']]==priority,'curation: altered actual selection/held/priority')
    require([r['index']for r in approval['coverage_dispositions']]==list(range(len(candidate['rounds'][-1]['sourceReview']['coverage_findings']))),
        'curation: incomplete original coverage disposition')
    return approval


def project(candidate,approval,revision):
    check_approval(candidate,approval);selected,held,priority=selection(candidate);selected=set(selected);priority=set(priority)
    doc=copy.deepcopy(candidate['document']);bank=doc['bank_snapshot'];bank['questions']=[q for q in bank['questions']if q['question_id']in selected]
    # All retained question records and all BANK context remain byte-identical.
    qs={q['question_id']:q for q in bank['questions']};review=doc['review'];last=candidate['rounds'][-1]
    source={r['question_id']:r for r in last['sourceReview']['reviews']};links=last['proposal']['links']
    entries=[(q['question_id'],i+1)for i,q in enumerate(candidate['document']['bank_snapshot']['questions'])if q['question_id']in selected]
    tids={'N'+str(i)+'_T'for _,i in entries};rids={'N'+str(i)+'_R'for _,i in entries};pids={'N'+str(i)+'_P'for _,i in entries}
    review['targets']=[t for t in review['targets']if t['target_id']in tids]
    for qid,i in entries:
        target=next(t for t in review['targets']if t['target_id']=='N'+str(i)+'_T')
        if qid in priority:
            target['importance']={axis:{'status':'unreviewed','reason':source[qid]['reason'],'evidence':[]}
                for axis in ('structural','exam','clinical')}
    review['relations']=[r for r in review['relations']if r['relation_id']in rids]
    for r in review['relations']:r['review_status']='reviewed'
    used={v for t in review['targets']for v in t['concept_ids']}
    used|={v for r in review['relations']for v in (r['from_id'],r['to_id'])}
    while True:
        parents={p for c in review['concepts']if c['concept_id']in used for p in c['parent_ids']}
        if parents<=used:break
        used|=parents
    review['concepts']=[c for c in review['concepts']if c['concept_id']in used]
    review['points']=[p for p in review['points']if p['point_id']in pids]
    review['mappings']=[];review['coverage']=[];doc['tasks']=[]
    for qid,i in entries:
        stem='N'+str(i);rid=stem+'_R';tid=stem+'_T';did=stem+'_D';pid=stem+'_P'
        review['mappings'].append({'question_id':qid,'question_sha256':question_hash(qs[qid],bank),'target_id':tid,'direction_id':did,
            'tested_relation_ids':[rid],'provided_relation_ids':[],'explanation_relation_ids':[],'reason':source[qid]['reason']})
        review['coverage'].append({'point_id':pid,'status':'covered','confirmed_direction_ids':[did],'partial_direction_ids':[],
            'missing_direction_ids':[],'unknown_direction_ids':[],'reason':source[qid]['reason'],'exclusion_basis':None})
        doc['tasks'].append({'task_id':'task-'+document_hash([qid,did])[:24],'question_id':qid,'direction_id':did})
    from .generation_v2 import graph_order
    order=graph_order(bank);doc['tasks'].sort(key=lambda t:order.index(t['question_id']))
    review['bank_sha256']=document_hash(bank)
    review['scope'].update(included=copy.deepcopy(approval['published_scope']),excluded=copy.deepcopy(approval['deferred_topics']),
        limitations=copy.deepcopy(approval['scope_limits']),outside_list_review=approval['summary'])
    review['provenance'].update(method=POLICY,notes='Factual/whole-answer/visual/medical positives only. Unverified priority claims removed, not approved. Full held candidate and all actual verdicts retained.')
    doc.update(revision=revision,adopted_target_ids=[t['target_id']for t in review['targets']],equivalences=[],prerequisites=[])
    require(not validate_bank(bank,[s['source_id']for s in review['sources']])['errors'],'curation: invalid projected BANK')
    return validate_document(doc)


def validate(base,value):
    require(value['policy']==POLICY,'curation: wrong policy');candidate=value['candidate'];original.validate(base,candidate)
    require(not candidate['ready']and value['parentResultHash']==candidate['parentResultHash']and value['repairRounds']==candidate['repairRounds'],
        'curation: changed held candidate/history')
    require(value['historicalRepairRounds']==candidate['historicalRepairRounds']==3,'curation: changed prior budget')
    approval=check_approval(candidate,value['approval'])
    original.check_execution({'scope':value['execution']},{'scope':approval})
    inp=value['reviewInput']
    require(value['execution']['inputHash']==value['inputHash']==document_hash(inp)
        and inp['candidateHash']==document_hash(candidate)
        and inp['sourceReview']==candidate['rounds'][-1]['sourceReview']and inp['medicalReview']==candidate['rounds'][-1]['medicalReview']
        and inp['bank']==clean(candidate['document']['bank_snapshot'])and inp['links']==candidate['rounds'][-1]['proposal']['links']
        and inp['independentOriginalMapPoints']==base['brief'],
        'curation: changed independent scope input')
    expected=project(candidate,approval,value['document']['revision'])
    require(value['document']==expected and value['document']['revision']!=candidate['document']['revision'],'curation: altered verified subset')
    ready=approval['approved']and bool(expected['tasks'])and not any(r['status']=='unresolved'for r in approval['coverage_dispositions'])
    require(value['ready']==ready,'curation: false scoped readiness')
    return value
