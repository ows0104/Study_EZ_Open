"""Explicit, reviewed recall units; never infer partitions from text or length."""
import copy
from .validate import document_hash
from studyez_contracts.learning_links.validate import require,index_by

POLICY='recall-units/1'

def enabled(brief):return brief.get('recall_policy')==POLICY

def project_brief(brief):
    value=copy.deepcopy(brief);value.pop('recall_policy',None);groups=[];used=set()
    for target in value['targets']:
        expanded=[]
        for direction in target['directions']:
            units=direction.pop('recall_units',[])
            require(enabled(brief)or not units,'recall units require explicit policy')
            if not units:
                leaves=[direction]
            else:
                parts={p['component_id']:p for p in direction['components']}
                ids=[cid for unit in units for cid in unit['component_ids']]
                require(len(ids)==len(set(ids))and set(ids)==set(parts),'recall units must partition every component exactly once')
                require(set().union(*(set(u['relation_ids'])for u in units))==set(direction['relation_ids']),
                    'recall units must retain all parent relations')
                leaves=[]
                for unit in units:
                    require(unit['component_ids']and unit['relation_ids']and len(unit['relation_ids'])==len(set(unit['relation_ids'])),
                        'recall unit needs distinct relation evidence')
                    leaves.append({**direction,'direction_id':unit['unit_id'],'cue':unit['cue'],
                        'answer_scope':unit['answer_scope'],'relation_ids':unit['relation_ids'],
                        'components':[parts[cid]for cid in unit['component_ids']]})
            for leaf in leaves:
                require(leaf['direction_id']not in used,'recall unit IDs must be globally unique')
                used.add(leaf['direction_id'])
            groups.append({'direction_id':direction['direction_id'],
                'kind':'distributed'if units else'integrated',
                'unit_direction_ids':[d['direction_id']for d in leaves]})
            expanded.extend(leaves)
        target['directions']=expanded
    return value,groups

def project_assessment(brief,bank,raw):
    projected,groups=project_brief(brief)
    if not enabled(brief):return projected,copy.deepcopy(raw),groups
    out=copy.deepcopy(raw);a=out['assessment'];design=index_by(a.get('design_checks',[]),'question_id')
    require(set(design)=={q['question_id']for q in bank['questions']},'every question needs an independent design check')
    all_dirs={d['direction_id']:d for t in projected['targets']for d in t['directions']}
    groups={g['direction_id']:g for g in groups}
    checks=index_by(a['direction_checks'],'direction_id')
    require(set(checks)==set(groups),'every parent direction needs one scope check')
    qids={q['question_id']for q in bank['questions']}
    require(all(row['direction_id']in groups and row['question_id']in qids for row in a['direction_evidence']),
        'recall evidence references an unknown question or parent')
    require(all(set(claim['direction_ids'])<=set(groups)for row in a['question_reviews']for claim in row['relations']),
        'recall claim references an unknown parent')
    require(all(set(row['direction_ids'])<=set(groups)for row in a['issues']),'recall issue references an unknown parent')
    a['direction_checks']=[{**row,'direction_id':did}for row in a['direction_checks']
        for did in groups[row['direction_id']]['unit_direction_ids']]
    evidence=[]
    for row in a['direction_evidence']:
        original=next(d for t in brief['targets']for d in t['directions']if d['direction_id']==row['direction_id'])
        parts=index_by(row['components'],'component_id')
        require(set(parts)=={p['component_id']for p in original['components']},'parent recall evidence is incomplete')
        for did in groups[row['direction_id']]['unit_direction_ids']:
            evidence.append({**row,'direction_id':did,
                'components':[parts[p['component_id']]for p in all_dirs[did]['components']]})
    a['direction_evidence']=evidence
    for row in a['question_reviews']:
        check=design[row['question_id']]
        if check['verdict']!='ok':
            if row['verdict']!='wrong':row['verdict']=check['verdict']
            row['note']+='; 문항 설계: '+check['reason']
        for claim in row['relations']:
            claim['direction_ids']=[did for parent in claim['direction_ids']
                for did in groups[parent]['unit_direction_ids']if claim['relation_id']in all_dirs[did]['relation_ids']]
    for issue in a['issues']:
        issue['direction_ids']=[did for parent in issue['direction_ids']for did in groups[parent]['unit_direction_ids']]
    # Source1/2 adapters still validate all existing semantic/reference guards.
    out['briefHash']=document_hash(projected)
    return projected,out,list(groups.values())

def summarize(groups,audit,answered=None):
    """`answered`: (question, unit) pairs that answer a component of the unit (review-relations/1, 2026-11-11-place-by-review):
    only those confirm a unit. None keeps the rule results were made with before."""
    mappings=audit['review']['mappings']
    directions={d['direction_id']:d for t in audit['review']['targets']for d in t['directions']}
    unknown={did for p in audit['review']['coverage']for did in p['unknown_direction_ids']}
    approved={did for p in audit['review']['coverage']for did in p['confirmed_direction_ids']}-unknown
    rows=[]
    for group in groups:
        confirmed=[did for did in group['unit_direction_ids']if did in approved and any(m['direction_id']==did
            and set(directions[did]['relation_ids'])<=set(m['tested_relation_ids'])
            and(answered is None or(m['question_id'],did)in answered)for m in mappings)]
        state=('confirmed'if len(confirmed)==len(group['unit_direction_ids'])else
               'unknown'if set(group['unit_direction_ids'])&unknown else'partial'if confirmed else'missing')
        rows.append({**group,'status':state,'confirmed_unit_ids':confirmed})
    return rows

def prepared_coverage(audit,document):
    """Content evidence is not clinical preparation or a learner's performance."""
    available={t['direction_id']for t in document['tasks']}
    return [{'direction_id':g['direction_id'],'unit_direction_ids':g['unit_direction_ids'],
        'prepared_unit_ids':[did for did in g['unit_direction_ids']if did in available],
        'status':'ready'if set(g['unit_direction_ids'])<=available else
            'partial'if set(g['unit_direction_ids'])&available else'blocked'}for g in audit.get('goal_coverage',[])]
