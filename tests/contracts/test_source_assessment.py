from copy import deepcopy
import jsonschema
import pytest
import automation_fixture as f
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import validate_result,make_document
from studyez_contracts.roots.source_assessment import source_assessment_schema,envelope,compile_source_assessment


def inputs():
    b=f.brief();bank=f.bank();return b,bank,f.assessment(b,bank)


def compile_(b,bank,a):return compile_source_assessment(b,bank,envelope(b,bank,a))


def test_compiles_immutable_core_hashes_and_consistent_coverage_without_mutation():
    b,bank,a=inputs();before=deepcopy((b,bank,a))
    result=compile_(b,bank,a)
    assert (b,bank,a)==before
    assert result['question_checks']['reviews']==f.checks(bank)['reviews']
    assert result['review']['coverage'][0]['confirmed_direction_ids']==['D1','D2']
    assert result['review']['coverage'][0]['status']=='covered'
    assert result['review']['mappings'][0]['question_sha256']!=result['review']['mappings'][1]['question_sha256']
    assert len(make_document(b,bank,result,revision='v',title='t',exam_date=None)['tasks'])==2


def test_direction_outside_relation_is_unrepresentable_at_model_boundary_and_rejected_locally():
    b,bank,a=inputs();a['question_reviews'][0]['relations'][0]['direction_ids']=['D2']
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(a,source_assessment_schema(b,bank))
    with pytest.raises(ValueError,match='outside direction'):compile_(b,bank,a)


@pytest.mark.parametrize('kind',['question-missing','question-duplicate','direction-missing','direction-duplicate',
    'relation-duplicate','role-overlap','provided-test','unknown-relation','unknown-direction'])
def test_bad_review_envelopes_are_not_silently_repaired(kind):
    b,bank,a=inputs();q=a['question_reviews'][0]
    if kind=='question-missing':a['question_reviews'].pop()
    if kind=='question-duplicate':a['question_reviews'].append(deepcopy(q))
    if kind=='direction-missing':a['direction_checks'].pop()
    if kind=='direction-duplicate':a['direction_checks'].append(deepcopy(a['direction_checks'][0]))
    if kind in ('relation-duplicate','role-overlap'):
        row=deepcopy(q['relations'][0]);q['relations'].append(row)
        if kind=='role-overlap':row.update(role='provided',direction_ids=[])
    if kind=='provided-test':q['relations'][0]['role']='provided'
    if kind=='unknown-relation':q['relations'][0]['relation_id']='not-an-id'
    if kind=='unknown-direction':a['direction_checks'][0]['direction_id']='not-a-direction'
    with pytest.raises(ValueError):compile_(b,bank,a)


def test_unplanned_test_cue_is_preserved_without_credit_to_other_directions():
    b,bank,a=inputs()
    claim=a['question_reviews'][0]['relations'][0]
    claim.update(direction_ids=[],reason='Synthetic reverse cue is absent from the declared plan')
    raw=envelope(b,bank,a);before=deepcopy(raw)
    jsonschema.validate(a,source_assessment_schema(b,bank))
    value=compile_source_assessment(b,bank,raw)
    coverage=value['review']['coverage'][0]
    assert raw==before and raw['assessment']['question_reviews'][0]['relations'][0]==claim
    assert coverage['missing_direction_ids']==['D1']
    assert coverage['confirmed_direction_ids']==['D2']
    assert coverage['status']=='partial'
    assert all(m['question_id']!='Q1' for m in value['review']['mappings'])
    tasks=make_document(b,bank,value,revision='v',title='t',exam_date=None)['tasks']
    assert len(tasks)==1 and tasks[0]['direction_id']=='D2'


def test_provided_and_explanation_never_count_as_tested_and_unknown_is_not_absence():
    b,bank,a=inputs();a['question_reviews'][0]['relations'][0].update(role='provided',direction_ids=[])
    result=compile_(b,bank,a);coverage=result['review']['coverage'][0]
    assert coverage['missing_direction_ids']==['D1'] and coverage['confirmed_direction_ids']==['D2']
    assert coverage['status']=='partial'
    a['direction_checks'][0]['status']='unknown'
    coverage=compile_(b,bank,a)['review']['coverage'][0]
    assert coverage['unknown_direction_ids']==['D1'] and not coverage['missing_direction_ids']
    a['question_reviews'][1]['relations'][0].update(role='explanation',direction_ids=[])
    a['direction_checks'][1]['status']='unknown'
    assert compile_(b,bank,a)['review']['coverage'][0]['status']=='unknown'


def test_gap_and_input_issues_and_wrong_doubt_are_preserved():
    b,bank,a=inputs()
    for row in a['question_reviews']:row['relations']=[]
    a['question_reviews'][0]['verdict']='wrong';a['question_reviews'][1]['verdict']='doubt'
    a['input_issues']=['Synthetic unresolved issue']
    value=compile_(b,bank,a)
    assert value['review']['coverage'][0]['status']=='gap'
    assert [r['verdict']for r in value['question_checks']['reviews']]==['wrong','doubt']
    assert value['input_issues']==a['input_issues']


def test_exclusions_and_source_only_provenance_are_preserved():
    b,bank,a=inputs();b['provenance']['independent_points']='confirmed'
    point=deepcopy(b['points'][0]);point.update(point_id='excluded',target_ids=[],scope_status='excluded',reason='Synthetic excluded item')
    b['points'].append(point);b['exclusions'].append({'point_id':'excluded','basis':'out_of_scope'})
    value=compile_(b,bank,a)
    assert value['review']['provenance']['independent_points']=='confirmed'
    assert value['review']['coverage'][1]['status']=='excluded'
    assert value['review']['coverage'][1]['reason']==point['reason']
    assert value['review']['coverage'][1]['exclusion_basis']=='out_of_scope'


def test_partial_is_computed_from_relations_and_union_is_not_a_whole_direction_task():
    b,bank,a=inputs();b['targets'][0]['directions']=b['targets'][0]['directions'][:1]
    b['targets'][0]['directions'][0]['relation_ids']=['R1','R2']
    a['direction_checks']=a['direction_checks'][:1]
    a['question_reviews'][1]['relations'][0]['direction_ids']=['D1']
    first=deepcopy(a);first['question_reviews'][1]['relations']=[]
    c=compile_(b,bank,first)['review']['coverage'][0]
    assert c['status']=='partial' and c['partial_direction_ids']==['D1']
    value=compile_(b,bank,a)
    assert value['review']['coverage'][0]['confirmed_direction_ids']==['D1']
    assert not make_document(b,bank,value,revision='v',title='t',exam_date=None)['tasks']


@pytest.mark.parametrize('part',['bankHash','briefHash'])
def test_revision_binding(part):
    b,bank,a=inputs();raw=envelope(b,bank,a);raw[part]='f'*64
    with pytest.raises(ValueError,match='revision'):compile_source_assessment(b,bank,raw)


@pytest.mark.parametrize('change',['raw','missing','compiled','format','hash'])
def test_consumer_recomputes_raw_assessment_not_only_reported_hashes(change):
    packet=f.packet();result=f.assessed_result(packet);validate_result(result,packet)
    manifest=result['manifest'];source=next(s for s in manifest['stages']if s['name']=='source-0')
    if change=='raw':manifest['sourceAssessment']['assessment']['question_reviews'][0]['verdict']='wrong'
    if change=='missing':del manifest['sourceAssessment']
    if change=='compiled':
        result['sourceAudit']['question_checks']['reviews'][0]['verdict']='wrong'
        source['outputHash']=document_hash(result['sourceAudit'])
    if change=='format':source['sourceFormat']='unknown'
    if change=='hash':source['rawOutputHash']='f'*64
    with pytest.raises(ValueError):validate_result(result,packet)


def test_new_packet_cannot_downgrade_to_legacy_evidence_but_old_result_still_loads():
    from studyez_contracts.roots.automation import packet_hash
    packet=f.packet();legacy=f.result(packet);validate_result(legacy,packet)
    packet['sourceAssessmentFormat']='source-assessment/1';packet['inputHash']=packet_hash(packet)
    value=f.assessed_result(packet);validate_result(value,packet)
    del value['manifest']['sourceAssessment']
    for s in value['manifest']['stages']:
        s.pop('sourceFormat',None);s.pop('rawOutputHash',None)
    with pytest.raises(ValueError):validate_result(value,packet)


@pytest.mark.parametrize('requirements',[['undecided','required'],['undecided','undecided'],['optional','optional']])
def test_fully_tested_directions_preserve_proof_when_required_point_coverage_is_undefined(requirements):
    b,bank,a=inputs()
    for d,requirement in zip(b['targets'][0]['directions'],requirements):d['requirement']=requirement
    before=deepcopy((b,bank,a));value=compile_(b,bank,a);coverage=value['review']['coverage'][0]
    assert coverage['status']=='unknown' and coverage['confirmed_direction_ids']==['D1','D2']
    assert not coverage['unknown_direction_ids']
    assert '필수 방향이 미정' in coverage['reason']
    assert (b,bank,a)==before
    assert len(make_document(b,bank,value,revision='v',title='t',exam_date=None)['tasks'])==2


def test_known_required_point_cannot_hide_complete_or_missing_review_with_unknown_label():
    from studyez_contracts.roots.automation import validate_audit
    b,bank,a=inputs();value=compile_(b,bank,a)
    value['review']['coverage'][0]['status']='unknown'
    with pytest.raises(ValueError,match='unknown needs'):validate_audit(b,bank,value)
