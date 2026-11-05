"""Model judgments in; immutable references and consistent coverage out.

This module never infers which relation a question tests. Those judgments and
direction-review uncertainty are supplied by the independent source reviewer.
"""
import copy

from studyez_contracts.learning_links.schema import TEXT, obj, arr, enum
from studyez_contracts.learning_links.validate import validate_shape, require, index_by, question_hash
from .validate import document_hash

VERSION = 'source-assessment/1'
RELATION = obj(relation_id=TEXT, role=enum('tested','provided','explanation'),
               direction_ids=arr(TEXT), reason=TEXT)
QUESTION = obj(question_id=TEXT, verdict=enum('ok','doubt','wrong'), note=TEXT,
               suggested_answer={'type':'string'}, relations=arr(RELATION))
SCHEMA = obj(schema_version=enum(VERSION), summary=TEXT, question_reviews=arr(QUESTION,1),
             direction_checks=arr(obj(direction_id=TEXT,status=enum('reviewed','unknown'),reason=TEXT),1),
             input_issues=arr(TEXT))


def directions_of(brief):
    return {d['direction_id']:(t['target_id'],d) for t in brief['targets'] for d in t['directions']}


def source_assessment_schema(brief, bank):
    """Bind output choices to actual IDs before the model can emit a reference."""
    directions=directions_of(brief)
    variants=[]
    for relation in brief['relations']:
        rid=relation['relation_id']
        allowed=[did for did,(_,d) in directions.items() if rid in d['relation_ids']]
        # A real tested relation can use a cue absent from the declared plan.
        # Keep that evidence in the raw assessment without awarding a direction.
        refs=arr(enum(*allowed) if allowed else TEXT)
        if not allowed:refs['maxItems']=0
        variants.append(obj(relation_id=enum(rid),role=enum('tested'),direction_ids=refs,reason=TEXT))
        none=arr(TEXT);none['maxItems']=0
        variants.append(obj(relation_id=enum(rid),role=enum('provided','explanation'),direction_ids=none,reason=TEXT))
    schema=copy.deepcopy(SCHEMA)
    questions=schema['properties']['question_reviews']
    questions.update(minItems=len(bank['questions']),maxItems=len(bank['questions']))
    questions['items']['properties']['question_id']=enum(*(q['question_id'] for q in bank['questions']))
    questions['items']['properties']['relations']['items']={'anyOf':variants}
    checks=schema['properties']['direction_checks']
    checks.update(minItems=len(directions),maxItems=len(directions))
    checks['items']['properties']['direction_id']=enum(*directions)
    return schema


def envelope(brief, bank, assessment):
    return {'briefHash':document_hash(brief),'bankHash':document_hash(bank),'assessment':copy.deepcopy(assessment)}


def compile_source_assessment(brief, bank, raw):
    """Compile without fixing, dropping, or upgrading any model judgment."""
    from .automation import pending_review,validate_brief,validate_audit
    # Packet-level callers separately verify whether this provenance was really
    # independently extracted; compilation must preserve either valid mode.
    validate_brief(brief,from_sources=brief['provenance']['independent_points']=='confirmed')
    require(type(raw) is dict and set(raw)=={'briefHash','bankHash','assessment'},'assessment: malformed envelope')
    require(raw['briefHash']==document_hash(brief) and raw['bankHash']==document_hash(bank),
            'assessment: input revision mismatch')
    assessment=raw['assessment'];validate_shape(assessment,SCHEMA,'assessment')
    directions=directions_of(brief)
    relations=index_by(brief['relations'],'relation_id')
    questions=index_by(bank['questions'],'question_id')
    reviews=index_by(assessment['question_reviews'],'question_id')
    require(set(reviews)==set(questions),'assessment: every question needs exactly one review')
    checks=index_by(assessment['direction_checks'],'direction_id')
    require(set(checks)==set(directions),'assessment: every direction needs exactly one review')
    review=pending_review(brief,bank)
    review['provenance'].update(status='reviewed',method=VERSION+'; '+review['provenance']['method'])
    review['provenance']['notes']+='\n'+assessment['summary']
    tested={did:set() for did in directions}
    for qid,row in reviews.items():
        roles=index_by(row['relations'],'relation_id')
        for rid,claim in roles.items():
            require(rid in relations,'assessment: unknown relation')
            ds=claim['direction_ids']
            require(len(ds)==len(set(ds)),'assessment: duplicate tested direction')
            if claim['role']!='tested':
                require(not ds,'assessment: provided/explanation is not tested')
                continue
            allowed={did for did,(_,d) in directions.items() if rid in d['relation_ids']}
            require(set(ds)<=allowed,'assessment: tested relation outside direction')
            require(relations[rid]['review_status']=='reviewed','assessment: unreviewed relation cannot be tested')
        active=[did for did in directions if any(c['role']=='tested' and did in c['direction_ids'] for c in roles.values())]
        for did in active:
            groups={role:[rid for rid,c in roles.items() if c['role']==role and (role!='tested' or did in c['direction_ids'])]
                    for role in ('tested','provided','explanation')}
            tested[did].update(groups['tested'])
            review['mappings'].append({'question_id':qid,'question_sha256':question_hash(questions[qid],bank),
                'target_id':directions[did][0],'direction_id':did,
                **{role+'_relation_ids':ids for role,ids in groups.items()},
                'reason':'; '.join(rid+': '+roles[rid]['reason'] for ids in groups.values() for rid in ids)})
    states={}
    for did,(_,direction) in directions.items():
        states[did]=('unknown' if checks[did]['status']=='unknown' else
            'confirmed' if set(direction['relation_ids'])<=tested[did] else 'partial' if tested[did] else 'missing')
    for coverage,point in zip(review['coverage'],brief['points']):
        if point['scope_status']=='excluded':
            coverage['reason']=point['reason'];continue
        relevant=[did for did,(tid,_) in directions.items() if tid in point['target_ids']]
        for state in ('confirmed','partial','missing','unknown'):
            coverage[state+'_direction_ids']=[did for did in relevant if states[did]==state]
        confirmed,partial,missing,unknown=(coverage[s+'_direction_ids'] for s in ('confirmed','partial','missing','unknown'))
        required={did for did in relevant if directions[did][1]['requirement']=='required'}
        if required<=set(confirmed) and required and all(directions[d][1]['requirement']!='undecided' for d in relevant):
            status='covered'
        elif (confirmed or partial) and (partial or missing or unknown):status='partial'
        elif missing and not confirmed and not partial and not unknown:status='gap'
        elif unknown:status='unknown'
        elif not required or any(directions[d][1]['requirement']=='undecided' for d in relevant):status='unknown'
        else:raise ValueError('assessment: point has no representable required-direction coverage: '+point['point_id'])
        coverage['status']=status
        coverage['reason']='; '.join(did+': '+checks[did]['reason'] for did in relevant)
        if status=='unknown' and not unknown:
            coverage['reason']='필수 방향이 미정이므로 목표 전체 충족은 보류한다. 실제 회상 관계 확인은 그대로 보존한다. '+coverage['reason']
    audit={'review':review,'question_checks':{'summary':assessment['summary'],'reviews':[
        {k:row[k] for k in ('question_id','verdict','note','suggested_answer')} for row in assessment['question_reviews']]},
        'input_issues':copy.deepcopy(assessment['input_issues'])}
    validate_audit(brief,bank,audit)
    return audit
