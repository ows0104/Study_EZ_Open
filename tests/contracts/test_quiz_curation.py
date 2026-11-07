import copy
import pytest
from quiz_curation_fixture import fixture
from studyez_contracts.roots import quiz_curation as c,task_supplement as r


def test_verbatim_verified_subset_and_fail_closed_priority_without_grade_promotion():
    base,v=fixture();before=copy.deepcopy(v['candidate']);c.validate(base,v)
    assert v['candidate']==before and v['candidate']['ready']is False
    assert len(v['document']['tasks'])==len(v['document']['bank_snapshot']['questions'])==1
    q=v['document']['bank_snapshot']['questions'][0]
    assert q==next(x for x in before['document']['bank_snapshot']['questions']if x['question_id']==q['question_id'])
    assert all(x['status']=='unreviewed'and x['evidence']==[]for x in v['document']['review']['targets'][0]['importance'].values())
    assert before['rounds'][-1]['sourceReview']['reviews'][0]['importance_verdict']=='doubt'
    assert before['rounds'][-1]['medicalReview']['reviews'][1]['verdict']=='doubt'
    assert all(t['question_id']!='Q2'for t in v['document']['tasks'])


@pytest.mark.parametrize('kind',['clinical','priority','input','receipt','scope','held'])
def test_curation_rejects_grade_edits_claimed_priority_false_scope_and_receipt_tamper(kind):
    base,v=fixture()
    if kind=='clinical':v['document']['bank_snapshot']['questions'][0]['answer']='Forged'
    elif kind=='priority':v['document']['review']['targets'][0]['importance']['exam']['status']='supported'
    elif kind=='input':v['reviewInput']['medicalReview']['reviews'][0]['verdict']='wrong'
    elif kind=='receipt':v['execution']['provider']['turns']=0
    elif kind=='scope':v['approval']['full_source_coverage']=True
    else:v['approval']['held_questions']=[]
    with pytest.raises(ValueError):c.validate(base,v)
