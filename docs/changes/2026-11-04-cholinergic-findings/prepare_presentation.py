"""Conservative adoption of the final review; preserve every original verdict."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import followup as f

def main():
    f.check();result=f.read(f.OUT/'result.json');resolution=result['resolution'];source_tasks=result['document']['tasks']
    task_by_direction={t['direction_id']:t for t in source_tasks};holds=[]
    original=next(d for d in resolution['directions']if d['original_direction_id']=='D10')
    f.require(not original['ready']and original['current_direction_ids']==['D10'],'Unexpected original-D10 disposition')
    holds.append({'direction_id':'D10','question_id':'Q077','reason':original['reason'],'basis':'resolution.directions[D10]'})
    for index,did,qid in [(0,'D57','Q142'),(2,'D21','Q092'),(3,'D61','Q109')]:
        text=resolution['new_open_findings'][index]
        f.require(did in text and qid in text and task_by_direction[did]['question_id']==qid,'Final review hold identity changed')
        holds.append({'direction_id':did,'question_id':qid,'reason':text,'basis':f'resolution.new_open_findings[{index}]'})
    source={r['question_id']:r for r in result['sourceAudit']['question_checks']['reviews']};medical={r['question_id']:r for r in result['medical']['reviews']}
    held={r['direction_id']for r in holds}
    usable=[t for t in source_tasks if t['direction_id']not in held and source[t['question_id']]['verdict']=='ok'and medical[t['question_id']]['verdict']=='ok']
    directions={d['direction_id']:d for t in result['brief']['targets']for d in t['directions']};ready={t['direction_id']for t in usable}
    schema=f.source_assessment_schema(result['brief'],result['bank'])
    variants=schema['properties']['question_reviews']['items']['properties']['relations']['items']['anyOf']
    variant=next(v for v in variants if v['properties']['relation_id']['enum']==['R18']and v['properties']['role']['enum']==['tested'])
    f.require(variant['properties']['direction_ids']['minItems']==0,'Unplanned-cue schema fix missing')
    question=next(q for q in result['sourceAssessment']['assessment']['question_reviews']if q['question_id']=='Q117')
    f.require(any(r['relation_id']=='R18'and r['role']=='tested'and not r['direction_ids']for r in question['relations']),'Actual unplanned-cue evidence missing')
    f.require(not any(m['question_id']=='Q117'for m in result['sourceAudit']['review']['mappings']),'Unplanned cue incorrectly awarded a direction')
    value={'schema_version':'root-example-presentation/1','resultHash':f.sha(f.OUT/'result.json'),
        'resolutionHash':f.g.document_hash(resolution),'sourceTaskCount':len(source_tasks),'reviewedTaskCount':len(usable),
        'reviewHolds':holds,'reviewedTasks':usable,'unreadyDirections':sorted(set(directions)-ready),
        'requiredDirectionCount':sum(d['requirement']=='required'for d in directions.values()),
        'readyRequiredDirectionCount':sum(directions[did]['requirement']=='required'for did in ready),
        'technicalEvidence':{'I01':{'verified':True,'reason':'Separate software verification, not a clinical verdict: dynamic schema accepts the actual Q117/R18 tested claim with no direction, compiler preserves it without awarding planned-direction credit.',
            'schemaHash':f.g.document_hash(schema),'rawAssessmentHash':f.g.document_hash(result['sourceAssessment']),
            'test':'tests/contracts/test_source_assessment.py::test_unplanned_test_cue_is_preserved_without_credit_to_other_directions'}},
        'policy':'Read-only conservative presentation. Preserve canonical source tasks and all review verdicts; exclude final-review holds/non-ok question checks from proposed usable tasks.',
        'builderHash':f.sha(Path(__file__))}
    f.g.write(f.OUT/'presentation-audit.json',value)
    print(json.dumps({k:value[k]for k in ('sourceTaskCount','reviewedTaskCount','requiredDirectionCount','readyRequiredDirectionCount','unreadyDirections')},ensure_ascii=False))
if __name__=='__main__':main()
