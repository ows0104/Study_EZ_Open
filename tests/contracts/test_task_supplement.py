import pytest
from studyez_contracts.roots import task_supplement as c
from task_supplement_fixture import fixture,proof,result
import copy

def test_fresh_document_every_question_has_one_task_no_invented_record_equivalence():
    b,v=result();c.validate(b,v);d=v['document']
    assert len(d['tasks'])==len(d['bank_snapshot']['questions']) and d['equivalences']==[]
    assert b['manifest']['repairRounds']==3 and v['repairRounds']==0


@pytest.mark.parametrize('field',['bank','task','budget','parent','receipt','source','readiness'])
def test_reject_changed_bank_task_budget_parent_actual_receipts_and_readiness(field):
    b,v=result()
    if field=='bank':v['document']['bank_snapshot']['questions'][0]['answer']='Changed'
    elif field=='task':v['document']['tasks'][0]['question_id']='unknown'
    elif field=='budget':v['repairRounds']=4
    elif field=='parent':v['parentResultHash']='0'*64
    elif field=='receipt':v['rounds'][0]['execution']['source']['provider']['turns']=0
    elif field=='source':v['rounds'][0]['sourceReview']['reviews'][0]['goal_verdict']='doubt'
    else:v['ready']=False
    with pytest.raises(ValueError):c.validate(b,v)


def test_uncertain_question_cannot_be_prepared_and_text_goal_has_no_image_lock():
    b,p,s,m=fixture();s['reviews'][0]['goal_verdict']='doubt';d=c.assemble(b,p,s,m,p['bank'],'followup')
    assert p['links'][0]['question_id']not in {t['question_id']for t in d['tasks']}
    p['links'][0]['requires_visual']=True
    with pytest.raises(ValueError):c.check_proposal(b,p)


def test_full_actual_answer_unit_and_all_new_question_reviews_required():
    b,p,s,m=fixture();p['links'][0]['components'][0]['answer_unit_indices']=[]
    with pytest.raises(ValueError):c.check_proposal(b,p)
    b,p,s,m=fixture();s['reviews'].pop()
    with pytest.raises(ValueError):c.check_source(p,s)


def test_missing_original_scope_coverage_keeps_final_result_held():
    b,v=result();v['rounds'][0]['sourceReview']['coverage_findings']=['Synthetic uncovered basic']
    row=v['rounds'][0];row['execution']['source']=proof('source',row['sourceReview']);v['ready']=False
    c.validate(b,v)


def test_completed_but_rejected_author_is_history_not_reset_or_pass():
    b,v=result();bad=copy.deepcopy(v['rounds'][0]['proposal']);bad['bank']['questions'][0]['format']='list'
    reason=c.rejection_reason(b,bad);p=proof('author',bad);p['status']='rejected'
    rejected={'round':0,'status':'author_rejected','proposal':bad,'rejection':reason,'execution':{'author':p}}
    v['rounds'][0]['round']=1;v['rounds'].insert(0,rejected);v['repairRounds']=1
    c.validate(b,v)
    rejected['rejection']='Pretend network failure'
    with pytest.raises(ValueError):c.validate(b,v)
