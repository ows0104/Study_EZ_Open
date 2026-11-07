"""Explicit replacement generation with whole-question links and a fresh budget."""
import copy
import hashlib
import json
from .validate import document_hash, validate_document
from .generation_v2 import AUTHOR_BANK, CONFLICT, PARALLEL_CROP, graph_order
from .generation_v2 import medical_input
from .media import validate_images
from studyez_contracts.bank.validate import validate_bank
from studyez_contracts.learning_links.schema import obj, arr, enum, TEXT, REF, TARGET
from studyez_contracts.learning_links.validate import require, validate_shape, question_hash

POLICY='verified-main-quiz-replacement/1'
COMPONENT=obj(text=TEXT,answer_unit_indices=arr({'type':'integer','minimum':0},1))
LINK=obj(question_id=TEXT,title=TEXT,cue=TEXT,answer_scope=TEXT,components=arr(COMPONENT,1),relation_fact=TEXT,
    evidence=arr(REF,1),importance=TARGET['properties']['importance'],requires_visual={'type':'boolean'},reason=TEXT)
PROPOSAL=obj(summary=TEXT,bank=AUTHOR_BANK,visual_stimuli=arr(PARALLEL_CROP),clinical_conflicts=arr(CONFLICT),links=arr(LINK,1))
SOURCE_ROW=obj(question_id=TEXT,source_verdict=enum('ok','doubt','wrong'),goal_verdict=enum('ok','doubt','wrong'),
    visual_verdict=enum('ok','doubt','wrong','not_applicable'),all_answer_units_covered={'type':'boolean'},importance_verdict=enum('ok','doubt','wrong'),reason=TEXT)
SOURCE_REVIEW=obj(summary=TEXT,coverage_findings=arr(TEXT),reviews=arr(SOURCE_ROW,1))


def selection(base):
    used={t['question_id']for t in base['document']['tasks']};src={x['question_id']:x['verdict']for x in base['sourceAudit']['question_checks']['reviews']}
    med={x['question_id']:x['verdict']for x in base['medical']['reviews']};missing=[q for q in base['document']['bank_snapshot']['questions']if q['question_id']not in used]
    passed=[q['question_id']for q in missing if src[q['question_id']]=='ok'and med[q['question_id']]=='ok'];images=[q['question_id']for q in missing if q.get('stimuli')]
    return passed,images,[q['question_id']for q in missing if q['question_id']in set(passed+images)]


def check_proposal(base,proposal):
    validate_shape(proposal,PROPOSAL,'replacement proposal');bank=proposal['bank'];ids=[q['question_id']for q in bank['questions']]
    require(ids and len(ids)==len(set(ids)),'replacement: distinct questions required')
    require([l['question_id']for l in proposal['links']]==ids,'replacement: every question needs one whole recall link')
    sources={s['source_id']:s for s in base['document']['review']['sources']}
    errors=validate_bank(bank,list(sources))['errors'];require(not errors,'replacement BANK: '+str(errors))
    visual={s['question_id']for s in proposal['visual_stimuli']};require(visual<=set(ids),'replacement: unknown image question')
    old_used={t['question_id']for t in base['document']['tasks']}
    old_visual=sum(bool(q.get('stimuli'))and q['question_id']in old_used for q in base['document']['bank_snapshot']['questions'])
    require(len(visual)>=old_visual,'replacement: cannot silently drop existing usable image-question coverage')
    medical_input(bank,proposal['clinical_conflicts'])
    for l,q in zip(proposal['links'],bank['questions']):
        ix=[i for c in l['components']for i in c['answer_unit_indices']]
        require(ix and len(ix)==len(set(ix))and set(ix)==set(range(len(q['answer_units']))),'replacement: cover all answer units exactly once')
        require(l['requires_visual']==(q['question_id']in visual),'replacement: image/text condition mismatch')
        for ref in l['evidence']:
            require(ref['source_id']in sources and ref['pages']and max(ref['pages'])<=sources[ref['source_id']]['page_count'],'replacement: invalid evidence')
    return proposal


def check_source(proposal,source):
    validate_shape(source,SOURCE_REVIEW,'replacement source review')
    require([r['question_id']for r in source['reviews']]==[q['question_id']for q in proposal['bank']['questions']],'replacement: incomplete/reordered source review')
    return source


def check_bank(base,proposal,bank):
    check_proposal(base,proposal);raw=copy.deepcopy(bank)
    for q in raw['questions']:q.pop('stimuli',None)
    require(raw==proposal['bank'],'replacement: rendered clinical content differs')
    validate_images(bank,base['document']['review']['sources']);expected={q['question_id']:[]for q in bank['questions']}
    sources={s['source_id']:s['sha256']for s in base['document']['review']['sources']}
    for s in proposal['visual_stimuli']:expected[s['question_id']].append((s['source_id'],sources[s['source_id']],s['page'],s['crop']))
    for q in bank['questions']:
        require([(s['source_id'],s['source_sha256'],s['page'],s['crop'])for s in q.get('stimuli',[])]==expected[q['question_id']],'replacement: changed image placement')
    return bank


def eligible(proposal,source,medical):
    check_source(proposal,source);ids=[q['question_id']for q in proposal['bank']['questions']]
    require([r['question_id']for r in medical['reviews']]==ids and medical['pool_checks']==[],'replacement: incomplete blind medical review')
    med={r['question_id']:r for r in medical['reviews']};links={l['question_id']:l for l in proposal['links']}
    require(all(r['verdict']in ('ok','doubt','wrong')and r['note']for r in med.values()),'replacement: invalid medical verdict')
    return [r['question_id']for r in source['reviews']if r['source_verdict']==r['goal_verdict']==r['importance_verdict']=='ok'
        and r['all_answer_units_covered']and med[r['question_id']]['verdict']=='ok'
        and r['visual_verdict']==('ok'if links[r['question_id']]['requires_visual']else'not_applicable')]


def assemble(base,proposal,source,medical,bank,revision):
    check_bank(base,proposal,bank);keep=set(eligible(proposal,source,medical));old=base['document'];review=copy.deepcopy(old['review'])
    review.update(bank_sha256=document_hash(bank),concepts=[{'concept_id':c['concept_id'],'label':c['title'],'parent_ids':[]}for c in bank['concepts']],
        relations=[],targets=[],points=[],mappings=[],coverage=[],provenance={'status':'reviewed','method':POLICY,
        'reviewer':'Independent CLI original-source/goal and blind medical sessions','independent_points':'derived',
        'notes':'New per-question goals checked against complete original PDF and earlier independent points. Earlier verdicts archived separately.'})
    qs={q['question_id']:q for q in bank['questions']};verdicts={r['question_id']:r for r in source['reviews']};tasks=[]
    for i,l in enumerate(proposal['links']):
        qid=l['question_id'];q=qs[qid];stem='N'+str(i+1);cid=stem+'_A';rid=stem+'_R';tid=stem+'_T';did=stem+'_D';pid=stem+'_P';ready=qid in keep
        require(q['concept_id']in {c['concept_id']for c in review['concepts']},'replacement: unknown concept')
        review['concepts'].append({'concept_id':cid,'label':l['answer_scope'],'parent_ids':[]})
        review['relations'].append({'relation_id':rid,'from_id':q['concept_id'],'to_id':cid,'kind':'association','condition':l['relation_fact'],
            'evidence':l['evidence'],'review_status':'reviewed'if ready else'unreviewed','reason':verdicts[qid]['reason']})
        direction={'direction_id':did,'cue':l['cue'],'answer_scope':l['answer_scope'],'requirement':'required','relation_ids':[rid],
            'components':[{'component_id':stem+'_C'+str(j+1),'text':c['text']}for j,c in enumerate(l['components'])],'requires_visual':l['requires_visual']}
        review['targets'].append({'target_id':tid,'title':l['title'],'concept_ids':[q['concept_id'],cid],'relation_ids':[rid],'role':'leaf',
            'reason':l['reason'],'evidence':l['evidence'],'directions':[direction],'importance':l['importance']})
        review['points'].append({'point_id':pid,'text':l['title'],'evidence':l['evidence'],'target_ids':[tid],'scope_status':'included','reason':l['reason']})
        review['coverage'].append({'point_id':pid,'status':'covered'if ready else'unknown','confirmed_direction_ids':[did]if ready else[],
            'partial_direction_ids':[],'missing_direction_ids':[],'unknown_direction_ids':[]if ready else[did],'reason':verdicts[qid]['reason'],'exclusion_basis':None})
        if ready:
            review['mappings'].append({'question_id':qid,'question_sha256':question_hash(q,bank),'target_id':tid,'direction_id':did,
                'tested_relation_ids':[rid],'provided_relation_ids':[],'explanation_relation_ids':[],'reason':verdicts[qid]['reason']})
            tasks.append({'task_id':'task-'+document_hash([qid,did])[:24],'question_id':qid,'direction_id':did})
    while True:
        present={t['question_id']for t in tasks};kept=[t for t in tasks if set(qs[t['question_id']]['prerequisites'])<=present]
        if tasks==kept:break
        tasks=kept
    order=graph_order(bank);tasks.sort(key=lambda t:order.index(t['question_id']))
    doc={**copy.deepcopy(old),'revision':revision,'review':review,'bank_snapshot':copy.deepcopy(bank),'bank_source':'standalone','bank_build_id':None,
        'adopted_target_ids':[t['target_id']for t in review['targets']],'tasks':tasks,'equivalences':[],'prerequisites':[]}
    return validate_document(doc)


def rejection_reason(base,proposal):
    validate_shape(proposal,PROPOSAL,'rejected replacement proposal')
    try:check_proposal(base,proposal)
    except ValueError as error:return str(error)
    raise ValueError('replacement: claimed author rejection actually passes')


def check_execution(execution,outputs,*,rejected=False):
    require(set(execution)==set(outputs),'replacement: missing real execution')
    for name,value in outputs.items():
        r=execution[name];p=r['provider'];raw=r['rawOutput'];sha=hashlib.sha256(raw.encode('utf-8')).hexdigest()
        require(r['status']==('rejected'if rejected else'completed')and p.get('session_id')and p.get('turns',0)>0,'replacement: no actual completed CLI turn')
        require(json.loads(raw)==value and r['outputHash']==document_hash(value)and r['outputSha256']==sha and r['providerHash']==document_hash(p),'replacement: altered provider/output')
        if name=='medical':require(p['text']==raw,'replacement: altered blind medical output')
        else:require(json.loads(p['text'])=={'path':'result.json','sha256':sha},'replacement: altered file receipt')


def validate(base,value):
    require(value['policy']==POLICY and value['parentResultHash']==document_hash(base),'replacement: changed historical input')
    require(value['runId']and value['document']['revision']!=base['document']['revision'],'replacement: separate generation required')
    require(value['historicalRepairRounds']==base['manifest']['repairRounds']==3,'replacement: changed earlier history')
    rounds=value['rounds'];require([r['round']for r in rounds]==list(range(len(rounds)))and 1<=len(rounds)<=4,'replacement: invalid new budget')
    for r in rounds:
        if r.get('status')=='author_rejected':
            require(r['rejection']==rejection_reason(base,r['proposal']),'replacement: changed structural rejection')
            check_execution(r['execution'],{'author':r['proposal']},rejected=True)
            continue
        check_proposal(base,r['proposal']);check_source(r['proposal'],r['sourceReview'])
        check_execution(r['execution'],{'author':r['proposal'],'source':r['sourceReview'],'medical':r['medicalReview']})
    last=rounds[-1];require(last.get('status')!='author_rejected'and value['repairRounds']==last['round']<=3,'replacement: new budget differs')
    expected=assemble(base,last['proposal'],last['sourceReview'],last['medicalReview'],value['document']['bank_snapshot'],value['document']['revision'])
    require(value['document']==expected,'replacement: altered reviewed document')
    ready=not last['sourceReview']['coverage_findings']and len(expected['tasks'])==len(expected['bank_snapshot']['questions'])
    require(value['ready']==ready,'replacement: false readiness')
    return value
