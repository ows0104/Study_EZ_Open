"""Versioned generation contracts. Semantic decisions belong to content reviewers."""
import copy
import json
import re
from .automation import BRIEF_SCHEMA, CORE, packet_hash
from .source_assessment import SCHEMA as SOURCE1, source_assessment_schema, envelope
from .validate import document_hash, validate_document,validate_prerequisites
from .media import CROP, validate_images
from studyez_contracts.learning_links.schema import obj,arr,enum,TEXT,REVIEW_SCHEMA
from studyez_contracts.learning_links.validate import require,validate_shape,index_by
from studyez_contracts.bank.schema import BANK
from studyez_contracts.bank.validate import validate_bank
from . import recall_units as recall

VERSION='source-assessment/2'
POLICY='root-generation/2'
COMPONENT=obj(component_id=TEXT,text=TEXT)
REVIEW2=copy.deepcopy(REVIEW_SCHEMA)
REVIEW2['properties']['schema_version']=enum('learning-links/2')
direction=REVIEW2['properties']['targets']['items']['properties']['directions']['items']
direction['properties'].update(components=arr(COMPONENT,1),requires_visual={'type':'boolean'})
direction['required']+=['components','requires_visual']
direction['properties']['recall_units']=arr(obj(unit_id=TEXT,cue=TEXT,answer_scope=TEXT,
    component_ids=arr(TEXT,1),relation_ids=arr(TEXT,1)),1)
BRIEF=copy.deepcopy(BRIEF_SCHEMA)
BRIEF['properties']['schema_version']=enum('learning-brief/2')
BRIEF['properties']['targets']=copy.deepcopy(REVIEW2['properties']['targets'])
BRIEF['properties']['recall_policy']=enum(recall.POLICY)
AUTHOR_BANK=copy.deepcopy(BANK)
AUTHOR_BANK['properties']['questions']['items']['properties'].pop('stimuli',None)
CONFLICT=obj(conflict_id=TEXT,facts=TEXT)
AUTHOR=obj(bank=AUTHOR_BANK,brief=BRIEF,visual_stimuli=arr(CROP),clinical_conflicts=arr(CONFLICT),map_change_reason=TEXT)
PARALLEL_CROP=copy.deepcopy(CROP)
PARALLEL_CROP['properties']['image_id']=TEXT
PARALLEL_AUTHOR=copy.deepcopy(AUTHOR)
PARALLEL_AUTHOR['properties']['visual_stimuli']=arr(PARALLEL_CROP)


def author_schema(parallel=False):
    return PARALLEL_AUTHOR if parallel else AUTHOR
TIER_POLICY='bank-tier-alias/1'


def tier_projection(value):
    """Only the canonical authored tier alias is a transport spelling change."""
    from studyez_contracts.bank.authored_json import canonical_tier
    result=copy.deepcopy(value);changes=[]
    if isinstance(result,dict)and isinstance(result.get('bank'),dict):
        questions=result['bank'].get('questions',[])
        for question in questions if isinstance(questions,list)else[]:
            if isinstance(question,dict)and question.get('tier')=='Must-Know':
                question['tier']=canonical_tier(question['tier'])
                changes.append({'question_id':question.get('question_id'),'from':'Must-Know','to':'Essential'})
    projection={'policy':TIER_POLICY,'rawHash':document_hash(value),'decodedHash':document_hash(result),
                'changes':changes}if changes else None
    return result,projection
ISSUE=obj(issue_id=TEXT,kind=enum('question_fix','map_fix','required_gap','optional_extension','limitation','confirmation'),
          text=TEXT,question_ids=arr(TEXT),direction_ids=arr(TEXT))
PART=obj(component_id=TEXT,location=enum('answer','provided','explanation','missing','unknown'),
         answer_unit_indices=arr({'type':'integer','minimum':0}),reason=TEXT)
EVIDENCE=obj(question_id=TEXT,direction_id=TEXT,components=arr(PART,1),
             visual_verdict=enum('ok','doubt','wrong','not_applicable'),reason=TEXT)
REL_CHECK=obj(relation_id=TEXT,status=enum('supported','conflict','unknown'),reason=TEXT)
TARGET_CHECK=obj(target_id=TEXT,status=enum('consistent','conflict','unknown'),reason=TEXT)
PRE_CHECK=obj(question_id=TEXT,prerequisite_id=TEXT,status=enum('supported','unnecessary','unknown'),reason=TEXT)
SOURCE=copy.deepcopy(SOURCE1)
SOURCE['properties']['schema_version']=enum(VERSION)
del SOURCE['properties']['input_issues'];SOURCE['required'].remove('input_issues')
SOURCE['properties'].update(direction_evidence=arr(EVIDENCE),relation_checks=arr(REL_CHECK,1),target_checks=arr(TARGET_CHECK,1),
    prerequisite_checks=arr(PRE_CHECK),issues=arr(ISSUE),clinical_context_status=enum('consistent','conflict','unknown'),clinical_context_reason=TEXT)
SOURCE['required']+=['direction_evidence','relation_checks','target_checks','prerequisite_checks','issues','clinical_context_status','clinical_context_reason']
SOURCE['properties']['direction_checks']['items']['properties']['scope_status']=enum('consistent','conflict','unknown')
SOURCE['properties']['direction_checks']['items']['required'].append('scope_status')
SOURCE['properties']['design_checks']=arr(obj(question_id=TEXT,verdict=enum('ok','doubt','wrong'),reason=TEXT))

def medical_input(bank,conflicts):
    fields=('question_id','concept_id','format','question','answer','answer_units','options','correct_option_ids',
        'matching_left','matching_right','answer_pairs','sequence_items','correct_order','conflict_id',
        'option_explanations','option_pools','explanation')
    result={'questions':[{k:q[k]for k in fields if k in q}for q in bank['questions']],
            'clinical_conflicts':copy.deepcopy(conflicts)}
    # Do not rewrite clinical prose. Explicit historical review markers are
    # rejected and routed back to the same bounded authoring loop.
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for v in value.values():yield from strings(v)
        elif isinstance(value,list):
            for v in value:yield from strings(v)
    history=r'sourceAudit|medicalVerdicts?|medicalReview|(?:과거|이전)\s*(?:AI|모델)\s*(?:검수|검토|판정)|(?:검수|검토)\s*판정'
    require(not any(re.search(history,s,re.I)for s in strings(result)),'medical input: historical review metadata must be separated by the content author')
    return result

def legacy_brief(brief):
    value=copy.deepcopy(brief);value['schema_version']='learning-brief/1'
    value.pop('recall_policy',None)
    for t in value['targets']:
        for d in t['directions']:
            d.pop('components',None);d.pop('requires_visual',None)
            d.pop('recall_units',None)
    return value

def validate_brief(brief,sources=None):
    from .automation import validate_brief as old
    validate_shape(brief,BRIEF,'brief2')
    view=legacy_brief(brief);view['prerequisites']=[]
    old(view,sources,from_sources=brief['provenance']['independent_points']=='confirmed')
    targets=index_by(brief['targets'],'target_id')
    validate_prerequisites(targets,index_by(brief['relations'],'relation_id'),brief['prerequisites'],set(targets),reviewed=False)
    for t in brief['targets']:
        for d in t['directions']:index_by(d['components'],'component_id')
    recall.project_brief(brief)
    return brief

def brief_findings(brief,sources=None):
    """Mechanical findings only; raw model-authored data stays intact."""
    validate_shape(brief,BRIEF,'brief2')
    errors=[]
    try:validate_brief(brief,sources)
    except (ValueError,KeyError) as error:errors.append(str(error))
    try:targets=index_by(brief['targets'],'target_id');relations=index_by(brief['relations'],'relation_id')
    except ValueError as error:return list(dict.fromkeys([*errors,str(error)]))
    for edge in brief['prerequisites']:
        relation=relations.get(edge['relation_id'],{});before=targets.get(edge['before_target'],{});after=targets.get(edge['after_target'],{})
        if (relation.get('kind')!='prerequisite'or relation.get('from_id')not in before.get('concept_ids',[])
                or relation.get('to_id')not in after.get('concept_ids',[])):
            errors.append('Invalid prerequisite binding: '+json.dumps(edge,sort_keys=True,ensure_ascii=False))
    return errors

def validate_initial_correction(before,after,reason):
    validate_shape(before,BRIEF,'initial brief2');validate_brief(after)
    preserve_map_inputs(before,after)
    require(before!=after and after['provenance']['independent_points']=='derived','initial correction: question-informed map must be derived')
    require(type(reason)is str and reason.strip(),'initial correction: reason required')

def source_schema(brief,bank):
    old=source_assessment_schema(legacy_brief(brief),bank)
    value=copy.deepcopy(SOURCE)
    if recall.enabled(brief):value['required'].append('design_checks')
    value['properties']['question_reviews']=old['properties']['question_reviews']
    value['properties']['direction_checks'].update(minItems=len(old['properties']['direction_checks']['items']['properties']['direction_id']['enum']),
        maxItems=len(old['properties']['direction_checks']['items']['properties']['direction_id']['enum']))
    value['properties']['direction_checks']['items']['properties']['direction_id']=old['properties']['direction_checks']['items']['properties']['direction_id']
    return value

def validate_authoring(value,previous=None):
    validate_shape(value,author_schema(any('image_id'in s for s in value.get('visual_stimuli',[]))),'authoring2');validate_brief(value['brief'])
    require(not any(q.get('stimuli')for q in value['bank']['questions']),'authoring: inline images are renderer-owned')
    conflicts=index_by(value['clinical_conflicts'],'conflict_id')
    require(set(conflicts)=={r['conflict_id']for r in value['bank']['source_conflicts']},'authoring: clinical conflicts need complete ID coverage')
    if previous is not None:
        validate_transition(previous['brief'],value['brief'],value['map_change_reason'])
    return value

def validate_transition(before,after,reason):
    validate_brief(before);validate_brief(after)
    preserve_map_inputs(before,after)
    changed=any(before[k]!=after[k]for k in ('concepts','relations','targets','points','prerequisites','scope'))
    if before['provenance']['independent_points']!='confirmed':
        require(after['provenance']['independent_points']!='confirmed','authoring: independent extraction cannot be re-certified after revision')
    if changed:
        require(after['provenance']['independent_points']=='derived','authoring: question-informed map is derived, not independent extraction')
        require(type(reason)is str and reason.strip(),'authoring: map revision reason required')

def preserve_map_inputs(before,after):
    for k in ('lecture_id','sources','exclusions'):
        require(before[k]==after[k],'authoring: source point/scope preservation: '+k)
    for k in ('label','included','excluded'):
        require(before['scope'][k]==after['scope'][k],'authoring: source point/scope preservation: scope.'+k)
    points=index_by(after['points'],'point_id')
    for p in before['points']:
        require(p['point_id']in points and all(p[k]==points[p['point_id']][k]for k in ('text','scope_status')),'authoring: original point text/scope changed')


def validate_recovered_authoring(before,after):
    """A rejected brief may be corrected; already completed questions stay exact."""
    validate_shape(before,AUTHOR,'rejected authoring2');validate_authoring(after)
    require(brief_findings(before['brief']),'recovery: rejected brief has no structural findings')
    preserve_map_inputs(before['brief'],after['brief'])
    for k in ('bank','visual_stimuli','clinical_conflicts'):
        require(before[k]==after[k],'recovery: completed authoring content changed: '+k)
    require(after['brief']['provenance']['independent_points']=='derived'and after['map_change_reason'].strip(),
            'recovery: corrected brief must be derived with a reason')


def validate_format_recoveries(meta,stages):
    rows=meta.get('formatRecoveries',[])
    require(type(rows)is list and len(rows)<=1,'result2: invalid format recovery history')
    for row in rows:
        require(type(row)is dict and set(row)=={'proof','proofHash'}and type(row['proof'])is dict
            and row['proofHash']==document_hash(row['proof']),'result2: changed format recovery proof')
        p=row['proof']
        require(set(p)=={'priorLedger','priorLedgerHash','packetHash','currentRuntimeHash','reason','stage',
            'rawAuthoring','projection','nativeJournalSha256','recoveryToolSha256','modelReplay'},'result2: malformed format recovery')
        old=p['priorLedger'];name=p['stage']
        require(type(old)is dict and type(old.get('stages'))is dict and old.get('pipelineVersion')==POLICY
            and p['priorLedgerHash']==document_hash(old)and not old.get('formatRecoveries')
            and type(old.get('identity'))is str and re.fullmatch(r'[a-f0-9]{64}',old['identity']),
            'result2: changed prior format ledger')
        format_runtime=meta['runtimeRevalidations'][0]['proof']['priorLedger']['identity']if meta.get('runtimeRevalidations')else meta['runtimeHash']
        require(type(name)is str and re.fullmatch(r'generate|repair-[1-3]',name)
            and p['packetHash']==meta['inputHash']and p['currentRuntimeHash']==format_runtime
            and p['modelReplay']is False and type(p['reason'])is str and p['reason'].strip(),
            'result2: changed format recovery identity')
        require(type(old.get('repairRounds'))is int and 0<=old['repairRounds']<=meta['repairRounds']<=3,
            'result2: format recovery reset budget')
        require(meta.get('authoringRecoveries',[])==old.get('authoringRecoveries',[]),
            'result2: earlier authoring recovery was changed')
        prior=old['stages'];entry=prior.get(name,{})
        require(type(entry)is dict and all(type(v)is dict for v in prior.values())
            and entry.get('status')=='failed'and set(prior)<=set(stages),'result2: format stage was not failed')
        for key,value in prior.items():
            if key!=name:require(stages[key]=={'name':key,**value},'result2: changed reused format stage')
        decoded,projection=tier_projection(p['rawAuthoring'])
        require(projection is not None and projection==p['projection'],'result2: wrong tier projection')
        validate_authoring(decoded)
        current=stages[name]
        require(current['status']=='completed'and current['inputHash']==entry['inputHash']
            and current['rawOutputHash']==document_hash(decoded)
            and current['briefHash']==document_hash(decoded['brief']),'result2: format output mismatch')
        require(all(type(p[k])is str and re.fullmatch(r'[a-f0-9]{64}',p[k])for k in ('nativeJournalSha256','recoveryToolSha256')),
            'result2: missing original Native rejection')
    return rows


def validate_runtime_revalidations(meta,stages):
    rows=meta.get('runtimeRevalidations',[])
    require(type(rows)is list and len(rows)<=1,'result2: invalid runtime revalidation history')
    for row in rows:
        require(type(row)is dict and set(row)=={'proof','proofHash'}and type(row['proof'])is dict
            and row['proofHash']==document_hash(row['proof']),'result2: changed runtime revalidation')
        p=row['proof']
        require(set(p)=={'priorLedger','priorLedgerHash','packetHash','currentRuntimeHash','reason','toolSha256','modelReplay'},
            'result2: malformed runtime revalidation')
        old=p['priorLedger']
        require(type(old)is dict and type(old.get('stages'))is dict and not old.get('runtimeRevalidations')
            and old.get('formatRecoveries')and p['priorLedgerHash']==document_hash(old)
            and old.get('pipelineVersion')==POLICY,'result2: invalid prior runtime ledger')
        require(p['packetHash']==meta['inputHash']and p['currentRuntimeHash']==meta['runtimeHash']
            and p['modelReplay']is False and type(p['reason'])is str and p['reason'].strip()
            and type(p['toolSha256'])is str and re.fullmatch(r'[a-f0-9]{64}',p['toolSha256']),
            'result2: changed runtime revalidation identity')
        require(meta.get('formatRecoveries',[])==old['formatRecoveries']
            and meta.get('authoringRecoveries',[])==old.get('authoringRecoveries',[])
            and type(old.get('repairRounds'))is int and old['repairRounds']==meta['repairRounds'],
            'result2: runtime revalidation changed history/budget')
        require(set(old['stages'])<=set(stages)and all(stages[k]=={'name':k,**v}for k,v in old['stages'].items()),
            'result2: runtime revalidation changed cached stages')
    return rows


def validate_authoring_recoveries(meta,stages):
    rows=meta.get('authoringRecoveries',[])
    require(type(rows)is list and len(rows)<=1,'result2: invalid authoring recovery history')
    for row in rows:
        require(type(row)is dict and set(row)=={'proof','proofHash'}and type(row['proof'])is dict
            and row['proofHash']==document_hash(row['proof']),
                'result2: changed authoring recovery proof')
        p=row['proof'];require(set(p)=={'priorLedger','priorLedgerHash','packetHash','currentRuntimeHash',
            'reason','mode','stage','rawAuthoring','findings','modelReplay'},'result2: malformed authoring recovery')
        old=p['priorLedger'];name=p['stage'];draft=p['rawAuthoring']
        require(type(old)is dict and type(old.get('stages'))is dict
            and type(old.get('identity'))is str and re.fullmatch(r'[a-f0-9]{64}',old['identity'])
            and type(name)is str and p['priorLedgerHash']==document_hash(old)and old.get('pipelineVersion')==POLICY,
                'result2: changed prior authoring ledger')
        require(not old.get('authoringRecoveries')and not old.get('normalizationRecoveries'),
                'result2: repeated or mixed authoring recovery')
        origin_runtime=meta['formatRecoveries'][0]['proof']['priorLedger']['identity']if meta.get('formatRecoveries')else meta['runtimeHash']
        require(p['packetHash']==meta['inputHash']and p['currentRuntimeHash']==origin_runtime
            and p['modelReplay']is False and type(p['reason'])is str and p['reason'].strip(),
            'result2: changed authoring recovery identity')
        prior=old.get('stages',{});entry=prior.get(name,{})
        initial_cost=int(bool(brief_findings(meta['initialBrief'])))
        require(all(type(v)is dict for v in prior.values())and type(entry)is dict
            and entry.get('status')=='failed'and set(prior)<=set(stages)
            and [k for k,v in prior.items()if v['status']=='failed']==[name],
            'result2: recovery was not one failed authoring acceptance')
        validate_shape(draft,AUTHOR,'rejected authoring2')
        require(all(type(entry.get(k))is str and re.fullmatch(r'[a-f0-9]{64}',entry[k])
            for k in ('inputHash','rawOutputHash','usageHash'))and entry.get('rawOutputHash')==document_hash(draft)
            and p['findings']==brief_findings(draft['brief']), 'result2: rejected authoring proof mismatch')
        require(type(old.get('repairRounds'))is int and 0<=old['repairRounds']<=3
            and meta['repairRounds']>=old['repairRounds'],'result2: recovered budget reset')
        for k,v in prior.items():
            if k!=name:require(stages[k]=={'name':k,**v},'result2: changed reused stage')
        current=stages[name]
        if p['mode']=='brief-repair':
            require(name=='generate'and set(prior)=={'normalize','generate'}and p['findings']
                and old['repairRounds']==initial_cost and meta['repairRounds']>=old['repairRounds']+1,
                'result2: invalid rejected-brief repair allowance')
            require(current=={'name':name,**entry},'result2: original rejected stage was changed')
        else:
            require(p['mode']=='acceptance-recheck'and re.fullmatch(r'repair-[1-3]',name)
                and old['repairRounds']==int(name.split('-')[1])+initial_cost
                and not p['findings'],'result2: invalid authoring acceptance recheck')
            validate_authoring(draft)
            require(current['status']=='completed'and current['rawOutputHash']==entry['rawOutputHash']
                and all(current[k]==entry[k]for k in ('inputHash','usageHash'))
                and current['briefHash']==document_hash(draft['brief']),
                'result2: completed recheck differs from original call')
    return rows

def graph_order(bank):
    qs=index_by(bank['questions'],'question_id');done=set();visiting=set();order=[]
    def visit(qid):
        require(qid in qs,'prerequisites: missing question '+str(qid))
        require(qid not in visiting,'prerequisites: cycle')
        if qid in done:return
        visiting.add(qid)
        deps=qs[qid].get('prerequisites',[])
        require(len(deps)==len(set(deps)),'prerequisites: duplicate edge')
        for pre in deps:visit(pre)
        visiting.remove(qid);done.add(qid);order.append(qid)
    for qid in qs:visit(qid)
    return order

def task_dependencies(doc):
    qs={q['question_id']:q for q in doc['bank_snapshot']['questions']};tasks=doc['tasks'];by_question={}
    owners={d['direction_id']:t['target_id']for t in doc['review']['targets']for d in t['directions']}
    for t in tasks:by_question.setdefault(t['question_id'],t['task_id'])
    deps={t['task_id']:[]for t in tasks}
    for t in tasks:
        for qid in qs[t['question_id']].get('prerequisites',[]):
            require(qid in by_question,'prerequisites: no prepared question '+qid)
            deps[t['task_id']].append(by_question[qid])
        for edge in doc['prerequisites']:
            if owners[t['direction_id']]==edge['after_target']:
                before=[p['task_id']for p in tasks if owners[p['direction_id']]==edge['before_target']]
                require(before,'prerequisites: no prepared target '+edge['before_target'])
                deps[t['task_id']]+=before
    return {k:list(dict.fromkeys(v))for k,v in deps.items()}

def order_plan(doc,selected,available,assessed):
    """Combine question and target prerequisites; a prior miss still opens the next step."""
    deps=task_dependencies(doc);tasks={t['task_id']:t for t in doc['tasks']};chosen={t['task_id']:t for t in selected}
    done=set();visiting=set();result=[]
    def emit(tid):
        require(tid not in visiting,'prerequisites: combined target/question cycle')
        if tid in done:return
        require(tid in available,'Prepared prerequisite became unavailable: '+tid);visiting.add(tid)
        for pre in deps[tid]:
            if tasks[pre]['question_id']not in assessed or pre in chosen:emit(pre)
        visiting.remove(tid);done.add(tid)
        result.append(chosen.get(tid,{**tasks[tid],'reason':'명시적 선행 문항'}))
    for t in selected:emit(t['task_id'])
    return result

def compile_assessment(brief,bank,raw):
    validate_brief(brief)
    require(raw==envelope(brief,bank,raw.get('assessment')),'assessment2: input revision mismatch')
    validate_shape(raw['assessment'],SOURCE,'assessment2')
    if not recall.enabled(brief):return _compile_assessment(brief,bank,raw)
    projected,proof,groups=recall.project_assessment(brief,bank,raw)
    audit=_compile_assessment(projected,bank,proof)
    audit['assessment']=copy.deepcopy(raw)
    audit['goal_coverage']=recall.summarize(groups,audit)
    return audit


def _compile_assessment(brief,bank,raw):
    from .source_assessment import compile_source_assessment as compile1
    validate_brief(brief);validate_images(bank,brief['sources'])
    require(type(raw)is dict and set(raw)=={'briefHash','bankHash','assessment'},'assessment2: malformed input envelope')
    require(raw==envelope(brief,bank,raw.get('assessment')),'assessment2: input revision mismatch')
    a=raw['assessment'];validate_shape(a,SOURCE,'assessment2')
    dirs={d['direction_id']:(t,d)for t in brief['targets']for d in t['directions']}
    qs=index_by(bank['questions'],'question_id');rels=index_by(a['relation_checks'],'relation_id');targets=index_by(a['target_checks'],'target_id')
    question_reviews=index_by(a['question_reviews'],'question_id')
    require(set(question_reviews)==set(qs),'assessment2: every question needs one review')
    direction_checks=index_by(a['direction_checks'],'direction_id')
    require(set(direction_checks)==set(dirs),'assessment2: missing direction checks')
    require(set(rels)=={r['relation_id']for r in brief['relations']},'assessment2: missing relation checks')
    require(set(targets)=={t['target_id']for t in brief['targets']},'assessment2: missing target checks')
    pres={(q['question_id'],p)for q in bank['questions']for p in q.get('prerequisites',[])}
    pre_checks={(r['question_id'],r['prerequisite_id']):r for r in a['prerequisite_checks']}
    require(len(pre_checks)==len(a['prerequisite_checks'])and set(pre_checks)==pres,'assessment2: every prerequisite needs one check')
    evid={};whole=set()
    for row in a['direction_evidence']:
        key=(row['question_id'],row['direction_id']);require(key not in evid,'assessment2: duplicate evidence')
        qid,did=key;require(qid in qs and did in dirs,'assessment2: unknown evidence reference')
        target,d=dirs[did];parts=index_by(row['components'],'component_id')
        require(set(parts)=={c['component_id']for c in d['components']},'assessment2: each component needs explicit evidence')
        for part in parts.values():
            ix=part['answer_unit_indices']
            require(len(ix)==len(set(ix))and all(i<len(qs[qid]['answer_units'])for i in ix),'assessment2: nonexistent answer unit')
            require(bool(ix)==(part['location']=='answer'),'assessment2: only actual answer units are recalled evidence')
        has_image=bool(qs[qid].get('stimuli'))
        visual=(has_image and row['visual_verdict']=='ok')if d['requires_visual']or has_image else row['visual_verdict']in ('ok','not_applicable')
        if (all(p['location']=='answer'for p in parts.values())and visual and targets[target['target_id']]['status']=='consistent'
            and all(pre_checks[(qid,p)]['status']=='supported'for p in qs[qid].get('prerequisites',[]))
            and a['clinical_context_status']=='consistent'and direction_checks[did]['scope_status']=='consistent'):whole.add(key)
        evid[key]=row
    for row in a['issues']:
        require(set(row['question_ids'])<=set(qs)and set(row['direction_ids'])<=set(dirs),'assessment2: issue references missing objects')
        if row['kind']=='required_gap':require(row['direction_ids']and all(dirs[d][1]['requirement']=='required'for d in row['direction_ids']),
            'assessment2: required gaps must reference required directions; unmapped goals need map_fix')
    index_by(a['issues'],'issue_id')
    # v1 adapter computes reference integrity and coverage; semantic claims stay in raw v2.
    projected=legacy_brief(brief)
    for r in projected['relations']:r['review_status']='reviewed'if rels[r['relation_id']]['status']=='supported'else'unreviewed'
    rows=copy.deepcopy(a['question_reviews'])
    for row in rows:
        qid=row['question_id'];kept=[]
        for claim in row['relations']:
            if claim['role']=='tested':
                if rels[claim['relation_id']]['status']!='supported':continue
                claim['direction_ids']=[d for d in claim['direction_ids']if (qid,d)in whole and row['verdict']=='ok']
            kept.append(claim)
        row['relations']=kept
    projected_checks=[]
    for check in a['direction_checks']:
        did=check['direction_id'];target,d=dirs[did]
        accepted=any((row['question_id'],did)in whole and row['verdict']=='ok'and set(d['relation_ids'])<={
            r['relation_id']for r in row['relations']if r['role']=='tested'and did in r['direction_ids']}for row in rows)
        candidates=[r for r in a['direction_evidence']if r['direction_id']==did]
        unknown=(check['scope_status']=='unknown'or targets[target['target_id']]['status']=='unknown'
            or any(rels[r]['status']=='unknown'for r in d['relation_ids'])or a['clinical_context_status']=='unknown'
            or any(r['visual_verdict']=='doubt'or question_reviews[r['question_id']]['verdict']=='doubt'
                or any(p['location']=='unknown'for p in r['components'])for r in candidates)
            or any(p['status']=='unknown'for p in a['prerequisite_checks']if p['question_id']in {r['question_id']for r in candidates}))
        projected_checks.append({'direction_id':did,'status':'unknown'if unknown and not accepted else check['status'],'reason':check['reason']})
    old={'schema_version':'source-assessment/1','summary':a['summary'],'question_reviews':rows,
         'direction_checks':projected_checks,
         'input_issues':list(dict.fromkeys(i['text']for i in a['issues']))}
    audit=compile1(projected,bank,envelope(projected,bank,old))
    audit['review']['schema_version']='learning-links/2'
    audit['review']['targets']=copy.deepcopy(brief['targets'])
    audit['review']['provenance']['method']=VERSION+'; deterministic reference adapter; '+brief['provenance']['method']
    labels={'provided':'발문에서 제공','explanation':'해설에만 있음','missing':'직접 회상 없음','unknown':'판단 보류'}
    for coverage in audit['review']['coverage']:
        relevant=set(coverage['confirmed_direction_ids']+coverage['partial_direction_ids']+coverage['missing_direction_ids']+coverage['unknown_direction_ids'])
        notes=[]
        for row in a['direction_evidence']:
            if row['direction_id']not in relevant:continue
            components={p['component_id']:p['text']for p in dirs[row['direction_id']][1]['components']}
            notes +=[row['direction_id']+'/'+row['question_id']+': '+components[p['component_id']]+' · '+labels[p['location']]
                for p in row['components']if p['location']!='answer']
            if row['visual_verdict']in ('doubt','wrong'):notes.append(row['direction_id']+': 그림 확인 필요 · '+row['reason'])
        for did in sorted(relevant):
            if direction_checks[did]['scope_status']!='consistent':notes.append(did+': '+direction_checks[did]['reason'])
            target=dirs[did][0]
            if targets[target['target_id']]['status']!='consistent':notes.append(did+': '+targets[target['target_id']]['reason'])
        if notes:coverage['reason']+='; '+'; '.join(dict.fromkeys(notes))
    audit.update(schema_version='source-audit/2',assessment=copy.deepcopy(raw))
    return audit

def equivalent_audit(left,right):
    """Legacy compiler appended unordered explanation fragments, never judgments."""
    if left==right:return True
    a,b=copy.deepcopy(left),copy.deepcopy(right)
    try:
        for value in (a,b):
            for row in value['review']['coverage']:
                if type(row['reason'])is not str:return False
                row['reason']=sorted(row['reason'].split('; '))
    except (KeyError,TypeError):return False
    return a==b


def validate_audit(brief,bank,audit):
    require(equivalent_audit(audit,compile_assessment(brief,bank,audit['assessment'])),'audit2: derived result differs from raw judgments')
    return audit

def make_document(brief,bank,audit,*,revision,title,exam_date,medical=None):
    validate_audit(brief,bank,audit)
    if recall.enabled(brief):brief=recall.project_brief(brief)[0]
    review=audit['review'];coverage={c['point_id']:c for c in review['coverage']};candidates=[]
    source={r['question_id']:r['verdict']for r in audit['question_checks']['reviews']}
    med={r['question_id']:r['verdict']for r in medical['reviews']}if medical else {}
    for t in brief['targets']:
        relevant=[coverage[p['point_id']]for p in brief['points']if t['target_id']in p['target_ids']]
        for d in t['directions']:
            did=d['direction_id']
            if not relevant or not all(did in c['confirmed_direction_ids']for c in relevant):continue
            qids={m['question_id']for m in review['mappings']if m['direction_id']==did and set(d['relation_ids'])<=set(m['tested_relation_ids'])}
            q=next((q for q in bank['questions']if q['question_id']in qids and source[q['question_id']]=='ok'and
                (medical is None or med.get(q['question_id'])=='ok')),None)
            if q:candidates.append({'task_id':'task-'+document_hash([q['question_id'],did])[:24],'question_id':q['question_id'],'direction_id':did})
    order=graph_order(bank);qs={q['question_id']:q for q in bank['questions']}
    owners={d['direction_id']:t['target_id']for t in brief['targets']for d in t['directions']}
    reviewed_relations={r['relation_id']for r in review['relations']if r['review_status']=='reviewed'}
    blocked_targets={e['after_target']for e in brief['prerequisites']if e['relation_id']not in reviewed_relations}
    adopted_edges=[e for e in brief['prerequisites']if e['relation_id']in reviewed_relations]
    while True:
        prepared={t['question_id']for t in candidates}
        prepared_targets={owners[t['direction_id']]for t in candidates}
        kept=[t for t in candidates if set(qs[t['question_id']].get('prerequisites',[]))<=prepared
            and owners[t['direction_id']]not in blocked_targets
            and all(e['before_target']in prepared_targets for e in adopted_edges if e['after_target']==owners[t['direction_id']])]
        if kept==candidates:break
        candidates=kept
    candidates.sort(key=lambda t:order.index(t['question_id']))
    doc={'schema_version':'roots/1','generation_policy':POLICY,'revision':revision,'title':title,
        'review':review,'bank_snapshot':bank,'bank_source':'standalone','bank_build_id':None,
        'adopted_target_ids':[t['target_id']for t in brief['targets']],'tasks':candidates,'exam_date':exam_date,
        'equivalences':[],'prerequisites':adopted_edges}
    doc['tasks']=[{k:t[k]for k in ('task_id','question_id','direction_id')}for t in order_plan(doc,candidates,{t['task_id']for t in candidates},set())]
    return validate_document(doc)

def repair_reasons(brief,bank,audit,medical,validation):
    if recall.enabled(brief):
        projected,raw,groups=recall.project_assessment(brief,bank,audit['assessment'])
        local=copy.deepcopy(audit);local['assessment']=raw;local.pop('goal_coverage',None)
        local['assessment']['assessment'].pop('design_checks',None)
        # Recompile with the same validated leaf scope; final result retains raw review.
        local=_compile_assessment(projected,bank,local['assessment'])
        reasons=repair_reasons(projected,bank,local,medical,validation)
        reasons +=[{'kind':'question_fix','text':'문항 설계: '+r['reason'],'question_ids':[r['question_id']],
            'direction_ids':[]}for r in audit['assessment']['assessment']['design_checks']if r['verdict']=='wrong']
        parent={did:g['direction_id']for g in groups for did in g['unit_direction_ids']}
        for r in reasons:r['direction_ids']=list(dict.fromkeys(parent.get(d,d)for d in r['direction_ids']))
        return reasons
    a=audit['assessment']['assessment'];reasons=[i for i in a['issues']if i['kind']in ('question_fix','map_fix','required_gap')]
    for label,rows in [('source',a['question_reviews']),('medical',medical['reviews']if medical else[])]:
        reasons +=[{'kind':'question_fix','text':label+': '+r['note'],'question_ids':[r['question_id']],'direction_ids':[]}for r in rows if r['verdict']=='wrong']
    reasons +=[{'kind':'question_fix','text':s,'question_ids':[],'direction_ids':[]}for s in validation['errors']]
    try:graph_order(bank)
    except ValueError as error:reasons.append({'kind':'question_fix','text':str(error),'question_ids':[],'direction_ids':[]})
    for field,kind,bad in [('relation_checks','map_fix','conflict'),('target_checks','map_fix','conflict'),('prerequisite_checks','question_fix','unnecessary')]:
        reasons +=[{'kind':kind,'text':r['reason'],'question_ids':[r['question_id']]if 'question_id'in r else[],'direction_ids':[]}for r in a[field]if r['status']==bad]
    if a['clinical_context_status']=='conflict':reasons.append({'kind':'question_fix','text':a['clinical_context_reason'],'question_ids':[],'direction_ids':[]})
    reasons +=[{'kind':'map_fix','text':r['reason'],'question_ids':[],'direction_ids':[r['direction_id']]}for r in a['direction_checks']if r['scope_status']=='conflict']
    reasons +=[{'kind':'question_fix','text':r['reason'],'question_ids':[r['question_id']],'direction_ids':[r['direction_id']]}for r in a['direction_evidence']if r['visual_verdict']=='wrong']
    states={d:c for c in audit['review']['coverage']for d in c['missing_direction_ids']+c['partial_direction_ids']}
    relation_status={r['relation_id']:r['status']for r in a['relation_checks']};target_status={r['target_id']:r['status']for r in a['target_checks']}
    qstatus={r['question_id']:r['verdict']for r in a['question_reviews']}
    for t in brief['targets']:
        for d in t['directions']:
            if d['requirement']=='required'and d['direction_id']in states:
                rows=[r for r in a['direction_evidence']if r['direction_id']==d['direction_id']]
                uncertain=(a['clinical_context_status']!='consistent'or target_status[t['target_id']]!='consistent'
                    or next(r for r in a['direction_checks']if r['direction_id']==d['direction_id'])['scope_status']!='consistent'
                    or any(relation_status[r]!='supported'for r in d['relation_ids'])
                    or any(p['location']=='unknown'for r in rows for p in r['components'])
                    or any(r['visual_verdict']=='doubt'or qstatus[r['question_id']]=='doubt'for r in rows)
                    or any(r['status']=='unknown'for r in a['prerequisite_checks']if r['question_id']in {x['question_id']for x in rows}))
                if uncertain:continue
                reasons.append({'kind':'required_gap','text':'필수 방향 전체 직접 회상 미확인','question_ids':[],'direction_ids':[d['direction_id']]})
    definitions={d['direction_id']:d for t in brief['targets']for d in t['directions']}
    prepared_questions={m['question_id']for m in audit['review']['mappings']if
        set(definitions[m['direction_id']]['relation_ids'])<=set(m['tested_relation_ids'])}
    med_status={r['question_id']:r['verdict']for r in medical['reviews']}if medical else{}
    for pre in a['prerequisite_checks']:
        qid=pre['prerequisite_id'];rows=[r for r in a['direction_evidence']if r['question_id']==qid]
        if(pre['status']=='supported'and qid not in prepared_questions and qstatus.get(qid)=='ok'and med_status.get(qid)=='ok'
           and all(r['visual_verdict']!='doubt'and all(p['location']!='unknown'for p in r['components'])for r in rows)
           and all(r['status']!='unknown'for r in a['relation_checks'])and a['clinical_context_status']=='consistent'):
            reasons.append({'kind':'map_fix','text':'명시적 선행 문항과 전체 회상 방향의 검토된 연결이 없음','question_ids':[qid],'direction_ids':[]})
    try:make_document(brief,bank,audit,revision='prerequisite-check',title='구조 검증',exam_date=None,medical=medical)
    except ValueError as error:reasons.append({'kind':'question_fix','text':str(error),'question_ids':[],'direction_ids':[]})
    return reasons

def validate_normalization_recoveries(meta,stages):
    rows=meta.get('normalizationRecoveries',[])
    require(type(rows)is list and len(rows)<=1,'result2: invalid normalization recovery history')
    require(rows or 'originRuntimeHash'not in stages['normalize'],'result2: recovery proof missing')
    for row in rows:
        require(type(row)is dict and set(row)=={'proof','proofHash'}and type(row['proof'])is dict,'result2: malformed recovery proof')
        require(set(row['proof'])=={'priorLedger','priorLedgerHash','packetHash','currentRuntimeHash','reason','modelReplay'},'result2: malformed recovery identity')
        proof=row['proof'];old=proof['priorLedger'];stage=stages['normalize']
        require(type(old)is dict and type(old.get('stages'))is dict and type(old.get('identity'))is str
                and re.fullmatch(r'[a-f0-9]{64}',old['identity']),'result2: malformed original runtime')
        prior=old['stages'].get('normalize',{})
        require(type(prior)is dict,'result2: malformed original stage')
        require(row['proofHash']==document_hash(proof)and proof['priorLedgerHash']==document_hash(old),'result2: changed recovery proof')
        require(old.get('pipelineVersion')==POLICY and old.get('repairRounds')==0 and set(old['stages'])=={'normalize'}
                and not old.get('normalizationRecoveries')and prior.get('status')=='failed','result2: recovery was not failed initial acceptance')
        require(proof['packetHash']==meta['inputHash']and proof['currentRuntimeHash']==meta['runtimeHash']
                and stage.get('originRuntimeHash')==old['identity'],'result2: changed recovery identity')
        require(proof.get('modelReplay')is False and type(proof.get('reason'))is str and proof['reason'].strip(),'result2: recovery cannot replay model')
        require(all(prior.get(k)==stage.get(k)for k in('inputHash','rawOutputHash','usageHash'))
                and stage['outputHash']==stage['rawOutputHash'],'result2: recovered raw/input/usage changed')

def validate_result(value,packet):
    from .automation import validate_checks
    require(set(value)=={'brief','document','sourceAudit','medical','validation','manifest'},'result2: unknown/missing artifacts')
    b=value['brief'];bank=value['document']['bank_snapshot'];a=value['sourceAudit'];m=value['medical'];meta=value['manifest']
    if packet.get('parallelAuthoring'):
        proof=meta.get('parallelAuthoring',{})
        require(packet.get('authoring')=='cli'and packet.get('inputMode')=='source','parallel: wrong authoring mode')
        require(proof.get('policy')=='parallel-source-authoring/1'and proof.get('inputHash')==packet['inputHash']and proof.get('model')==meta.get('model'),'parallel: missing original provenance')
        rows=proof.get('branches',{})
        require(set(rows)=={'bank','map','point'},'parallel: missing independent branch')
        for kind,row in rows.items():
            require(row.get('state')=='completed'and row.get('kind')==kind and row.get('identity')==proof.get('identity'),'parallel: branch not completed')
            require(all(re.fullmatch(r'[a-f0-9]{64}',row.get(key,''))for key in('inputHash','outputHash','providerHash')),'parallel: missing receipt hashes')
        require(len({row['inputHash']for row in rows.values()})==1,'parallel: different source-only inputs')
    else:require('parallelAuthoring'not in meta,'parallel: unsolicited provenance')
    validate_brief(b);validate_checks(m,bank);validate_audit(b,bank,a);validate_images(bank,b['sources'])
    require(b['lecture_id']==packet['subject']+'/'+packet['runId'],'result2: wrong lecture')
    require({s['source_id']:s['sha256']for s in b['sources']}=={s['id']:s['sha256']for s in packet['sources']},'result2: wrong sources')
    original={s['id']:s for s in packet['sources']}
    for s in b['sources']:
        require(s['label']==original[s['source_id']]['filename'],'result2: source label mismatch')
        require((type(s['page_count'])is int and s['page_count']>0)if s['label'].lower().endswith('.pdf')else s['page_count']is None,'result2: invalid page inventory')
    require(meta['inputHash']==packet['inputHash']and packet_hash(packet)==packet['inputHash'],'result2: input mismatch')
    require(meta['pipelineVersion']==POLICY and meta['bankHash']==document_hash(bank)and meta['briefHash']==document_hash(b),'result2: stale manifest')
    require(type(meta.get('runtimeHash'))is str and re.fullmatch(r'[a-f0-9]{64}',meta['runtimeHash'])and
        type(meta.get('model'))is str and meta['model'].strip(),'result2: missing runtime identity')
    require(meta['sourceAssessment']==a['assessment'],'result2: assessment mismatch')
    require(a['assessment']['assessment']['clinical_context_status']=='consistent','result2: final clinical input separation not verified')
    require(meta['webResponseHash']==packet.get('webResponseHash'),'result2: web response mismatch')
    total=meta['repairRounds'];require(type(total)is int and 0<=total<=3,'result2: repair budget exceeded')
    findings=brief_findings(meta['initialBrief']);initial_cost=int(bool(findings))
    correction=meta.get('initialMapCorrection',{'errors':[],'consumedRounds':0})
    require(correction=={'errors':findings,'consumedRounds':initial_cost},'result2: missing initial correction evidence')
    n=total-initial_cost;require(n>=0,'result2: initial correction not counted')
    stages=index_by(meta['stages'],'name')
    from .parallel import validate_schema_recovery
    validate_schema_recovery(meta,stages)
    validate_runtime_revalidations(meta,stages)
    validate_format_recoveries(meta,stages)
    recoveries=validate_authoring_recoveries(meta,stages)
    rejected=recoveries[0]['proof']['rawAuthoring']if recoveries and recoveries[0]['proof']['mode']=='brief-repair'else None
    start_round=1 if rejected else 0
    require(n>=start_round,'result2: recovered authoring correction not counted')
    needed={'normalize','generate'}|{f'{k}-{i}'for i in range(start_round,n+1)for k in ('source','medical')}|{f'repair-{i}'for i in range(1,n+1)}
    require(set(stages)==needed,'result2: incomplete/ambiguous stages')
    for name,s in stages.items():
        if name=='generate'and rejected:
            require(s['status']=='failed','result2: rejected authoring failure must remain visible');continue
        if s['status']=='blocked':
            require(name.startswith('medical-')and int(name.split('-')[1])<n,'result2: incomplete final medical review')
            require(s['blockedReport']['reason']and s['blockedHash']==document_hash(s['blockedReport']),'result2: missing blocked review evidence')
        else:
            require(s['status']=='completed','result2: incomplete/ambiguous stages')
            require(all(type(s.get(k))is str and re.fullmatch(r'[a-f0-9]{64}',s[k])for k in ('inputHash','outputHash','rawOutputHash')),'result2: missing stage fingerprints')
    require(stages['normalize']['outputHash']==document_hash(meta['initialBrief']),'result2: initial brief proof mismatch')
    validate_shape(meta['initialBrief'],BRIEF,'initial brief2')
    validate_normalization_recoveries(meta,stages)
    if packet.get('inputMode')=='source':require(meta['initialBrief']['provenance']['independent_points']=='confirmed','result2: initial extraction must be independent')
    else:require(meta['initialBrief']['provenance']['independent_points']!='confirmed','result2: supplied map is not independent extraction')
    revisions=meta['briefRevisions']
    names=([]if rejected else['generate'])+[f'repair-{i}'for i in range(1,n+1)]
    require(len(revisions)==len(names),'result2: missing map revision lineage')
    require(bool(meta.get('authoringRecoveryOutput'))==bool(rejected),'result2: missing/extra authoring recovery output')
    if rejected:
        accepted=meta['authoringRecoveryOutput'];validate_recovered_authoring(rejected,accepted)
        require(stages['repair-1']['rawOutputHash']==document_hash(accepted)
            and revisions[0]['brief']==accepted['brief'],'result2: recovered authoring output changed')
    previous=meta['initialBrief']
    for i,(name,revision)in enumerate(zip(names,revisions)):
        require(revision['stage']==name and stages[name]['briefHash']==document_hash(revision['brief']),'result2: map stage revision mismatch')
        if i==0 and initial_cost:validate_initial_correction(previous,revision['brief'],revision['reason'])
        else:
            validate_transition(previous,revision['brief'],revision['reason'])
            if i==0 and not rejected:require(revision['brief']==previous,'result2: initial authoring changed independent map')
        previous=revision['brief']
    require(previous==b,'result2: final map not in revision lineage')
    author={'bank':bank,'brief':b,'visual_stimuli':meta['visualStimuli'],'clinical_conflicts':meta['clinicalConflicts'],'map_change_reason':meta['mapChangeReason']}
    final=stages[f'repair-{n}'if n else'generate']
    require(final['outputHash']==document_hash(author)and stages[f'source-{n}']['outputHash']==document_hash(a)and stages[f'medical-{n}']['outputHash']==document_hash(m),'result2: stage output mismatch')
    raw_author=copy.deepcopy(author)
    for q in raw_author['bank']['questions']:q.pop('stimuli',None)
    require(final['rawOutputHash']==document_hash(raw_author),'result2: authored input mismatch')
    validate_authoring(raw_author)
    require(stages[f'source-{n}']['rawOutputHash']==document_hash(a['assessment']),'result2: raw source proof mismatch')
    require(meta['medicalInputHash']==stages[f'medical-{n}']['inputHash'],'result2: medical input proof mismatch')
    require(meta['medicalInputHash']==document_hash({'title':packet['title'],'bank':bank,
        'clinicalInput':medical_input(bank,meta['clinicalConflicts']),'_pipeline_version':POLICY}),'result2: actual medical projection mismatch')
    require(stages[f'source-{n}']['clinicalContextHash']==document_hash(meta['clinicalConflicts']),'result2: source reviewed different clinical context')
    specs={q['question_id']:[]for q in bank['questions']}
    for s in meta['visualStimuli']:
        require(s['question_id']in specs,'result2: unknown stimulus question')
        specs[s['question_id']].append({k:s[k]for k in ('source_id','page','crop')})
    for q in bank['questions']:
        require(specs[q['question_id']]==[{k:s[k]for k in ('source_id','page','crop')}for s in q.get('stimuli',[])],'result2: rendered image is not the authored crop')
    actual=validate_bank(bank,[s['id']for s in packet['sources']])
    require(all(value['validation'].get(k)==actual[k]for k in ('pass','errors','warnings'))and validate_bank(bank,[s['id']for s in packet['sources']],check_quality=False)['pass'],'result2: invalid bank or validation')
    expected=make_document(b,bank,a,revision=packet['revision'],title=packet['title'],exam_date=packet['examDate'],medical=m)
    if recall.enabled(b):require(meta.get('goalPreparation')==recall.prepared_coverage(a,expected),'result2: altered prepared goal coverage')
    require(value['document']==expected,'result2: altered readiness/document')
    return expected
