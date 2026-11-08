import copy
import pytest
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.source_assessment import envelope

def compile_value(b,bank,a):return c.compile_assessment(b,bank,envelope(b,bank,a))

def test_partial_explanation_and_union_do_not_award_whole_goal():
    b=f.brief();bank=f.old.bank();d=b['targets'][0]['directions'][0]
    d['components'].append({'component_id':'condition','text':'Synthetic necessary condition'})
    a=f.assessment(b,bank);a['direction_evidence'][0]['components'][1].update(location='explanation',answer_unit_indices=[])
    audit=compile_value(b,bank,a)
    doc=c.make_document(b,bank,audit,revision='test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert 'D1'not in {t['direction_id']for t in doc['tasks']}
    assert a['direction_evidence'][0]['components'][1]['location']=='explanation'

def test_unreviewed_relation_is_reviewed_only_by_explicit_fresh_status():
    b=f.brief();bank=f.old.bank();b['relations'][0]['review_status']='unreviewed';a=f.assessment(b,bank)
    audit=compile_value(b,bank,a)
    assert b['relations'][0]['review_status']=='unreviewed'
    assert audit['review']['relations'][0]['review_status']=='reviewed'
    a['relation_checks'][0]['status']='unknown';audit=compile_value(b,bank,a)
    assert 'D1'in audit['review']['coverage'][0]['unknown_direction_ids']
    assert not any(m['direction_id']=='D1'for m in audit['review']['mappings'])

def test_impossible_answer_anchor_and_missing_component_rejected():
    b=f.brief();bank=f.old.bank();a=f.assessment(b,bank)
    a['direction_evidence'][0]['components'][0]['answer_unit_indices']=[100]
    with pytest.raises(ValueError):compile_value(b,bank,a)
    a=f.assessment(b,bank);a['direction_evidence'][0]['components']=[]
    with pytest.raises(ValueError):compile_value(b,bank,a)

def test_prerequisite_order_and_cycle_are_deterministic():
    bank=f.old.bank();bank['questions'][0]['prerequisites']=['Q2']
    assert c.graph_order(bank)==['Q2','Q1']
    bank['questions'][1]['prerequisites']=['Q1']
    with pytest.raises(ValueError):c.graph_order(bank)

def test_two_partial_questions_cannot_be_unioned_into_complete_recall():
    b=f.brief();bank=f.old.bank();b['targets'][0]['directions'][0]['components'].append({'component_id':'condition','text':'Synthetic condition'})
    a=f.assessment(b,bank);first=a['direction_evidence'][0]
    first['components'][1].update(location='provided',answer_unit_indices=[])
    second=copy.deepcopy(first);second['question_id']='Q2'
    second['components'][0].update(location='explanation',answer_unit_indices=[])
    second['components'][1].update(location='answer',answer_unit_indices=[0]);a['direction_evidence'].append(second)
    a['question_reviews'][1]['relations'].append({'relation_id':'R1','role':'tested','direction_ids':['D1'],'reason':'Synthetic partial condition'})
    audit=compile_value(b,bank,a)
    assert not any(m['direction_id']=='D1'for m in audit['review']['mappings'])
    assert 'D1'in audit['review']['coverage'][0]['missing_direction_ids']

@pytest.mark.parametrize('field',['clinical_context_status','scope_status','target_status'])
def test_unconfirmed_context_scope_or_importance_never_prepares_goals(field):
    b=f.brief();bank=f.old.bank();a=f.assessment(b,bank)
    if field=='clinical_context_status':a[field]='unknown'
    elif field=='scope_status':a['direction_checks'][0][field]='conflict'
    else:a['target_checks'][0]['status']='unknown'
    audit=compile_value(b,bank,a)
    doc=c.make_document(b,bank,audit,revision='test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert not any(t['direction_id']=='D1'for t in doc['tasks'])

def test_wrong_medical_answer_cannot_prepare_itself_or_its_dependent():
    b=f.brief();bank=f.old.bank();bank['questions'][1]['prerequisites']=['Q1'];a=f.assessment(b,bank)
    audit=compile_value(b,bank,a);med=f.old.checks(bank);med['reviews'][0]['verdict']='wrong'
    doc=c.make_document(b,bank,audit,revision='test',title='Synthetic',exam_date=None,medical=med)
    assert doc['tasks']==[]

def test_needed_question_prerequisite_is_added_before_followup_without_requiring_success():
    b=f.brief();bank=f.old.bank();bank['questions'][0]['prerequisites']=['Q2'];a=f.assessment(b,bank)
    doc=c.make_document(b,bank,compile_value(b,bank,a),revision='test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    tasks={t['question_id']:t for t in doc['tasks']};selected=[{**tasks['Q1'],'reason':'new'}];available={t['task_id']for t in doc['tasks']}
    assert [t['question_id']for t in c.order_plan(doc,selected,available,set())]==['Q2','Q1']
    assert [t['question_id']for t in c.order_plan(doc,selected,available,{'Q2'})]==['Q1']

def test_unknown_is_not_a_repairable_missing_fact_and_map_conflict_routes_separately():
    from studyez_contracts.bank.validate import validate_bank
    b=f.brief();bank=f.old.bank();a=f.assessment(b,bank);a['relation_checks'][0]['status']='unknown'
    audit=compile_value(b,bank,a)
    assert not c.repair_reasons(b,bank,audit,f.old.checks(bank),validate_bank(bank,['S1']))
    a=f.assessment(b,bank);a['direction_checks'][0]['scope_status']='conflict';audit=compile_value(b,bank,a)
    reasons=c.repair_reasons(b,bank,audit,f.old.checks(bank),validate_bank(bank,['S1']))
    assert any(r['kind']=='map_fix'for r in reasons)

def test_answer_quality_warnings_become_question_fixes_without_new_rounds():
    from studyez_contracts.bank.validate import validate_bank
    b=f.brief();bank=f.old.bank();audit=compile_value(b,bank,f.assessment(b,bank))
    assert not c.quality_reasons(bank)
    q=bank['questions'][0];q['format']='basic';q['answer_units']=['first unit','second unit'];q['answer']='first unit; second unit'
    fixes=c.quality_reasons(bank)
    assert [r['question_ids']for r in fixes]==[[q['question_id']]]and fixes[0]['kind']=='question_fix'
    reasons=c.repair_reasons(b,bank,audit,f.old.checks(bank),validate_bank(bank,['S1']))
    assert any(r['text'].startswith('문항 품질: ')and r['question_ids']==[q['question_id']]for r in reasons)

def test_changed_map_needs_derived_provenance_and_source_point_preservation():
    before=f.author();after=copy.deepcopy(before)
    after['brief']['targets'][0]['directions'][0]['answer_scope']='New synthetic answer scope'
    after['brief']['provenance']['independent_points']='confirmed'
    with pytest.raises(ValueError):c.validate_authoring(after,before)
    after['brief']['provenance']['independent_points']='derived';c.validate_authoring(after,before)
    after['brief']['points'][0]['text']='Erased original'
    with pytest.raises(ValueError):c.validate_authoring(after,before)

def test_same_id_changed_goal_does_not_have_the_same_learning_identity():
    from studyez_contracts.roots import direction_hash
    b=f.brief();bank=f.old.bank();doc=c.make_document(b,bank,compile_value(b,bank,f.assessment(b,bank)),revision='test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    changed=copy.deepcopy(doc);changed['review']['targets'][0]['directions'][0]['components'][0]['text']='Changed condition'
    assert direction_hash(doc,'D1')!=direction_hash(changed,'D1')

def test_combined_target_and_question_cycle_is_rejected_even_when_each_graph_is_acyclic():
    from root_fixture import document
    doc=document();doc['bank_snapshot']['questions'][0]['prerequisites']=['Q3']
    assert c.graph_order(doc['bank_snapshot'])
    with pytest.raises(ValueError,match='combined'):
        c.order_plan(doc,doc['tasks'],{t['task_id']for t in doc['tasks']},set())

def test_optional_direction_cannot_be_misclassified_as_required_repair():
    b=f.brief();bank=f.old.bank();b['targets'][0]['directions'][0]['requirement']='optional';a=f.assessment(b,bank)
    a['issues']=[{'issue_id':'bad-required','kind':'required_gap','text':'Synthetic mislabeled optional','question_ids':[],'direction_ids':['D1']}]
    with pytest.raises(ValueError,match='required gaps'):compile_value(b,bank,a)

def test_any_presented_picture_needs_explicit_visual_review_even_for_textual_goal():
    import base64,hashlib,struct,zlib
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00'))+chunk(b'IEND',b'')
    b=f.brief();bank=f.old.bank();b['sources'][0].update(label='synthetic.pdf',page_count=1)
    bank['questions'][0]['stimuli']=[{'source_id':'S1','source_sha256':b['sources'][0]['sha256'],'page':1,'crop':[0,0,1,1],
        'sha256':hashlib.sha256(png).hexdigest(),'width':1,'height':1,'png_base64':base64.b64encode(png).decode()}]
    a=f.assessment(b,bank);assert a['direction_evidence'][0]['visual_verdict']=='not_applicable'
    doc=c.make_document(b,bank,compile_value(b,bank,a),revision='visual-test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert not any(t['direction_id']=='D1'for t in doc['tasks'])
    a['direction_evidence'][0]['visual_verdict']='ok'
    doc=c.make_document(b,bank,compile_value(b,bank,a),revision='visual-test',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert any(t['direction_id']=='D1'for t in doc['tasks'])
