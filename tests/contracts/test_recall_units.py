import copy
import pytest
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as c,recall_units as recall
from studyez_contracts.roots.source_assessment import envelope

def example():
    b=f.brief();bank=f.old.bank();b['recall_policy']=recall.POLICY
    d=b['targets'][0]['directions'][0]
    d['components'].append({'component_id':'second','text':'Second independent synthetic fact'})
    d['recall_units']=[{'unit_id':'U1','cue':'Recall first','answer_scope':'First fact',
        'component_ids':['fact'],'relation_ids':d['relation_ids']},
        {'unit_id':'U2','cue':'Recall second','answer_scope':'Second fact',
        'component_ids':['second'],'relation_ids':d['relation_ids']}]
    a=f.assessment(b,bank)
    a['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'One clear synthetic recall'}for q in bank['questions']]
    first=a['direction_evidence'][0]
    first['components'][1].update(location='missing',answer_unit_indices=[])
    second=copy.deepcopy(first);second['question_id']='Q2'
    second['components'][0].update(location='provided',answer_unit_indices=[])
    second['components'][1].update(location='answer',answer_unit_indices=[0])
    a['direction_evidence'].append(second)
    a['question_reviews'][1]['relations'].append({'relation_id':'R1','role':'tested','direction_ids':['D1'],'reason':'Second synthetic unit'})
    return b,bank,a

def compile(b,bank,a):return c.compile_assessment(b,bank,envelope(b,bank,a))

def test_explicit_units_allow_distributed_content_and_independent_tasks():
    b,bank,a=example();original=copy.deepcopy((b,bank,a));audit=compile(b,bank,a)
    group=next(g for g in audit['goal_coverage']if g['direction_id']=='D1')
    assert group['status']=='confirmed'and group['confirmed_unit_ids']==['U1','U2']
    doc=c.make_document(b,bank,audit,revision='units',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert {t['direction_id']:t['question_id']for t in doc['tasks']}=={'U1':'Q1','U2':'Q2','D2':'Q2'}
    assert (b,bank,a)==original
    assert audit['assessment']==envelope(b,bank,a)

@pytest.mark.parametrize('location',['provided','explanation','missing','unknown'])
def test_missing_unit_never_completes_parent(location):
    b,bank,a=example();a['direction_evidence'][-1]['components'][1].update(location=location,answer_unit_indices=[])
    audit=compile(b,bank,a)
    assert audit['goal_coverage'][0]['status']!='confirmed'
    assert audit['goal_coverage'][0]['confirmed_unit_ids']==['U1']

def test_atomic_integration_still_cannot_union_partial_questions():
    b,bank,a=example();b['targets'][0]['directions'][0].pop('recall_units')
    audit=compile(b,bank,a)
    assert audit['goal_coverage'][0]['status']!='confirmed'
    assert not any(m['direction_id']=='D1'for m in audit['review']['mappings'])

@pytest.mark.parametrize('verdict',['wrong','doubt'])
def test_design_failure_blocks_content_and_preparation(verdict):
    b,bank,a=example();a['design_checks'][1]['verdict']=verdict
    audit=compile(b,bank,a)
    assert audit['goal_coverage'][0]['status']!='confirmed'
    doc=c.make_document(b,bank,audit,revision='bad-design',title='Synthetic',exam_date=None,medical=f.old.checks(bank))
    assert all(t['question_id']!='Q2'for t in doc['tasks'])

def test_wrong_design_routes_to_repair_and_medical_wrong_blocks_task():
    from studyez_contracts.bank.validate import validate_bank
    b,bank,a=example();a['design_checks'][0].update(verdict='wrong',reason='Independent requirements overloaded')
    audit=compile(b,bank,a)
    assert any(r['kind']=='question_fix'and r['question_ids']==['Q1']for r in c.repair_reasons(b,bank,audit,f.old.checks(bank),validate_bank(bank,['S1'])))
    b,bank,a=example();audit=compile(b,bank,a);medical=f.old.checks(bank);medical['reviews'][0]['verdict']='wrong'
    doc=c.make_document(b,bank,audit,revision='wrong-medical',title='Synthetic',exam_date=None,medical=medical)
    assert all(t['question_id']!='Q1'for t in doc['tasks'])
    group=recall.prepared_coverage(audit,doc)[0]
    assert group['status']=='partial'and group['prepared_unit_ids']==['U2']

def test_unit_deletion_overlap_reference_and_missing_review_rejected():
    for mode in ('drop','overlap','relation','duplicate','no-policy','review'):
        b,bank,a=example();d=b['targets'][0]['directions'][0]
        if mode=='drop':d['recall_units'].pop()
        elif mode=='overlap':d['recall_units'][1]['component_ids'].append('fact')
        elif mode=='relation':d['recall_units'][1]['relation_ids']=['UNKNOWN']
        elif mode=='duplicate':d['recall_units'][1]['unit_id']='U1'
        elif mode=='no-policy':b.pop('recall_policy')
        else:a['design_checks'].pop()
        with pytest.raises(ValueError):compile(b,bank,a)

def test_derived_coverage_tampering_rejected():
    b,bank,a=example();audit=compile(b,bank,a);audit['goal_coverage'][0]['confirmed_unit_ids'].pop()
    with pytest.raises(ValueError):c.validate_audit(b,bank,audit)

def test_unknown_parent_in_explicit_evidence_is_a_contract_error():
    b,bank,a=example();a['direction_evidence'][0]['direction_id']='UNKNOWN'
    with pytest.raises(ValueError,match='unknown'):compile(b,bank,a)

def test_unknown_scope_review_cannot_confirm_parent_even_with_answer_evidence():
    b,bank,a=example();a['direction_checks'][0]['status']='unknown'
    audit=compile(b,bank,a)
    assert audit['goal_coverage'][0]['status']=='unknown'
    assert audit['goal_coverage'][0]['confirmed_unit_ids']==[]

def test_legacy_explanation_fragment_order_is_compatible_without_changing_judgments():
    b=f.brief();bank=f.old.bank();audit=compile(b,bank,f.assessment(b,bank))
    audit['review']['coverage'][0]['reason']='; '.join(reversed(audit['review']['coverage'][0]['reason'].split('; ')))
    c.validate_audit(b,bank,audit)
    audit['review']['coverage'][0]['status']='gap'
    with pytest.raises(ValueError):c.validate_audit(b,bank,audit)
