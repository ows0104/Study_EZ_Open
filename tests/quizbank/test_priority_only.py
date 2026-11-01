import copy
import pytest
from quizbank.priority_only import apply, content, review_targets
from quizbank.session import SessionError


def fixture():
    bank={'questions':[{'question_id':'Q1','tier':'Important','importance':4,'advanced':True,'question':'unchanged','answer':'unchanged'}],
          'concepts':[{'concept_id':'C1','tier':'Important','importance':4,'text':'unchanged'}],
          'retrieval_plan':[{'target_mastery':.8}],'other':{'history':'unchanged'}}
    evidence={'status':'verified','recommended_tier':'Essential','recommended_importance':5,
              'source_refs':['S1 p.1'],'evidence':'교수: 알고 있는 게 좋을 것 같아요','reason':'교수의 완곡한 필수 지식 강조'}
    report={'summary':'review','pages_checked':[1],
            'questions':[{'question_id':'Q1',**evidence,'tested_target':'actual target','basis':'must_know_implied'}],
            'concepts':[{'concept_id':'C1',**evidence}],'limitations':[]}
    return bank,report


def test_indirect_signal_changes_only_priority():
    bank,report=fixture();before=copy.deepcopy(bank)
    result,changes=apply(bank,report,1)
    assert result['questions'][0]['tier']=='Essential'
    assert result['questions'][0]['advanced'] is True
    assert content(result)==content(before) and bank==before
    assert changes['changedQuestions']==1


@pytest.mark.parametrize('tier,importance',[('Essential',5),('Advanced',3)])
def test_uncertain_preserves_existing_priority(tier,importance):
    bank,report=fixture()
    bank['questions'][0].update(tier=tier,importance=importance)
    report['questions'][0]['status']='uncertain'
    result,changes=apply(bank,report,1)
    assert result['questions']==bank['questions']
    assert changes['uncertainQuestions']==['Q1']


@pytest.mark.parametrize('fault',['duplicate','missing','pages','basis','refs'])
def test_incomplete_or_unsupported_review_rejected(fault):
    bank,report=fixture()
    if fault=='duplicate':report['questions']*=2
    if fault=='missing':report['questions']=[]
    if fault=='pages':report['pages_checked']=[]
    if fault=='basis':report['questions'][0]['basis']='note_emphasis'
    if fault=='refs':report['questions'][0]['source_refs']=[]
    with pytest.raises(SessionError):apply(bank,report,1)


def test_reuse_accepts_only_identical_review_targets():
    bank,report=fixture();updated,_=apply(bank,report,1)
    updated['other']={'publication':'new'}
    assert review_targets(updated)==review_targets(bank)
    for field,value in [('answer','changed'),('advanced',False),('question_id','new-id')]:
        changed=copy.deepcopy(updated);changed['questions'][0][field]=value
        assert review_targets(changed)!=review_targets(bank)
    changed=copy.deepcopy(updated);changed['concepts'][0]['text']='changed'
    assert review_targets(changed)!=review_targets(bank)
